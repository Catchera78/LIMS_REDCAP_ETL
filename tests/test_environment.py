"""Tests de la vérification d'environnement (réserve R3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import environment


def test_report_keys():
    r = environment.report()
    for k in ("python", "openpyxl", "pytest",
              "excel_read_engine", "excel_write_engine"):
        assert k in r
    assert isinstance(r["openpyxl"], bool)


def test_advisory_consistent_with_availability():
    if environment.openpyxl_available():
        assert environment.advisory() is None
    else:
        adv = environment.advisory()
        assert adv and "openpyxl" in adv and "pip install" in adv


def test_engines_reflect_openpyxl():
    r = environment.report()
    expected = "openpyxl" if r["openpyxl"] else "stdlib"
    assert r["excel_read_engine"] == expected
    assert r["excel_write_engine"] == expected


def test_format_report_is_readable():
    out = environment.format_report()
    assert "Verification de l'environnement" in out
    assert "openpyxl" in out
    assert "Moteur lecture xlsx" in out


def test_check_flag_returns_code():
    """--check : code 0 si openpyxl present, 1 sinon (verifiable au deploiement)."""
    from run_pipeline import run
    rc = run(["--check"])
    assert rc == (0 if environment.openpyxl_available() else 1)


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn(); passed += 1; print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", e); traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
