"""Tests du lecteur Excel et de l'archivage.

- tests unitaires de find_input_xlsx (0 / 1 / >1 fichier) ;
- test d'archivage (copie, original intact) ;
- test d'integration sur l'extraction LIMS reelle SI elle est presente
  (sinon ignore proprement).
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.excel_reader import (
    find_input_xlsx, read_grid, list_sheet_names, ExcelReadError,
)
from src.header_parser import detect_headers
from src.archiver import archive_original, build_run_dirs, ArchiveError
from src.config_loader import load_pipeline_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "config" / "pipeline.json"
# L'extraction reelle se trouve dans .../LIMS → REDCap ETL v1.0/Doc sources/
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"


def test_normalize_part_absolute_and_relative():
    """Cible de relation workbook : absolue, relative, ou deja prefixee.
    (regression : les vraies extractions LIMS utilisent des cibles ABSOLUES
    '/xl/worksheets/sheet2.xml' qui produisaient un chemin double 'xl/xl/...').
    """
    from src.excel_reader import _normalize_part
    assert _normalize_part("/xl/worksheets/sheet2.xml") == "xl/worksheets/sheet2.xml"
    assert _normalize_part("worksheets/sheet2.xml") == "xl/worksheets/sheet2.xml"
    assert _normalize_part("xl/worksheets/sheet2.xml") == "xl/worksheets/sheet2.xml"


def test_find_input_none_raises():
    with tempfile.TemporaryDirectory() as d:
        try:
            find_input_xlsx(Path(d))
            raised = False
        except ExcelReadError:
            raised = True
        assert raised


def test_find_input_single_ok():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "Extrait LIMS.xlsx"
        f.write_bytes(b"dummy")
        (Path(d) / "~$Extrait LIMS.xlsx").write_bytes(b"lock")  # temp Excel ignore
        got = find_input_xlsx(Path(d))
        assert got == f


def test_find_input_multiple_raises():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "a.xlsx").write_bytes(b"1")
        (Path(d) / "b.xlsx").write_bytes(b"2")
        try:
            find_input_xlsx(Path(d))
            raised = False
        except ExcelReadError:
            raised = True
        assert raised


def test_archive_copies_and_keeps_original():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "orig.xlsx"
        src.write_bytes(b"CONTENU-ORIGINAL")
        before = src.read_bytes()
        dirs = build_run_dirs(Path(d) / "archive", "2026-08-13", ["raw", "logs"])
        dest = archive_original(src, dirs["raw"])
        assert dest.is_file()
        assert dest.read_bytes() == b"CONTENU-ORIGINAL"
        # original inchange
        assert src.read_bytes() == before


def test_archive_refuses_same_location():
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "orig.xlsx"
        src.write_bytes(b"x")
        try:
            archive_original(src, Path(d))  # destination == dossier source
            raised = False
        except ArchiveError:
            raised = True
        assert raised


def test_integration_real_sample_if_present():
    """Lecture reelle de l'onglet LIMS + detection, si le fichier est present."""
    if not SAMPLE.is_file():
        print(f"[SKIP] echantillon absent : {SAMPLE}")
        return
    cfg = load_pipeline_config(CONFIG)

    size_before = SAMPLE.stat().st_size
    mtime_before = SAMPLE.stat().st_mtime

    sheets = list_sheet_names(SAMPLE)
    assert any("resultat" in s.casefold().replace("é", "e") or "sultat" in s.casefold()
               for s in sheets), f"onglet Resultats absent des onglets {sheets}"

    grid, real, engine = read_grid(SAMPLE, cfg["sheet_name"],
                                   cfg.get("sheet_name_fallback_contains"))
    assert "sultat" in real.casefold()
    assert engine in ("openpyxl", "stdlib")

    hd = cfg["header_detection"]
    r = detect_headers(
        grid,
        anchor_fields=hd["anchor_fields"],
        identity_column_1based=cfg["data_rows"]["identity_column_1based"],
        max_scan_rows=hd.get("max_header_scan_rows", 20),
        min_anchor_matches=hd.get("min_anchor_matches", 2),
    )
    # Structure attendue : ~101 colonnes, ~940 lignes de donnees.
    assert r.n_columns >= 100, f"colonnes={r.n_columns}"
    assert r.n_data_rows > 900, f"lignes_donnees={r.n_data_rows}"
    assert r.code_row_index is not None

    # lecture NON destructive : fichier original inchange
    assert SAMPLE.stat().st_size == size_before
    assert SAMPLE.stat().st_mtime == mtime_before
    print(f"[OK] onglet='{real}' moteur={engine} colonnes={r.n_columns} "
          f"lignes_donnees={r.n_data_rows}")


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
