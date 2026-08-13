"""Tests de l'identite metier des colonnes (section + champ + occurrence).

Point cle (exigence Prompt 2) : inserer une colonne AVANT une variable ne doit
pas changer son identification. Les noms simples repetes (COLDA, COLTI, Date...)
ne sont jamais des identifiants seuls.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.column_identity import (
    parse_column_identities, find_column, duplicate_field_keys, ColumnIdentityError,
)
from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers
from src.column_identity import parse_from_detection

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "config" / "pipeline.json"
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"

SECTIONS = ["MDFT-SAL0", "MDFT-SAL3", "MDFT-PL", "MDFT-SAMP"]


def _grid():
    """Grille synthetique : zone admin (bannieres) + 3 sections MDFT."""
    code = ["Reçu en Lab", "",
            "MDFT-SAL0", "MDFT-COLDA", "MDFT-COLTI",
            "MDFT-SAL3", "MDFT-COLDA", "MDFT-COLTI",
            "MDFT-PL", "MDFT-COLDA"]
    name = ["Date", "Heure",
            "Saliva H0", "COLDA", "COLTI",
            "Saliva H3", "COLDA", "COLTI",
            "Plasma", "COLDA"]
    return [code, name], 0, 1, len(code)


def _ids():
    grid, ci, ni, n = _grid()
    return parse_column_identities(grid, ci, ni, n, SECTIONS)


def test_spec_conceptual_keys():
    """MDFT-SAL0|COLDA|1, MDFT-SAL3|COLDA|1, MDFT-PL|COLDA|1 (exemple de la spec)."""
    ids = _ids()
    assert find_column(ids, "MDFT-SAL0", "COLDA", 1).position == 4
    assert find_column(ids, "MDFT-SAL3", "COLDA", 1).position == 7
    assert find_column(ids, "MDFT-PL", "COLDA", 1).position == 10
    # toutes en occurrence 1
    for g in ("MDFT-SAL0", "MDFT-SAL3", "MDFT-PL"):
        assert find_column(ids, g, "COLDA", 1).occurrence == 1


def test_repeated_names_never_collide():
    """Les colonnes 'COLDA' repetees ont des cles DISTINCTES."""
    ids = _ids()
    colda_keys = [i.key for i in ids if i.field.upper() == "COLDA"]
    assert len(colda_keys) == 3
    assert len(set(colda_keys)) == 3          # aucune collision


def test_section_start_column_identity():
    """La colonne de tete de section porte le nom d'echantillon."""
    ids = _ids()
    head = find_column(ids, "MDFT-SAL0", "Saliva H0", 1)
    assert head.position == 3
    assert head.raw_code == "MDFT-SAL0"


def test_admin_banner_disambiguates_date():
    """'Date' sous deux bannieres differentes -> deux identites distinctes."""
    code = ["Capture", "", "Reçu en Lab", ""]
    name = ["Date", "Heure", "Date", "Heure"]
    ids = parse_column_identities([code, name], 0, 1, 4, SECTIONS)
    assert find_column(ids, "Capture", "Date", 1).position == 1
    assert find_column(ids, "Reçu en Lab", "Date", 1).position == 3
    assert find_column(ids, "Capture", "Date", 1).key != \
           find_column(ids, "Reçu en Lab", "Date", 1).key


def test_insertion_before_does_not_change_identity():
    """EXIGENCE : inserer une colonne AVANT ne change pas l'identite des autres."""
    ids_before = _ids()
    key_sal0 = find_column(ids_before, "MDFT-SAL0", "COLDA", 1)
    key_pl = find_column(ids_before, "MDFT-PL", "COLDA", 1)
    pos_sal0_before = key_sal0.position

    # on prepend une colonne administrative quelconque
    grid, ci, ni, n = _grid()
    grid2 = [["ZZZ-CODE"] + grid[0], ["Colonne ajoutee"] + grid[1]]
    ids_after = parse_column_identities(grid2, ci, ni, n + 1, SECTIONS)

    a_sal0 = find_column(ids_after, "MDFT-SAL0", "COLDA", 1)
    a_pl = find_column(ids_after, "MDFT-PL", "COLDA", 1)

    # identite (group, field, occurrence) inchangee...
    assert a_sal0.norm_key == key_sal0.norm_key
    assert a_pl.norm_key == key_pl.norm_key
    # ...meme si la POSITION a bouge de +1
    assert a_sal0.position == pos_sal0_before + 1


def test_insertion_inside_absorbed_but_target_stable():
    """Une colonne inseree avant PL (non-section) est absorbee par la section
    courante, sans affecter l'identite de MDFT-PL|COLDA|1."""
    grid, ci, ni, n = _grid()
    # insere un champ 'Temp' juste avant le bloc PL (index 8)
    code = grid[0][:8] + ["MDFT-TEMP"] + grid[0][8:]
    name = grid[1][:8] + ["Temp"] + grid[1][8:]
    ids = parse_column_identities([code, name], ci, ni, n + 1, SECTIONS)
    pl = find_column(ids, "MDFT-PL", "COLDA", 1)
    assert pl.occurrence == 1
    # la colonne inseree est rattachee a la section precedente (MDFT-SAL3)
    temp = find_column(ids, "MDFT-SAL3", "Temp", 1)
    assert temp.raw_code == "MDFT-TEMP"


def test_occurrence_increments_for_true_duplicate():
    """Deux champs identiques dans la MEME section -> occurrences 1 puis 2."""
    code = ["MDFT-SAL0", "MDFT-COLDA", "MDFT-COLDA"]
    name = ["Saliva H0", "COLDA", "COLDA"]
    ids = parse_column_identities([code, name], 0, 1, 3, SECTIONS)
    assert find_column(ids, "MDFT-SAL0", "COLDA", 1).position == 2
    assert find_column(ids, "MDFT-SAL0", "COLDA", 2).position == 3
    assert "mdft-sal0|colda" in duplicate_field_keys(ids)


def test_find_column_not_found_raises():
    ids = _ids()
    try:
        find_column(ids, "MDFT-SAL0", "INEXISTANT", 1)
        raised = False
    except ColumnIdentityError:
        raised = True
    assert raised


def test_case_and_accent_tolerant():
    ids = _ids()
    # accents/casse differents -> meme colonne trouvee
    assert find_column(ids, "mdft-sal0", "colda", 1).position == 4
    assert find_column(ids, "reçu en lab", "date", 1).position == 1


def test_integration_real_sample_if_present():
    if not SAMPLE.is_file():
        print(f"[SKIP] echantillon absent : {SAMPLE}")
        return
    cfg = load_pipeline_config(CONFIG)
    grid, real, engine = read_grid(SAMPLE, cfg["sheet_name"],
                                   cfg.get("sheet_name_fallback_contains"))
    det = detect_headers(
        grid, cfg["header_detection"]["anchor_fields"],
        cfg["data_rows"]["identity_column_1based"],
        cfg["header_detection"].get("max_header_scan_rows", 20),
        cfg["header_detection"].get("min_anchor_matches", 2),
    )
    ids = parse_from_detection(grid, det, cfg["column_identity"]["section_start_codes"])

    # positions reelles verifiees dans l'extraction 26_08_05
    assert find_column(ids, "MDFT-SAL0", "COLDA", 1).position == 65
    assert find_column(ids, "MDFT-SAL3", "COLDA", 1).position == 71
    assert find_column(ids, "MDFT-SAL4", "COLDA", 1).position == 76
    assert find_column(ids, "MDFT-PL", "COLDA", 1).position == 87
    assert find_column(ids, "Reçu en Lab", "Date", 1).position == 45

    # les 5 colonnes COLDA reelles ont 5 identites distinctes
    colda = [i for i in ids if i.raw_name.upper() == "COLDA"]
    assert len(colda) == 5
    assert len({i.key for i in colda}) == 5

    # incoherence connue conservee pour le QC (position 79)
    pos79 = next(i for i in ids if i.position == 79)
    assert pos79.raw_code == "MDFT-SAMCC"
    assert pos79.raw_name == "SAMCO"
    print(f"[OK] identites reelles verifiees (moteur {engine})")


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
