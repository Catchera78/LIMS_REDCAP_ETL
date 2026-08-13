"""Tests de l'export Ready_Data (Prompt 8)."""
import sys
import csv
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.redcap_exporter import (
    validate_output_columns, write_csv, export, output_filename,
    derive_dataset_date, compute_status, ExportError,
    STATUS_READY, STATUS_READY_WITH_WARNINGS, STATUS_NOT_READY,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = PROJECT_ROOT.parent / "Doc sources" / "Ready_Data_26_08_13.csv"

EXPORT_CFG = {
    "delimiter": ";", "encoding": "utf-8-sig", "line_terminator": "\r\n",
    "ready_filename": "Ready_Data_{date}.csv",
    "not_ready_filename": "NOT_READY_Data_{date}.csv",
    "run_date_format": "%y_%m_%d", "dataset_date_pattern": r"(\d{2}_\d{2}_\d{2})",
}
COLS = ["patid", "redcap_event_name", "lims_site1"]


def _recs():
    return [
        {"patid": "H-1-1-1", "redcap_event_name": "e1", "lims_site1": "1"},
        {"patid": "H-1-1-2", "redcap_event_name": "e2", "lims_site1": "2"},
    ]


def test_validate_ok():
    validate_output_columns(_recs(), COLS)      # ne leve pas


def test_validate_extra_column_blocks():
    recs = _recs()
    recs[0]["_internal"] = "x"                    # colonne technique interne
    try:
        validate_output_columns(recs, COLS); raised = False
    except ExportError:
        raised = True
    assert raised


def test_validate_missing_column_blocks():
    recs = _recs()
    del recs[1]["lims_site1"]
    try:
        validate_output_columns(recs, COLS); raised = False
    except ExportError:
        raised = True
    assert raised


def test_write_format_matches_reference_conventions():
    with tempfile.TemporaryDirectory() as d:
        p = write_csv(_recs(), COLS, Path(d) / "out.csv", EXPORT_CFG)
        raw = p.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"                 # BOM UTF-8
        assert b"\r\n" in raw                              # CRLF
        assert raw.count(b'"') == 0                        # pas de guillemets
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(text.splitlines(), delimiter=";"))
        assert rows[0] == COLS                             # en-tete = colonnes, dans l'ordre
        assert rows[1] == ["H-1-1-1", "e1", "1"]


def test_column_order_is_exact():
    reordered = [{"lims_site1": "1", "patid": "P", "redcap_event_name": "e"}]
    with tempfile.TemporaryDirectory() as d:
        p = write_csv(reordered, COLS, Path(d) / "o.csv", EXPORT_CFG)
        header = p.read_text(encoding="utf-8-sig").splitlines()[0]
        assert header == "patid;redcap_event_name;lims_site1"   # ordre config, pas dict


def test_status_and_filename():
    assert compute_status(False, False) == STATUS_READY
    assert compute_status(False, True) == STATUS_READY_WITH_WARNINGS
    assert compute_status(True, False) == STATUS_NOT_READY
    assert compute_status(False, False, schema_failed=True) == STATUS_NOT_READY
    assert output_filename(STATUS_READY, "26_08_05", EXPORT_CFG) == "Ready_Data_26_08_05.csv"
    assert output_filename(STATUS_READY_WITH_WARNINGS, "26_08_05", EXPORT_CFG) == "Ready_Data_26_08_05.csv"
    assert output_filename(STATUS_NOT_READY, "26_08_05", EXPORT_CFG) == "NOT_READY_Data_26_08_05.csv"


def test_not_ready_never_named_ready():
    with tempfile.TemporaryDirectory() as d:
        p = export(_recs(), COLS, Path(d), STATUS_NOT_READY, "26_08_05", EXPORT_CFG)
        assert p.name == "NOT_READY_Data_26_08_05.csv"
        assert "Ready_Data" != p.name


def test_derive_dataset_date():
    assert derive_dataset_date("Extrait LIMS 26_08_05.xlsx", "99_99_99",
                               r"(\d{2}_\d{2}_\d{2})") == "26_08_05"
    assert derive_dataset_date("sans_date.xlsx", "26_08_13",
                               r"(\d{2}_\d{2}_\d{2})") == "26_08_13"


def test_header_matches_reference_file():
    """L'en-tete produit doit correspondre a celui de Ready_Data_26_08_13.csv."""
    if not REFERENCE.is_file():
        print(f"[SKIP] reference absente : {REFERENCE}")
        return
    ref_header = REFERENCE.read_text(encoding="utf-8-sig").splitlines()[0].split(";")
    assert len(ref_header) == 45
    # la liste config doit reproduire exactement cet en-tete
    from src.mapping_loader import load_output_columns
    cols = load_output_columns(PROJECT_ROOT / "config" / "redcap_output_columns.csv")
    assert cols == ref_header, f"\nconfig={cols}\nref   ={ref_header}"


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
