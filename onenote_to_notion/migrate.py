#!/usr/bin/env python3
"""
OneNote .mht → Notion migration script.

Usage
-----
Single file (flat – all pages under one parent):
  python migrate.py --input Notebook.mht --token ntn_xxx --parent-id PAGE_ID

Folder of section exports (creates a sub-page per file, named from filename):
  python migrate.py --input ./sections/ --token ntn_xxx --parent-id PAGE_ID

Dry run (parse only, no Notion writes):
  python migrate.py --input Notebook.mht --dry-run
"""

import argparse
import email
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
REQ_SLEEP = 0.4          # ~2.5 req/s, well under the 3/s limit
MAX_BLOCKS_PER_REQ = 100
MAX_RICH_TEXT_LEN = 2000


# ── MHTML decoding ────────────────────────────────────────────────────────────

def decode_mht(path: Path) -> str:
    """Extract the main HTML body from an MHTML (.mht) file."""
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    raise ValueError(f"No HTML content found in {path}")


# ── HTML element classification ───────────────────────────────────────────────

def is_page_div(tag) -> bool:
    """Top-level OneNote page container: <div style='...border-width:100%'>"""
    return (
        isinstance(tag, Tag)
        and tag.name == "div"
        and "border-width:100%" in tag.get("style", "")
    )


def is_page_title(tag) -> bool:
    """OneNote page title: <p> with Calibri Light 20pt."""
    if not isinstance(tag, Tag) or tag.name != "p":
        return False
    style = tag.get("style", "")
    return "Calibri Light" in style and "20.0pt" in style


def is_metadata_div(div: Tag) -> bool:
    """Div containing only date/time gray text (color:#767676)."""
    if not isinstance(div, Tag) or div.name != "div":
        return False
    tag_children = [c for c in div.children if isinstance(c, Tag)]
    p_children = [c for c in tag_children if c.name == "p"]
    # Must have only <p> children, and all must be the gray date/time style
    if not p_children or len(p_children) != len(tag_children):
        return False
    return all("#767676" in c.get("style", "") for c in p_children)


def is_spacer(tag: Tag) -> bool:
    """Layout spacer with no real content."""
    style = tag.get("style", "")
    if "font-size:1pt" in style:
        return True
    text = tag.get_text(strip=True).replace("\xa0", "")
    return not text


# ── Notion rich text builders ─────────────────────────────────────────────────

def make_rich_text(text: str, bold=False, italic=False, code=False) -> dict:
    text = " ".join(text.replace("\xa0", " ").split())[:MAX_RICH_TEXT_LEN]
    rt = {"type": "text", "text": {"content": text}}
    ann = {}
    if bold:
        ann["bold"] = True
    if italic:
        ann["italic"] = True
    if code:
        ann["code"] = True
    if ann:
        rt["annotations"] = ann
    return rt


def node_to_rich_text(node, bold=False, italic=False, code=False) -> list:
    """Recursively convert an HTML node to a list of Notion rich_text objects."""
    parts = []
    if isinstance(node, NavigableString):
        text = str(node).replace("\xa0", " ")
        if text.strip():
            parts.append(make_rich_text(text, bold=bold, italic=italic, code=code))
        return parts

    if not isinstance(node, Tag):
        return parts

    # Skip images (checkbox icons, etc.) — capture alt text if meaningful
    if node.name == "img":
        alt = node.get("alt", "")
        if alt and alt.lower() not in ("to do", "checkbox", ""):
            parts.append(make_rich_text(f"[{alt}]", bold=bold, italic=italic))
        return parts

    # Propagate inline formatting
    is_bold = bold or node.name in ("b", "strong") or "font-weight:bold" in node.get("style", "")
    is_italic = italic or node.name in ("i", "em")
    is_code = code or node.name == "code"

    for child in node.children:
        parts.extend(node_to_rich_text(child, bold=is_bold, italic=is_italic, code=is_code))
    return parts


def rich_text_text(rt_list: list) -> str:
    """Extract plain text from a rich_text list."""
    return "".join(
        item["text"]["content"]
        for item in rt_list
        if item.get("type") == "text"
    )


# ── Block builders ────────────────────────────────────────────────────────────

def li_to_block(li: Tag, list_type: str = "bullet") -> dict:
    """Convert a <li> element to a Notion list item block, with nested children."""
    rt = []
    children = []

    for child in li.children:
        if isinstance(child, Tag):
            if child.name in ("ul", "ol"):
                # Nested list inside the <li> (standard HTML)
                sub_type = "bullet" if child.name == "ul" else "numbered"
                children.extend(ul_to_blocks(child, sub_type))
            elif child.name == "img" and child.get("alt", "").lower() in ("to do", "checkbox", ""):
                pass  # skip checkbox images
            else:
                rt.extend(node_to_rich_text(child))
        else:
            rt.extend(node_to_rich_text(child))

    if not rt:
        rt = [make_rich_text("")]

    block_type = "bulleted_list_item" if list_type == "bullet" else "numbered_list_item"
    block = {
        "type": block_type,
        block_type: {"rich_text": rt},
    }
    if children:
        block[block_type]["children"] = children
    return block


def ul_to_blocks(ul: Tag, list_type: str = "bullet") -> list:
    """
    Convert a <ul>/<ol> to blocks, handling OneNote's invalid nesting where
    sub-lists appear as siblings of <li> rather than children.
    Pattern: <li>item</li><ul>sub-items</ul> → item with sub-items as children.
    """
    blocks = []
    pending: dict | None = None

    for child in ul.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "li":
            if pending is not None:
                blocks.append(pending)
            pending = li_to_block(child, list_type)
        elif child.name in ("ul", "ol"):
            sub_type = "bullet" if child.name == "ul" else "numbered"
            sub_blocks = ul_to_blocks(child, sub_type)
            if pending is not None and sub_blocks:
                # Associate this sub-list with the preceding <li>
                btype = pending["type"]
                pending[btype].setdefault("children", []).extend(sub_blocks)
            else:
                blocks.extend(sub_blocks)

    if pending is not None:
        blocks.append(pending)
    return blocks


def el_to_blocks(el: Tag) -> list:
    """Convert a single HTML element to a list of Notion blocks."""
    blocks = []
    if not isinstance(el, Tag):
        return blocks

    name = el.name

    if name in ("ul", "ol"):
        sub_type = "bullet" if name == "ul" else "numbered"
        blocks.extend(ul_to_blocks(el, sub_type))

    elif name == "p":
        if is_spacer(el):
            return blocks
        rt = node_to_rich_text(el)
        text = rich_text_text(rt)
        if not text.strip():
            return blocks
        # Bold short paragraphs → heading_3 (OneNote section labels)
        is_bold = (
            "font-weight:bold" in el.get("style", "")
            or any("font-weight:bold" in c.get("style", "") for c in el.find_all(True, limit=1))
        )
        if is_bold and len(text) < 120:
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": rt}})
        else:
            blocks.append({"type": "paragraph", "paragraph": {"rich_text": rt}})

    elif name in ("h1", "h2", "h3"):
        rt = node_to_rich_text(el)
        if rich_text_text(rt).strip():
            level = name[1]
            blocks.append({f"type": f"heading_{level}", f"heading_{level}": {"rich_text": rt}})

    elif name == "table":
        # Multi-column canvas layout — recurse into non-spacer cells
        for td in el.find_all("td"):
            if "1pt" not in td.get("style", "") and "1px" not in td.get("style", ""):
                for child in td.children:
                    blocks.extend(el_to_blocks(child))

    elif name == "div":
        if not is_spacer(el):
            for child in el.children:
                blocks.extend(el_to_blocks(child))

    return blocks


# ── Page extraction ───────────────────────────────────────────────────────────

def extract_pages(html: str) -> list:
    """
    Parse HTML and return a list of dicts: {title: str, blocks: list}.
    Each dict represents one OneNote page.
    """
    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body") or soup

    pages = []
    for page_div in body.find_all(is_page_div, recursive=False):
        # The page_div has one immediate child: the layout wrapper div
        inner = next((c for c in page_div.children if isinstance(c, Tag) and c.name == "div"), None)
        if not inner:
            continue

        title_tag = inner.find(is_page_title)
        if not title_tag:
            continue

        title = " ".join(title_tag.get_text(" ", strip=True).split())
        blocks = []

        for child in inner.children:
            if not isinstance(child, Tag):
                continue
            # Skip the title div
            if child.find(is_page_title):
                continue
            # Skip the date/time metadata div
            if is_metadata_div(child):
                continue
            blocks.extend(el_to_blocks(child))

        pages.append({"title": title, "blocks": blocks})

    return pages


# ── Notion API ────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _post(url: str, token: str, payload: dict) -> dict:
    r = requests.post(url, headers=_headers(token), json=payload)
    r.raise_for_status()
    time.sleep(REQ_SLEEP)
    return r.json()


def _patch(url: str, token: str, payload: dict) -> dict:
    r = requests.patch(url, headers=_headers(token), json=payload)
    r.raise_for_status()
    time.sleep(REQ_SLEEP)
    return r.json()


def create_page(token: str, parent_id: str, title: str, blocks: list | None = None) -> str:
    """Create a Notion page and append all blocks. Returns the new page ID."""
    payload = {
        "parent": {"type": "page_id", "page_id": parent_id},
        "properties": {
            "title": {"title": [{"text": {"content": title[:255]}}]}
        },
        "children": (blocks or [])[:MAX_BLOCKS_PER_REQ],
    }
    page_id = _post(f"{NOTION_API}/pages", token, payload)["id"]

    # Append remaining blocks in batches
    remaining = (blocks or [])[MAX_BLOCKS_PER_REQ:]
    while remaining:
        _patch(
            f"{NOTION_API}/blocks/{page_id}/children",
            token,
            {"children": remaining[:MAX_BLOCKS_PER_REQ]},
        )
        remaining = remaining[MAX_BLOCKS_PER_REQ:]

    return page_id


# ── Migration orchestration ───────────────────────────────────────────────────

def migrate_file(path: Path, token: str, parent_id: str, section_name: str | None = None, dry_run: bool = False):
    print(f"\n[{path.name}] Decoding MHTML...")
    html = decode_mht(path)

    print(f"[{path.name}] Extracting pages...")
    pages = extract_pages(html)
    print(f"[{path.name}] Found {len(pages)} page(s)")

    if dry_run:
        for i, page in enumerate(pages, 1):
            print(f"  [{i}] '{page['title']}' — {len(page['blocks'])} block(s)")
        return

    target_parent = parent_id
    if section_name:
        print(f"  Creating section page: '{section_name}'")
        target_parent = create_page(token, parent_id, section_name)

    for i, page in enumerate(pages, 1):
        print(f"  [{i}/{len(pages)}] '{page['title']}' ({len(page['blocks'])} blocks)")
        try:
            create_page(token, target_parent, page["title"], page["blocks"])
        except requests.HTTPError as exc:
            print(f"    ERROR: {exc.response.status_code} — {exc.response.text[:300]}")


def main():
    parser = argparse.ArgumentParser(description="Migrate OneNote .mht exports to Notion")
    parser.add_argument("--input", required=True, help=".mht file or folder containing .mht files")
    parser.add_argument("--token", help="Notion integration token (ntn_...)")
    parser.add_argument("--parent-id", help="Notion page ID to import content under")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no Notion writes")
    args = parser.parse_args()

    if not args.dry_run and (not args.token or not args.parent_id):
        parser.error("--token and --parent-id are required unless --dry-run is set")

    input_path = Path(args.input)

    if input_path.is_file():
        migrate_file(input_path, args.token, args.parent_id, dry_run=args.dry_run)
    elif input_path.is_dir():
        files = sorted(input_path.glob("*.mht"))
        if not files:
            print("No .mht files found in directory.")
            sys.exit(1)
        print(f"Found {len(files)} section file(s)")
        for f in files:
            section_name = f.stem.replace("_", " ").replace("-", " ")
            migrate_file(f, args.token, args.parent_id, section_name=section_name, dry_run=args.dry_run)
    else:
        print(f"Input not found: {input_path}")
        sys.exit(1)

    print("\nDone!")


if __name__ == "__main__":
    main()
