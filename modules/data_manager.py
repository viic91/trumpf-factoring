"""Supabase Datenbank-Manager fuer Factoring-Datensaetze."""

import re as _re
from datetime import datetime, date
from typing import Optional
import pandas as pd
import streamlit as st
from supabase import create_client, Client


# ---------------------------------------------------------------------------
# Supabase Client (Singleton via st.cache_resource)
# ---------------------------------------------------------------------------

@st.cache_resource
def _get_supabase() -> Client:
    """Erstellt einen Supabase-Client aus Streamlit Secrets."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def get_supabase() -> Client:
    return _get_supabase()


TABLE = "factoring_records"
BUCKET_INVOICES = "factoring-invoices"
BUCKET_REPORTS = "factoring-reports"


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _parse_date(val) -> Optional[str]:
    """Konvertiert verschiedene Datumsformate zu ISO-String (YYYY-MM-DD)."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def _safe_float(val) -> Optional[float]:
    """Sicher einen Wert zu float konvertieren."""
    if val is None:
        return None
    try:
        f = float(val)
        return round(f, 2)
    except (ValueError, TypeError):
        return None


def _sanitize_folder_name(name: str) -> str:
    """Entfernt ungueltige Zeichen aus Ordnernamen."""
    cleaned = _re.sub(r'[<>:"/\\|?*]', '_', name)
    return cleaned.strip('. ')


def _prepare_record(data: dict) -> dict:
    """Bereitet einen Datensatz fuer Supabase vor (Datumsfelder parsen, None-Handling)."""
    date_fields = {
        "re_datum_lieferant", "valuta_trumpf", "re_datum_trumpf", "zahlung_an_trumpf"
    }
    numeric_fields = {
        "netto_betrag", "brutto_betrag", "trumpf_netto", "trumpf_brutto",
        "bereits_gezahlt", "offener_betrag", "zinsen", "zinsaufschlag",
        "eff_jahreszins", "zinsen_pro_tag", "zinssatz_30_tage",
    }
    int_fields = {"tage_finanziert"}
    skip_fields = {"id", "created_at", "updated_at"}

    prepared = {}
    for key, val in data.items():
        if key in skip_fields:
            continue
        if key in date_fields:
            prepared[key] = _parse_date(val)
        elif key in numeric_fields:
            prepared[key] = _safe_float(val) if val is not None else None
        elif key in int_fields:
            prepared[key] = int(val) if val is not None else None
        else:
            prepared[key] = val
    return prepared


# ---------------------------------------------------------------------------
# CRUD-Funktionen
# ---------------------------------------------------------------------------

def insert_record(data: dict) -> int:
    """Fuegt einen neuen Datensatz ein und gibt die ID zurueck."""
    sb = get_supabase()
    prepared = _prepare_record(data)
    result = sb.table(TABLE).insert(prepared).execute()
    return result.data[0]["id"]


def update_record(record_id: int, data: dict):
    """Aktualisiert einen bestehenden Datensatz."""
    sb = get_supabase()
    prepared = _prepare_record(data)
    sb.table(TABLE).update(prepared).eq("id", record_id).execute()


def delete_record(record_id: int):
    """Loescht einen Datensatz."""
    sb = get_supabase()
    sb.table(TABLE).delete().eq("id", record_id).execute()


def get_record(record_id: int) -> Optional[dict]:
    """Holt einen einzelnen Datensatz."""
    sb = get_supabase()
    result = sb.table(TABLE).select("*").eq("id", record_id).execute()
    if result.data:
        return result.data[0]
    return None


def get_all_records() -> pd.DataFrame:
    """Holt alle Datensaetze als DataFrame."""
    sb = get_supabase()
    result = sb.table(TABLE).select("*").order("id").execute()
    if not result.data:
        return pd.DataFrame()
    return pd.DataFrame(result.data)


def get_filtered_records(
    status: Optional[str] = None,
    lieferant: Optional[str] = None,
    von_datum: Optional[str] = None,
    bis_datum: Optional[str] = None,
) -> pd.DataFrame:
    """Holt gefilterte Datensaetze."""
    sb = get_supabase()
    query = sb.table(TABLE).select("*")
    if status and status != "Alle":
        query = query.eq("status", status)
    if lieferant and lieferant != "Alle":
        query = query.eq("lieferant", lieferant)
    if von_datum:
        query = query.gte("valuta_trumpf", von_datum)
    if bis_datum:
        query = query.lte("valuta_trumpf", bis_datum)
    result = query.order("valuta_trumpf", desc=True).execute()
    if not result.data:
        return pd.DataFrame()
    return pd.DataFrame(result.data)


def get_unique_lieferanten() -> list:
    """Gibt alle einzigartigen Lieferanten zurueck."""
    sb = get_supabase()
    result = sb.table(TABLE).select("lieferant").execute()
    if not result.data:
        return []
    lieferanten = sorted(set(r["lieferant"] for r in result.data if r["lieferant"]))
    return lieferanten


def get_status_options() -> list:
    """Gibt alle verfuegbaren Status-Optionen zurueck."""
    return ["Beauftragt", "Fakturiert", "Bezahlt", "Offene Teilzahlung", "Abgeschlossen"]


# ---------------------------------------------------------------------------
# Suche
# ---------------------------------------------------------------------------

def find_by_trumpf_re_nr(re_nr: str) -> list:
    """Sucht Datensaetze anhand der Trumpf-Rechnungsnummer."""
    sb = get_supabase()
    result = sb.table(TABLE).select("*").eq("re_nr_trumpf", re_nr.strip()).execute()
    return result.data or []


def find_by_lieferant_re_nr(re_nr: str) -> list:
    """Sucht Datensaetze anhand der Lieferanten-Rechnungsnummer."""
    sb = get_supabase()
    result = sb.table(TABLE).select("*").eq("re_nr_lieferant", re_nr.strip()).execute()
    return result.data or []


def record_count() -> int:
    """Anzahl aller Datensaetze."""
    sb = get_supabase()
    result = sb.table(TABLE).select("id", count="exact").execute()
    return result.count or 0


# ---------------------------------------------------------------------------
# PDF-Speicherung (Supabase Storage)
# ---------------------------------------------------------------------------

def get_storage_path(re_nr_trumpf: str, lieferant: str) -> str:
    """Generiert einen Storage-Pfad fuer einen Vorgang.

    Struktur: {RE_Trumpf}_{Lieferant_kurz}/
    """
    lief_kurz = lieferant.split(" ")[0] if lieferant else "Unbekannt"
    lief_kurz = _sanitize_folder_name(lief_kurz)
    trumpf_nr = str(re_nr_trumpf).strip() if re_nr_trumpf else "ohne_RE"
    return f"{trumpf_nr}_{lief_kurz}"


def save_invoice_pdf(file_bytes: bytes, storage_folder: str, doc_type: str, re_nr: str = "") -> str:
    """Speichert eine Rechnungs-PDF in Supabase Storage.

    Args:
        file_bytes: PDF als Bytes
        storage_folder: Ordner-Pfad im Bucket (z.B. "663240_Soieta")
        doc_type: 'lieferant' oder 'trumpf'
        re_nr: Rechnungsnummer fuer den Dateinamen

    Returns:
        Storage-Pfad (z.B. "663240_Soieta/Trumpf_663240.pdf")
    """
    sb = get_supabase()
    re_str = f"_{re_nr}" if re_nr else ""
    if doc_type == "trumpf":
        filename = f"Trumpf{re_str}.pdf"
    else:
        filename = f"Lieferantenrechnung{re_str}.pdf"

    storage_path = f"{storage_folder}/{filename}"

    sb.storage.from_(BUCKET_INVOICES).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return storage_path


def get_invoice_url(storage_path: str, expires_in: int = 3600) -> Optional[str]:
    """Erstellt eine signierte URL fuer eine gespeicherte Rechnung.

    Args:
        storage_path: Pfad im Storage-Bucket
        expires_in: Gueltigkeitsdauer in Sekunden (Standard: 1 Stunde)

    Returns:
        Signierte URL oder None
    """
    if not storage_path:
        return None
    try:
        sb = get_supabase()
        result = sb.storage.from_(BUCKET_INVOICES).create_signed_url(
            storage_path, expires_in
        )
        return result.get("signedURL") or result.get("signedUrl")
    except Exception:
        return None


def save_report(file_bytes: bytes, filename: str) -> str:
    """Speichert einen Report (Excel/PDF) in Supabase Storage.

    Args:
        file_bytes: Report als Bytes
        filename: Dateiname (z.B. "Trumpf_Factoring_Report_2026-03-02.xlsx")

    Returns:
        Storage-Pfad
    """
    sb = get_supabase()
    content_type = "application/pdf" if filename.endswith(".pdf") else \
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    sb.storage.from_(BUCKET_REPORTS).upload(
        path=filename,
        file=file_bytes,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return filename


# ---------------------------------------------------------------------------
# Abwaertskompatibilitaet: get_vorgang_dir -> get_storage_path
# ---------------------------------------------------------------------------

def get_vorgang_dir(re_nr_trumpf: str, lieferant: str) -> str:
    """Alias fuer get_storage_path (Abwaertskompatibilitaet)."""
    return get_storage_path(re_nr_trumpf, lieferant)
