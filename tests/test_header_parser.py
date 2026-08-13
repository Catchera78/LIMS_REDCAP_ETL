"""Tests de la detection des lignes d'en-tete (fonction pure, sans Excel)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.header_parser import detect_headers, HeaderDetectionError, HeaderDetectionResult

ANCHORS = ["ID de Participant", "N° de Visite", "Sexe", "Essai Clinique", "Laboratoire"]


def _sample_grid():
    """Grille synthetique reproduisant la structure LIMS (3 en-tetes + legende)."""
    return [
        ["Résultats d'Analyse par Numéro de Lab", "", "", "", "", "", "", "", ""],   # 0 titre
        ["Num de", "", "", "MDFT-X", "DÉTAILS...", "", "", "MDFT-SAL0", "MDFT-COLDA"],  # 1 codes
        ["Laboratoire", "Sites", "EssaiClin", "Essai Clinique", "ID de Participant",
         "N° de Visite", "Sexe", "Saliva H0", "COLDA"],                                # 2 noms
        ["ACC-0002", "TBR", "MDFH", "MDF HC", "PT-0001", "M3[1]", "M",
         "saliva H0", "06-Mai-2024"],                                                  # 3 data
        ["ACC-0003", "SAFO", "MDFH", "MDF HC", "PT-0002", "M6[2]", "F",
         "saliva H0", "07-Mai-2024"],                                                  # 4 data
        ["", "COLDA: Date de collecte", "", "", "", "", "", "", ""],                   # 5 legende
        ["", "SAMCD: Remarque échantillon", "", "", "", "", "", "", ""],               # 6 legende
    ]


def test_detects_name_and_code_rows():
    r = detect_headers(_sample_grid(), ANCHORS)
    assert isinstance(r, HeaderDetectionResult)
    assert r.name_row_index == 2          # ligne des noms
    assert r.code_row_index == 1          # ligne des codes juste au-dessus
    assert r.data_start_index == 3        # donnees juste apres


def test_counts_columns_and_data_rows():
    r = detect_headers(_sample_grid(), ANCHORS)
    assert r.n_columns == 9
    assert r.n_data_rows == 2             # 2 lignes de donnees (legende exclue)
    assert r.n_total_rows == 7


def test_legend_rows_excluded():
    """Les lignes de legende (colonne d'identite vide) ne sont pas comptees."""
    grid = _sample_grid()
    r = detect_headers(grid, ANCHORS, identity_column_1based=1)
    # 2 lignes de donnees + 2 lignes de legende dans la grille apres l'en-tete
    assert r.n_data_rows == 2


def test_all_anchors_matched():
    r = detect_headers(_sample_grid(), ANCHORS)
    assert set(r.matched_anchors) == set(ANCHORS)


def test_position_independent_leading_column():
    """L'insertion d'une colonne AVANT ne casse pas la detection de l'en-tete.

    La ligne des noms reste identifiee par ses champs d'ancrage, pas par une
    position fixe. La colonne d'identite est configurable.
    """
    grid = _sample_grid()
    shifted = [["EXTRA"] + row for row in grid]
    # identite deplacee en colonne 2 (1-based) ; legende garde col d'identite vide
    shifted[5][1] = ""   # ligne legende : identite vide
    shifted[6][1] = ""
    r = detect_headers(shifted, ANCHORS, identity_column_1based=2)
    assert r.name_row_index == 2
    assert r.code_row_index == 1
    assert r.n_data_rows == 2
    assert r.n_columns == 10             # une colonne de plus


def test_raises_when_structure_unexpected():
    """Sans champs d'ancrage suffisants -> erreur explicite (pas de devinette)."""
    grid = [
        ["a", "b", "c"],
        ["x", "y", "z"],
        ["1", "2", "3"],
    ]
    try:
        detect_headers(grid, ANCHORS, min_anchor_matches=2)
        raised = False
    except HeaderDetectionError:
        raised = True
    assert raised, "detect_headers aurait du lever HeaderDetectionError"


def test_empty_grid_raises():
    try:
        detect_headers([], ANCHORS)
        raised = False
    except HeaderDetectionError:
        raised = True
    assert raised


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
