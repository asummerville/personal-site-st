# Personal Site + Construction Cost Explorer

This repo contains two independent Streamlit apps deployed on Streamlit Cloud.

---

## Construction Cost Explorer

A multi-page tool for construction cost analysis using [FRED](https://fred.stlouisfed.org/) data.

**Live app:** *(add your Streamlit Cloud URL here)*

### What it does

| Feature | Description |
|---|---|
| Trend: Single Series | Plot any FRED cost series, view YoY % change, or scan change over standard lookback windows |
| Trend: Multi-Series | Compare multiple series normalized to a common base date, or combine index + diffusion series on dual axes |
| Change Calculator | Compute total % change and CAGR between any two dates across up to 5 series |
| Custom Index Builder | Build a weighted composite index reflecting a project's specific cost mix |
| Project Escalation | Escalate past project costs to today using a single index or per-cost-type indices |
| Currency Normalization | Convert a foreign-currency cost to USD at a historical FRED exchange rate |

### Running locally

```bash
pip install -r requirements.txt

# Requires a FRED API key — get one free at https://fred.stlouisfed.org/docs/api/api_key.html
echo "FRED_API_KEY=your_key_here" > .env

streamlit run fred_app/app.py
```

### Data sources

All data is pulled live from the [FRED API](https://fred.stlouisfed.org/). Key series:

| Series | Name | Category |
|---|---|---|
| WPU801 | PPI: Construction Cost Index | Cost Indices |
| WPUSI012011 | PPI: Construction Materials & Components | Materials |
| CES2000000003 | Construction: Avg Hourly Earnings | Labor |
| ECICONWAG | Employment Cost Index: Construction | Labor |
| WPU112 | PPI: Construction Machinery & Equipment | Equipment |
| TTLCONS | Total Construction Spending | Spending |

---

## Personal Site

```bash
streamlit run app/main.py
```

Static portfolio site. No API key required.
