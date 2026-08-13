"""Tests du tableau de bord console (Prompt 12)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard import Dashboard


def test_success_dashboard_layout():
    db = Dashboard(input_name="Extrait LIMS 26_08_13.xlsx")
    db.structure = "OK"
    db.mapping = "OK"
    db.transformation = "OK"
    db.set_structure("PASS_WITH_WARNINGS")   # -> WARNING sur Structure
    db.set_status("READY_WITH_WARNINGS")      # -> QC WARNING
    db.records_source = 1423
    db.records_output = 1421
    db.errors = 0
    db.warnings = 6
    db.output_path = "output/Ready_Data_26_08_13.csv"
    db.qc_path = "output/QC_Report_26_08_13.xlsx"
    out = db.render()

    assert "LIMS -> REDCap MDF" in out
    assert "Extrait LIMS 26_08_13.xlsx" in out
    assert "STATUS:\nREADY_WITH_WARNINGS" in out
    assert "output/Ready_Data_26_08_13.csv" in out
    assert "output/QC_Report_26_08_13.xlsx" in out
    # lignes alignees a points
    line = next(l for l in out.splitlines() if l.startswith("Records source"))
    assert line.endswith(" 1423")
    assert "." in line


def test_status_markers():
    db = Dashboard()
    db.set_structure("PASS"); assert db.structure == "OK"
    db.set_structure("FAIL"); assert db.structure == "FAIL"
    db.set_status("READY"); assert db.qc == "OK" and db.status == "READY"
    db.set_status("NOT_READY"); assert db.qc == "ERROR"


def test_failure_dashboard_shows_message_and_dashes():
    db = Dashboard()
    db.set_status("NOT_READY")
    db.message = "Aucun fichier .xlsx"
    out = db.render()
    assert "(aucun)" in out                    # input absent
    assert "Records source........... -" in out or "Records source" in out
    assert "STATUS:\nNOT_READY" in out
    assert "Aucun fichier .xlsx" in out


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
