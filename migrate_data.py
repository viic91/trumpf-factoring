"""Einmal-Skript: SQLite-Daten + lokale PDFs nach Supabase migrieren.

Ausfuehren mit: python migrate_data.py
Voraussetzung: .streamlit/secrets.toml mit SUPABASE_URL und SUPABASE_KEY
"""

import sqlite3
import os
import re
import tomllib
from datetime import datetime
from supabase import create_client

# --- Konfiguration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "factoring.db")
DOCS_DIR = os.path.join(BASE_DIR, "Dokumente")
SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

TABLE = "factoring_records"
BUCKET_INVOICES = "factoring-invoices"


def load_secrets():
    with open(SECRETS_PATH, "rb") as f:
        return tomllib.load(f)


def get_sqlite_records():
    """Liest alle Datensaetze aus der SQLite-DB."""
    if not os.path.exists(DB_PATH):
        print(f"SQLite-DB nicht gefunden: {DB_PATH}")
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM factoring_records ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def sanitize_folder_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', name)
    return cleaned.strip('. ')


def migrate():
    secrets = load_secrets()
    sb = create_client(secrets["SUPABASE_URL"], secrets["SUPABASE_KEY"])

    # 1. SQLite Daten lesen
    records = get_sqlite_records()
    if not records:
        print("Keine Daten in SQLite gefunden.")
        return

    print(f"{len(records)} Datensaetze in SQLite gefunden.")

    # 2. Pruefen ob Supabase-Tabelle leer ist
    existing = sb.table(TABLE).select("id", count="exact").execute()
    if existing.count and existing.count > 0:
        print(f"WARNUNG: Supabase-Tabelle hat bereits {existing.count} Eintraege!")
        answer = input("Trotzdem fortfahren? (j/n): ")
        if answer.lower() != "j":
            print("Abgebrochen.")
            return

    migrated = 0
    pdfs_uploaded = 0

    for rec in records:
        old_id = rec.pop("id", None)

        # Datumsfelder: SQLite hat TEXT, PostgreSQL braucht DATE oder NULL
        date_fields = ["re_datum_lieferant", "valuta_trumpf", "re_datum_trumpf", "zahlung_an_trumpf"]
        for df in date_fields:
            val = rec.get(df)
            if val and val.strip():
                # Sicherstellen dass es ISO-Format ist
                try:
                    datetime.strptime(val.strip()[:10], "%Y-%m-%d")
                    rec[df] = val.strip()[:10]
                except ValueError:
                    rec[df] = None
            else:
                rec[df] = None

        # Timestamps entfernen (werden automatisch gesetzt)
        rec.pop("created_at", None)
        rec.pop("updated_at", None)

        # PDF-Pfade: Lokale Pfade durch Storage-Pfade ersetzen
        old_pdf_lief = rec.get("invoice_pdf_lieferant")
        old_pdf_trumpf = rec.get("invoice_pdf_trumpf")

        # Storage-Ordner generieren
        lieferant = rec.get("lieferant", "Unbekannt")
        re_nr_trumpf = rec.get("re_nr_trumpf", "")
        lief_kurz = lieferant.split(" ")[0] if lieferant else "Unbekannt"
        lief_kurz = sanitize_folder_name(lief_kurz)
        trumpf_nr = str(re_nr_trumpf).strip() if re_nr_trumpf else "ohne_RE"
        storage_folder = f"{trumpf_nr}_{lief_kurz}"

        # PDFs hochladen
        rec["invoice_pdf_lieferant"] = None
        rec["invoice_pdf_trumpf"] = None

        if old_pdf_lief and os.path.exists(old_pdf_lief):
            try:
                with open(old_pdf_lief, "rb") as f:
                    pdf_bytes = f.read()
                filename = os.path.basename(old_pdf_lief)
                storage_path = f"{storage_folder}/{filename}"
                sb.storage.from_(BUCKET_INVOICES).upload(
                    path=storage_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
                rec["invoice_pdf_lieferant"] = storage_path
                pdfs_uploaded += 1
                print(f"  PDF hochgeladen: {storage_path}")
            except Exception as e:
                print(f"  FEHLER beim PDF-Upload ({old_pdf_lief}): {e}")

        if old_pdf_trumpf and os.path.exists(old_pdf_trumpf):
            try:
                with open(old_pdf_trumpf, "rb") as f:
                    pdf_bytes = f.read()
                filename = os.path.basename(old_pdf_trumpf)
                storage_path = f"{storage_folder}/{filename}"
                sb.storage.from_(BUCKET_INVOICES).upload(
                    path=storage_path,
                    file=pdf_bytes,
                    file_options={"content-type": "application/pdf", "upsert": "true"},
                )
                rec["invoice_pdf_trumpf"] = storage_path
                pdfs_uploaded += 1
                print(f"  PDF hochgeladen: {storage_path}")
            except Exception as e:
                print(f"  FEHLER beim PDF-Upload ({old_pdf_trumpf}): {e}")

        # Datensatz einfuegen
        try:
            result = sb.table(TABLE).insert(rec).execute()
            new_id = result.data[0]["id"]
            migrated += 1
            print(f"  #{old_id} -> #{new_id}: {lieferant} | {rec.get('re_nr_lieferant', '')}")
        except Exception as e:
            print(f"  FEHLER bei #{old_id}: {e}")

    print(f"\n--- Migration abgeschlossen ---")
    print(f"Datensaetze migriert: {migrated}/{len(records)}")
    print(f"PDFs hochgeladen: {pdfs_uploaded}")


if __name__ == "__main__":
    migrate()
