"""Tests du rapport QC (Prompt 9) : contenu des feuilles + round-trip xlsx."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.transformer import Issue, SEVERITY_ERROR, SEVERITY_WARNING
from src.schema_guard import SchemaCheckResult, ReferenceColumn, PASS_WITH_WARNINGS
from src.column_identity import ColumnIdentity
from src.mapping_loader import MappingRow
from src.qc_reporter import QCContext, build_sheets, write_qc_report, ISSUE_HEADER
from src.xlsx_writer import write_workbook
from src.excel_reader import read_grid, list_sheet_names

EXPECTED_SHEETS = ["SUMMARY", "SCHEMA", "ERRORS", "WARNINGS",
                   "UNKNOWN_VISITS", "UNKNOWN_COLUMNS", "DUPLICATES", "MAPPING"]


def _ctx():
    issues = [
        Issue("ERROR_UNKNOWN_VISIT", SEVERITY_ERROR, 42, "H-1-1-9",
              "redcap_event_name", "M99[42]", "Visite inconnue"),
        Issue("WARNING_MULTIPLE_RECORDS_SAME_EVENT", SEVERITY_WARNING, 10, "H-1-1-1",
              "redcap_repeat_instance", "2", "2 lignes pour patid=H-1-1-1 / event=e"),
    ]
    schema = SchemaCheckResult(
        status=PASS_WITH_WARNINGS, sheet_name_expected="S", sheet_name_found="S",
        n_expected=91, n_found=92,
        new_columns=[ColumnIdentity(93, "MDFT-TEMP", "Temp", 1)],
        moved_columns=[(ReferenceColumn(80, "MDFT-PL", "Plasma", 1, False),
                        ColumnIdentity(82, "MDFT-PL", "Plasma", 1))],
    )
    return QCContext(
        input_file="Extrait LIMS 26_08_05.xlsx",
        run_id="26_08_05_120000", run_datetime="2026-08-13 12:00:00",
        status="READY_WITH_WARNINGS",
        n_source_rows=936, n_skipped_rows=43, n_participants=200, n_output_rows=936,
        issues=issues, schema_result=schema,
        resolution={"lims_site1": ColumnIdentity(5, "CODES POUR...", "Sites", 1)},
        mapping_rows=[MappingRow("CODES POUR...", "Sites", 1, "lims_site1",
                                 True, "categorical", True)],
    )


def test_build_all_eight_sheets():
    sheets = build_sheets(_ctx())
    names = [n for n, _ in sheets]
    assert names == EXPECTED_SHEETS


def test_errors_sheet_columns_and_content():
    sheets = dict(build_sheets(_ctx()))
    err = sheets["ERRORS"]
    assert err[0] == ISSUE_HEADER
    assert err[1][0] == "ERROR_UNKNOWN_VISIT"
    assert err[1][2] == 42               # source_row
    assert err[1][3] == "H-1-1-9"        # patid
    assert err[1][5] == "M99[42]"        # source_value


def test_warnings_separated_from_errors():
    sheets = dict(build_sheets(_ctx()))
    assert len(sheets["ERRORS"]) == 2         # header + 1 erreur
    assert len(sheets["WARNINGS"]) == 2       # header + 1 warning
    assert sheets["WARNINGS"][1][0] == "WARNING_MULTIPLE_RECORDS_SAME_EVENT"


def test_summary_has_status_and_counts():
    sheets = dict(build_sheets(_ctx()))
    flat = {r[0]: r[1] for r in sheets["SUMMARY"] if len(r) == 2}
    assert flat["STATUT FINAL"] == "READY_WITH_WARNINGS"
    assert flat["Erreurs"] == 1
    assert flat["Avertissements"] == 1
    assert flat["Lignes output"] == 936


def test_unknown_visits_and_columns_and_duplicates():
    sheets = dict(build_sheets(_ctx()))
    assert sheets["UNKNOWN_VISITS"][1][0] == "M99[42]"
    assert sheets["UNKNOWN_COLUMNS"][1][:2] == ["MDFT-TEMP", "Temp"]
    assert sheets["DUPLICATES"][1][0] == "H-1-1-1"


def test_mapping_sheet_shows_resolution():
    sheets = dict(build_sheets(_ctx()))
    row = sheets["MAPPING"][1]
    assert row[0] == "lims_site1"
    assert row[4] == 5            # position resolue
    assert row[7] == "OUI"       # resolue


def test_xlsx_roundtrip_readable():
    """Le .xlsx produit est relu correctement (valide le writer stdlib)."""
    with tempfile.TemporaryDirectory() as d:
        p = write_qc_report(_ctx(), Path(d) / "QC.xlsx")
        assert p.is_file()
        names = list_sheet_names(p)
        assert names == EXPECTED_SHEETS
        grid, real, engine = read_grid(p, "SUMMARY")
        # la grille SUMMARY contient le statut
        flat = {row[0]: (row[1] if len(row) > 1 else "") for row in grid}
        assert flat.get("STATUT FINAL") == "READY_WITH_WARNINGS"
        grid_err, _, _ = read_grid(p, "ERRORS")
        assert grid_err[0][:7] == ISSUE_HEADER


def test_number_cells_readable():
    with tempfile.TemporaryDirectory() as d:
        p = write_workbook(Path(d) / "n.xlsx", [("T", [["a", "b"], [1, 2]])])
        grid, _, _ = read_grid(p, "T")
        assert grid[1][0] == "1" and grid[1][1] == "2"


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
