# TRUMPF Factoring Tool - Gebrauchsanweisung

## Was ist dieses Tool?

Das TRUMPF Factoring Tool hilft dir, deine Factoring-Rechnungen zu verwalten. Wenn du als Firma (GRAIL Automotive) ueber TRUMPF Financial Services Lieferantenrechnungen vorfinanzierst, entsteht ein Kreislauf:

1. **Lieferant** (z.B. Soieta Tech) schickt dir eine Rechnung
2. **TRUMPF Financial Services** bezahlt den Lieferanten und schickt dir eine eigene Rechnung (mit Aufschlag/Zinsen)
3. **Du** bezahlst TRUMPF

Dieses Tool verwaltet alle drei Schritte, berechnet automatisch Zinsen und Kosten, und haelt dein PDF-Archiv aktuell.

---

## Tool starten

1. Oeffne ein Terminal / Eingabeaufforderung
2. Navigiere zum Projektordner:
   ```
   cd "C:\Users\Victor_Grail\Documents\07_KI-Tools\KI-Projekte\Trumpf-Factoring-Tool"
   ```
3. Starte die App:
   ```
   streamlit run app.py
   ```
4. Der Browser oeffnet automatisch `http://localhost:8501`

**Tipp:** Die App laeuft solange das Terminal offen ist. Zum Beenden: `Strg+C` im Terminal.

---

## Die vier Seiten im Ueberblick

### Startseite (app.py)
Die App leitet automatisch zum Dashboard weiter. Es gibt keine separate Startseite - du landest direkt im Dashboard.

---

### Seite 1: Dashboard

**Was du hier siehst:**
- 5 KPI-Kennzahlen oben (Offene Betraege, Offene Rechnungen, Jahreszins, Tage finanziert, Gesamtzinsen)
- Balkendiagramm: Offene Betraege nach Monat, aufgeteilt nach Lieferant
- Kreisdiagramm: Verteilung des Volumens nach Lieferant
- Liniendiagramm: Zinskosten-Entwicklung ueber die Zeit
- Bubble-Chart: Zinsanalyse nach Lieferant (Tage vs. Zinssatz)
- Tabelle: Naechste faellige Zahlungen

**Filter (linke Seitenleiste):**
- Status filtern (Alle, Beauftragt, Fakturiert, etc.)
- Lieferant filtern

---

### Seite 2: Rechnungen Upload

**So laedt man Rechnungen hoch:**

1. Klicke auf "Browse files" oder ziehe PDF-Dateien per Drag & Drop in das Upload-Feld
2. Du kannst **eine oder mehrere PDFs gleichzeitig** hochladen
3. Klicke auf "X Datei(en) analysieren"

**Was dann passiert (automatisch):**
- Jede PDF wird gelesen und der Typ erkannt (Trumpf-Rechnung oder Lieferantenrechnung)
- Rechnungsnummer, Datum, Betraege werden automatisch aus der PDF extrahiert
- Das System sucht automatisch nach einem bestehenden Vorgang (ueber die Lieferanten-Rechnungsnummer)
- Dir wird eine Uebersicht gezeigt:
  - **Gruener Punkt**: Neuer Vorgang wird angelegt
  - **Gelber Punkt**: Bestehender Vorgang wird ergaenzt (z.B. fehlende Felder oder PDF)
  - **Blaue Info**: Duplikat - alle Daten identisch, wird uebersprungen

4. Pruefe die Uebersicht und klicke "X Datei(en) verarbeiten" zum Bestaetigen

**Wie matcht das Tool die Rechnungen?**
- Die **Lieferanten-Rechnungsnummer** (z.B. `202510089` oder `2619100002`) steht auf BEIDEN Dokumenten
- Das Tool nutzt diese Nummer, um Lieferantenrechnung und Trumpf-Rechnung zusammenzufuehren
- Du musst nichts manuell zuordnen!

**PDFs werden gespeichert unter:**
```
Dokumente/{Trumpf-RE-Nr}_{Lieferant-Kurzname}/
  Lieferantenrechnung_{Lieferanten-RE-Nr}.pdf
  Trumpf_{Trumpf-RE-Nr}.pdf
```
Beispiel: `Dokumente/663240_Soieta/Lieferantenrechnung_202510081.pdf`

---

### Seite 3: Datenverwaltung

Die Hauptseite fuer die taegliche Arbeit. Hat 4 Tabs:

#### Tab "Offene Posten"
- Zeigt alle Rechnungen die noch offen sind (Beauftragt, Fakturiert, Offene Teilzahlung)
- Spalten: ID, Lieferant, RE-Nummern, Valuta, Betraege, Bezahlt am, Status, Zinsen, Tage, PDFs
- **PDFs-Spalte**: Zeigt ob beide PDFs (Lieferant + Trumpf) vorhanden sind

#### Tab "Alle"
- Alle Datensaetze auf einen Blick, sortiert nach Status (offen zuerst)
- Alle Finanzkennzahlen sichtbar inkl. "Bezahlt am" (Datum der Vollzahlung)
- PDFs-Spalte zeigt Archiv-Vollstaendigkeit

#### Tab "Abgeschlossen"
- Nur abgeschlossene/archivierte Vorgaenge
- Gesamtvolumen, Gesamtzinsen und "Bezahlt am"-Datum sichtbar
- PDFs-Spalte fuer Archiv-Pruefung

#### Tab "Bearbeiten"
- Datensatz auswaehlen (Dropdown mit ID, Lieferant, RE-Nr., Status)
- Alle Felder manuell editierbar
- Berechnete Kennzahlen werden live angezeigt
- Speichern oder Loeschen (mit Bestaetigung)
- Verlinkte PDFs werden unten angezeigt

**Zahlung zuordnen (Expander oben):**
1. Trumpf RE-Nr. eingeben (z.B. `663715`)
2. Betrag eingeben
3. Zahlungsdatum waehlen
4. "Zuordnen" klicken

**Wichtig zur Zahlungslogik:**
- Bei **Teilzahlung**: Betrag wird hochgezaehlt, Status wird "Offene Teilzahlung", KEIN Zahldatum gesetzt
- Bei **Vollzahlung** (Betrag >= Trumpf Brutto): Status wird "Bezahlt", Zahldatum wird gesetzt
- Erst bei Vollzahlung werden Tage finanziert, Eff. Jahreszins etc. berechnet

**Filter (linke Seitenleiste):**
- Textsuche (RE-Nr., Lieferant)
- Lieferant-Filter

---

### Seite 4: Export

**Filter:**
Du kannst vor dem Export nach Status und Lieferant filtern. Der Filter "Offene Posten" zeigt direkt alle noch offenen Rechnungen (Beauftragt, Fakturiert, Offene Teilzahlung).

**Excel-Report:**
- Klick auf "Excel generieren", dann "Excel herunterladen"
- Enthaelt 4 Sheets:
  - **Dashboard**: KPIs mit Charts
  - **Offene Posten**: Ampel-Formatierung (rot > 20.000, gelb > 10.000, gruen)
  - **Alle Rechnungen**: Vollstaendige Tabelle mit Autofilter
  - **Zinsanalyse**: Zusammenfassung nach Lieferant

**PDF-Report (GRAIL Ist-Report):**
- Klick auf "PDF generieren", dann "PDF herunterladen"
- **Portrait A4**, optimiert fuer Handy-Ansicht
- GRAIL-Branding mit dunklem Design (Neon-Gelb auf Schwarz)
- Alles auf **einer Seite**:
  - Banner: "GRAIL Offene Posten | TRUMPF Factoring"
  - Dominante Anzeige der naechsten Faelligkeit (Datum, Betrag, RE-Nr.)
  - 3 KPI-Karten: "Noch zu zahlen", "Offene Rechnungen", "Trumpf-Brutto"
  - Zwei Tabellen nebeneinander: Monats-Summen + Faelligkeiten
  - Detail-Tabelle: Alle offenen Posten mit Ampel-Faerbung
- Bei sehr vielen offenen Posten automatischer Seitenumbruch

**Auto-Archivierung:**
Jeder generierte Report (Excel + PDF) wird automatisch im Ordner `Archiv/` gespeichert. Pro Tag wird maximal ein Report gespeichert (bei mehreren Exporten am selben Tag wird der vorherige ueberschrieben).
Dateiname-Format: `Trumpf_Factoring_Report_YYYY-MM-DD.xlsx` bzw. `.pdf`

---

## Status-Lebenszyklus einer Rechnung

```
Beauftragt  -->  Fakturiert  -->  Offene Teilzahlung  -->  Bezahlt  -->  Abgeschlossen
    |                |                    |                    |
    |                |                    |                    v
    |                |                    |              (Zahldatum gesetzt,
    |                |                    |               Kennzahlen berechnet)
    |                |                    |
    |                v                    v
    |          (Trumpf-Rechnung     (Teilzahlung
    |           eingetroffen)        erfasst)
    v
(Lieferantenrechnung
 eingegangen)
```

---

## Berechnete Kennzahlen erklaert

| Kennzahl | Formel | Wann berechnet |
|---|---|---|
| **Offener Betrag** | Trumpf Brutto - Bereits gezahlt | Immer |
| **Zinsen** | Trumpf Netto - Lieferant Netto | Wenn beide Netto-Werte vorhanden |
| **Zinsaufschlag** | Zinsen / Lieferant Netto | Wenn Zinsen und Netto vorhanden |
| **Tage finanziert** | Zahldatum - RE-Datum Trumpf | Erst bei Vollzahlung |
| **Eff. Jahreszins** | (Zinsen / Netto) * (365 / Tage) | Erst bei Vollzahlung |
| **Zinsen pro Tag** | Zinsen / Tage finanziert | Erst bei Vollzahlung |
| **Zinssatz je 30 Tage** | Zinsaufschlag * (30 / Tage) | Erst bei Vollzahlung |

---

## Haeufige Fragen

**Warum zeigt eine Rechnung "-" bei Tage/Eff. Zins?**
Weil noch keine Zahlung an Trumpf erfasst wurde. Diese Werte werden erst bei Vollzahlung berechnet.

**Warum steht "Warnung Lief." oder "Warnung Trumpf" in der PDFs-Spalte?**
Es fehlt die entsprechende PDF im Archiv. Lade sie ueber "Rechnungen Upload" hoch.

**Kann ich eine Rechnung nachtraeglich korrigieren?**
Ja, im Tab "Bearbeiten" der Datenverwaltung. Alle Felder sind editierbar.

**Was passiert wenn ich eine PDF doppelt hochlade?**
Das Tool vergleicht alle Felder. Wenn alles identisch ist und die PDF bereits vorhanden ist, wird die Datei uebersprungen. Wenn Felder abweichen oder die PDF fehlt, wird ergaenzt.

**Wo liegen meine Daten?**
- Datenbank: `data/factoring.db` (SQLite)
- PDFs: `Dokumente/{Vorgang}/` (pro Vorgang ein Ordner)
- Reports: `Archiv/` (automatisch archivierte Excel- und PDF-Reports)

**Wie sichere ich meine Daten?**
Kopiere den gesamten Projektordner. Die Datenbank (`data/factoring.db`), der `Dokumente/`-Ordner und der `Archiv/`-Ordner enthalten alle Daten, PDFs und Reports.
