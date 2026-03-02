"""Dashboard - KPIs, Charts und Übersicht."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules.data_manager import get_all_records, get_unique_lieferanten, get_status_options

st.set_page_config(page_title="Dashboard | Factoring", page_icon="\U0001f4ca", layout="wide")

st.markdown("## \U0001f4ca Dashboard")

df = get_all_records()

if df.empty:
    st.warning("Keine Daten vorhanden. Bitte zuerst Rechnungen importieren.")
    st.stop()

# --- Sidebar Filter ---
with st.sidebar:
    st.markdown("### Filter")

    status_filter = st.selectbox(
        "Status",
        ["Alle"] + get_status_options(),
        index=0,
    )
    lieferanten = get_unique_lieferanten()
    lief_filter = st.selectbox(
        "Lieferant",
        ["Alle"] + lieferanten,
        index=0,
    )

# Filter anwenden
filtered = df.copy()
if status_filter != "Alle":
    filtered = filtered[filtered["status"] == status_filter]
if lief_filter != "Alle":
    filtered = filtered[filtered["lieferant"] == lief_filter]

# --- KPIs ---
offene = filtered[filtered["status"] != "Abgeschlossen"]
alle = filtered

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    gesamt_offen = offene["offener_betrag"].sum() if not offene.empty else 0
    st.metric(
        "Offene Betr\u00e4ge",
        f"{gesamt_offen:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", "."),
    )
with col2:
    st.metric("Offene Rechnungen", f"{len(offene)}")
with col3:
    avg_zins = alle["eff_jahreszins"].dropna().mean() * 100 if not alle["eff_jahreszins"].dropna().empty else 0
    st.metric("\u00d8 eff. Jahreszins", f"{avg_zins:.1f}%".replace(".", ","))
with col4:
    avg_tage = alle["tage_finanziert"].dropna().mean() if not alle["tage_finanziert"].dropna().empty else 0
    st.metric("\u00d8 Tage finanziert", f"{avg_tage:.0f}")
with col5:
    gesamt_zinsen = alle["zinsen"].dropna().sum()
    st.metric(
        "Gesamtzinsen",
        f"{gesamt_zinsen:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", "."),
    )

st.divider()

# --- Charts ---
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.markdown("#### Offene Betr\u00e4ge nach Monat")
    if not offene.empty and "valuta_trumpf" in offene.columns:
        chart_df = offene.copy()
        chart_df["valuta_trumpf"] = pd.to_datetime(chart_df["valuta_trumpf"], errors="coerce")
        chart_df["monat"] = chart_df["valuta_trumpf"].dt.to_period("M").astype(str)
        monthly = chart_df.groupby(["monat", "lieferant"])["offener_betrag"].sum().reset_index()
        fig_bar = px.bar(
            monthly,
            x="monat",
            y="offener_betrag",
            color="lieferant",
            labels={"monat": "Monat", "offener_betrag": "Offener Betrag (\u20ac)", "lieferant": "Lieferant"},
            color_discrete_sequence=["#2E86AB", "#1B2A4A", "#A23B72", "#F18F01", "#28A745"],
        )
        fig_bar.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title=""),
            yaxis=dict(title="Betrag (\u20ac)", gridcolor="#e9ecef"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Keine offenen Posten vorhanden.")

with chart_col2:
    st.markdown("#### Verteilung nach Lieferant")
    if not alle.empty:
        lief_vol = alle.groupby("lieferant")["netto_betrag"].sum().reset_index()
        fig_pie = px.pie(
            lief_vol,
            values="netto_betrag",
            names="lieferant",
            color_discrete_sequence=["#2E86AB", "#1B2A4A", "#A23B72", "#F18F01", "#28A745"],
            hole=0.4,
        )
        fig_pie.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

st.divider()

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    st.markdown("#### Zinskosten-Entwicklung")
    if not alle.empty and "valuta_trumpf" in alle.columns:
        zins_df = alle.copy()
        zins_df["valuta_trumpf"] = pd.to_datetime(zins_df["valuta_trumpf"], errors="coerce")
        zins_df["monat"] = zins_df["valuta_trumpf"].dt.to_period("M").astype(str)
        monthly_zinsen = zins_df.groupby("monat")["zinsen"].sum().reset_index()
        monthly_zinsen = monthly_zinsen.sort_values("monat")
        fig_line = px.area(
            monthly_zinsen,
            x="monat",
            y="zinsen",
            labels={"monat": "Monat", "zinsen": "Zinsen (\u20ac)"},
            color_discrete_sequence=["#2E86AB"],
        )
        fig_line.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(title=""),
            yaxis=dict(title="Zinsen (\u20ac)", gridcolor="#e9ecef"),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_line, use_container_width=True)

with chart_col4:
    st.markdown("#### Zinsanalyse nach Lieferant")
    if not alle.empty:
        zins_lief = (
            alle.groupby("lieferant")
            .agg(
                zinsen_gesamt=("zinsen", "sum"),
                avg_jahreszins=("eff_jahreszins", "mean"),
                avg_tage=("tage_finanziert", "mean"),
                anzahl=("id", "count"),
            )
            .reset_index()
        )
        zins_lief["avg_jahreszins_pct"] = zins_lief["avg_jahreszins"] * 100
        fig_scatter = px.scatter(
            zins_lief,
            x="avg_tage",
            y="avg_jahreszins_pct",
            size="zinsen_gesamt",
            color="lieferant",
            labels={
                "avg_tage": "\u00d8 Tage finanziert",
                "avg_jahreszins_pct": "\u00d8 eff. Jahreszins (%)",
                "zinsen_gesamt": "Gesamtzinsen",
                "lieferant": "Lieferant",
            },
            color_discrete_sequence=["#2E86AB", "#1B2A4A", "#A23B72", "#F18F01"],
        )
        fig_scatter.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#e9ecef"),
            yaxis=dict(gridcolor="#e9ecef"),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# --- N\u00e4chste f\u00e4llige Zahlungen ---
st.markdown("#### N\u00e4chste f\u00e4llige Zahlungen")
if not offene.empty:
    upcoming = offene.copy()
    upcoming["valuta_trumpf"] = pd.to_datetime(upcoming["valuta_trumpf"], errors="coerce")
    upcoming = upcoming.sort_values("valuta_trumpf")
    display = upcoming[["lieferant", "re_nr_lieferant", "valuta_trumpf", "trumpf_brutto", "offener_betrag", "status"]].head(10)
    display.columns = ["Lieferant", "RE-Nr.", "Valuta", "Trumpf Brutto (\u20ac)", "Offen (\u20ac)", "Status"]
    st.dataframe(display, use_container_width=True, hide_index=True)
else:
    st.success("Keine offenen Posten!")
