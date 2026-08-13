"""Normalisation des dates et heures (Prompt 6).

Remplace les dizaines de substitutions de mois du do-file Stata par UNE fonction
testee. Accepte :
  - les objets date/datetime/time reels (dates Excel via openpyxl) ;
  - les chaines a mois francais : "02-Mai-2024", "2-Mai-2024" ;
  - les formats numeriques : "02/05/2024", "02-05-2024", "2024-05-02" ;
  - les fractions Excel d'heure : 0.65069... -> 15:37 (lecture directe .xlsx) ;
  - le numero de serie Excel d'une date (repli lecteur stdlib).

Une date/heure impossible leve DateParseError / TimeParseError -> le programme
la signale (ERROR_INVALID_DATE / ERROR_INVALID_TIME) au lieu de produire une
valeur vide silencieuse. La valeur source originale est conservee par l'appelant
pour le rapport QC.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Dict, Optional, Union


class DateParseError(ValueError):
    """Date non interpretable."""


class TimeParseError(ValueError):
    """Heure non interpretable."""


# Mois francais par defaut (cles normalisees : sans accent, minuscules).
DEFAULT_FRENCH_MONTHS: Dict[str, int] = {
    "janv": 1, "janvier": 1, "jan": 1,
    "fevr": 2, "fevrier": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avr": 4, "avril": 4,
    "mai": 5,
    "juin": 6,
    "juil": 7, "juillet": 7,
    "aout": 8,
    "sept": 9, "septembre": 9, "sep": 9,
    "oct": 10, "octobre": 10,
    "nov": 11, "novembre": 11,
    "dec": 12, "decembre": 12,
}

# Epoque Excel (Windows) : le jour 1 = 1900-01-01, avec le bug du 29/02/1900,
# donc l'origine effective est le 1899-12-30.
_EXCEL_EPOCH = datetime(1899, 12, 30)


def _norm_token(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def _norm_month_map(month_map: Optional[Dict[str, int]]) -> Dict[str, int]:
    if not month_map:
        return DEFAULT_FRENCH_MONTHS
    return {_norm_token(k): int(v) for k, v in month_map.items()}


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
_FR_DATE = re.compile(r"^\s*(\d{1,2})[\s./-]+([^\s./-]+)[\s./-]+(\d{4})\s*$")
_NUM_DMY = re.compile(r"^\s*(\d{1,2})[./-](\d{1,2})[./-](\d{4})\s*$")
_NUM_YMD = re.compile(r"^\s*(\d{4})[./-](\d{1,2})[./-](\d{1,2})\s*$")
_SERIAL = re.compile(r"^\s*(\d+)(?:\.0+)?\s*$")


def parse_date(value: Union[str, date, datetime, None],
               month_map: Optional[Dict[str, int]] = None) -> date:
    """Interprete une date ; leve DateParseError si impossible."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        raise DateParseError("date vide")

    s = str(value).strip()
    if s == "":
        raise DateParseError("date vide")

    months = _norm_month_map(month_map)

    def _build(y: int, m: int, d: int) -> date:
        try:
            return date(y, m, d)
        except ValueError as exc:
            raise DateParseError(f"date impossible : {value!r} ({exc})") from exc

    # 1) mois francais : "02-Mai-2024"
    m = _FR_DATE.match(s)
    if m:
        day, mon_tok, year = m.group(1), m.group(2), m.group(3)
        mkey = re.sub(r"[^a-z]", "", _norm_token(mon_tok))
        if mkey in months:
            return _build(int(year), months[mkey], int(day))
        # si le token du milieu est numerique, on tombera dans les branches suivantes
        if not mkey:
            pass
        else:
            raise DateParseError(f"mois inconnu dans {value!r} : {mon_tok!r}")

    # 2) YYYY-MM-DD
    m = _NUM_YMD.match(s)
    if m:
        return _build(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # 3) DD/MM/YYYY ou DD-MM-YYYY (jour en premier, comme la reference)
    m = _NUM_DMY.match(s)
    if m:
        return _build(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    # 4) numero de serie Excel (repli lecteur stdlib), plage plausible
    m = _SERIAL.match(s)
    if m:
        serial = int(m.group(1))
        if 20000 <= serial <= 80000:      # ~1954..2119, evite les faux positifs
            return (_EXCEL_EPOCH + timedelta(days=serial)).date()

    raise DateParseError(f"format de date non reconnu : {value!r}")


def format_date(d: date, fmt: str = "%d/%m/%Y") -> str:
    return d.strftime(fmt)


# --------------------------------------------------------------------------- #
# Heures
# --------------------------------------------------------------------------- #
_HMS = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$")
_FLOAT = re.compile(r"^\s*\d*\.\d+\s*$|^\s*\d+\s*$")


def parse_time(value: Union[str, time, datetime, None]) -> time:
    """Interprete une heure ; leve TimeParseError si impossible."""
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    if value is None:
        raise TimeParseError("heure vide")

    s = str(value).strip()
    if s == "":
        raise TimeParseError("heure vide")

    # 1) HH:MM ou HH:MM:SS
    m = _HMS.match(s)
    if m:
        h = int(m.group(1)); mi = int(m.group(2)); se = int(m.group(3) or 0)
        if h > 23 or mi > 59 or se > 59:
            raise TimeParseError(f"heure impossible : {value!r}")
        return time(h, mi, se)

    # 2) fraction Excel du jour (0 <= f < 1)
    if _FLOAT.match(s):
        f = float(s)
        if 0.0 <= f < 1.0:
            total = min(int(round(f * 86400)), 86399)
            h, rem = divmod(total, 3600)
            mi, se = divmod(rem, 60)
            return time(h, mi, se)

    raise TimeParseError(f"format d'heure non reconnu : {value!r}")


def format_time(t: time, fmt: str = "%H:%M") -> str:
    return t.strftime(fmt)
