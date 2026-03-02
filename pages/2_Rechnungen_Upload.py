"""Rechnungen Upload - PDFs hochladen, automatisch erkennen und zuordnen."""

import streamlit as st
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from modules.data_manager import (
    insert_record, find_by_trumpf_re_nr, find_by_lieferant_re_nr,
    update_record, get_vorgang_dir, save_invoice_pdf, get_record,
)
from modules.calculations import berechne_alle_felder
from modules.invoice_parser import parse_invoice_pdf

st.set_page_config(page_title="Upload | Factoring", page_icon="\U0001f4e4", layout="wide")

st.markdown("## \U0001f4e4 Rechnungen hochladen")
st.markdown("Eine oder mehrere PDFs hochladen – Typ wird automatisch erkannt, Daten extrahiert und zugeordnet.")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _extract_fields(result, invoice_type):
    """Extrahierte Parser-Felder in flaches Dict mappen."""
    fields = result["fields"]
    extracted = {}
    if invoice_type == "trumpf":
        doc_type = "trumpf"
        if fields.get("rechnungsnummer", {}).get("value"):
            extracted["re_nr_trumpf"] = fields["rechnungsnummer"]["value"]
        if fields.get("rechnungsdatum", {}).get("value"):
            extracted["re_datum_trumpf"] = fields["rechnungsdatum"]["value"]
        if fields.get("netto_betrag", {}).get("value"):
            extracted["trumpf_netto"] = fields["netto_betrag"]["value"]
        if fields.get("brutto_betrag", {}).get("value"):
            extracted["trumpf_brutto"] = fields["brutto_betrag"]["value"]
        if fields.get("faelligkeitsdatum", {}).get("value"):
            extracted["valuta_trumpf"] = fields["faelligkeitsdatum"]["value"]
        if fields.get("lieferanten_re_nr", {}).get("value"):
            extracted["lieferanten_re_nr_from_trumpf"] = fields["lieferanten_re_nr"]["value"]
    else:
        doc_type = "lieferant"
        if fields.get("rechnungsnummer", {}).get("value"):
            extracted["re_nr_lieferant"] = fields["rechnungsnummer"]["value"]
        if fields.get("rechnungsdatum", {}).get("value"):
            extracted["re_datum_lieferant"] = fields["rechnungsdatum"]["value"]
        if fields.get("netto_betrag", {}).get("value"):
            extracted["netto_betrag"] = fields["netto_betrag"]["value"]
        if fields.get("brutto_betrag", {}).get("value"):
            extracted["brutto_betrag"] = fields["brutto_betrag"]["value"]
        if fields.get("lieferant", {}).get("value"):
            extracted["lieferant"] = fields["lieferant"]["value"]
    return doc_type, extracted


def _find_existing(extracted, doc_type):
    """Bestehenden Vorgang per RE-Nr suchen."""
    # Per Trumpf RE-Nr
    trumpf_nr = extracted.get("re_nr_trumpf", "")
    if trumpf_nr:
        matches = find_by_trumpf_re_nr(trumpf_nr)
        if matches:
            return matches[0]

    # Per Lieferanten-RE-Nr (aus Trumpf-Rechnung)
    lief_re_nr = extracted.get("lieferanten_re_nr_from_trumpf", "")
    if lief_re_nr:
        matches = find_by_lieferant_re_nr(lief_re_nr)
        if matches:
            return matches[0]

    # Per Lieferanten-RE-Nr (aus Lieferantenrechnung)
    lief_re_nr = extracted.get("re_nr_lieferant", "")
    if lief_re_nr:
        matches = find_by_lieferant_re_nr(lief_re_nr)
        if matches:
            return matches[0]

    return None


def _compare_fields(extracted, rec, doc_type):
    """Vergleicht extrahierte Werte mit bestehendem Record.

    Returns: (new_fields, changed_fields, pdf_missing)
    """
    pdf_field = "invoice_pdf_trumpf" if doc_type == "trumpf" else "invoice_pdf_lieferant"

    if doc_type == "trumpf":
        field_map = [
            ("re_nr_trumpf", "re_nr_trumpf"),
            ("re_datum_trumpf", "re_datum_trumpf"),
            ("valuta_trumpf", "valuta_trumpf"),
            ("trumpf_netto", "trumpf_netto"),
            ("trumpf_brutto", "trumpf_brutto"),
        ]
    else:
        field_map = [
            ("re_nr_lieferant", "re_nr_lieferant"),
            ("re_datum_lieferant", "re_datum_lieferant"),
            ("netto_betrag", "netto_betrag"),
            ("brutto_betrag", "brutto_betrag"),
            ("lieferant", "lieferant"),
        ]

    new_fields = {}
    changed_fields = {}

    for ext_key, db_key in field_map:
        ext_val = extracted.get(ext_key)
        if not ext_val:
            continue
        db_val = rec.get(db_key)
        if not db_val:
            new_fields[db_key] = ext_val
        else:
            if isinstance(ext_val, float) and isinstance(db_val, (int, float)):
                if round(float(ext_val), 2) != round(float(db_val), 2):
                    changed_fields[db_key] = {"alt": db_val, "neu": ext_val}
            elif str(ext_val).strip() != str(db_val).strip():
                changed_fields[db_key] = {"alt": db_val, "neu": ext_val}

    pdf_missing = not rec.get(pdf_field)
    return new_fields, changed_fields, pdf_missing


def _process_file(pdf_bytes, doc_type, extracted, existing_match):
    """Verarbeitet eine einzelne Datei: Update oder Create.

    Returns: (success_msg, error_msg)
    """
    type_label = "Trumpf" if doc_type == "trumpf" else "Lieferant"

    if existing_match:
        rec = get_record(existing_match["id"])
        rid = rec["id"]
        new_fields, changed_fields, pdf_missing = _compare_fields(extracted, rec, doc_type)

        if not new_fields and not changed_fields and not pdf_missing:
            return None, f"#{rid}: Alle Daten identisch, PDF vorhanden. Uebersprungen."

        update_data = {}
        update_data.update(new_fields)
        for k, info in changed_fields.items():
            update_data[k] = info["neu"]

        lieferant = rec.get("lieferant", "Unbekannt")
        trumpf_nr = rec.get("re_nr_trumpf") or update_data.get("re_nr_trumpf", "")
        vorgang_dir = get_vorgang_dir(trumpf_nr, lieferant)

        re_nr_for_file = ""
        if doc_type == "trumpf":
            re_nr_for_file = trumpf_nr
        else:
            re_nr_for_file = rec.get("re_nr_lieferant") or update_data.get("re_nr_lieferant", "")

        path = save_invoice_pdf(pdf_bytes, vorgang_dir, doc_type, re_nr_for_file)
        pdf_field = "invoice_pdf_trumpf" if doc_type == "trumpf" else "invoice_pdf_lieferant"
        update_data[pdf_field] = path

        rec.update(update_data)
        rec = berechne_alle_felder(rec)
        update_record(rid, rec)

        parts = []
        if new_fields:
            parts.append(f"{len(new_fields)} Felder ergaenzt")
        if changed_fields:
            parts.append(f"{len(changed_fields)} Felder aktualisiert")
        if pdf_missing:
            parts.append("PDF abgelegt")
        detail = ", ".join(parts) if parts else "PDF abgelegt"
        return f"#{rid} aktualisiert ({type_label}): {detail}", None

    else:
        data = {
            "lieferant": extracted.get("lieferant", ""),
            "re_nr_lieferant": extracted.get("re_nr_lieferant", ""),
            "re_datum_lieferant": extracted.get("re_datum_lieferant"),
            "netto_betrag": extracted.get("netto_betrag"),
            "brutto_betrag": extracted.get("brutto_betrag"),
            "valuta_trumpf": extracted.get("valuta_trumpf"),
            "re_nr_trumpf": extracted.get("re_nr_trumpf", ""),
            "re_datum_trumpf": extracted.get("re_datum_trumpf"),
            "zahlung_an_trumpf": None,
            "trumpf_netto": extracted.get("trumpf_netto"),
            "trumpf_brutto": extracted.get("trumpf_brutto"),
            "bereits_gezahlt": 0.0,
            "status": "Beauftragt",
        }
        data = berechne_alle_felder(data)

        lieferant = data.get("lieferant", "")
        re_nr_trumpf = data.get("re_nr_trumpf", "")
        vorgang_dir = get_vorgang_dir(re_nr_trumpf, lieferant)

        re_nr_for_file = re_nr_trumpf if doc_type == "trumpf" else data.get("re_nr_lieferant", "")
        path = save_invoice_pdf(pdf_bytes, vorgang_dir, doc_type, re_nr_for_file)
        pdf_field = "invoice_pdf_trumpf" if doc_type == "trumpf" else "invoice_pdf_lieferant"
        data[pdf_field] = path

        record_id = insert_record(data)
        return f"#{record_id} neu angelegt ({type_label}): {lieferant or re_nr_trumpf}", None


# ---------------------------------------------------------------------------
# Upload-Bereich
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader(
    "PDF-Rechnungen (Lieferant oder Trumpf)",
    type=["pdf"],
    accept_multiple_files=True,
    key="upload_pdfs",
)

if uploaded_files and st.button(
    f"\U0001f50d {len(uploaded_files)} Datei(en) analysieren",
    type="primary",
):
    # --- Schritt 1: Alle Dateien analysieren ---
    analyses = []  # Liste von (filename, pdf_bytes, doc_type, extracted, existing_match, status)

    for uf in uploaded_files:
        pdf_bytes = uf.read()
        uf.seek(0)
        filename = uf.name

        result = parse_invoice_pdf(pdf_bytes)
        if not result["success"]:
            analyses.append({
                "filename": filename,
                "status": "error",
                "error": result.get("error", "Unbekannter Fehler"),
            })
            continue

        invoice_type = result.get("meta", {}).get("invoice_type", "unbekannt")
        doc_type, extracted = _extract_fields(result, invoice_type)
        existing_match = _find_existing(extracted, doc_type)

        # Bestimmen was passiert
        if existing_match:
            rec = get_record(existing_match["id"])
            new_fields, changed_fields, pdf_missing = _compare_fields(extracted, rec, doc_type)
            if not new_fields and not changed_fields and not pdf_missing:
                action = "skip"
                action_text = f"Duplikat (#{rec['id']} – alle Daten identisch)"
            else:
                action = "update"
                parts = []
                if new_fields:
                    parts.append(f"{len(new_fields)} neue Felder")
                if changed_fields:
                    parts.append(f"{len(changed_fields)} abweichend")
                if pdf_missing:
                    parts.append("PDF fehlt")
                action_text = f"Vorgang #{rec['id']} ergaenzen ({', '.join(parts)})"
        else:
            action = "create"
            lief = extracted.get("lieferant", "")
            re_nr = extracted.get("re_nr_lieferant") or extracted.get("re_nr_trumpf", "")
            action_text = f"Neuer Vorgang ({lief or re_nr})"

        type_label = "Trumpf" if doc_type == "trumpf" else "Lieferant"

        analyses.append({
            "filename": filename,
            "status": action,
            "action_text": action_text,
            "type_label": type_label,
            "pdf_bytes": pdf_bytes,
            "doc_type": doc_type,
            "extracted": extracted,
            "existing_match": existing_match,
        })

    # --- Schritt 2: Uebersicht anzeigen ---
    st.divider()
    st.markdown("### Ergebnis der Analyse")

    actionable = []
    for a in analyses:
        if a["status"] == "error":
            st.error(f"**{a['filename']}**: {a['error']}")
        elif a["status"] == "skip":
            st.info(f"**{a['filename']}** ({a['type_label']}): {a['action_text']}")
        else:
            icon = "\U0001f7e2" if a["status"] == "create" else "\U0001f7e1"
            st.markdown(f"{icon} **{a['filename']}** ({a['type_label']}): {a['action_text']}")
            actionable.append(a)

    # In Session speichern
    st.session_state["pending_files"] = actionable

st.divider()

# --- Schritt 3: Bestaetigung ---
if "pending_files" in st.session_state and st.session_state["pending_files"]:
    pending = st.session_state["pending_files"]
    count = len(pending)

    if st.button(
        f"\u2705 {count} Datei(en) verarbeiten",
        type="primary",
        key="btn_confirm_all",
    ):
        successes = []
        skips = []

        for a in pending:
            # Vor jeder Datei erneut pruefen: Vielleicht wurde der
            # passende Vorgang gerade durch eine vorherige Datei angelegt.
            fresh_match = _find_existing(a["extracted"], a["doc_type"])
            ok, skip = _process_file(
                a["pdf_bytes"], a["doc_type"], a["extracted"],
                fresh_match or a["existing_match"],
            )
            if ok:
                successes.append(ok)
            if skip:
                skips.append(skip)

        if successes:
            for msg in successes:
                st.success(msg)
        if skips:
            for msg in skips:
                st.info(msg)

        st.session_state["pending_files"] = None

        if successes:
            st.balloons()
