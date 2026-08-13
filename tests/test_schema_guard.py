"""Tests du Schema Guard : PASS / PASS_WITH_WARNINGS / FAIL.

Scenarios exiges (Prompt 3) :
  1. fichier identique          -> PASS
  2. colonne deplacee           -> PASS_WITH_WARNINGS (non bloquant)
  3. colonne supplementaire     -> PASS_WITH_WARNINGS
  4. colonne optionnelle absente-> PASS_WITH_WARNINGS
  5. colonne obligatoire absente-> FAIL
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.column_identity import ColumnIdentity, parse_from_detection
from src.schema_guard import (
    ReferenceColumn, ReferenceSchema, compare, load_reference_schema,
    PASS, PASS_WITH_WARNINGS, FAIL,
)
from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "config" / "pipeline.json"
REF_SCHEMA = PROJECT_ROOT / "config" / "reference_schema.json"
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"


def _mkid(pos, group, field, occ=1):
    return ColumnIdentity(position=pos, group=group, field=field, occurrence=occ,
                          raw_code=field, raw_name=field)


def _reference():
    cols = [
        ReferenceColumn(1, "Num de", "Laboratoire", 1, True),
        ReferenceColumn(2, "DETAILS", "ID de Participant", 1, True),
        ReferenceColumn(3, "DETAILS", "Sexe", 1, True),
        ReferenceColumn(4, "MDFT-SAL0", "COLDA", 1, False),
        ReferenceColumn(5, "MDFT-SAL0", "COLTI", 1, False),
    ]
    return ReferenceSchema(sheet_name="Résultats des Analyse", n_columns=5, columns=cols)


def _identical_current():
    return [
        _mkid(1, "Num de", "Laboratoire"),
        _mkid(2, "DETAILS", "ID de Participant"),
        _mkid(3, "DETAILS", "Sexe"),
        _mkid(4, "MDFT-SAL0", "COLDA"),
        _mkid(5, "MDFT-SAL0", "COLTI"),
    ]


def test_scenario1_identical_pass():
    res = compare(_identical_current(), _reference(), n_columns_found=5)
    assert res.status == PASS, res.as_dict()
    assert not res.missing_required and not res.new_columns and not res.moved_columns


def test_scenario2_moved_column_warning():
    cur = _identical_current()
    # COLDA passe de la position 4 a la position 6 (colonne inseree avant)
    cur[3] = _mkid(6, "MDFT-SAL0", "COLDA")
    res = compare(cur, _reference(), n_columns_found=6)
    assert res.status == PASS_WITH_WARNINGS
    assert not res.is_fail
    moved_keys = [r.key for r, c in res.moved_columns]
    assert "MDFT-SAL0 | COLDA | 1" in moved_keys


def test_scenario3_extra_column_warning():
    cur = _identical_current() + [_mkid(6, "MDFT-SAL0", "SAMCA")]
    res = compare(cur, _reference(), n_columns_found=6)
    assert res.status == PASS_WITH_WARNINGS
    assert "MDFT-SAL0 | SAMCA | 1" in [c.key for c in res.new_columns]


def test_scenario4_optional_removed_warning():
    cur = _identical_current()
    cur = [c for c in cur if c.field != "COLTI"]   # retire une OPTIONNELLE
    res = compare(cur, _reference(), n_columns_found=4)
    assert res.status == PASS_WITH_WARNINGS
    assert "MDFT-SAL0 | COLTI | 1" in [c.key for c in res.missing_optional]
    assert not res.missing_required


def test_scenario5_required_removed_fail():
    cur = _identical_current()
    cur = [c for c in cur if c.field != "Sexe"]    # retire une OBLIGATOIRE
    res = compare(cur, _reference(), n_columns_found=4)
    assert res.status == FAIL
    assert "DETAILS | Sexe | 1" in [c.key for c in res.missing_required]


def test_ambiguous_required_fails():
    """Une identite obligatoire dupliquee dans l'extraction -> FAIL."""
    cur = _identical_current() + [_mkid(6, "DETAILS", "ID de Participant")]
    res = compare(cur, _reference(), n_columns_found=6)
    assert res.status == FAIL
    assert any(a.field == "ID de Participant" for a in res.ambiguous_columns)


def test_moved_is_not_fail_even_with_new_and_optional():
    """Cumul de warnings non bloquants -> PASS_WITH_WARNINGS (jamais FAIL)."""
    cur = _identical_current()
    cur[4] = _mkid(9, "MDFT-SAL0", "COLTI")          # deplacee
    cur.append(_mkid(10, "MDFT-SAL0", "SAMCA"))      # nouvelle
    res = compare(cur, _reference(), n_columns_found=10)
    assert res.status == PASS_WITH_WARNINGS


def test_reference_schema_file_loads():
    if not REF_SCHEMA.is_file():
        print(f"[SKIP] reference absente : {REF_SCHEMA}")
        return
    ref = load_reference_schema(REF_SCHEMA)
    assert ref.n_columns == 100
    assert len(ref.columns) == 91
    assert sum(1 for c in ref.columns if c.required) == 9


def test_integration_current_matches_reference_pass():
    """L'extraction de reference comparee a son propre schema -> PASS."""
    if not (REF_SCHEMA.is_file() and SAMPLE.is_file()):
        print("[SKIP] reference ou echantillon absent")
        return
    cfg = load_pipeline_config(CONFIG)
    ref = load_reference_schema(REF_SCHEMA)
    grid, real, engine = read_grid(SAMPLE, cfg["sheet_name"],
                                   cfg.get("sheet_name_fallback_contains"))
    det = detect_headers(
        grid, cfg["header_detection"]["anchor_fields"],
        cfg["data_rows"]["identity_column_1based"],
        cfg["header_detection"].get("max_header_scan_rows", 20),
        cfg["header_detection"].get("min_anchor_matches", 2))
    ids = parse_from_detection(grid, det, cfg["column_identity"]["section_start_codes"])
    res = compare(ids, ref, sheet_name_found=real, n_columns_found=det.n_columns)
    assert res.status == PASS, res.as_dict()
    print(f"[OK] extraction de reference conforme (statut {res.status})")


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
