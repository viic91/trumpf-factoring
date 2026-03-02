"""Trumpf Factoring Tool - Hauptapp (Weiterleitung zum Dashboard)."""

import streamlit as st

st.set_page_config(
    page_title="Trumpf Factoring Tool",
    page_icon="\U0001f4ca",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Secrets-Check
if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("Supabase-Zugangsdaten fehlen! Bitte SUPABASE_URL und SUPABASE_KEY in den Secrets eintragen.")
    st.stop()

# Custom CSS fuer Sidebar-Styling (gilt global)
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1B2A4A 0%, #2E4A6E 100%);
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label {
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# Direkt zum Dashboard weiterleiten
st.switch_page("pages/1_Dashboard.py")
