"""Datenverwaltung - Alle Einträge verwalten, bearbeiten, löschen."""

import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules.data_manager import (
    get_all_records, get_unique_lieferanten, get_status_options,
    update_record, delete_record, get_record, find_by_trumpf_re_nr,
    get_invoice_url,
)
from modules.calculations import berechne_alle_felder

st.set_page_config(page_title="Datenverwaltung | Factoring", page_icon="\U0001f5c2", layout="wide")

# --- Custom CSS ---
st.markdown("""
<style>
    .status-card {
        padding: 0.8rem 1.2rem;
        border-radius: 0.6rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid;
    }
    .status-offen { background: #2d1b1b; border-color: #DC3545; }
    .status-fakturiert { background: #2d2a1b; border-color: #FFC107; }
    .status-bezahlt { background: #1b2d1e; border-color: #28A745; }
    .status-abgeschlossen { background: #1b2229; border-color: #6c757d; }
    .status-teilzahlung { background: #2d1b29; border-color: #A23B72; }
    .record-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 0.75rem;
        padding: 1rem 1.2rem;
        margin-bottom: 0.6rem;
    }
    .record-card:hover {
        background: rgba(255,255,255,0.06);
        border-color: #2E86AB;
    }
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-offen { background: #DC3545; color: white; }
    .badge-fakturiert { background: #FFC107; color: #1B2A4A; }
    .badge-bezahlt { background: #28A745; color: white; }
    .badge-abgeschlossen { background: #6c757d; color: white; }
    .badge-teilzahlung { background: #A23B72; color: white; }
    .amount-big { font-size: 1.1rem; font-weight: 700; color: #2E86AB; }
</style>
""", unsafe_allow_html=True)

st.markdown("## \U0001f5c2 Datenverwaltung")

df = get_all_records()

if df.empty:
    st.warning("Keine Daten vorhanden.")
    st.stop()


# --- Hilfsfunktionen ---
def _fmt_eur(val):
    if val is None or pd.isna(val):
        return "-"
    return f"{val:,.2f} \u20ac".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(val):
    if val is None or pd.isna(val) or val == "":
        return "-"
    try:
        d = datetime.strptime(str(val)[:10], "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(val)


def _status_badge(status):
    css_map = {
        "Beauftragt": "offen",
        "Fakturiert": "fakturiert",
        "Bezahlt": "bezahlt",
        "Abgeschlossen": "abgeschlossen",
        "Offene Teilzahlung": "teilzahlung",
    }
    css = css_map.get(status, "offen")
    return f'<span class="badge badge-{css}">{status}</span>'


def _status_sort_key(status):
    order = {
        "Beauftragt": 0,
        "Fakturiert": 1,
        "Offene Teilzahlung": 2,
        "Bezahlt": 3,
        "Abgeschlossen": 4,
    }
    return order.get(status, 99)


def _doc_status(row):
    has_lief = bool(row.get("invoice_pdf_lieferant") and not pd.isna(row.get("invoice_pdf_lieferant")))
    has_trumpf = bool(row.get("invoice_pdf_trumpf") and not pd.isna(row.get("invoice_pdf_trumpf")))
    if has_lief and has_trumpf:
        return "\u2705"
    parts = []
    if not has_lief:
        parts.append("Lief.")
    if not has_trumpf:
        parts.append("Trumpf")
    return "\u26a0 " + " + ".join(parts)


# --- Sidebar Filter + Suche ---
with st.sidebar:
    st.markdown("### Filter")
    search = st.text_input("\U0001f50d Suche", placeholder="RE-Nr., Lieferant...")
    lief_filter = st.selectbox("Lieferant", ["Alle"] + get_unique_lieferanten())

filtered = df.copy()
if lief_filter != "Alle":
    filtered = filtered[filtered["lieferant"] == lief_filter]
if search:
    mask = (
        filtered["re_nr_lieferant"].astype(str).str.contains(search, case=False, na=False)
        | filtered["re_nr_trumpf"].astype(str).str.contains(search, case=False, na=False)
        | filtered["lieferant"].astype(str).str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

# --- Status-Übersicht oben ---
status_counts = df["status"].value_counts().to_dict()
offene_stati = ["Beauftragt", "Fakturiert", "Offene Teilzahlung"]
n_offen = sum(status_counts.get(s, 0) for s in offene_stati)
n_bezahlt = status_counts.get("Bezahlt", 0)
n_abgeschlossen = status_counts.get("Abgeschlossen", 0)

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
    st.metric("Offen / Fakturiert", n_offen, help="Beauftragt + Fakturiert + Offene Teilzahlung")
with col_s2:
    st.metric("Bezahlt", n_bezahlt)
with col_s3:
    st.metric("Abgeschlossen", n_abgeschlossen)
with col_s4:
    st.metric("Gesamt", len(df))

st.divider()

# --- Bestaetigungsmeldung nach Zahlung (ueberlebt st.rerun) ---
if "zahlung_msg" in st.session_state:
    msg_type, msg_text = st.session_state.pop("zahlung_msg")
    if msg_type == "success":
        st.success(msg_text)
    else:
        st.warning(msg_text)

# --- Zahlung zuordnen ---
with st.expander("Zahlung zuordnen (per Trumpf RE-Nr.)", expanded=False):
    zc1, zc2, zc3, zc4 = st.columns([2, 2, 2, 1])
    with zc1:
        z_re_nr = st.text_input("Trumpf RE-Nr. (66XXXX)", placeholder="z.B. 663715", key="z_renr")
    with zc2:
        z_betrag = st.number_input("Betrag überwiesen (€)", value=0.0, step=0.01, format="%.2f", key="z_betrag")
    with zc3:
        z_datum = st.date_input("Zahlungsdatum", value=datetime.now().date(), format="DD.MM.YYYY", key="z_datum")
    with zc4:
        st.markdown("")  # Spacer
        z_submit = st.button("Zuordnen", type="primary", key="z_submit")

    if z_submit and z_re_nr.strip():
        matches = find_by_trumpf_re_nr(z_re_nr.strip())
        if not matches:
            st.error(f"Keine Rechnung mit Trumpf RE-Nr. **{z_re_nr}** gefunden.")
        elif len(matches) > 1:
            st.warning(f"{len(matches)} Treffer für RE-Nr. {z_re_nr} – bitte im Bearbeiten-Tab manuell zuordnen.")
            for m in matches:
                st.caption(f"#{m['id']} - {m['lieferant']} - Offen: {_fmt_eur(m.get('offener_betrag'))}")
        else:
            rec = matches[0]
            rid = rec["id"]
            alte_zahlung = rec.get("bereits_gezahlt") or 0
            neue_zahlung = alte_zahlung + z_betrag
            rec["bereits_gezahlt"] = neue_zahlung

            # Status + Zahldatum automatisch setzen
            trumpf_brutto = rec.get("trumpf_brutto") or 0
            if neue_zahlung >= trumpf_brutto and trumpf_brutto > 0:
                rec["status"] = "Bezahlt"
                rec["zahlung_an_trumpf"] = str(z_datum)
            elif neue_zahlung > 0:
                rec["status"] = "Offene Teilzahlung"

            rec = berechne_alle_felder(rec)
            update_record(rid, rec)

            if rec["status"] == "Offene Teilzahlung":
                rest = _fmt_eur(rec.get("offener_betrag", 0))
                st.session_state["zahlung_msg"] = (
                    "warning",
                    f"Teilzahlung von **{_fmt_eur(z_betrag)}** erfasst fuer "
                    f"**#{rid} – {rec['lieferant']}**. "
                    f"Noch offen: **{rest}**",
                )
            else:
                st.session_state["zahlung_msg"] = (
                    "success",
                    f"Zahlung von **{_fmt_eur(z_betrag)}** zugeordnet an "
                    f"**#{rid} – {rec['lieferant']}** (RE {rec.get('re_nr_lieferant', '')}). "
                    f"Vorgang komplett bezahlt! Zahldatum: **{_fmt_date(rec.get('zahlung_an_trumpf'))}**",
                )
            st.rerun()
    elif z_submit:
        st.warning("Bitte Trumpf RE-Nr. eingeben.")

# --- Tabs: Offene zuerst! ---
tab_offen, tab_alle, tab_abgeschlossen, tab_bearbeiten = st.tabs([
    f"\U0001f534 Offene Posten ({n_offen})",
    f"\U0001f4cb Alle ({len(filtered)})",
    f"\u2705 Abgeschlossen ({n_abgeschlossen})",
    "\u270f\ufe0f Bearbeiten",
])

# ============================================================
# TAB 1: OFFENE POSTEN (Prioritäts-Ansicht)
# ============================================================
with tab_offen:
    offene = filtered[filtered["status"].isin(offene_stati)].copy()
    offene["_sort"] = offene["status"].apply(_status_sort_key)
    offene = offene.sort_values(["_sort", "valuta_trumpf"])

    if offene.empty:
        st.success("Keine offenen Posten! Alles erledigt.")
    else:
        # Kompakte Zusammenfassung
        total_offen = offene["offener_betrag"].sum()
        total_zinsen = offene["zinsen"].sum()
        st.markdown(f"**{len(offene)} offene Posten** | Gesamt offen: **{_fmt_eur(total_offen)}** | Gesamtzinsen: **{_fmt_eur(total_zinsen)}**")

        # Prozent-Spalten vorbereiten
        if "eff_jahreszins" in offene.columns:
            offene["eff_jahreszins_pct"] = offene["eff_jahreszins"].apply(
                lambda x: x * 100 if x and not pd.isna(x) else None
            )
        if "zinssatz_30_tage" in offene.columns:
            offene["zinssatz_30t_pct"] = offene["zinssatz_30_tage"].apply(
                lambda x: x * 100 if x and not pd.isna(x) else None
            )

        offene["docs"] = offene.apply(_doc_status, axis=1)

        # Kompakte Tabelle - alles auf einen Blick
        offen_cols = [
            "id", "lieferant", "re_nr_lieferant", "re_nr_trumpf",
            "valuta_trumpf", "netto_betrag", "trumpf_brutto",
            "offener_betrag", "status", "zahlung_an_trumpf", "zinsen",
            "tage_finanziert", "eff_jahreszins_pct", "zinssatz_30t_pct", "docs",
        ]
        offen_names = {
            "id": "ID",
            "lieferant": "Lieferant",
            "re_nr_lieferant": "RE Lief.",
            "re_nr_trumpf": "RE Trumpf",
            "valuta_trumpf": "Valuta",
            "netto_betrag": "Netto",
            "trumpf_brutto": "Trumpf Brutto",
            "offener_betrag": "Offen",
            "status": "Status",
            "zahlung_an_trumpf": "Bezahlt am",
            "zinsen": "Zinsen",
            "tage_finanziert": "Tage",
            "eff_jahreszins_pct": "Eff. Zins %",
            "zinssatz_30t_pct": "Zins/30T %",
            "docs": "PDFs",
        }
        avail = [c for c in offen_cols if c in offene.columns]
        st.dataframe(
            offene[avail].rename(columns=offen_names),
            use_container_width=True,
            hide_index=True,
            height=min(len(offene) * 40 + 60, 600),
            column_config={
                "Netto": st.column_config.NumberColumn(format="%.2f"),
                "Trumpf Brutto": st.column_config.NumberColumn(format="%.2f"),
                "Offen": st.column_config.NumberColumn(format="%.2f"),
                "Zinsen": st.column_config.NumberColumn(format="%.2f"),
                "Eff. Zins %": st.column_config.NumberColumn(format="%.2f"),
                "Zins/30T %": st.column_config.NumberColumn(format="%.2f"),
            },
        )

# ============================================================
# TAB 2: ALLE DATENSÄTZE
# ============================================================
with tab_alle:
    # Sortierung nach Status (offen zuerst)
    display = filtered.copy()
    display["_sort"] = display["status"].apply(_status_sort_key)
    display = display.sort_values(["_sort", "valuta_trumpf"])

    display_cols = [
        "id", "lieferant", "re_nr_lieferant", "valuta_trumpf",
        "netto_betrag", "trumpf_netto", "trumpf_brutto", "offener_betrag",
        "status", "zinsen", "zinsaufschlag", "tage_finanziert",
        "eff_jahreszins", "zinsen_pro_tag", "zinssatz_30_tage",
    ]
    # Zinsaufschlag und Jahreszins als Prozent-Spalten vorbereiten
    if "zinsaufschlag" in display.columns:
        display["zinsaufschlag_pct"] = display["zinsaufschlag"].apply(
            lambda x: x * 100 if x and not pd.isna(x) else None
        )
    if "eff_jahreszins" in display.columns:
        display["eff_jahreszins_pct"] = display["eff_jahreszins"].apply(
            lambda x: x * 100 if x and not pd.isna(x) else None
        )
    if "zinssatz_30_tage" in display.columns:
        display["zinssatz_30t_pct"] = display["zinssatz_30_tage"].apply(
            lambda x: x * 100 if x and not pd.isna(x) else None
        )

    display["docs"] = display.apply(_doc_status, axis=1)

    display_cols_final = [
        "id", "lieferant", "re_nr_lieferant", "re_nr_trumpf",
        "valuta_trumpf", "netto_betrag", "trumpf_netto", "trumpf_brutto",
        "offener_betrag", "status", "zahlung_an_trumpf", "zinsen",
        "zinsaufschlag_pct", "tage_finanziert", "eff_jahreszins_pct",
        "zinsen_pro_tag", "zinssatz_30t_pct", "docs",
    ]
    display_names = {
        "id": "ID",
        "lieferant": "Lieferant",
        "re_nr_lieferant": "RE Lief.",
        "re_nr_trumpf": "RE Trumpf",
        "valuta_trumpf": "Valuta",
        "netto_betrag": "Netto (\u20ac)",
        "trumpf_netto": "Trumpf Netto (\u20ac)",
        "trumpf_brutto": "Trumpf Brutto (\u20ac)",
        "offener_betrag": "Offen (\u20ac)",
        "status": "Status",
        "zahlung_an_trumpf": "Bezahlt am",
        "zinsen": "Zinsen (\u20ac)",
        "zinsaufschlag_pct": "Aufschlag (%)",
        "tage_finanziert": "Tage fin.",
        "eff_jahreszins_pct": "Eff. Jahreszins (%)",
        "zinsen_pro_tag": "Zinsen/Tag (\u20ac)",
        "zinssatz_30t_pct": "Zins/30T (%)",
        "docs": "PDFs",
    }

    available = [c for c in display_cols_final if c in display.columns]
    st.dataframe(
        display[available].rename(columns=display_names),
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "Netto (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
            "Trumpf Netto (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
            "Trumpf Brutto (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
            "Offen (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
            "Zinsen (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
            "Aufschlag (%)": st.column_config.NumberColumn(format="%.2f"),
            "Eff. Jahreszins (%)": st.column_config.NumberColumn(format="%.2f"),
            "Zinsen/Tag (\u20ac)": st.column_config.NumberColumn(format="%.4f"),
            "Zins/30T (%)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

# ============================================================
# TAB 3: ABGESCHLOSSEN (Archiv)
# ============================================================
with tab_abgeschlossen:
    done = filtered[filtered["status"] == "Abgeschlossen"].copy()
    done = done.sort_values("valuta_trumpf", ascending=False)

    if done.empty:
        st.info("Keine abgeschlossenen Datens\u00e4tze.")
    else:
        st.markdown(f"**{len(done)} abgeschlossene Rechnungen** | Gesamtvolumen: {_fmt_eur(done['netto_betrag'].sum())} | Gesamtzinsen: {_fmt_eur(done['zinsen'].sum())}")

        # Prozent-Spalten berechnen
        if "zinsaufschlag" in done.columns:
            done["zinsaufschlag_pct"] = done["zinsaufschlag"].apply(
                lambda x: x * 100 if x and not pd.isna(x) else None
            )
        if "eff_jahreszins" in done.columns:
            done["eff_jahreszins_pct"] = done["eff_jahreszins"].apply(
                lambda x: x * 100 if x and not pd.isna(x) else None
            )
        if "zinssatz_30_tage" in done.columns:
            done["zinssatz_30t_pct"] = done["zinssatz_30_tage"].apply(
                lambda x: x * 100 if x and not pd.isna(x) else None
            )

        done["docs"] = done.apply(_doc_status, axis=1)

        arch_cols = [
            "lieferant", "re_nr_lieferant", "valuta_trumpf",
            "netto_betrag", "trumpf_brutto", "zahlung_an_trumpf", "zinsen",
            "zinsaufschlag_pct", "tage_finanziert",
            "eff_jahreszins_pct", "zinsen_pro_tag", "zinssatz_30t_pct",
            "docs",
        ]
        arch_names = {
            "lieferant": "Lieferant",
            "re_nr_lieferant": "RE-Nr.",
            "valuta_trumpf": "Valuta",
            "netto_betrag": "Netto (\u20ac)",
            "trumpf_brutto": "Trumpf Brutto (\u20ac)",
            "zahlung_an_trumpf": "Bezahlt am",
            "zinsen": "Zinsen (\u20ac)",
            "zinsaufschlag_pct": "Aufschlag (%)",
            "tage_finanziert": "Tage fin.",
            "eff_jahreszins_pct": "Eff. Jahreszins (%)",
            "zinsen_pro_tag": "Zinsen/Tag (\u20ac)",
            "zinssatz_30t_pct": "Zins/30T (%)",
            "docs": "PDFs",
        }
        avail = [c for c in arch_cols if c in done.columns]
        st.dataframe(
            done[avail].rename(columns=arch_names),
            use_container_width=True,
            hide_index=True,
            height=500,
            column_config={
                "Netto (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
                "Trumpf Brutto (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
                "Zinsen (\u20ac)": st.column_config.NumberColumn(format="%.2f"),
                "Aufschlag (%)": st.column_config.NumberColumn(format="%.2f"),
                "Eff. Jahreszins (%)": st.column_config.NumberColumn(format="%.2f"),
                "Zinsen/Tag (\u20ac)": st.column_config.NumberColumn(format="%.4f"),
                "Zins/30T (%)": st.column_config.NumberColumn(format="%.2f"),
            },
        )

# ============================================================
# TAB 4: BEARBEITEN (Detail-Editor)
# ============================================================
with tab_bearbeiten:
    record_ids = filtered["id"].tolist()
    if not record_ids:
        st.info("Keine Datens\u00e4tze zum Bearbeiten.")
    else:
        selected_id = st.selectbox(
            "Datensatz ausw\u00e4hlen",
            record_ids,
            format_func=lambda x: f"#{x} - {df[df['id'] == x]['lieferant'].values[0]} | {df[df['id'] == x]['re_nr_lieferant'].values[0]} | {df[df['id'] == x]['status'].values[0]}",
        )

        record = get_record(selected_id)
        if record:
            # Status-Badge oben anzeigen
            st.markdown(
                f"### {record.get('lieferant', '')} &mdash; {_status_badge(record.get('status', ''))}",
                unsafe_allow_html=True,
            )

            with st.form("edit_form"):
                st.markdown("#### Lieferantendaten")
                col1, col2, col3 = st.columns(3)
                with col1:
                    e_lieferant = st.text_input("Lieferant", value=record.get("lieferant", ""))
                    e_re_nr = st.text_input("RE-Nr. Lieferant", value=record.get("re_nr_lieferant", ""))
                with col2:
                    e_netto = st.number_input("Netto (\u20ac)", value=float(record.get("netto_betrag") or 0), format="%.2f")
                    e_brutto = st.number_input("Brutto (\u20ac)", value=float(record.get("brutto_betrag") or 0), format="%.2f")
                with col3:
                    e_re_datum = st.text_input("RE-Datum", value=record.get("re_datum_lieferant", "") or "")
                    e_valuta = st.text_input("Valuta Trumpf", value=record.get("valuta_trumpf", "") or "")

                st.markdown("#### Trumpf-Daten")
                col4, col5, col6 = st.columns(3)
                with col4:
                    e_trumpf_nr = st.text_input("RE-Nr. Trumpf", value=record.get("re_nr_trumpf", ""))
                    e_trumpf_datum = st.text_input("RE-Datum Trumpf", value=record.get("re_datum_trumpf", "") or "")
                with col5:
                    e_trumpf_netto = st.number_input("Trumpf Netto (\u20ac)", value=float(record.get("trumpf_netto") or 0), format="%.2f")
                    e_trumpf_brutto = st.number_input("Trumpf Brutto (\u20ac)", value=float(record.get("trumpf_brutto") or 0), format="%.2f")
                with col6:
                    e_zahlung = st.text_input("Zahlung an Trumpf", value=record.get("zahlung_an_trumpf", "") or "")
                    e_bereits = st.number_input("Bereits gezahlt (\u20ac)", value=float(record.get("bereits_gezahlt") or 0), format="%.2f")

                st.markdown("#### Status")
                col7, col8 = st.columns([2, 1])
                with col7:
                    all_statuses = get_status_options()
                    current_status = record.get("status", "Beauftragt")
                    status_idx = all_statuses.index(current_status) if current_status in all_statuses else 0
                    e_status = st.selectbox("Status", all_statuses, index=status_idx)
                with col8:
                    st.markdown("")  # spacer

                # Berechnete Finanzkennzahlen als Info-Block anzeigen
                st.markdown("#### Berechnete Kennzahlen")
                kc1, kc2, kc3, kc4 = st.columns(4)
                with kc1:
                    st.metric("Offener Betrag", _fmt_eur(record.get("offener_betrag")))
                    st.metric("Zinsen", _fmt_eur(record.get("zinsen")))
                with kc2:
                    za = record.get("zinsaufschlag")
                    st.metric("Zinsaufschlag", f"{za*100:.2f} %" if za else "-")
                    tage = record.get("tage_finanziert")
                    st.metric("Tage finanziert", f"{int(tage)}" if tage else "-")
                with kc3:
                    ej = record.get("eff_jahreszins")
                    st.metric("Eff. Jahreszins", f"{ej*100:.2f} %" if ej else "-")
                    zpt = record.get("zinsen_pro_tag")
                    st.metric("Zinsen/Tag", f"{zpt:.4f} \u20ac" if zpt else "-")
                with kc4:
                    z30 = record.get("zinssatz_30_tage")
                    st.metric("Zinssatz je 30 Tage", f"{z30*100:.2f} %" if z30 else "-")

                col_btn1, col_btn2, _ = st.columns([1, 1, 3])
                with col_btn1:
                    save_btn = st.form_submit_button("\U0001f4be Speichern", type="primary")
                with col_btn2:
                    delete_btn = st.form_submit_button("\U0001f5d1 L\u00f6schen")

                if save_btn:
                    update_data = {
                        "lieferant": e_lieferant,
                        "re_nr_lieferant": e_re_nr,
                        "netto_betrag": e_netto,
                        "brutto_betrag": e_brutto,
                        "re_datum_lieferant": e_re_datum if e_re_datum else None,
                        "valuta_trumpf": e_valuta if e_valuta else None,
                        "re_nr_trumpf": e_trumpf_nr,
                        "re_datum_trumpf": e_trumpf_datum if e_trumpf_datum else None,
                        "zahlung_an_trumpf": e_zahlung if e_zahlung else None,
                        "trumpf_netto": e_trumpf_netto,
                        "trumpf_brutto": e_trumpf_brutto,
                        "bereits_gezahlt": e_bereits,
                        "status": e_status,
                    }
                    update_data = berechne_alle_felder(update_data)
                    update_record(selected_id, update_data)
                    st.success(f"Datensatz #{selected_id} aktualisiert!")
                    st.rerun()

                if delete_btn:
                    st.session_state[f"confirm_delete_{selected_id}"] = True

            # Lösch-Bestätigung
            if st.session_state.get(f"confirm_delete_{selected_id}"):
                st.warning(f"Datensatz #{selected_id} wirklich l\u00f6schen?")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if st.button("Ja, l\u00f6schen", type="primary"):
                        delete_record(selected_id)
                        del st.session_state[f"confirm_delete_{selected_id}"]
                        st.success(f"Datensatz #{selected_id} gel\u00f6scht!")
                        st.rerun()
                with col_d2:
                    if st.button("Abbrechen"):
                        del st.session_state[f"confirm_delete_{selected_id}"]
                        st.rerun()

            # PDF-Links (signierte Download-URLs aus Supabase Storage)
            if record.get("invoice_pdf_lieferant") or record.get("invoice_pdf_trumpf"):
                st.divider()
                st.markdown("#### Verlinkte Rechnungs-PDFs")
                if record.get("invoice_pdf_lieferant"):
                    url = get_invoice_url(record["invoice_pdf_lieferant"])
                    if url:
                        st.markdown(f"\U0001f4c4 [Lieferantenrechnung herunterladen]({url})")
                    else:
                        st.write(f"\U0001f4c4 Lieferantenrechnung: `{record['invoice_pdf_lieferant']}`")
                if record.get("invoice_pdf_trumpf"):
                    url = get_invoice_url(record["invoice_pdf_trumpf"])
                    if url:
                        st.markdown(f"\U0001f4c4 [Trumpf-Rechnung herunterladen]({url})")
                    else:
                        st.write(f"\U0001f4c4 Trumpf-Rechnung: `{record['invoice_pdf_trumpf']}`")
