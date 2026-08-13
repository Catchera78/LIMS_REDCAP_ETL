"""Tests de la normalisation des dates et heures (Prompt 6)."""
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.date_parser import (
    parse_date, format_date, parse_time, format_time,
    DateParseError, TimeParseError,
)

# Un exemple par mois francais (couvre les 12 mois du do-file Stata).
MONTHS = [
    ("15-Janv-2024", 1), ("15-Févr-2024", 2), ("15-Mars-2024", 3),
    ("15-Avr-2024", 4), ("15-Mai-2024", 5), ("15-Juin-2024", 6),
    ("15-Juil-2024", 7), ("15-Août-2024", 8), ("15-Sept-2024", 9),
    ("15-Oct-2024", 10), ("15-Nov-2024", 11), ("15-Déc-2024", 12),
]


def test_each_french_month():
    for text, month in MONTHS:
        d = parse_date(text)
        assert d == date(2024, month, 15), f"{text} -> {d} (attendu mois {month})"


def test_required_formats():
    assert parse_date("02-Mai-2024") == date(2024, 5, 2)
    assert parse_date("2-Mai-2024") == date(2024, 5, 2)     # jour non zero-padde
    assert parse_date("02/05/2024") == date(2024, 5, 2)
    assert parse_date("2024-05-02") == date(2024, 5, 2)
    assert parse_date("02-05-2024") == date(2024, 5, 2)


def test_output_format_ddmmyyyy():
    assert format_date(date(2024, 5, 2)) == "02/05/2024"       # reproduit la reference
    assert format_date(parse_date("2-Mai-2024")) == "02/05/2024"


def test_real_excel_date_object():
    assert parse_date(date(2024, 5, 2)) == date(2024, 5, 2)
    assert parse_date(datetime(2024, 5, 2, 9, 30)) == date(2024, 5, 2)


def test_excel_serial_date():
    # 45414 = 2024-05-02 (epoque Excel 1899-12-30)
    assert parse_date("45414") == date(2024, 5, 2)


def test_invalid_date_raises():
    for bad in ["32-Mai-2024", "02-Foo-2024", "2024-13-02", "abc", "31/02/2024", ""]:
        try:
            parse_date(bad)
            raised = False
        except DateParseError:
            raised = True
        assert raised, f"{bad!r} aurait du lever DateParseError"


# ------------------------------- heures ------------------------------------ #
def test_time_strings():
    assert parse_time("11:27") == time(11, 27)
    assert parse_time("11:27:00") == time(11, 27, 0)
    assert parse_time("17:05:58") == time(17, 5, 58)


def test_time_excel_fractions():
    # 0.65069444 -> 15:37 ; 0.43055555 -> 10:20 (valeurs reelles de l'extraction)
    assert format_time(parse_time("0.65069444444444402")) == "15:37"
    assert format_time(parse_time("0.43055555555555602")) == "10:20"
    assert parse_time("0.5") == time(12, 0, 0)


def test_time_real_object():
    assert parse_time(time(15, 3)) == time(15, 3)
    assert parse_time(datetime(2024, 5, 2, 15, 3, 20)) == time(15, 3, 20)


def test_time_output_format_hhmm():
    assert format_time(time(15, 37, 45)) == "15:37"           # HH:MM (reference)


def test_invalid_time_raises():
    for bad in ["25:72", "abc", "24:00:00", "", "12:60"]:
        try:
            parse_time(bad)
            raised = False
        except TimeParseError:
            raised = True
        assert raised, f"{bad!r} aurait du lever TimeParseError"


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
            print("PASS", fn.__name__)
        except Exception as e:
            failed += 1
            print("FAIL", fn.__name__, "->", e)
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
