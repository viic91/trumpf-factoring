# TRUMPF Factoring Tool - Technische Komplettdokumentation

## 1. Ueberblick

### Zweck
Webbasiertes Factoring-Management-Tool fuer GRAIL Automotive. Verwaltet den Rechnungsfluss:
Lieferant (z.B. Soieta Tech) -> TRUMPF Financial Services (Vorfinanzierung) -> GRAIL Automotive (Zahlung).

### Tech-Stack
- **Python 3.12**
- **Streamlit 1.53+** - Web-UI (Multi-Page App, laeuft lokal im Browser)
- **SQLite** (built-in) - Lokale Datenbank
- **pdfplumber** - PDF-Textextraktion (kein OCR, benoetigt Text-Layer)
- **plotly** - Interaktive Charts im Dashboard
- **openpyxl** - Excel-Export mit professioneller Formatierung
- **fpdf2** - PDF-Report-Generierung
- **pandas** - Datenverarbeitung

### Voraussetzungen
```
pip install streamlit pdfplumber plotly openpyxl fpdf2 pandas
```
Oder via `requirements.txt`:
```
pip install -r requirements.txt
```

---

## 2. Projektstruktur

```
Trumpf-Factoring-Tool/
|
|-- app.py                              # Streamlit Hauptapp (Redirect zum Dashboard)
|-- requirements.txt                    # Python-Dependencies
|-- GEBRAUCHSANWEISUNG.md              # Benutzerhandbuch
|-- TECHNISCHE_DOKUMENTATION.md        # Diese Datei
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
|   |-- data_manager.py                # SQLite CRUD + Dateiverwaltung
|   |-- calculations.py                # Zins-/Kosten-Berechnungen
|   |-- excel_export.py                # Professioneller Excel-Report
|   |-- pdf_report.py                  # PDF Ist-Report (GRAIL-Branding)
|
|-- data/                               # Laufzeitdaten (auto-erstellt)
|   |-- factoring.db                    # SQLite-Datenbank
|   |-- invoices/                       # (Legacy, nicht mehr aktiv genutzt)
|
|-- Dokumente/                          # PDF-Archiv (pro Vorgang ein Ordner)
|   |-- {Trumpf-RE-Nr}_{Lieferant}/
|       |-- Lieferantenrechnung_{RE-Nr}.pdf
|       |-- Trumpf_{RE-Nr}.pdf
|
|-- Archiv/                             # Auto-archivierte Reports (1 pro Tag)
|   |-- Trumpf_Factoring_Report_YYYY-MM-DD.xlsx
|   |-- Trumpf_Factoring_Report_YYYY-MM-DD.pdf
|
|-- .claude/
    |-- launch.json                     # Dev-Server Konfiguration
```

---

## 3. Datenbank-Schema

### Tabelle: `factoring_records`

SQLite-Datenbank unter `data/factoring.db`. Wird automatisch beim ersten Import von `data_manager.py` erstellt.

```sql
CREATE TABLE IF NOT EXISTS factoring_records (
    -- Primaerschluessel
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Lieferanten-Daten
    lieferant TEXT NOT NULL,             -- Firmenname (z.B. "Soieta Tech s.r.o")
    re_nr_lieferant TEXT,                -- Rechnungsnummer des Lieferanten (z.B. "202510089")
    re_datum_lieferant TEXT,             -- Rechnungsdatum (ISO: YYYY-MM-DD)
    netto_betrag REAL,                   -- Nettobetrag Lieferantenrechnung
    brutto_betrag REAL,                  -- Bruttobetrag Lieferantenrechnung

    -- Trumpf-Daten
    valuta_trumpf TEXT,                  -- Faelligkeitsdatum/Valuta der Trumpf-Rechnung
    re_nr_trumpf TEXT,                   -- Trumpf-Rechnungsnummer (Format: 66XXXX)
    re_datum_trumpf TEXT,                -- Rechnungsdatum Trumpf (ISO)
    zahlung_an_trumpf TEXT,              -- Datum der Vollzahlung an Trumpf (ISO)
    trumpf_netto REAL,                   -- Nettobetrag Trumpf-Rechnung
    trumpf_brutto REAL,                  -- Bruttobetrag Trumpf-Rechnung

    -- Zahlungsstatus
    bereits_gezahlt REAL DEFAULT 0,      -- Summe bisheriger Zahlungen
    offener_betrag REAL,                 -- BERECHNET: trumpf_brutto - bereits_gezahlt
    status TEXT DEFAULT 'Beauftragt',    -- Workflow-Status (siehe unten)

    -- Berechnete Finanzkennzahlen
    zinsen REAL,                         -- BERECHNET: trumpf_netto - netto_betrag
    zinsaufschlag REAL,                  -- BERECHNET: zinsen / netto_betrag (Dezimalzahl)
    eff_jahreszins REAL,                 -- BERECHNET: (zinsen/netto) * (365/tage) (Dezimalzahl)
    tage_finanziert INTEGER,             -- BERECHNET: zahlung_an_trumpf - re_datum_trumpf
    zinsen_pro_tag REAL,                 -- BERECHNET: zinsen / tage_finanziert
    zinssatz_30_tage REAL,               -- BERECHNET: zinsaufschlag * (30/tage)

    -- PDF-Referenzen (absolute Dateipfade)
    invoice_pdf_lieferant TEXT,          -- Pfad zur Lieferantenrechnung-PDF
    invoice_pdf_trumpf TEXT,             -- Pfad zur Trumpf-Rechnung-PDF

    -- Metadaten
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
```

### Status-Werte
- `Beauftragt` - Lieferantenrechnung eingegangen, Factoring beauftragt
- `Fakturiert` - Trumpf-Rechnung liegt vor
- `Offene Teilzahlung` - Teilweise bezahlt, Rest offen
- `Bezahlt` - Vollstaendig an Trumpf bezahlt (Zahldatum gesetzt)
- `Abgeschlossen` - Archiviert/Erledigt

### Datumsformat
Alle Datumsfelder werden als ISO-String (`YYYY-MM-DD`) in der DB gespeichert. Die Funktion `_parse_date()` in `data_manager.py` konvertiert automatisch aus:
- `datetime` / `date` Objekte
- `YYYY-MM-DD` Strings
- `DD.MM.YYYY` Strings (deutsches Format)
- `DD/MM/YYYY` Strings

---

## 4. Module im Detail

### 4.1 `modules/data_manager.py`

Zentrale Datenschicht. Wird von allen Seiten importiert. Initialisiert die DB automatisch beim Import (`init_db()` am Modulende).

**Pfad-Konstanten:**
```python
DB_DIR = <Projektordner>/data/
DB_PATH = <Projektordner>/data/factoring.db
INVOICES_DIR = <Projektordner>/data/invoices/    # Legacy
DOCS_DIR = <Projektordner>/Dokumente/            # Aktives PDF-Archiv
```

**Kernfunktionen:**

| Funktion | Beschreibung |
|---|---|
| `get_connection()` | SQLite-Verbindung mit WAL-Mode und Row-Factory |
| `init_db()` | Erstellt Tabelle falls nicht vorhanden |
| `insert_record(data)` | Neuen Datensatz einfuegen, gibt ID zurueck |
| `update_record(id, data)` | Datensatz aktualisieren (setzt `updated_at`) |
| `delete_record(id)` | Datensatz loeschen |
| `get_record(id)` | Einzelnen Datensatz als `dict` holen |
| `get_all_records()` | Alle Datensaetze als `pandas.DataFrame` |
| `get_filtered_records(status, lieferant, von, bis)` | Gefilterte Abfrage |
| `get_unique_lieferanten()` | Liste aller Lieferantennamen |
| `get_status_options()` | Hartcodierte Status-Liste |
| `find_by_trumpf_re_nr(nr)` | Suche per Trumpf-RE-Nr (fuer Zahlungszuordnung) |
| `find_by_lieferant_re_nr(nr)` | Suche per Lieferanten-RE-Nr (fuer Vorgang-Matching) |
| `get_vorgang_dir(re_nr_trumpf, lieferant)` | Erstellt/gibt Ordnerpfad zurueck |
| `save_invoice_pdf(bytes, dir, type, nr)` | Speichert PDF im Vorgangsordner |
| `import_from_excel(path)` | Initialer Excel-Import (Sheet "2025_NEU") |
| `record_count()` | Anzahl Datensaetze |

**Ordnerstruktur fuer PDFs:**
```
Dokumente/{RE_Trumpf}_{Lieferant_kurz}/
```
- `Lieferant_kurz` = erster Teil des Lieferantennamens vor dem Leerzeichen
- Ungueltige Zeichen (`<>:"/\|?*`) werden durch `_` ersetzt
- Falls keine Trumpf-RE-Nr vorhanden: `ohne_RE_{Lieferant_kurz}/`

**PDF-Dateinamen:**
- Trumpf: `Trumpf_{Trumpf-RE-Nr}.pdf` (z.B. `Trumpf_663240.pdf`)
- Lieferant: `Lieferantenrechnung_{Lieferanten-RE-Nr}.pdf` (z.B. `Lieferantenrechnung_202510081.pdf`)

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

- Leitet automatisch zum Dashboard weiter via `st.switch_page("pages/1_Dashboard.py")`
- Custom CSS fuer Sidebar-Styling (dunkles Farbschema, wird global angewendet)
- Keine eigene Seitenanzeige mehr

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
  3. _find_existing(extracted, type)    # Bestehenden Vorgang suchen
  4. _compare_fields(extracted, rec)    # Vergleich: neu/geaendert/PDF fehlt
    |
    v
Uebersicht anzeigen (gruen=neu, gelb=update, blau=skip, rot=fehler)
    |
    v
"X Datei(en) verarbeiten" Button
    |
    v
_process_file() pro Datei -> insert_record / update_record + save_invoice_pdf
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
- Update: Fehlende/geaenderte Felder mergen, PDF speichern, `berechne_alle_felder()`, `update_record()`
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

**Auto-Archivierung:**
```python
ARCHIV_DIR = Path(<Projektordner>) / "Archiv"
ARCHIV_DIR.mkdir(exist_ok=True)

def _archiviere(daten: bytes, dateiname: str):
    (ARCHIV_DIR / dateiname).write_bytes(daten)
```
- Jeder generierte Report wird automatisch im `Archiv/`-Ordner gespeichert
- Dateiname: `Trumpf_Factoring_Report_YYYY-MM-DD.xlsx` bzw. `.pdf`
- Maximal 1 Report pro Tag (bei erneutem Export am selben Tag wird ueberschrieben)
- `try/except` um Archivierung: darf Export nicht blockieren

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
1. Gibt es einen bestehenden Vorgang? (per RE-Nr Matching)
2. Falls ja: Feld-fuer-Feld-Vergleich
   - `new_fields`: Feld in DB leer, Wert in PDF vorhanden -> ergaenzen
   - `changed_fields`: Feld in DB anders als in PDF -> aktualisieren
   - `pdf_missing`: PDF-Datei fehlt im Vorgang -> ablegen
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

### Concurrent Access
SQLite wird mit `journal_mode=WAL` betrieben, was parallele Lesezugriffe erlaubt. Da Streamlit pro Tab eine eigene Session hat, koennen theoretisch Race Conditions bei gleichzeitigem Schreiben auftreten. Fuer den Ein-Benutzer-Betrieb ist das unkritisch.

---

## 8. Wiederherstellung / Neuaufbau

### Minimale Schritte zum Neuaufbau:

1. **Python 3.12+ installieren**
2. **Projektordner anlegen** mit obiger Struktur
3. **Dependencies installieren:**
   ```
   pip install streamlit pdfplumber plotly openpyxl fpdf2 pandas
   ```
4. **Alle Python-Dateien** aus `modules/` und `pages/` sowie `app.py` anlegen (siehe Quellcode)
5. **Starten:**
   ```
   streamlit run app.py
   ```
   Die Datenbank wird automatisch erstellt.

### Daten migrieren:
- `data/factoring.db` kopieren -> enthaelt alle Datensaetze
- `Dokumente/` kopieren -> enthaelt alle PDF-Archivdateien
- `Archiv/` kopieren -> enthaelt auto-archivierte Reports
- **Achtung:** Die PDF-Pfade in der DB sind absolut. Bei Umzug auf einen anderen Rechner muessen die Pfade in `invoice_pdf_lieferant` und `invoice_pdf_trumpf` angepasst werden (SQL UPDATE).

### Excel-Import (einmalig):
Falls die urspruengliche Excel-Datei importiert werden soll:
```python
from modules.data_manager import import_from_excel
import_count = import_from_excel("Pfad/zur/Excel.xlsm")
```
Liest Sheet `2025_NEU`, erwartet 14 Spalten in fester Reihenfolge (siehe `import_from_excel()` Quellcode).

---

## 9. Konfiguration

### Streamlit
- Layout: `wide` auf allen Seiten
- Sidebar: Dunkles Farbschema via Custom CSS
- `set_page_config()` pro Seite mit individuellem Titel und Icon

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

---

## 10. Abhaengigkeiten (requirements.txt)

```
streamlit>=1.30.0
pdfplumber>=0.10.0
plotly>=5.18.0
openpyxl>=3.1.0
fpdf2>=2.7.0
pandas>=2.0.0
```

Alle Pakete sind via `pip install` verfuegbar. Keine externen System-Dependencies (kein Tesseract, kein Poppler etc.).
