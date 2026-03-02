"""PDF Ist-Report: Offene Posten – 1 Seite, Portrait, GRAIL."""

import io
from datetime import datetime
from fpdf import FPDF
import pandas as pd

# --- Farben ---
NEON = (232, 255, 0)
BLACK = (0, 0, 0)
DARK = (26, 26, 26)
DARK2 = (40, 40, 40)
WHITE = (255, 255, 255)
G1 = (246, 247, 248)
G2 = (255, 255, 255)
TXT = (25, 25, 25)
TXT2 = (100, 105, 110)
TXT3 = (155, 158, 162)
RED_BG = (255, 232, 232)
YEL_BG = (255, 250, 230)
RED = (210, 50, 60)
YEL = (230, 175, 0)
GREEN = (40, 160, 65)

MONATE = {
    1: "Januar", 2: "Februar", 3: "Maerz", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

PW = 190  # Portrait A4 nutzbar
LM = 10


def _s(t):
    for o, n in {"\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue", "\u00c4": "Ae",
                 "\u00d6": "Oe", "\u00dc": "Ue", "\u00df": "ss", "\u20ac": "EUR", "\u00d8": "O"}.items():
        t = str(t).replace(o, n)
    return t

def _eur(v):
    if v is None or pd.isna(v): return "-"
    return f"{v:,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", ".")

def _dat(v):
    if v is None or pd.isna(v) or v == "": return "-"
    try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except: return str(v)

def _pd(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "": return None
    try: return datetime.strptime(str(v)[:10], "%Y-%m-%d")
    except: return None


class _R(FPDF):
    def cell(self, w=0, h=None, text="", **kw):
        return super().cell(w, h, _s(text), **kw)

    def header(self):
        pass  # Nur 1 Seite – Header ist manuell

    def footer(self):
        self.set_y(-8)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.15)
        self.line(LM, self.get_y(), LM + PW, self.get_y())
        self.ln(0.5)
        self.set_font("Helvetica", "", 5.5)
        self.set_text_color(*TXT3)
        self.cell(0, 3, "GRAIL Automotive  |  TRUMPF Financial Services  |  Vertraulich")
        self.set_xy(LM, self.get_y())
        self.cell(0, 3, f"Seite {self.page_no()} / {{nb}}", align="R")


# --- Zeichenhelfer ---

def _hdr(pdf, cols, x, y):
    h = 5.5
    tw = sum(c[1] for c in cols)
    pdf.set_fill_color(*DARK)
    pdf.rect(x, y, tw, h, style="F")
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_text_color(*NEON)
    for t, w, a in cols:
        pdf.cell(w, h, t, align=a)
    return y + h


def _row(pdf, cells, cols, x, y, idx=0, fill=None):
    h = 5
    tw = sum(c[1] for c in cols)
    if fill:
        pdf.set_fill_color(*fill)
    elif idx % 2 == 0:
        pdf.set_fill_color(*G1)
    else:
        pdf.set_fill_color(*G2)
    pdf.rect(x, y, tw, h, style="F")
    pdf.set_draw_color(228, 230, 232)
    pdf.line(x, y + h, x + tw, y + h)
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*TXT)
    for val, (_, w, a) in zip(cells, cols):
        pdf.cell(w, h, val, align=a)
    return y + h


def _srow(pdf, cells, cols, x, y):
    h = 5.5
    tw = sum(c[1] for c in cols)
    pdf.set_fill_color(*DARK2)
    pdf.rect(x, y, tw, h, style="F")
    pdf.set_draw_color(*NEON)
    pdf.set_line_width(0.3)
    pdf.line(x, y, x + tw, y)
    pdf.set_line_width(0.2)
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_text_color(*NEON)
    for val, (_, w, a) in zip(cells, cols):
        pdf.cell(w, h, val, align=a)
    return y + h


def _title(pdf, text, y):
    pdf.set_xy(LM, y)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TXT)
    pdf.cell(0, 6, text)
    ny = y + 6.5
    pdf.set_fill_color(*NEON)
    pdf.rect(LM, ny, 25, 0.5, style="F")
    pdf.set_fill_color(218, 220, 218)
    pdf.rect(LM + 25, ny, PW - 25, 0.15, style="F")
    return ny + 2.5


# ================================================================

def generate_pdf_report(df: pd.DataFrame) -> bytes:
    pdf = _R(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=10)

    now = datetime.now()

    # --- Daten ---
    ost = ["Beauftragt", "Fakturiert", "Offene Teilzahlung"]
    op = df[df["status"].isin(ost)].copy()
    nv = len(op[op["status"].isin(["Beauftragt", "Fakturiert"])])
    nt = len(op[op["status"] == "Offene Teilzahlung"])
    s_of = op["offener_betrag"].dropna().sum() if not op.empty else 0
    s_br = op["trumpf_brutto"].dropna().sum() if not op.empty else 0
    s_zi = op["zinsen"].dropna().sum() if not op.empty else 0

    op["_vd"] = op["valuta_trumpf"].apply(_pd)
    ops = op.dropna(subset=["_vd"]).sort_values("_vd")

    # Faelligkeiten gruppiert
    fg = pd.DataFrame()
    if not ops.empty:
        fg = (ops.groupby("_vd").agg(
            b=("offener_betrag", "sum"),
            r=("re_nr_trumpf", lambda x: ", ".join(str(v) for v in x if v and not (isinstance(v, float) and pd.isna(v)))),
        ).sort_index())

    # Monats-Summen
    mg = pd.DataFrame()
    if not ops.empty:
        ops["_mk"] = ops["_vd"].apply(lambda d: d.strftime("%Y-%m"))
        ops["_ml"] = ops["_vd"].apply(lambda d: f"{MONATE[d.month]} {d.year}")
        mg = ops.groupby(["_mk", "_ml"]).agg(s=("offener_betrag", "sum"), n=("id", "count")).sort_index()

    # ================================================================
    # ALLES AUF EINER SEITE
    # ================================================================
    pdf.add_page()

    # --- Banner (kompakt) ---
    bh = 26
    pdf.set_fill_color(*BLACK)
    pdf.rect(0, 0, 210, bh, style="F")
    pdf.set_fill_color(*NEON)
    pdf.rect(0, bh, 210, 0.8, style="F")

    pdf.set_xy(LM, 3)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*NEON)
    pdf.cell(36, 8, "GRAIL")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 8, "Offene Posten  |  TRUMPF Factoring")

    pdf.set_xy(LM, 13)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(145, 150, 145)
    pdf.cell(0, 4,
             f"Stichtag: {now.strftime('%d.%m.%Y')}  |  "
             f"{len(op)} offene Rechnungen  |  "
             f"Noch zu zahlen: {_eur(s_of)}  |  "
             f"TRUMPF Financial Services")

    # --- Uebersicht ---
    y = _title(pdf, "Uebersicht", bh + 4)

    # Naechste Faelligkeit – dominant
    naechste_dt = None
    naechste_betrag = 0
    naechste_re = ""
    if not fg.empty:
        naechste_dt = fg.index[0]
        naechste_betrag = fg.iloc[0]["b"]
        naechste_re = str(fg.iloc[0]["r"])

    pdf.set_fill_color(*DARK)
    pdf.rect(LM, y, PW, 16, style="F")
    pdf.set_fill_color(*NEON)
    pdf.rect(LM, y, 2, 16, style="F")
    pdf.set_xy(LM + 5, y + 1.5)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*NEON)
    pdf.cell(40, 3, "NAECHSTE FAELLIGKEIT")
    if naechste_dt:
        pdf.set_xy(LM + 5, y + 6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*WHITE)
        pdf.cell(30, 6, naechste_dt.strftime("%d.%m.%Y"))
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*NEON)
        pdf.cell(50, 6, _eur(naechste_betrag))
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(160, 165, 160)
        pdf.cell(0, 6, f"RE {naechste_re}")
    else:
        pdf.set_xy(LM + 5, y + 6)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*WHITE)
        pdf.cell(0, 6, "Keine Faelligkeiten")

    y += 20

    # 3 KPI-Karten
    gap = 4
    cw = (PW - 2 * gap) / 3
    ch = 17
    cards = [
        ("Noch zu zahlen", _eur(s_of), "Offene Forderungen abzgl. Teilzahlungen", RED),
        ("Offene Rechnungen", f"{nv} offen + {nt} Teilz.", "", YEL),
        ("Trumpf-Brutto (offen)", _eur(s_br), "Rechnungssumme vor Teilzahlungen", NEON),
    ]
    for i, (lbl, val, sub, acc) in enumerate(cards):
        cx = LM + i * (cw + gap)
        pdf.set_fill_color(244, 245, 246)
        pdf.rect(cx, y, cw, ch, style="F")
        pdf.set_fill_color(*acc)
        pdf.rect(cx, y, 1.5, ch, style="F")
        pdf.set_xy(cx + 4, y + 1)
        pdf.set_font("Helvetica", "", 6)
        pdf.set_text_color(*TXT2)
        pdf.cell(cw - 5, 3, lbl)
        pdf.set_xy(cx + 4, y + 5.5)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*TXT)
        pdf.cell(cw - 5, 5, val)
        if sub:
            pdf.set_xy(cx + 4, y + 12)
            pdf.set_font("Helvetica", "I", 4.5)
            pdf.set_text_color(*TXT3)
            pdf.cell(cw - 5, 3, sub)

    y += ch + 5

    # --- Zwei Tabellen nebeneinander: Monats-Summen + Faelligkeiten ---
    col_gap = 6
    col_w = (PW - col_gap) / 2

    # Titel
    pdf.set_xy(LM, y)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*TXT)
    pdf.cell(col_w, 5, "Offene Summen nach Monaten")
    pdf.set_xy(LM + col_w + col_gap, y)
    pdf.cell(col_w, 5, "Faelligkeiten")
    y += 5.5

    pdf.set_fill_color(*NEON)
    pdf.rect(LM, y, 20, 0.4, style="F")
    pdf.rect(LM + col_w + col_gap, y, 20, 0.4, style="F")
    y += 2

    lx = LM
    rx = LM + col_w + col_gap

    # LINKS: Monats-Summen
    ly = y
    if not mg.empty:
        lc = [("Monat", col_w - 46, "L"), ("Anz.", 16, "C"), ("Betrag", 30, "R")]
        ly = _hdr(pdf, lc, lx, ly)
        for idx, ((k, l), r) in enumerate(mg.iterrows()):
            ly = _row(pdf, [l, str(int(r["n"])), _eur(r["s"])], lc, lx, ly, idx)
        ly = _srow(pdf, ["Gesamt", str(len(ops)), _eur(s_of)], lc, lx, ly)

    # RECHTS: Faelligkeiten
    ry = y
    if not fg.empty:
        rc = [("Datum", 22, "C"), ("Betrag", 30, "R"), ("RE-Nr.", col_w - 52, "L")]
        ry = _hdr(pdf, rc, rx, ry)
        sf = 0
        for idx, (dt, r) in enumerate(fg.iterrows()):
            ry = _row(pdf, [dt.strftime("%d.%m.%Y"), _eur(r["b"]), str(r["r"])[:25]], rc, rx, ry, idx)
            sf += r["b"]
        ry = _srow(pdf, ["Summe", _eur(sf), f"{len(op)} Rechnungen"], rc, rx, ry)

    y = max(ly, ry) + 5

    # --- Detail-Tabelle ---
    y = _title(pdf, "Offene Posten (Detail)", y)

    pdf.set_xy(LM, y)
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*TXT2)
    pdf.cell(0, 3.5,
             f"{len(op)} Rechnungen  |  Offen: {_eur(s_of)}  |  "
             f"Brutto: {_eur(s_br)}  |  Zinsen: {_eur(s_zi)}")
    y += 5

    if not op.empty:
        # Spalten: 190mm gesamt
        dc = [
            ("Lieferant", 36, "L"),
            ("RE Lief.", 22, "C"),
            ("RE Trumpf", 20, "C"),
            ("RE-Datum", 20, "C"),
            ("Valuta", 20, "C"),
            ("Brutto", 26, "R"),
            ("Offen", 26, "R"),
            ("Zinsen", 20, "R"),
        ]
        y = _hdr(pdf, dc, LM, y)

        tb, to, tz = 0, 0, 0
        for idx, (_, r) in enumerate(op.sort_values("_vd").iterrows()):
            ov = r.get("offener_betrag", 0) or 0
            fl = None
            if ov > 20000: fl = RED_BG
            elif ov > 10000: fl = YEL_BG

            # Seitenumbruch falls noetig (bei sehr vielen offenen Posten)
            if y > 275:
                pdf.add_page()
                y = 16
                y = _hdr(pdf, dc, LM, y)

            y = _row(pdf, [
                str(r.get("lieferant", ""))[:18],
                str(r.get("re_nr_lieferant", "")),
                str(r.get("re_nr_trumpf", "")),
                _dat(r.get("re_datum_lieferant")),
                _dat(r.get("valuta_trumpf")),
                _eur(r.get("trumpf_brutto")),
                _eur(ov),
                _eur(r.get("zinsen")),
            ], dc, LM, y, idx, fill=fl)

            br = (r.get("trumpf_brutto") or 0) if not pd.isna(r.get("trumpf_brutto", None)) else 0
            zi = (r.get("zinsen") or 0) if not pd.isna(r.get("zinsen", None)) else 0
            tb += br; to += ov; tz += zi

        y = _srow(pdf, ["SUMME", "", "", "", "", _eur(tb), _eur(to), _eur(tz)], dc, LM, y)

        # Legende
        y += 2
        pdf.set_font("Helvetica", "", 5.5)
        pdf.set_text_color(*TXT3)
        pdf.set_fill_color(*RED_BG)
        pdf.rect(LM, y + 0.3, 3, 2, style="F")
        pdf.set_xy(LM + 4, y)
        pdf.cell(22, 3, "> 20.000 EUR offen")
        pdf.set_fill_color(*YEL_BG)
        pdf.rect(LM + 30, y + 0.3, 3, 2, style="F")
        pdf.set_xy(LM + 34, y)
        pdf.cell(22, 3, "> 10.000 EUR offen")

    else:
        pdf.set_xy(LM, y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 8, "Keine offenen Posten!")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
