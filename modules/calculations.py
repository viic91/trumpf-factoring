"""Berechnungen für Factoring-Zinsen und Kosten."""

from datetime import date, datetime
from typing import Optional


def berechne_offener_betrag(trumpf_brutto: float, bereits_gezahlt: float) -> float:
    """Offener Betrag = Trumpf-Brutto - Bereits gezahlt."""
    return round(trumpf_brutto - bereits_gezahlt, 2)


def berechne_zinsen(trumpf_netto: float, netto_betrag: float) -> float:
    """Zinsen = Trumpf-Netto - Lieferanten-Netto."""
    return round(trumpf_netto - netto_betrag, 2)


def berechne_zinsaufschlag(zinsen: float, netto_betrag: float) -> Optional[float]:
    """Zinsaufschlag = Zinsen / Netto-Betrag (als Dezimalzahl)."""
    if netto_betrag and netto_betrag > 0:
        return round(zinsen / netto_betrag, 6)
    return None


def berechne_tage_finanziert(
    zahlung_an_trumpf, re_datum_trumpf
) -> Optional[int]:
    """Tage finanziert = Zahlung an Trumpf - RE-Datum Trumpf."""
    if zahlung_an_trumpf and re_datum_trumpf:
        zahlung_an_trumpf = _to_date(zahlung_an_trumpf)
        re_datum_trumpf = _to_date(re_datum_trumpf)
        if zahlung_an_trumpf and re_datum_trumpf:
            return (zahlung_an_trumpf - re_datum_trumpf).days
    return None


def _to_date(val):
    """Konvertiert verschiedene Typen zu date."""
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        s = val.strip()[:10]
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


def berechne_eff_jahreszins(
    zinsen: float, netto_betrag: float, tage_finanziert: Optional[int]
) -> Optional[float]:
    """Effektiver Jahreszins = (Zinsen / Netto) * (365 / Tage finanziert)."""
    if netto_betrag and netto_betrag > 0 and tage_finanziert and tage_finanziert > 0:
        return round((zinsen / netto_betrag) * (365 / tage_finanziert), 6)
    return None


def berechne_zinsen_pro_tag(
    zinsen: float, tage_finanziert: Optional[int]
) -> Optional[float]:
    """Zinsen pro Tag = Zinsen / Tage finanziert."""
    if tage_finanziert and tage_finanziert > 0:
        return round(zinsen / tage_finanziert, 4)
    return None


def berechne_zinssatz_30_tage(
    zinsaufschlag: Optional[float], tage_finanziert: Optional[int]
) -> Optional[float]:
    """Zinssatz je 30 Tage = Zinsaufschlag * (30 / Tage finanziert)."""
    if zinsaufschlag is not None and tage_finanziert and tage_finanziert > 0:
        return round(zinsaufschlag * (30 / tage_finanziert), 6)
    return None


def berechne_alle_felder(record: dict) -> dict:
    """Berechnet alle abgeleiteten Felder für einen Datensatz."""
    netto = record.get("netto_betrag") or 0
    trumpf_netto = record.get("trumpf_netto") or 0
    trumpf_brutto = record.get("trumpf_brutto") or 0
    bereits_gezahlt = record.get("bereits_gezahlt") or 0

    zinsen = berechne_zinsen(trumpf_netto, netto)
    zinsaufschlag = berechne_zinsaufschlag(zinsen, netto)
    # Tage finanziert: nur wenn tatsaechlich gezahlt wurde
    tage = berechne_tage_finanziert(
        record.get("zahlung_an_trumpf"), record.get("re_datum_trumpf")
    )

    record["offener_betrag"] = berechne_offener_betrag(trumpf_brutto, bereits_gezahlt)
    record["zinsen"] = zinsen
    record["zinsaufschlag"] = zinsaufschlag
    record["tage_finanziert"] = tage
    record["eff_jahreszins"] = berechne_eff_jahreszins(zinsen, netto, tage)
    record["zinsen_pro_tag"] = berechne_zinsen_pro_tag(zinsen, tage)
    record["zinssatz_30_tage"] = berechne_zinssatz_30_tage(zinsaufschlag, tage)

    return record
