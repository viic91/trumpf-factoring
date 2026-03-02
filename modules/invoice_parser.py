"""
invoice_parser.py - Hybrid OCR Invoice Parser fuer deutsches Factoring-Management.

Extrahiert strukturierte Rechnungsdaten aus PDF-Dateien mithilfe von pdfplumber
und regulaeren Ausdruecken. Optimiert fuer deutsche Rechnungsformate.
"""

import io
import re
from datetime import datetime
from typing import Optional

import pdfplumber


# ---------------------------------------------------------------------------
# Hilfsfunktionen (Helper Functions)
# ---------------------------------------------------------------------------

def parse_german_amount(text: str) -> float:
    """Wandelt einen deutschen Geldbetrag-String in einen float um.

    Beispiele:
        "1.234,56"  -> 1234.56
        "1234,56"   -> 1234.56
        "234,5"     -> 234.5
        "1.234.567,89" -> 1234567.89
        "50,00 EUR" -> 50.0

    Args:
        text: Der zu parsende Betrag als String.

    Returns:
        Der Betrag als float.

    Raises:
        ValueError: Wenn der Text nicht als Betrag interpretiert werden kann.
    """
    if not text or not text.strip():
        raise ValueError("Leerer Betrag-String")

    cleaned = text.strip()

    # Waehrungssymbole und Leerzeichen entfernen
    cleaned = re.sub(r"[€$\s]", "", cleaned)
    cleaned = re.sub(r"(EUR|USD|CHF)", "", cleaned, flags=re.IGNORECASE).strip()

    # Negatives Vorzeichen erhalten
    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("-")

    # Deutsches Format: Punkte als Tausendertrenner, Komma als Dezimaltrenner
    # Pruefe ob deutsches Format vorliegt (Komma als Dezimaltrenner)
    if "," in cleaned:
        # Tausenderpunkte entfernen, Komma durch Punkt ersetzen
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.replace(",", ".")
    # Falls kein Komma vorhanden, aber Punkte: koennte Tausendertrenner sein
    # z.B. "1.234" (ohne Dezimalstellen) vs. "12.34" (englisches Format)
    # Wir nehmen deutsches Format an: Punkt = Tausendertrenner
    elif "." in cleaned:
        parts = cleaned.split(".")
        # Wenn der letzte Teil genau 3 Ziffern hat, ist es ein Tausendertrenner
        if len(parts[-1]) == 3:
            cleaned = cleaned.replace(".", "")
        # Sonst koennte es ein Dezimalpunkt sein (z.B. "12.5")
        # In diesem Fall belassen wir es so

    try:
        result = float(cleaned)
    except ValueError:
        raise ValueError(f"Kann '{text}' nicht als Betrag interpretieren")

    return -result if negative else result


def parse_german_date(text: str) -> str:
    """Wandelt ein deutsches Datum (DD.MM.YYYY) in ISO-Format (YYYY-MM-DD) um.

    Unterstuetzte Formate:
        "13.09.2024"   -> "2024-09-13"
        "1.9.2024"     -> "2024-09-01"
        "13.09.24"     -> "2024-09-13"
        "13/09/2024"   -> "2024-09-13"

    Args:
        text: Der zu parsende Datums-String.

    Returns:
        Das Datum im ISO-Format (YYYY-MM-DD).

    Raises:
        ValueError: Wenn der Text nicht als Datum interpretiert werden kann.
    """
    if not text or not text.strip():
        raise ValueError("Leerer Datums-String")

    cleaned = text.strip()

    # Verschiedene Trennzeichen normalisieren
    cleaned = cleaned.replace("/", ".").replace("-", ".")

    # Datumsformat DD.MM.YYYY oder DD.MM.YY parsen
    date_patterns = [
        (r"(\d{1,2})\.(\d{1,2})\.(\d{4})", "%d.%m.%Y"),
        (r"(\d{1,2})\.(\d{1,2})\.(\d{2})", "%d.%m.%y"),
    ]

    for pattern, fmt in date_patterns:
        match = re.match(pattern, cleaned)
        if match:
            try:
                # Zum Normalisieren durch datetime parsen
                day, month, year = match.groups()
                date_str = f"{day}.{month}.{year}"
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

    raise ValueError(f"Kann '{text}' nicht als Datum interpretieren")


# ---------------------------------------------------------------------------
# PDF-Textextraktion
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrahiert den gesamten Text aus einer PDF-Datei.

    Verarbeitet mehrseitige PDFs und konkateniert den Text aller Seiten.

    Args:
        file_bytes: Die PDF-Datei als Bytes.

    Returns:
        Der extrahierte Text. Leer, falls kein Text gefunden wurde
        (z.B. bei gescannten Bildern ohne OCR-Layer).

    Raises:
        ValueError: Wenn die Datei keine gueltige PDF ist.
    """
    if not file_bytes:
        raise ValueError("Leere Datei erhalten")

    try:
        pdf_stream = io.BytesIO(file_bytes)
        full_text = []

        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)

        return "\n\n".join(full_text)

    except Exception as e:
        raise ValueError(f"Fehler beim Lesen der PDF-Datei: {e}")


# ---------------------------------------------------------------------------
# Feld-Extraktoren (Field Extractors)
# ---------------------------------------------------------------------------

def _extract_invoice_number(text: str) -> dict:
    """Extrahiert die Rechnungsnummer aus dem Text."""
    patterns = [
        # Hohe Konfidenz: Explizite Rechnungsnummer-Labels
        (r"Rechnungsnummer[:\s]+([A-Za-z0-9\-/]+)", "high"),
        (r"Rechnung\s*Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)", "high"),
        (r"RE[\-\s]?Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)", "high"),
        (r"Invoice\s*No\.?\s*[:\s]+([A-Za-z0-9\-/]+)", "high"),
        (r"Rechnungs[\-\s]?Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)", "high"),
        # Mittlere Konfidenz: Kuerzere / weniger spezifische Muster
        (r"Rechnung\s+(\d{4,}[\-/]?\d*)", "medium"),
        (r"Nr\.?\s*[:\s]+(\d{4,}[\-/]?\d*)", "medium"),
        (r"Beleg[\-\s]?Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)", "medium"),
        # Niedrige Konfidenz: Allgemeine Nummernmuster
        (r"(?:RE|RG|INV)[\-]?(\d{4,})", "low"),
    ]

    for pattern, confidence in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                "value": match.group(1).strip(),
                "confidence": confidence,
            }

    return {"value": None, "confidence": None}


def _extract_invoice_date(text: str) -> dict:
    """Extrahiert das Rechnungsdatum aus dem Text."""
    # Deutsches Datumsformat: DD.MM.YYYY
    date_regex = r"(\d{1,2}\.\d{1,2}\.\d{2,4})"

    patterns = [
        # Hohe Konfidenz: Explizites Rechnungsdatum
        (rf"Rechnungsdatum[:\s]+{date_regex}", "high"),
        (rf"Datum\s*der\s*Rechnung[:\s]+{date_regex}", "high"),
        (rf"Invoice\s*Date[:\s]+{date_regex}", "high"),
        # Mittlere Konfidenz: Allgemeines Datum-Label
        (rf"Datum[:\s]+{date_regex}", "medium"),
        (rf"Date[:\s]+{date_regex}", "medium"),
        (rf"Ausstellungsdatum[:\s]+{date_regex}", "medium"),
    ]

    for pattern, confidence in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_date = match.group(1).strip()
            try:
                iso_date = parse_german_date(raw_date)
                return {
                    "value": iso_date,
                    "raw": raw_date,
                    "confidence": confidence,
                }
            except ValueError:
                continue

    # Niedrige Konfidenz: Erstes plausibles Datum im Dokument nehmen
    all_dates = re.findall(date_regex, text)
    for raw_date in all_dates:
        try:
            iso_date = parse_german_date(raw_date)
            return {
                "value": iso_date,
                "raw": raw_date,
                "confidence": "low",
            }
        except ValueError:
            continue

    return {"value": None, "raw": None, "confidence": None}


def _extract_amount(text: str, amount_type: str = "netto") -> dict:
    """Extrahiert einen Geldbetrag (netto oder brutto) aus dem Text.

    Args:
        text: Der zu durchsuchende Text.
        amount_type: "netto" oder "brutto".

    Returns:
        Dict mit value (float), raw (Original-String) und confidence.
    """
    # Betragsmuster: Zahl mit optionalen Tausenderpunkten und Dezimalkomma
    amount_regex = r"(\-?\d{1,3}(?:\.\d{3})*,\d{2})"
    # Alternatives Muster ohne Tausendertrenner
    amount_regex_simple = r"(\-?\d+,\d{2})"

    if amount_type == "netto":
        label_patterns_high = [
            rf"Nettobetrag[:\s]*{amount_regex}",
            rf"Summe\s*netto[:\s]*{amount_regex}",
            rf"Zwischensumme[:\s]*{amount_regex}",
            rf"Net\s*(?:Amount|Total)[:\s]*{amount_regex}",
            rf"Netto[:\s]*{amount_regex}",
        ]
        label_patterns_medium = [
            rf"Warenwert[:\s]*{amount_regex}",
            rf"Rechnungsbetrag\s*netto[:\s]*{amount_regex}",
            rf"Summe[:\s]*{amount_regex}",
        ]
    else:  # brutto
        label_patterns_high = [
            rf"Bruttobetrag[:\s]*{amount_regex}",
            rf"Gesamtbetrag[:\s]*{amount_regex}",
            rf"Endbetrag[:\s]*{amount_regex}",
            rf"Rechnungsbetrag[:\s]*{amount_regex}",
            rf"Total[:\s]*{amount_regex}",
            rf"Gross\s*(?:Amount|Total)[:\s]*{amount_regex}",
        ]
        label_patterns_medium = [
            rf"Zahlbetrag[:\s]*{amount_regex}",
            rf"Brutto[:\s]*{amount_regex}",
            rf"Gesamt[:\s]*{amount_regex}",
            rf"zu\s*zahlen[:\s]*{amount_regex}",
        ]

    # Hohe Konfidenz
    for pattern in label_patterns_high:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_amount = match.group(1)
            try:
                return {
                    "value": parse_german_amount(raw_amount),
                    "raw": raw_amount,
                    "confidence": "high",
                }
            except ValueError:
                continue

    # Auch mit einfacherem Betragsmuster versuchen (ohne Tausenderpunkt)
    for pattern in label_patterns_high:
        pattern_simple = pattern.replace(amount_regex, amount_regex_simple)
        match = re.search(pattern_simple, text, re.IGNORECASE)
        if match:
            raw_amount = match.group(1)
            try:
                return {
                    "value": parse_german_amount(raw_amount),
                    "raw": raw_amount,
                    "confidence": "high",
                }
            except ValueError:
                continue

    # Mittlere Konfidenz
    for pattern in label_patterns_medium:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_amount = match.group(1)
            try:
                return {
                    "value": parse_german_amount(raw_amount),
                    "raw": raw_amount,
                    "confidence": "medium",
                }
            except ValueError:
                continue

    for pattern in label_patterns_medium:
        pattern_simple = pattern.replace(amount_regex, amount_regex_simple)
        match = re.search(pattern_simple, text, re.IGNORECASE)
        if match:
            raw_amount = match.group(1)
            try:
                return {
                    "value": parse_german_amount(raw_amount),
                    "raw": raw_amount,
                    "confidence": "medium",
                }
            except ValueError:
                continue

    return {"value": None, "raw": None, "confidence": None}


def _extract_company_name(text: str) -> dict:
    """Versucht den Firmennamen/Lieferanten aus dem Kopfbereich zu extrahieren.

    Heuristik: Die ersten Zeilen einer Rechnung enthalten typischerweise
    den Absender (Lieferant). Wir suchen nach typischen Rechtsformen.
    """
    # Nur die ersten ~15 Zeilen betrachten (Kopfbereich)
    lines = text.strip().split("\n")
    header_lines = lines[:15]
    header_text = "\n".join(header_lines)

    # Muster fuer deutsche Firmenbezeichnungen (Rechtsformen)
    company_patterns = [
        # Hohe Konfidenz: Zeile mit bekannter Rechtsform
        (r"^(.+?(?:GmbH\s*&?\s*Co\.?\s*KG|GmbH|AG|SE|e\.K\.|OHG|KG|UG|mbH))\s*$",
         "high"),
        (r"^(.+?(?:GmbH\s*&?\s*Co\.?\s*KG|GmbH|AG|SE|e\.K\.|OHG|KG|UG|mbH))",
         "high"),
    ]

    for pattern, confidence in company_patterns:
        match = re.search(pattern, header_text, re.MULTILINE | re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Mindestens 3 Zeichen und nicht nur Sonderzeichen
            if len(name) >= 3 and re.search(r"[A-Za-z]", name):
                return {
                    "value": name,
                    "confidence": confidence,
                }

    # Mittlere Konfidenz: Erste nicht-leere Zeile als Firmenname nehmen
    for line in header_lines:
        cleaned = line.strip()
        # Mindestlaenge und keine reine Zahl/Datum
        if (len(cleaned) >= 3
                and re.search(r"[A-Za-z]", cleaned)
                and not re.match(r"^\d", cleaned)
                and not re.match(r"^(Rechnung|Seite|Datum|Tel|Fax|E-?Mail)", cleaned,
                                 re.IGNORECASE)):
            return {
                "value": cleaned,
                "confidence": "low",
            }

    return {"value": None, "confidence": None}


def _extract_due_date(text: str) -> dict:
    """Extrahiert das Faelligkeitsdatum / Valuta aus dem Text."""
    date_regex = r"(\d{1,2}\.\d{1,2}\.\d{2,4})"

    patterns = [
        # Hohe Konfidenz
        (rf"Valuta[:\s]+{date_regex}", "high"),
        (rf"F[aä]lligkeitsdatum[:\s]+{date_regex}", "high"),
        (rf"Zahlbar\s*bis[:\s]+{date_regex}", "high"),
        (rf"F[aä]llig\s*(?:am|zum)?[:\s]+{date_regex}", "high"),
        (rf"Due\s*Date[:\s]+{date_regex}", "high"),
        # Mittlere Konfidenz
        (rf"Zahlungsziel[:\s]+.*?{date_regex}", "medium"),
        (rf"Zahlung\s*bis[:\s]+{date_regex}", "medium"),
        (rf"zu\s*zahlen\s*bis[:\s]+{date_regex}", "medium"),
    ]

    for pattern, confidence in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_date = match.group(1).strip()
            try:
                iso_date = parse_german_date(raw_date)
                return {
                    "value": iso_date,
                    "raw": raw_date,
                    "confidence": confidence,
                }
            except ValueError:
                continue

    # Niedrige Konfidenz: Zahlungsziel in Tagen (kein konkretes Datum)
    payment_term_match = re.search(
        r"Zahlungsziel[:\s]+(\d+)\s*Tage", text, re.IGNORECASE
    )
    if payment_term_match:
        return {
            "value": None,
            "raw": f"{payment_term_match.group(1)} Tage",
            "confidence": "low",
            "note": f"Zahlungsziel: {payment_term_match.group(1)} Tage (kein konkretes Datum)",
        }

    return {"value": None, "raw": None, "confidence": None}


# ---------------------------------------------------------------------------
# Spezialisierte Parser fuer bekannte Rechnungsformate
# ---------------------------------------------------------------------------

def _parse_trumpf_invoice(text: str) -> dict:
    """Spezialisierter Parser fuer TRUMPF Financial Services Rechnungen.

    Trumpf-Rechnungen haben ein konsistentes Format:
    - "Rechnung Nr. XXXXXX"
    - "Datum DD.MM.YYYY"
    - "Valuta Datum DD.MM.YYYY"
    - "Summe XX.XXX,XX EUR" (Netto)
    - "Endbetrag XX.XXX,XX EUR" (Brutto)
    - "Material (Lieferant)-RG-Nr.: ..." gefolgt von Lieferanten-RE-Nr
    """
    fields = {}
    date_re = r"(\d{1,2}\.\d{1,2}\.\d{4})"
    amt_re = r"(\d{1,3}(?:\.\d{3})*,\d{2})"

    # RE-Nr Trumpf: "Nr. 663715" oder "Rechnung\nNr. 663715"
    m = re.search(r"Nr\.\s*(\d{5,7})", text)
    if m:
        fields["rechnungsnummer"] = {"value": m.group(1), "confidence": "high"}

    # RE-Datum: "Durchwahl Datum\n... 13.02.2026"
    # pdfplumber extrahiert die Tabellenspalten auf einer Zeile,
    # daher steht das Datum am Ende der Folgezeile (nach anderen Feldern).
    # Wichtig: NICHT "Valuta Datum" matchen!
    m = re.search(r"Durchwahl\s+Datum\s*\n.*?" + date_re, text)
    if m:
        try:
            fields["rechnungsdatum"] = {
                "value": parse_german_date(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass
    # Fallback: Datum gefolgt von Zeilenumbruch und direkt Datum (ohne Valuta)
    if "rechnungsdatum" not in fields:
        m = re.search(r"(?<!Valuta )Datum\s*\n\s*" + date_re, text)
        if m:
            try:
                fields["rechnungsdatum"] = {
                    "value": parse_german_date(m.group(1)),
                    "raw": m.group(1),
                    "confidence": "medium",
                }
            except ValueError:
                pass

    # Valuta: "Valuta Datum\nDD.MM.YYYY"
    m = re.search(r"Valuta\s*Datum\s*\n?" + date_re, text)
    if m:
        try:
            fields["faelligkeitsdatum"] = {
                "value": parse_german_date(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass

    # Netto (Summe): "Summe XX.XXX,XX"
    m = re.search(r"Summe\s+" + amt_re, text)
    if m:
        try:
            fields["netto_betrag"] = {
                "value": parse_german_amount(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass

    # Brutto (Endbetrag): "Endbetrag XX.XXX,XX"
    m = re.search(r"Endbetrag\s+" + amt_re, text)
    if m:
        try:
            fields["brutto_betrag"] = {
                "value": parse_german_amount(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass

    # Lieferanten-RE-Nr: "Material (Lieferant)-RG-Nr.:\nXXXXXXXXXX"
    m = re.search(r"Material\s*\(Lieferant\)-RG-Nr\.?:?\s*(?:" + amt_re + r"\s*.)?\s*\n\s*(\d{5,})", text)
    if m:
        fields["lieferanten_re_nr"] = {
            "value": m.group(2),
            "confidence": "high",
        }

    # Vertragsnummer
    m = re.search(r"Vertrag:?\s*(\d+)", text)
    if m:
        fields["vertrag"] = {"value": m.group(1), "confidence": "high"}

    # Firmenname = immer TRUMPF Financial Services GmbH
    fields["firmenname"] = {
        "value": "TRUMPF Financial Services GmbH",
        "confidence": "high",
    }

    return fields


def _parse_soieta_invoice(text: str) -> dict:
    """Spezialisierter Parser fuer SOIETA TECH s.r.o. Rechnungen.

    Soieta-Rechnungen sind auf Englisch mit:
    - "INVOICE - TAX DOCUMENT No. XXXXXXXXXX"
    - "Invoice date: DD.MM.YYYY"
    - "Due date: DD.MM.YYYY"
    - "TOTAL DUE Currency EUR X,XXX.XX" (englisches Zahlenformat!)
    """
    fields = {}
    date_re = r"(\d{1,2}\.\d{1,2}\.\d{4})"

    # RE-Nr: "INVOICE - TAX DOCUMENT No. 2619100003" oder "No. 2619100003"
    m = re.search(r"(?:INVOICE\s*[-–]\s*TAX\s*DOCUMENT\s*)?No\.?\s*(\d{7,})", text)
    if m:
        fields["rechnungsnummer"] = {"value": m.group(1), "confidence": "high"}

    # RE-Datum: "Invoice date: DD.MM.YYYY"
    m = re.search(r"Invoice\s*date:?\s*" + date_re, text, re.IGNORECASE)
    if m:
        try:
            fields["rechnungsdatum"] = {
                "value": parse_german_date(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass

    # Faelligkeit: "Due date: DD.MM.YYYY"
    m = re.search(r"Due\s*date:?\s*" + date_re, text, re.IGNORECASE)
    if m:
        try:
            fields["faelligkeitsdatum"] = {
                "value": parse_german_date(m.group(1)),
                "raw": m.group(1),
                "confidence": "high",
            }
        except ValueError:
            pass

    # Betrag: "TOTAL DUE Currency EUR X,XXX.XX" (englisches Format!)
    # Englisches Format: Komma = Tausendertrenner, Punkt = Dezimal
    m = re.search(r"TOTAL\s*DUE\s+Currency\s+EUR\s+([\d,]+\.\d{2})", text)
    if m:
        raw = m.group(1)
        # Englisches Format parsen: "7,010.00" -> 7010.00
        val = float(raw.replace(",", ""))
        fields["netto_betrag"] = {"value": val, "raw": raw, "confidence": "high"}
        fields["brutto_betrag"] = {"value": val, "raw": raw, "confidence": "high"}

    # Alternativ: "Total amount X,XXX.XX"
    if "netto_betrag" not in fields:
        m = re.search(r"Total\s*amount\s+([\d,]+\.\d{2})", text)
        if m:
            raw = m.group(1)
            val = float(raw.replace(",", ""))
            fields["netto_betrag"] = {"value": val, "raw": raw, "confidence": "medium"}

    # Lieferant
    fields["firmenname"] = {
        "value": "Soieta Tech s.r.o",
        "confidence": "high",
    }

    return fields


def _parse_generic_supplier_invoice(text: str) -> dict:
    """Parser fuer andere Lieferanten (Lip Technik, CS-Celik, Wit, etc.)."""
    fields = {}
    date_re = r"(\d{1,2}\.\d{1,2}\.\d{4})"
    amt_re = r"(\d{1,3}(?:\.\d{3})*,\d{2})"

    # RE-Nr
    for pattern in [
        r"Rechnungsnummer[:\s]+([A-Za-z0-9\-/]+)",
        r"Rechnung\s*Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)",
        r"RE[\-\s]?Nr\.?\s*[:\s]+([A-Za-z0-9\-/]+)",
        r"Invoice\s*(?:No|Nr)\.?\s*[:\s]+([A-Za-z0-9\-/]+)",
        r"Nr\.?\s*[:\s]+(\d{4,})",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            fields["rechnungsnummer"] = {"value": m.group(1).strip(), "confidence": "high"}
            break

    # Datum
    for pattern, conf in [
        (rf"Rechnungsdatum[:\s]+{date_re}", "high"),
        (rf"Invoice\s*[Dd]ate:?\s*{date_re}", "high"),
        (rf"Datum[:\s]+{date_re}", "medium"),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                fields["rechnungsdatum"] = {
                    "value": parse_german_date(m.group(1)),
                    "raw": m.group(1),
                    "confidence": conf,
                }
                break
            except ValueError:
                continue

    # Brutto
    for pattern in [
        rf"Endbetrag[:\s]*{amt_re}",
        rf"Gesamtbetrag[:\s]*{amt_re}",
        rf"Bruttobetrag[:\s]*{amt_re}",
        rf"Rechnungsbetrag[:\s]*{amt_re}",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                fields["brutto_betrag"] = {
                    "value": parse_german_amount(m.group(1)),
                    "raw": m.group(1),
                    "confidence": "high",
                }
                break
            except ValueError:
                continue

    # Netto
    for pattern in [
        rf"Nettobetrag[:\s]*{amt_re}",
        rf"Summe\s*netto[:\s]*{amt_re}",
        rf"Netto[:\s]*{amt_re}",
        rf"Summe[:\s]*{amt_re}",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                fields["netto_betrag"] = {
                    "value": parse_german_amount(m.group(1)),
                    "raw": m.group(1),
                    "confidence": "medium",
                }
                break
            except ValueError:
                continue

    # Faelligkeit
    for pattern, conf in [
        (rf"F[aä]llig(?:keit)?[:\s]+.*?{date_re}", "high"),
        (rf"Zahlbar\s*bis[:\s]+{date_re}", "high"),
        (rf"Due\s*[Dd]ate:?\s*{date_re}", "high"),
        (rf"Valuta[:\s]+{date_re}", "high"),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                fields["faelligkeitsdatum"] = {
                    "value": parse_german_date(m.group(1)),
                    "raw": m.group(1),
                    "confidence": conf,
                }
                break
            except ValueError:
                continue

    # Firmenname aus Kopf
    lines = text.strip().split("\n")[:15]
    for line in lines:
        cleaned = line.strip()
        if re.search(r"(GmbH|AG|SE|e\.K\.|OHG|KG|UG|s\.r\.o|Ltd|Inc)", cleaned, re.IGNORECASE):
            if not re.search(r"TRUMPF|GRAIL", cleaned, re.IGNORECASE):
                fields["firmenname"] = {"value": cleaned, "confidence": "medium"}
                break

    return fields


def _detect_invoice_type(text: str) -> str:
    """Erkennt den Rechnungstyp anhand von Schluesselwoertern."""
    text_lower = text.lower()
    if "trumpf financial" in text_lower and "endbetrag" in text_lower:
        return "trumpf"
    if "soieta" in text_lower:
        return "soieta"
    return "generic"


# ---------------------------------------------------------------------------
# Hauptfunktion (Main Parser)
# ---------------------------------------------------------------------------

def parse_invoice_pdf(file_bytes: bytes) -> dict:
    """Analysiert eine PDF-Rechnung und extrahiert strukturierte Rechnungsdaten.

    Verarbeitet deutsche Rechnungen und erkennt gaengige Felder wie
    Rechnungsnummer, Datum, Netto-/Bruttobetrag, Lieferant und Faelligkeitsdatum.

    Args:
        file_bytes: Die PDF-Datei als Bytes (z.B. von einem Streamlit file_uploader).

    Returns:
        Ein Dictionary mit folgender Struktur:
        {
            "success": bool,
            "error": str | None,
            "raw_text": str,
            "fields": {
                "rechnungsnummer": {"value": ..., "confidence": ...},
                "rechnungsdatum": {"value": ..., "raw": ..., "confidence": ...},
                "netto_betrag": {"value": ..., "raw": ..., "confidence": ...},
                "brutto_betrag": {"value": ..., "raw": ..., "confidence": ...},
                "lieferant": {"value": ..., "confidence": ...},
                "faelligkeitsdatum": {"value": ..., "raw": ..., "confidence": ...},
            },
            "meta": {
                "pages": int,
                "text_length": int,
                "note": str | None,
            }
        }
    """
    result = {
        "success": False,
        "error": None,
        "raw_text": "",
        "fields": {},
        "meta": {
            "pages": 0,
            "text_length": 0,
            "note": None,
        },
    }

    # --- Schritt 1: Text aus PDF extrahieren ---
    try:
        raw_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        result["error"] = str(e)
        return result

    result["raw_text"] = raw_text

    # Seitenzahl ermitteln
    try:
        pdf_stream = io.BytesIO(file_bytes)
        with pdfplumber.open(pdf_stream) as pdf:
            result["meta"]["pages"] = len(pdf.pages)
    except Exception:
        pass

    result["meta"]["text_length"] = len(raw_text)

    # --- Schritt 2: Pruefen ob Text vorhanden ist ---
    if not raw_text.strip():
        result["error"] = "Kein Text in der PDF gefunden"
        result["meta"]["note"] = (
            "Die PDF enthaelt keinen extrahierbaren Text. "
            "Moeglicherweise handelt es sich um ein gescanntes Dokument. "
            "Bitte verwenden Sie eine PDF mit Text-Layer (OCR)."
        )
        # Leere Felder zurueckgeben
        result["fields"] = {
            "rechnungsnummer": {"value": None, "confidence": None},
            "rechnungsdatum": {"value": None, "raw": None, "confidence": None},
            "netto_betrag": {"value": None, "raw": None, "confidence": None},
            "brutto_betrag": {"value": None, "raw": None, "confidence": None},
            "lieferant": {"value": None, "confidence": None},
            "faelligkeitsdatum": {"value": None, "raw": None, "confidence": None},
        }
        return result

    # --- Schritt 3: Rechnungstyp erkennen und passenden Parser waehlen ---
    invoice_type = _detect_invoice_type(raw_text)
    result["meta"]["invoice_type"] = invoice_type

    if invoice_type == "trumpf":
        specialized_fields = _parse_trumpf_invoice(raw_text)
    elif invoice_type == "soieta":
        specialized_fields = _parse_soieta_invoice(raw_text)
    else:
        specialized_fields = _parse_generic_supplier_invoice(raw_text)

    # Spezialisierte Felder in Standard-Format bringen
    # (firmenname -> lieferant fuer Konsistenz)
    if "firmenname" in specialized_fields:
        specialized_fields["lieferant"] = specialized_fields.pop("firmenname")

    # Standardfelder sicherstellen (leere Werte als Fallback)
    standard_keys = [
        "rechnungsnummer", "rechnungsdatum", "netto_betrag",
        "brutto_betrag", "lieferant", "faelligkeitsdatum",
    ]
    for key in standard_keys:
        if key not in specialized_fields:
            specialized_fields[key] = {"value": None, "confidence": None}

    result["fields"] = specialized_fields
    result["success"] = True

    # Hinweis generieren, wenn wenige Felder erkannt wurden
    extracted_count = sum(
        1 for field in result["fields"].values()
        if field.get("value") is not None
    )

    if extracted_count <= 2:
        result["meta"]["note"] = (
            "Es konnten nur wenige Felder erkannt werden. "
            "Bitte pruefen Sie die extrahierten Daten manuell."
        )

    return result
