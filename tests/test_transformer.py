"""Tests des transformations metier (Prompt 5)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.column_identity import ColumnIdentity, parse_from_detection, find_column_by_field
from src.mapping_loader import MappingConfig, MappingRow, load_all, resolve_columns
from src.transformer import Transformer, extract_data_rows, DataRow, SEVERITY_ERROR
from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "config" / "pipeline.json"
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"

TRANSFORM_CFG = {
    "patid_variable": "lims_id_participant",
    "constants": {
        "lims_tab_id": "LIMS",
        "redcap_data_access_group": "",
        "redcap_repeat_instrument": "labo_prlvements_biologiques_sousetude_mdf_lims",
    },
    "value_recodes": {
        "lims_site1": {"map": "sites", "severity": "ERROR", "error_code": "ERROR_UNKNOWN_SITE"},
        "lims_sexe": {"map": "sex", "severity": "WARNING", "error_code": "WARNING_UNKNOWN_SEX"},
    },
    "event_recodes": {
        "redcap_event_name": {"map": "visits", "severity": "ERROR", "error_code": "ERROR_UNKNOWN_VISIT"},
    },
    "deferred_variables": ["redcap_repeat_instance"],
}

OUTPUT_COLS = [
    "patid", "redcap_repeat_instrument", "redcap_event_name", "redcap_repeat_instance",
    "redcap_data_access_group", "lims_tab_id", "lims_site1", "lims_id_participant",
    "lims_sexe", "lims_date_reu_en_lab",
]


def _mc():
    return MappingConfig(
        rows=[], sites={"tbr": "1", "safo": "2"}, sex={"m": "1", "f": "2"},
        visits={"m3[1]": "initiation__mois_3_arm_4", "m6[2]": "suivi__mois_6__sit_arm_4"},
        output_columns=OUTPUT_COLS,
        allowed_data_types=[], technical_variables=[],
    )


def _resolution():
    # colonnes fictives : site=1, id=2, sexe=3, visite=4, date=5
    return {
        "lims_site1": ColumnIdentity(1, "CODES POUR...", "Sites", 1),
        "lims_id_participant": ColumnIdentity(2, "DETAILS", "ID de Participant", 1),
        "lims_sexe": ColumnIdentity(3, "DETAILS", "Sexe", 1),
        "redcap_event_name": ColumnIdentity(4, "DETAILS", "N° de Visite", 1),
        "lims_date_reu_en_lab": ColumnIdentity(5, "Reçu en Lab", "Date", 1),
    }


def _rows(cells_list):
    return [DataRow(sheet_row=10 + n, cells=c) for n, c in enumerate(cells_list)]


def test_constants_patid_and_recodes():
    rows = _rows([
        ["TBR", "PT-0001", "M", "M3[1]", "06-Mai-2024"],
        ["SAFO", "PT-0003", "F", "M6[2]", "07-Mai-2024"],
    ])
    tr = Transformer(_mc(), TRANSFORM_CFG).transform(rows, _resolution())
    r0, r1 = tr.records
    assert r0["patid"] == "PT-0001"
    assert r0["lims_tab_id"] == "LIMS"
    assert r0["redcap_data_access_group"] == ""
    assert r0["redcap_repeat_instrument"] == "labo_prlvements_biologiques_sousetude_mdf_lims"
    assert r0["redcap_repeat_instance"] == ""            # differe (Prompt 7)
    assert r0["lims_site1"] == "1" and r1["lims_site1"] == "2"
    assert r0["lims_sexe"] == "1" and r1["lims_sexe"] == "2"
    assert r0["redcap_event_name"] == "initiation__mois_3_arm_4"
    assert r1["redcap_event_name"] == "suivi__mois_6__sit_arm_4"
    assert r0["lims_date_reu_en_lab"] == "06-Mai-2024"   # copie brute (Prompt 6)
    assert not tr.issues


def test_unknown_visit_generates_error_code():
    rows = _rows([["TBR", "PT-0001", "M", "M99[42]", "06-Mai-2024"]])
    tr = Transformer(_mc(), TRANSFORM_CFG).transform(rows, _resolution())
    rec = tr.records[0]
    # jamais un event vide silencieux : le code d'erreur est visible dans la cellule
    assert rec["redcap_event_name"] == "ERROR_UNKNOWN_VISIT"
    errs = tr.errors()
    assert len(errs) == 1
    assert errs[0].error_code == "ERROR_UNKNOWN_VISIT"
    assert errs[0].source_value == "M99[42]"
    assert errs[0].patid == "PT-0001"


def test_empty_visit_also_flagged():
    rows = _rows([["TBR", "PT-0001", "M", "", "06-Mai-2024"]])
    tr = Transformer(_mc(), TRANSFORM_CFG).transform(rows, _resolution())
    assert tr.records[0]["redcap_event_name"] == "ERROR_UNKNOWN_VISIT"
    assert len(tr.errors()) == 1


def test_empty_site_and_sex_stay_empty_without_error():
    """Comme Stata : une valeur source vide reste vide, sans erreur."""
    rows = _rows([["", "PT-0001", "", "M3[1]", "06-Mai-2024"]])
    tr = Transformer(_mc(), TRANSFORM_CFG).transform(rows, _resolution())
    assert tr.records[0]["lims_site1"] == ""
    assert tr.records[0]["lims_sexe"] == ""
    assert not tr.issues                     # aucun signalement pour du manquant


def test_unknown_site_is_error_unknown_sex_is_warning():
    rows = _rows([["GARIN", "PT-0001", "X", "M3[1]", "06-Mai-2024"]])
    tr = Transformer(_mc(), TRANSFORM_CFG).transform(rows, _resolution())
    assert tr.records[0]["lims_site1"] == ""      # valeur de sortie vide
    assert tr.records[0]["lims_sexe"] == ""
    codes = {(i.error_code, i.severity) for i in tr.issues}
    assert ("ERROR_UNKNOWN_SITE", "ERROR") in codes
    assert ("WARNING_UNKNOWN_SEX", "WARNING") in codes


def _mc_typed():
    """MappingConfig avec data_type pour tester le parsing date/heure."""
    rows = [
        MappingRow("Reçu en Lab", "Date", 1, "lims_date_reu_en_lab", True, "date", True),
        MappingRow("Reçu en Lab", "Heure", 1, "lims_heure_reu_en_lab", False, "time", True),
    ]
    return MappingConfig(
        rows=rows, sites={}, sex={}, visits={},
        output_columns=["patid", "lims_id_participant",
                        "lims_date_reu_en_lab", "lims_heure_reu_en_lab"],
        allowed_data_types=[], technical_variables=[],
    )


def _res_typed():
    return {
        "lims_id_participant": ColumnIdentity(1, "DETAILS", "ID de Participant", 1),
        "lims_date_reu_en_lab": ColumnIdentity(2, "Reçu en Lab", "Date", 1),
        "lims_heure_reu_en_lab": ColumnIdentity(3, "Reçu en Lab", "Heure", 1),
    }


def test_date_and_time_columns_parsed():
    rows = _rows([["H-1-1-1", "02-Mai-2024", "0.65069444444444402"]])
    tr = Transformer(_mc_typed(), TRANSFORM_CFG).transform(rows, _res_typed())
    rec = tr.records[0]
    assert rec["lims_date_reu_en_lab"] == "02/05/2024"    # DD/MM/YYYY
    assert rec["lims_heure_reu_en_lab"] == "15:37"        # fraction Excel -> HH:MM
    assert not tr.issues


def test_invalid_date_produces_error_invalid_date():
    rows = _rows([["H-1-1-1", "32-Mai-2024", "10:00"]])
    tr = Transformer(_mc_typed(), TRANSFORM_CFG).transform(rows, _res_typed())
    rec = tr.records[0]
    assert rec["lims_date_reu_en_lab"] == ""             # vide, mais PAS silencieux
    errs = [i for i in tr.issues if i.error_code == "ERROR_INVALID_DATE"]
    assert len(errs) == 1
    assert errs[0].severity == SEVERITY_ERROR
    assert errs[0].source_value == "32-Mai-2024"          # valeur originale conservee


def test_extract_data_rows_uses_identity_column():
    grid = [
        ["h1", "h2", "h3"],                       # 0 en-tete
        ["c1", "c2", "c3"],                       # 1 en-tete
        ["NMA1", "H-1-1-1", "x"],                 # 2 data (id rempli)
        ["Legende", "", "y"],                     # 3 legende (id vide) -> exclue
        ["NMA2", "H-1-1-2", "z"],                 # 4 data
    ]
    # colonne d'identite = participant = colonne 2 (1-based)
    rows = extract_data_rows(grid, data_start_index=2, identity_column_1based=2)
    assert [r.sheet_row for r in rows] == [3, 5]  # lignes 3 et 5 (1-based)


# --------------------------- integration reelle ---------------------------- #
def test_integration_real_extraction_clean():
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
        cfg["header_detection"].get("min_anchor_matches", 2))
    ids = parse_from_detection(grid, det, cfg["column_identity"]["section_start_codes"])
    mc = load_all(cfg, PROJECT_ROOT)
    res = resolve_columns(mc.rows, ids)
    pid = find_column_by_field(ids, cfg["data_rows"]["identity_field"])
    data_rows = extract_data_rows(grid, det.data_start_index, pid.position)
    tr = Transformer(mc, cfg["transform"]).transform(data_rows, res.resolved)

    # les 4 fausses lignes de legende (identifiees par col1) sont exclues
    assert len(data_rows) == 936
    assert len(tr.records) == 936
    # extraction 26_08_05 propre : aucune erreur bloquante
    assert len(tr.errors()) == 0, [e.as_dict() for e in tr.errors()[:3]]
    # Le 1er enregistrement (que le do-file Stata supprime) est BIEN present,
    # avec un participant renseigne et des transformations correctes.
    first = tr.records[0]
    assert first["patid"] != ""                # participant present (record recupere)
    assert first["patid"] == first["lims_id_participant"]
    assert first["lims_site1"] in ("1", "2")   # site recode
    assert first["lims_sexe"] in ("1", "2")    # sexe recode
    assert first["redcap_event_name"].startswith(("initiation__", "suivi__"))
    assert first["lims_tab_id"] == "LIMS"
    print(f"[OK] 936 enregistrements, 0 erreur (moteur {engine})")


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
