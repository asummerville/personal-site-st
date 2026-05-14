import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="Construction Cost Explorer",
    page_icon="🏗",
    layout="wide",
)

# Pages are declared here and lazily loaded by st.navigation.
PAGES = {
    "Explore": [
        st.Page(
            "pages/trend_single.py",
            title="Trend: Single Series",
            icon="📈",
            url_path="trend-single",
        ),
        st.Page(
            "pages/trend_multi.py",
            title="Trend: Multi-Series",
            icon="📊",
            url_path="trend-multi",
        ),
    ],
    "Analyze": [
        st.Page(
            "pages/change_calculator.py",
            title="Change Calculator",
            icon="📐",
            url_path="change-calculator",
        ),
        st.Page(
            "pages/custom_index_builder.py",
            title="Custom Index Builder",
            icon="🧪",
            url_path="custom-index-builder",
        ),
    ],
}

nav = st.navigation(PAGES)
nav.run()
