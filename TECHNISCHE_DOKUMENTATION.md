# TRUMPF Factoring Tool - Technische Komplettdokumentation

## 1. Ueberblick

### Zweck
Webbasiertes Factoring-Management-Tool fuer GRAIL Automotive. Verwaltet den Rechnungsfluss:
Lieferant (z.B. Soieta Tech) -> TRUMPF Financial Services (Vorfinanzierung) -> GRAIL Automotive (Zahlung).

### Tech-Stack
- **Python 3.12** (festgelegt via `runtime.txt`)
- **Streamlit 1.53+** - Web-UI (Multi-Page App)
- **Supabase** - Cloud-Datenbank (PostgreSQL) + Storage (PDFs/Reports)
- **pdfplumber** - PDF-Textextraktion (kein OCR, benoetigt Text-Layer)
- **plotly** - Interaktive Charts im Dashboard
- **openpyxl** - Excel-Export mit professioneller Formatierung
- **fpdf2** - PDF-Report-Generierung
- **pandas** - Datenverarbeitung

### Hosting & Deployment
- **App:** Streamlit Community Cloud (automatisches Deployment bei Push auf `master`)
- **Datenbank + Storage:** Supabase-Projekt `victor` (`utmaraahcnavgumuqtjm`)
- **Quellcode:** GitHub `viic91/trumpf-factoring` (public, Branch `master`)

### Voraussetzungen (lokal)
```
pip install -r requirements.txt
```
Zusaetzlich: `.streamlit/secrets.toml` mit `SUPABASE_URL` und `SUPABASE_KEY`.

---

## 2. Projektstruktur

```
Trumpf-Factoring-Tool/
|
|-- app.py                              # Streamlit Hauptapp (Redirect zum Dashboard)
|-- requirements.txt                    # Python-Dependencies
|-- runtime.txt                         # Python-Version fuer Streamlit Cloud (3.12)
|-- GEBRAUCHSANWEISUNG.md              # Benutzerhandbuch
|-- TECHNISCHE_DOKUMENTATION.md        # Diese Datei
|-- migrate_data.py                    # Einmaliges Migrationsskript (SQLite -> Supabase)
|
|-- pages/                              # Streamlit Multi-Page Navigation
|   |-- 1_Dashboard.py                  # KPIs + Charts
|   |-- 2_Rechnungen_Upload.py          # PDF Upload + Auto-Erkennung
|   |-- 3_Datenverwaltung.py            # CRUD + Zahlung zuordnen
|   |-- 4_Export.py                     # Excel + PDF Export + Auto-Archivierung
|
|-- modules/                            # Backend-Logik
|   |-- __init__.py                     # (leer, Package-Marker)
|   |-- invoice_parser.py              # PDF-Parsing + Regex-Extraktion
|   |-- data_manager.py                # Supabase CRUD + Storage-Verwaltung
|   |-- calculations.py                # Zins-/Kosten-Berechnungen
|   |-- excel_export.py                # Professioneller Excel-Report
|   |-- pdf_report.py                  # PDF Ist-Report (GRAIL-Branding)
|
|-- .streamlit/
|   |-- config.toml                     # Streamlit-Konfiguration
|   |-- secrets.toml                    # Lokale Secrets (in .gitignore!)
|
|-- data/                               # Legacy (nur lokal, nicht mehr aktiv)
|   |-- factoring.db                    # Alte SQLite-Datenbank (historisch)
|
|-- Dokumente/                          # Legacy lokales PDF-Archiv (nicht mehr aktiv)
|-- .claude/
    |-- launch.json                     # Dev-Server Konfiguration
```

### Supabase-Ressourcen
- **Tabelle:** `factoring_records` (91 Datensaetze, migriert aus SQLite)
- **Storage-Bucket:** `factoring-invoices` (28 PDFs, Rechnungsarchiv)
- **Storage-Bucket:** `factoring-reports` (Auto-archivierte Excel/PDF-Reports)

---

## 3. Datenbank-Schema

### Tabelle: `factoring_records` (Supabase/PostgreSQL)

```sql
-- Primaerschluessel
id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,

-- Lieferanten-Daten
lieferant TEXT NOT NULL,             -- Firmenname (z.B. "Soieta Tech s.r.o")
re_nr_lieferant TEXT,                -- Rechnungsnummer des Lieferanten (z.B. "202510089")
re_datum_lieferant TEXT,             -- Rechnungsdatum (ISO: YYYY-MM-DD)
netto_betrag DOUBLE PRECISION,      -- Nettobetrag Lieferantenrechnung
brutto_betrag DOUBLE PRECISION,     -- Bruttobetrag Lieferantenrechnung

-- Trumpf-Daten
valuta_trumpf TEXT,                  -- Faelligkeitsdatum/Valuta der Trumpf-Rechnung
re_nr_trumpf TEXT,                   -- Trumpf-Rechnungsnummer (Format: 66XXXX)
re_datum_trumpf TEXT,                -- Rechnungsdatum Trumpf (ISO)
zahlung_an_trumpf TEXT,              -- Datum der Vollzahlung an Trumpf (ISO)
trumpf_netto DOUBLE PRECISION,      -- Nettobetrag Trumpf-Rechnung
trumpf_brutto DOUBLE PRECISION,     -- Bruttobetrag Trumpf-Rechnung

-- Zahlungsstatus
bereits_gezahlt DOUBLE PRECISION DEFAULT 0,  -- Summe bisheriger Zahlungen
offener_betrag DOUBLE PRECISION,             -- BERECHNET: trumpf_brutto - bereits_gezahlt
status TEXT DEFAULT 'Beauftragt',            -- Workflow-Status (siehe unten)

-- Berechnete Finanzkennzahlen
zinsen DOUBLE PRECISION,             -- BERECHNET: trumpf_netto - netto_betrag
zinsaufschlag DOUBLE PRECISION,      -- BERECHNET: zinsen / netto_betrag (Dezimalzahl)
eff_jahreszins DOUBLE PRECISION,     -- BERECHNET: (zinsen/netto) * (365/tage) (Dezimalzahl)
tage_finanziert INTEGER,             -- BERECHNET: zahlung_an_trumpf - re_datum_trumpf
zinsen_pro_tag DOUBLE PRECISION,     -- BERECHNET: zinsen / tage_finanziert
zinssatz_30_tage DOUBLE PRECISION,   -- BERECHNET: zinsaufschlag * (30/tage)

-- PDF-Referenzen (Supabase Storage Pfade)
invoice_pdf_lieferant TEXT,          -- Storage-Pfad zur Lieferantenrechnung-PDF
invoice_pdf_trumpf TEXT,             -- Storage-Pfad zur Trumpf-Rechnung-PDF

-- Metadaten
created_at TIMESTAMPTZ DEFAULT now(),
updated_at TIMESTAMPTZ DEFAULT now()
```

### Status-Werte
- `Beauftragt` - Lieferantenrechnung eingegangen, Factoring beauftragt
- `Fakturiert` - Trumpf-Rechnung liegt vor
- `Offene Teilzahlung` - Teilweise bezahlt, Rest offen
- `Bezahlt` - Vollstaendig an Trumpf bezahlt (Zahldatum gesetzt)
- `Abgeschlossen` - Archiviert/Erledigt

### Datumsformat
Alle Datumsfelder werden als ISO-String (`YYYY-MM-DD`) gespeichert. Die Funktion `_parse_date()` in `data_manager.py` konvertiert automatisch aus:
- `datetime` / `date` Objekte
- `YYYY-MM-DD` Strings
- `DD.MM.YYYY` Strings (deutsches Format)
- `DD/MM/YYYY` Strings

---

## 4. Module im Detail

### 4.1 `modules/data_manager.py`

Zentrale Datenschicht mit Supabase-Client. Wird von allen Seiten importiert.

**Supabase-Client (Singleton):**
```python
@st.cache_resource
def _get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)
```

**Konstanten:**
```python
TABLE = "factoring_records"
BUCKET_INVOICES = "factoring-invoices"
BUCKET_REPORTS = "factoring-reports"
```

**CRUD-Funktionen:**

| Funktion | Beschreibung |
|---|---|
| `get_supabase()` | Supabase-Client (gecacht) |
| `insert_record(data)` | Neuen Datensatz einfuegen, gibt ID zurueck |
| `update_record(id, data)` | Datensatz aktualisieren |
| `delete_record(id)` | Datensatz loeschen |
| `get_record(id)` | Einzelnen Datensatz als `dict` holen |
| `get_all_records()` | Alle Datensaetze als `pandas.DataFrame` |
| `get_filtered_records(status, lieferant, von, bis)` | Gefilterte Abfrage |
| `get_unique_lieferanten()` | Liste aller Lieferantennamen |
| `get_status_options()` | Hartcodierte Status-Liste |
| `find_by_trumpf_re_nr(nr)` | Suche per Trumpf-RE-Nr (fuer Zahlungszuordnung) |
| `find_by_lieferant_re_nr(nr)` | Suche per Lieferanten-RE-Nr (fuer Vorgang-Matching) |
| `record_count()` | Anzahl Datensaetze |

**Storage-Funktionen:**

| Funktion | Beschreibung |
|---|---|
| `get_storage_path(re_nr_trumpf, lieferant)` | Generiert Storage-Ordnerpfad |
| `save_invoice_pdf(bytes, folder, type, nr)` | Speichert PDF in Supabase Storage (upsert) |
| `get_invoice_url(path, expires_in)` | Signierte URL fuer eine gespeicherte PDF |
| `save_report(bytes, filename)` | Speichert Report in Supabase Storage |
| `get_vorgang_dir(...)` | Alias fuer `get_storage_path` (Abwaertskompatibilitaet) |

**Storage-Pfad-Struktur:**
```
{RE_Trumpf}_{Lieferant_kurz}/
```
- `Lieferant_kurz` = erster Teil des Lieferantennamens vor dem Leerzeichen
- Ungueltige Zeichen (`<>:"/\|?*`) werden durch `_` ersetzt
- Falls keine Trumpf-RE-Nr vorhanden: `ohne_RE_{Lieferant_kurz}/`

**PDF-Dateinamen:**
- Trumpf: `Trumpf_{Trumpf-RE-Nr}.pdf` (z.B. `Trumpf_663240.pdf`)
- Lieferant: `Lieferantenrechnung_{Lieferanten-RE-Nr}.pdf` (z.B. `Lieferantenrechnung_202510081.pdf`)

**Hilfsfunktionen:**
- `_parse_date(val)` - Datumskonvertierung zu ISO-String
- `_safe_float(val)` - Sichere Float-Konvertierung mit Rundung auf 2 Stellen
- `_sanitize_folder_name(name)` - Ungueltige Zeichen aus Ordnernamen entfernen
- `_prepare_record(data)` - Datensatz fuer Supabase vorbereiten (Typen konvertieren)

---

### 4.2 `modules/calculations.py`

Reine Berechnungslogik, keine DB-Abhaengigkeit.

**Einzelfunktionen:**

| Funktion | Formel | Rueckgabe |
|---|---|---|
| `berechne_offener_betrag(brutto, gezahlt)` | `brutto - gezahlt` | `float` |
| `berechne_zinsen(trumpf_netto, netto)` | `trumpf_netto - netto` | `float` |
| `berechne_zinsaufschlag(zinsen, netto)` | `zinsen / netto` | `float` oder `None` |
| `berechne_tage_finanziert(zahlung, re_datum)` | `(zahlung - re_datum).days` | `int` oder `None` |
| `berechne_eff_jahreszins(zinsen, netto, tage)` | `(zinsen/netto) * (365/tage)` | `float` oder `None` |
| `berechne_zinsen_pro_tag(zinsen, tage)` | `zinsen / tage` | `float` oder `None` |
| `berechne_zinssatz_30_tage(aufschlag, tage)` | `aufschlag * (30/tage)` | `float` oder `None` |

**Hauptfunktion `berechne_alle_felder(record: dict) -> dict`:**
- Nimmt ein Record-Dict, berechnet alle abgeleiteten Felder, gibt das erweiterte Dict zurueck
- **Wichtig**: `tage_finanziert` wird NUR berechnet wenn `zahlung_an_trumpf` gesetzt ist (nicht bei Teilzahlung)
- Ohne `zahlung_an_trumpf` sind `tage_finanziert`, `eff_jahreszins`, `zinsen_pro_tag`, `zinssatz_30_tage` alle `None`

**Datumskonvertierung `_to_date(val)`:**
Unterstuetzt: `date`, `datetime`, `str` (Formate `YYYY-MM-DD` und `DD.MM.YYYY`)

---

### 4.3 `modules/invoice_parser.py`

PDF-Textextraktion und Datenextraktion mittels Regex. Kein OCR - die PDFs muessen einen Text-Layer haben.

**Architektur:**

```
parse_invoice_pdf(file_bytes)
    |
    v
extract_text_from_pdf(file_bytes)     # pdfplumber Text-Extraktion
    |
    v
_detect_invoice_type(text)             # Erkennung: "trumpf" | "soieta" | "generic"
    |
    v
_parse_trumpf_invoice(text)            # oder _parse_soieta_invoice / _parse_generic_supplier_invoice
    |
    v
Ergebnis-Dict mit fields + meta
```

**Rechnungstyp-Erkennung (`_detect_invoice_type`):**
- `"trumpf"` wenn "trumpf financial" UND "endbetrag" im Text
- `"soieta"` wenn "soieta" im Text
- `"generic"` sonst (Fallback fuer andere Lieferanten)

**Spezialisierte Parser:**

#### `_parse_trumpf_invoice(text)`
Fuer TRUMPF Financial Services GmbH Rechnungen.
- RE-Nr: `Nr. XXXXXX` (5-7 Ziffern, Format 66XXXX)
- RE-Datum: `Durchwahl Datum\n... DD.MM.YYYY` (Datum am Ende der Folgezeile)
  - ACHTUNG: Nicht "Valuta Datum" matchen! Fallback mit Negative Lookbehind: `(?<!Valuta )Datum`
  - pdfplumber extrahiert die Tabellenspalten als eine Zeile, das Datum steht am ENDE
- Valuta: `Valuta Datum\nDD.MM.YYYY`
- Netto: `Summe XX.XXX,XX`
- Brutto: `Endbetrag XX.XXX,XX`
- Lieferanten-RE-Nr: `Material (Lieferant)-RG-Nr.:\n....\nXXXXXXXXXX`

#### `_parse_soieta_invoice(text)`
Fuer SOIETA TECH s.r.o. Rechnungen (englischsprachig!).
- RE-Nr: `No. XXXXXXXXXX` (7+ Ziffern)
- RE-Datum: `Invoice date: DD.MM.YYYY`
- Faelligkeit: `Due date: DD.MM.YYYY`
- Betrag: `TOTAL DUE Currency EUR X,XXX.XX` - **ENGLISCHES Zahlenformat** (Komma = Tausender, Punkt = Dezimal)
- Soieta ist steuerbefreit, daher Netto = Brutto

#### `_parse_generic_supplier_invoice(text)`
Generischer Parser fuer unbekannte Lieferanten.
- Sucht nach gaengigen deutschen Rechnungsfeld-Labels
- Firmenname wird aus den ersten 15 Zeilen extrahiert (sucht nach Rechtsformen wie GmbH, AG, etc.)

**Hilfsfunktionen:**
- `parse_german_amount(text)` - Deutsches Geldformat parsen: `1.234,56` -> `1234.56`
- `parse_german_date(text)` - Deutsches Datum parsen: `13.09.2024` -> `2024-09-13`
- `extract_text_from_pdf(bytes)` - pdfplumber Text-Extraktion, alle Seiten

**Ergebnis-Struktur von `parse_invoice_pdf()`:**
```python
{
    "success": True/False,
    "error": "..." oder None,
    "raw_text": "...",                    # Kompletter PDF-Text
    "fields": {
        "rechnungsnummer": {"value": "663715", "confidence": "high"},
        "rechnungsdatum":  {"value": "2026-02-13", "raw": "13.02.2026", "confidence": "high"},
        "netto_betrag":    {"value": 7010.0, "raw": "7.010,00", "confidence": "high"},
        "brutto_betrag":   {"value": 8341.90, "raw": "8.341,90", "confidence": "high"},
        "lieferant":       {"value": "Soieta Tech s.r.o", "confidence": "high"},
        "faelligkeitsdatum": {"value": "2026-05-13", "raw": "13.05.2026", "confidence": "high"},
        "lieferanten_re_nr": {"value": "2619100002", "confidence": "high"},  # Nur bei Trumpf
    },
    "meta": {
        "pages": 1,
        "text_length": 1234,
        "invoice_type": "trumpf",         # "trumpf" | "soieta" | "generic"
        "note": "..." oder None,
    }
}
```

**Confidence-Level:**
- `"high"` - Explizites Label gefunden (z.B. "Rechnungsnummer: ...")
- `"medium"` - Allgemeineres Label oder Muster
- `"low"` - Heuristik / Fallback

---

### 4.4 `modules/excel_export.py`

Erzeugt professionelle Excel-Reports mit 4 Sheets.

**Funktion:** `generate_excel_report(df: pd.DataFrame) -> bytes`

**4 Sheets:**

1. **Dashboard**
   - Titel + Datum
   - 4 KPI-Boxen (Offene Betraege, Jahreszins, Tage, Anzahl)
   - Balkendiagramm: Offene Betraege nach Monat
   - Kreisdiagramm: Verteilung nach Lieferant

2. **Offene Posten**
   - Tabelle mit Lieferant, RE-Nr, Valuta, Trumpf Brutto, Bereits gezahlt, Offen, Status
   - Bedingte Formatierung auf "Offen"-Spalte:
     - Rot: > 20.000 EUR
     - Gelb: 10.001 - 20.000 EUR
     - Gruen: <= 10.000 EUR
   - Autofilter aktiviert

3. **Alle Rechnungen**
   - Vollstaendige Tabelle (20 Spalten)
   - Waehrungs-/Prozent-/Ganzzahl-Formatierung
   - Abwechselnde Zeilenfarben
   - Erste Zeile fixiert, Autofilter aktiviert

4. **Zinsanalyse**
   - Gruppierung nach Lieferant: Anzahl, Volumen, Zinsen, Jahreszins, Tage
   - GESAMT-Zeile mit Doppel-Rahmen

**Styling-Konstanten:**
- Firmenfarben: `#1B2A4A` (Header), `#2E86AB` (Akzent), `#28A745` (Erfolg), `#FFC107` (Warnung), `#DC3545` (Gefahr)
- Fonts: Helvetica, Groessen 10-18
- Waehrungsformat: `#,##0.00 "EUR"`

---

### 4.5 `modules/pdf_report.py`

Generiert einen GRAIL-gebrandeten Ist-Report im Portrait A4-Format (optimiert fuer Handy-Ansicht).

**Funktion:** `generate_pdf_report(df: pd.DataFrame) -> bytes`

**Klasse `_R(FPDF)`:**
- `cell()` ueberschrieben fuer automatische Unicode-Bereinigung (`_s()`)
- Umlaute werden ersetzt: ae, oe, ue, ss (Helvetica kann kein Unicode)
- `header()` leer (1-Seiten-Report, Header manuell)
- `footer()`: Trennlinie + "GRAIL Automotive | TRUMPF Financial Services | Vertraulich" + Seitennummer

**Farbschema (GRAIL-Branding):**
- `NEON = (232, 255, 0)` - Primaerfarbe (Neon-Gelb)
- `BLACK = (0, 0, 0)` / `DARK = (26, 26, 26)` - Hintergrund Banner/Tabellen-Header
- Ampel: `RED_BG = (255, 232, 232)` fuer > 20.000 EUR, `YEL_BG = (255, 250, 230)` fuer > 10.000 EUR

**Zeichenhelfer (absolute Positionierung mit x, y):**
- `_hdr(pdf, cols, x, y)` - Tabellen-Header (dunkel mit Neon-Text)
- `_row(pdf, cells, cols, x, y, idx, fill)` - Tabellenzeile (abwechselnde Farben)
- `_srow(pdf, cells, cols, x, y)` - Summenzeile (dunkel mit Neon-Text und Trennlinie)
- `_title(pdf, text, y)` - Sektions-Titel mit Neon-Akzent-Linie

**Seitenaufbau (1 Seite, Portrait A4, 190mm nutzbar):**
1. **Banner** (26mm): Schwarz, "GRAIL" in Neon + "Offene Posten | TRUMPF Factoring" + Stichtag-Info
2. **Uebersicht-Sektion**:
   - Dominanter "NAECHSTE FAELLIGKEIT"-Block (dunkel, Neon-Akzent links, Datum + Betrag + RE-Nr.)
   - 3 gleichbreite KPI-Karten: "Noch zu zahlen" (mit Subtext), "Offene Rechnungen", "Trumpf-Brutto (offen)" (mit Subtext)
3. **Zwei Tabellen nebeneinander** (je ~92mm):
   - Links: "Offene Summen nach Monaten" (Monat, Anzahl, Betrag + Gesamt-Summe)
   - Rechts: "Faelligkeiten" (Datum, Betrag, RE-Nr. + Summe)
4. **Detail-Tabelle "Offene Posten (Detail)"**:
   - Spalten (190mm): Lieferant(36) + RE Lief.(22) + RE Trumpf(20) + RE-Datum(20) + Valuta(20) + Brutto(26) + Offen(26) + Zinsen(20)
   - Ampel-Faerbung pro Zeile basierend auf offenem Betrag
   - SUMME-Zeile am Ende
   - Legende fuer Ampel-Farben
   - Auto-Seitenumbruch bei y > 275mm (bei sehr vielen offenen Posten)

---

## 5. Seiten im Detail

### 5.1 `app.py` (Redirect)

- Prueft ob `SUPABASE_URL` und `SUPABASE_KEY` in Secrets vorhanden sind
- Leitet automatisch zum Dashboard weiter via `st.switch_page("pages/1_Dashboard.py")`
- Custom CSS fuer Sidebar-Styling (dunkles Farbschema, wird global angewendet)
- Keine eigene Seitenanzeige

### 5.2 `pages/1_Dashboard.py`

- 5 KPIs in einer Reihe
- 4 plotly-Charts:
  - `px.bar` - Offene Betraege gestapelt nach Monat + Lieferant
  - `px.pie` - Volumen-Verteilung (Donut-Chart mit `hole=0.4`)
  - `px.area` - Zinskosten-Entwicklung
  - `px.scatter` - Bubble-Chart Zinsanalyse (Tage vs. Zinssatz, Groesse = Zinsen)
- Tabelle: Naechste faellige Zahlungen (Top 10, sortiert nach Valuta)
- Sidebar-Filter: Status + Lieferant

### 5.3 `pages/2_Rechnungen_Upload.py`

**Ablauf:**

```
Upload (Drag & Drop, mehrere PDFs)
    |
    v
"X Datei(en) analysieren" Button
    |
    v
Fuer jede Datei:
  1. parse_invoice_pdf(bytes)           # Text extrahieren + Typ erkennen
  2. _extract_fields(result, type)      # Parser-Output -> flaches Dict
  3. _find_existing(extracted, type)    # Bestehenden Vorgang suchen (Supabase)
  4. _compare_fields(extracted, rec)    # Vergleich: neu/geaendert/PDF fehlt
    |
    v
Uebersicht anzeigen (gruen=neu, gelb=update, blau=skip, rot=fehler)
    |
    v
"X Datei(en) verarbeiten" Button
    |
    v
_process_file() pro Datei -> insert_record / update_record + save_invoice_pdf (Supabase Storage)
```

**Hilfsfunktionen:**

`_extract_fields(result, invoice_type)`:
- Mappt Parser-Output auf Datenbank-Feldnamen
- Trumpf: `rechnungsnummer` -> `re_nr_trumpf`, `netto_betrag` -> `trumpf_netto`, etc.
- Lieferant: `rechnungsnummer` -> `re_nr_lieferant`, `netto_betrag` -> `netto_betrag`, etc.

`_find_existing(extracted, doc_type)`:
3-stufiges Matching:
1. Per `re_nr_trumpf` -> `find_by_trumpf_re_nr()`
2. Per `lieferanten_re_nr_from_trumpf` -> `find_by_lieferant_re_nr()` (Lieferanten-RE-Nr aus Trumpf-Rechnung)
3. Per `re_nr_lieferant` -> `find_by_lieferant_re_nr()` (Lieferanten-RE-Nr aus Lieferantenrechnung)

`_compare_fields(extracted, rec, doc_type)`:
- Vergleicht jeden extrahierten Wert mit dem DB-Wert
- Floats: Rundung auf 2 Dezimalstellen
- Strings: `.strip()` vor Vergleich
- Returns: `(new_fields, changed_fields, pdf_missing)`

`_process_file(pdf_bytes, doc_type, extracted, existing_match)`:
- Update: Fehlende/geaenderte Felder mergen, PDF in Supabase Storage speichern, `berechne_alle_felder()`, `update_record()`
- Create: Neuen Datensatz anlegen mit allen extrahierten Feldern

### 5.4 `pages/3_Datenverwaltung.py`

**Globale Hilfsfunktionen:**
- `_fmt_eur(val)` - `1234.56` -> `"1.234,56 EUR"`
- `_fmt_date(val)` - `"2026-02-13"` -> `"13.02.2026"`
- `_status_badge(status)` - HTML-Badge mit Farbe
- `_status_sort_key(status)` - Sortierreihenfolge: Beauftragt(0) -> Abgeschlossen(4)
- `_doc_status(row)` - PDF-Vollstaendigkeit pruefen (Checkmark oder Warnung)

**Zahlung zuordnen (Expander):**
```python
neue_zahlung = alte_zahlung + z_betrag
if neue_zahlung >= trumpf_brutto:
    status = "Bezahlt"
    zahlung_an_trumpf = z_datum        # NUR bei Vollzahlung
elif neue_zahlung > 0:
    status = "Offene Teilzahlung"
    # KEIN Zahldatum gesetzt!
```

**4 Tabs:**
1. **Offene Posten** - `filtered[status in offene_stati]`, Spalte "Bezahlt am" (`zahlung_an_trumpf`)
2. **Alle** - Alle Datensaetze, sortiert nach Status, alle Kennzahlen + "Bezahlt am" + PDFs-Spalte
3. **Abgeschlossen** - `filtered[status == "Abgeschlossen"]`, inkl. "Bezahlt am"-Datum
4. **Bearbeiten** - `st.form` mit allen editierbaren Feldern, Kennzahlen-Anzeige, Loeschen mit Bestaetigung

**Hinweis:** Die Spalte "Bezahlt am" zeigt `zahlung_an_trumpf` (Datum der Vollzahlung), NICHT `bereits_gezahlt` (Betrag).

**Prozent-Spalten:**
`zinsaufschlag`, `eff_jahreszins`, `zinssatz_30_tage` sind in der DB als Dezimalzahlen gespeichert (z.B. 0.0534). Fuer die Anzeige werden sie mit `* 100` in `_pct`-Spalten umgerechnet.

### 5.5 `pages/4_Export.py`

- **Filter**: Status + Lieferant. Der Status-Filter enthaelt "Offene Posten" als Schnelloption (kombiniert Beauftragt + Fakturiert + Offene Teilzahlung)
- Zwei Spalten: Excel-Export + PDF-Export
- `generate_excel_report(df)` -> `st.download_button`
- `generate_pdf_report(df)` -> `st.download_button`
- Datenvorschau-Tabelle unten

**Auto-Archivierung (Supabase Storage):**
```python
def _archiviere(daten: bytes, dateiname: str):
    try:
        save_report(daten, dateiname)   # -> Bucket "factoring-reports"
    except Exception:
        pass  # Archivierung darf Export nicht blockieren
```
- Jeder generierte Report wird automatisch in Supabase Storage archiviert
- Dateiname: `Trumpf_Factoring_Report_YYYY-MM-DD.xlsx` bzw. `.pdf`
- Maximal 1 Report pro Tag (bei erneutem Export am selben Tag wird ueberschrieben via upsert)

---

## 6. Geschaeftslogik

### Matching-Regeln

**Vorgang-Matching (Upload):**
Der gemeinsame Identifikator ist die **Lieferanten-Rechnungsnummer**. Diese steht auf BEIDEN Dokumenten:
- Auf der Lieferantenrechnung als RE-Nr (z.B. `202510089`)
- Auf der Trumpf-Rechnung unter "Material (Lieferant)-RG-Nr."

**Zahlungs-Matching (Zahlung zuordnen):**
Zahlungen werden per **Trumpf-Rechnungsnummer** zugeordnet (Format `66XXXX`).

### Zahlungslogik

```
Teilzahlung:
  bereits_gezahlt += betrag
  status = "Offene Teilzahlung"
  zahlung_an_trumpf = NULL           # Kein Datum!
  -> Tage/Zins-Kennzahlen = None

Vollzahlung (bereits_gezahlt >= trumpf_brutto):
  bereits_gezahlt += betrag
  status = "Bezahlt"
  zahlung_an_trumpf = zahlungsdatum  # Datum der finalen Zahlung
  -> Tage/Zins-Kennzahlen werden berechnet
```

### Berechnungslogik

**Immer berechnet (sobald Daten vorhanden):**
- `offener_betrag` = trumpf_brutto - bereits_gezahlt
- `zinsen` = trumpf_netto - netto_betrag
- `zinsaufschlag` = zinsen / netto_betrag

**Nur bei Vollzahlung berechnet (zahlung_an_trumpf gesetzt):**
- `tage_finanziert` = zahlung_an_trumpf - re_datum_trumpf (in Tagen)
- `eff_jahreszins` = (zinsen / netto) * (365 / tage)
- `zinsen_pro_tag` = zinsen / tage
- `zinssatz_30_tage` = zinsaufschlag * (30 / tage)

### Smart Duplicate Detection (Upload)

Beim Upload wird fuer jede PDF geprueft:
1. Gibt es einen bestehenden Vorgang? (per RE-Nr Matching in Supabase)
2. Falls ja: Feld-fuer-Feld-Vergleich
   - `new_fields`: Feld in DB leer, Wert in PDF vorhanden -> ergaenzen
   - `changed_fields`: Feld in DB anders als in PDF -> aktualisieren
   - `pdf_missing`: PDF-Datei fehlt im Storage -> ablegen
3. Falls ALLES identisch UND PDF vorhanden -> Skip ("Duplikat")
4. Falls Unterschiede -> Update mit Details anzeigen

---

## 7. Bekannte Besonderheiten

### pdfplumber + Trumpf-PDFs
Trumpf-Rechnungen haben ein Tabellen-Layout. pdfplumber extrahiert die Spaltenkoepfe als eine Zeile:
```
Durchwahl Datum
DE332594299 THS120 31096 13.02.2026
```
Das RE-Datum steht am ENDE der Folgezeile, nicht direkt nach "Datum". Der Parser muss daher:
```python
re.search(r"Durchwahl\s+Datum\s*\n.*?" + date_re, text)
```
und das Datum aus der gesamten Folgezeile extrahieren.

### Soieta-Rechnungen: Englisches Zahlenformat
Soieta Tech nutzt englisches Zahlenformat: `7,010.00` (Komma = Tausender, Punkt = Dezimal).
Der Parser erkennt dies am Muster `TOTAL DUE Currency EUR X,XXX.XX` und parst mit `float(raw.replace(",", ""))`.

### Umlaute in PDF-Reports
Helvetica (fpdf2 Standard-Font) unterstuetzt keine deutschen Umlaute. Die Klasse `FactoringReport` ersetzt automatisch:
`ae/oe/ue/Ae/Oe/Ue/ss/EUR` via `_safe_text()`.

---

## 8. Deployment & Updates

### Streamlit Community Cloud
- **Repo:** `viic91/trumpf-factoring` (GitHub, public)
- **Branch:** `master`
- **Main file:** `app.py`
- **Secrets:** `SUPABASE_URL` + `SUPABASE_KEY` (in Streamlit Cloud Dashboard konfiguriert)
- **Auto-Deploy:** Jeder Push auf `master` loest automatisch ein Redeployment aus

### Update-Workflow
1. Code lokal aendern (oder via Claude Code)
2. `git add` + `git commit` + `git push origin master`
3. Streamlit Cloud erkennt den Push und deployed die neue Version automatisch (1-2 Minuten)

### Secrets aendern
Supabase-Credentials werden ueber das **Streamlit Cloud Dashboard** verwaltet (Settings -> Secrets). Nicht ueber Git.

### Supabase
- **Projekt:** `victor` (`utmaraahcnavgumuqtjm`)
- **Region:** eu-central-1 (Frankfurt)
- **URL:** `https://utmaraahcnavgumuqtjm.supabase.co`

---

## 9. Wiederherstellung / Neuaufbau

### Minimale Schritte zum Neuaufbau:

1. **GitHub-Repo klonen:**
   ```
   git clone https://github.com/viic91/trumpf-factoring.git
   ```
2. **Dependencies installieren:**
   ```
   pip install -r requirements.txt
   ```
3. **Secrets einrichten** (`.streamlit/secrets.toml`):
   ```toml
   SUPABASE_URL = "https://utmaraahcnavgumuqtjm.supabase.co"
   SUPABASE_KEY = "<anon-key>"
   ```
4. **Starten:**
   ```
   streamlit run app.py
   ```

### Supabase-Tabelle neu erstellen (falls noetig):
Die Tabelle `factoring_records` muss im Supabase-Projekt existieren. Schema siehe Abschnitt 3.

### Daten migrieren (SQLite -> Supabase):
Das Skript `migrate_data.py` wurde fuer die einmalige Migration von SQLite nach Supabase verwendet. Bei Bedarf kann es erneut ausgefuehrt werden.

---

## 10. Abhaengigkeiten (requirements.txt)

```
streamlit>=1.30.0
pdfplumber>=0.10.0
plotly>=5.18.0
openpyxl>=3.1.0
fpdf2>=2.7.0
pandas>=2.0.0
supabase>=2.0.0
```

Alle Pakete sind via `pip install` verfuegbar. Keine externen System-Dependencies (kein Tesseract, kein Poppler etc.).

---

## 11. Konfiguration

### Streamlit
- Layout: `wide` auf allen Seiten
- Sidebar: Dunkles Farbschema via Custom CSS
- `set_page_config()` pro Seite mit individuellem Titel und Icon

### runtime.txt
```
python-3.12
```
Stellt sicher, dass Streamlit Cloud die richtige Python-Version verwendet.

### Dev-Server (`.claude/launch.json`)
```json
{
    "version": "0.0.1",
    "configurations": [{
        "name": "streamlit",
        "runtimeExecutable": "streamlit",
        "runtimeArgs": ["run", "app.py"],
        "port": 8501
    }]
}
```
