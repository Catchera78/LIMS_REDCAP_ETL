"""Tests de la logique de non-regression (Prompt 10)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent / "regression"))

import compare_with_stata as cmp  # noqa: E402  (dossier tests/regression)

DATE_VARS = {"lims_date_reu_en_lab"}
TIME_VARS = {"lims_heure_reu_en_lab"}
RECODE_VARS = {"lims_site1", "lims_sexe", "redcap_event_name"}


def C(var, a, b):
    return cmp.classify(var, a, b, DATE_VARS, TIME_VARS, RECODE_VARS)


def test_classify_equal_is_none():
    assert C("lims_age", "91", "91") is None


def test_classify_missing_and_extra():
    assert C("lims_age", "91", "") == "MISSING"       # valeur cote Stata seulement
    assert C("lims_age", "", "91") == "EXTRA"          # valeur cote Python seulement


def test_classify_date_same_is_format_else_date():
    assert C("lims_date_reu_en_lab", "2024-05-06", "06/05/2024") == "FORMAT"
    assert C("lims_date_reu_en_lab", "06/05/2024", "07/05/2024") == "DATE"


def test_classify_time():
    assert C("lims_heure_reu_en_lab", "15:03:00", "15:03") == "FORMAT"
    assert C("lims_heure_reu_en_lab", "15:03", "16:03") == "TIME"


def test_classify_mapping():
    assert C("lims_site1", "1", "2") == "MAPPING"


def test_classify_encoding_artifact_is_format():
    # mojibake Stata vs UTF-8 correct Python -> meme contenu -> FORMAT
    assert C("lims_sel_samcd", "Attente Ã©chantillon", "Attente échantillon") == "FORMAT"


def test_classify_value():
    assert C("lims_inspar", "AB", "CD") == "VALUE"


def _cfg():
    from src.config_loader import load_pipeline_config
    return load_pipeline_config(Path(__file__).resolve().parents[1] / "config" / "pipeline.json")


def test_compare_counts_and_keys():
    cols = ["patid", "redcap_event_name", "redcap_repeat_instance", "lims_age"]
    stata = [
        {"patid": "P1", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "10"},
        {"patid": "P2", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "20"},
    ]
    python = [
        {"patid": "P1", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "10"},
        {"patid": "P3", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "30"},
    ]
    r = cmp.compare(cols, stata, cols, python, _cfg())
    assert r.rows_stata == 2 and r.rows_python == 2
    assert len(r.only_stata) == 1     # P2 absent cote python
    assert len(r.only_python) == 1    # P3 absent cote stata
    assert r.cells_compared == 4      # 1 ligne commune x 4 colonnes
    assert r.cells_equal == 4 and r.cells_different == 0


def test_compare_detects_cell_difference():
    cols = ["patid", "redcap_event_name", "redcap_repeat_instance", "lims_age"]
    stata = [{"patid": "P1", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "10"}]
    python = [{"patid": "P1", "redcap_event_name": "E", "redcap_repeat_instance": "1", "lims_age": "11"}]
    r = cmp.compare(cols, stata, cols, python, _cfg())
    assert r.cells_different == 1
    assert r.differences[0][3] == "lims_age"
    assert r.differences[0][4] == "10" and r.differences[0][5] == "11"


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
