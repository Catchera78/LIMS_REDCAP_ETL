"""Tests du calcul de redcap_repeat_instance (Prompt 7)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repeat_instance import assign_repeat_instances

CFG = {
    "field": "redcap_repeat_instance",
    "group_by": ["patid", "redcap_event_name"],
    "sort_by": "lims_date_reu_en_lab",
    "multiple_warning": {"severity": "WARNING",
                         "error_code": "WARNING_MULTIPLE_RECORDS_SAME_EVENT"},
}


def _rec(patid, event, date):
    return {"patid": patid, "redcap_event_name": event, "lims_date_reu_en_lab": date}


def test_prompt_example():
    """PT-0001 / suivi__mois_15__si_arm_4 : 07/05/2025 -> 1 ; 20/05/2025 -> 2."""
    recs = [
        _rec("PT-0001", "suivi__mois_15__si_arm_4", "07/05/2025"),
        _rec("PT-0001", "suivi__mois_15__si_arm_4", "20/05/2025"),
    ]
    issues = assign_repeat_instances(recs, [10, 11], CFG)
    assert recs[0]["redcap_repeat_instance"] == "1"
    assert recs[1]["redcap_repeat_instance"] == "2"
    # repetition -> un avertissement
    assert len(issues) == 1
    assert issues[0].error_code == "WARNING_MULTIPLE_RECORDS_SAME_EVENT"


def test_input_order_reversed_still_chronological():
    """Meme si les lignes arrivent dans le desordre, le tri est chronologique."""
    recs = [
        _rec("P1", "E", "20/05/2025"),
        _rec("P1", "E", "07/05/2025"),
    ]
    assign_repeat_instances(recs, [10, 11], CFG)
    assert recs[0]["redcap_repeat_instance"] == "2"   # 20/05 -> 2
    assert recs[1]["redcap_repeat_instance"] == "1"   # 07/05 -> 1


def test_chronological_not_lexicographic():
    """Tri par date REELLE, pas par la chaine DD/MM/YYYY."""
    recs = [
        _rec("P1", "E", "07/12/2024"),   # decembre 2024
        _rec("P1", "E", "07/05/2025"),   # mai 2025 (plus tard)
    ]
    assign_repeat_instances(recs, [10, 11], CFG)
    # lexicographiquement "07/05/2025" < "07/12/2024", mais chronologiquement l'inverse
    assert recs[0]["redcap_repeat_instance"] == "1"   # dec 2024 en premier
    assert recs[1]["redcap_repeat_instance"] == "2"   # mai 2025 ensuite


def test_singleton_no_warning():
    recs = [_rec("P1", "E", "01/01/2025")]
    issues = assign_repeat_instances(recs, [10], CFG)
    assert recs[0]["redcap_repeat_instance"] == "1"
    assert issues == []


def test_independent_groups():
    recs = [
        _rec("P1", "E1", "01/01/2025"),
        _rec("P1", "E2", "01/01/2025"),
        _rec("P2", "E1", "01/01/2025"),
    ]
    issues = assign_repeat_instances(recs, [10, 11, 12], CFG)
    assert all(r["redcap_repeat_instance"] == "1" for r in recs)  # groupes distincts
    assert issues == []


def test_missing_date_sorts_last():
    """Une date manquante recoit l'instance la plus haute (comme Stata)."""
    recs = [
        _rec("P1", "E", ""),             # manquante
        _rec("P1", "E", "07/05/2025"),
        _rec("P1", "E", "20/05/2025"),
    ]
    assign_repeat_instances(recs, [10, 11, 12], CFG)
    assert recs[1]["redcap_repeat_instance"] == "1"   # 07/05
    assert recs[2]["redcap_repeat_instance"] == "2"   # 20/05
    assert recs[0]["redcap_repeat_instance"] == "3"   # manquante en dernier


def test_ties_broken_by_input_order():
    """Meme date -> ordre d'apparition (deterministe)."""
    recs = [
        _rec("P1", "E", "07/05/2025"),
        _rec("P1", "E", "07/05/2025"),
    ]
    assign_repeat_instances(recs, [10, 11], CFG)
    assert recs[0]["redcap_repeat_instance"] == "1"
    assert recs[1]["redcap_repeat_instance"] == "2"


def test_all_instances_are_permutation_within_group():
    """Propriete generale : instances = permutation de 1..n par groupe."""
    recs = [
        _rec("P1", "E", "03/01/2025"),
        _rec("P1", "E", "01/01/2025"),
        _rec("P1", "E", "02/01/2025"),
    ]
    assign_repeat_instances(recs, [10, 11, 12], CFG)
    vals = sorted(int(r["redcap_repeat_instance"]) for r in recs)
    assert vals == [1, 2, 3]


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
