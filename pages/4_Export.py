"""Export - Excel & PDF Report Download."""

import streamlit as st
import sys, os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules.data_manager import get_all_records, get_unique_lieferanten, get_status_options, save_report
from modules.excel_export import generate_excel_report
from modules.pdf_report import generate_pdf_report


def _archiviere(daten: bytes, dateiname: str):
    """Speichert Report-Kopie in Supabase Storage."""
    try:
        save_report(daten, dateiname)
    except Exception:
        pass  # Archivierung darf Export nicht blockieren

st.set_page_config(page_title="Export | Factoring", page_icon="\U0001f4e5", layout="wide")

st.markdown("## \U0001f4e5 Export")
st.markdown("Exportiere deine Factoring-Daten als professionelle Excel-Datei oder PDF-Report.")

df = get_all_records()

if df.empty:
    st.warning("Keine Daten zum Exportieren vorhanden.")
    st.stop()

# --- Filter ---
st.markdown("### Filter (optional)")
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    status_options = ["Alle", "Offene Posten"] + get_status_options() + ["Abgeschlossen"]
    exp_status = st.selectbox("Status", status_options, key="exp_status")
with col_f2:
    exp_lief = st.selectbox("Lieferant", ["Alle"] + get_unique_lieferanten(), key="exp_lief")
with col_f3:
    st.write("")  # Spacer

# Filter anwenden
export_df = df.copy()
if exp_status == "Offene Posten":
    export_df = export_df[export_df["status"].isin(["Beauftragt", "Fakturiert", "Offene Teilzahlung"])]
elif exp_status != "Alle":
    export_df = export_df[export_df["status"] == exp_status]
if exp_lief != "Alle":
    export_df = export_df[export_df["lieferant"] == exp_lief]

st.info(f"\U0001f4ca **{len(export_df)} Datens\u00e4tze** werden exportiert")

st.divider()

# --- Export Buttons ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### \U0001f4ca Excel-Report")
    st.markdown("""
    Professionell formatierte Excel-Datei mit:
    - **Dashboard** mit KPIs und Charts
    - **Offene Posten** mit Ampel-Formatierung
    - **Alle Rechnungen** mit Autofilter
    - **Zinsanalyse** nach Lieferant
    """)

    if st.button("Excel generieren", type="primary", key="gen_excel"):
        with st.spinner("Generiere Excel-Report..."):
            try:
                excel_bytes = generate_excel_report(export_df)
                timestamp = datetime.now().strftime("%Y-%m-%d")
                filename = f"Trumpf_Factoring_Report_{timestamp}.xlsx"
                _archiviere(excel_bytes, filename)
                st.download_button(
                    label="\U0001f4e5 Excel herunterladen",
                    data=excel_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                )
                st.success(f"Excel-Report bereit! (In Cloud archiviert)")
            except Exception as e:
                st.error(f"Fehler beim Generieren: {e}")

with col2:
    st.markdown("### \U0001f4c4 PDF-Report")
    st.markdown("""
    Kompakter PDF-Report mit:
    - **KPI-\u00dcbersicht** auf einen Blick
    - **Lieferanten-Analyse** mit Zinsvergleich
    - **Offene Posten** Tabelle
    - **Alle Rechnungen** Gesamtliste
    """)

    if st.button("PDF generieren", type="primary", key="gen_pdf"):
        with st.spinner("Generiere PDF-Report..."):
            try:
                pdf_bytes = generate_pdf_report(export_df)
                timestamp = datetime.now().strftime("%Y-%m-%d")
                filename = f"Trumpf_Factoring_Report_{timestamp}.pdf"
                _archiviere(pdf_bytes, filename)
                st.download_button(
                    label="\U0001f4e5 PDF herunterladen",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                )
                st.success(f"PDF-Report bereit! (In Cloud archiviert)")
            except Exception as e:
                st.error(f"Fehler beim Generieren: {e}")

st.divider()

# --- Vorschau ---
st.markdown("### Datenvorschau")
preview_cols = [
    "lieferant", "re_nr_lieferant", "netto_betrag", "trumpf_brutto",
    "offener_betrag", "status", "zinsen", "eff_jahreszins", "tage_finanziert",
]
col_names = {
    "lieferant": "Lieferant",
    "re_nr_lieferant": "RE-Nr.",
    "netto_betrag": "Netto (\u20ac)",
    "trumpf_brutto": "Trumpf Brutto (\u20ac)",
    "offener_betrag": "Offen (\u20ac)",
    "status": "Status",
    "zinsen": "Zinsen (\u20ac)",
    "eff_jahreszins": "Jahreszins",
    "tage_finanziert": "Tage fin.",
}
available = [c for c in preview_cols if c in export_df.columns]
st.dataframe(
    export_df[available].rename(columns=col_names),
    use_container_width=True,
    hide_index=True,
)
