"""Tests du chargement / validation / resolution des mappings (Prompt 4)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mapping_loader import (
    MappingRow, MappingConfig, load_all, validate_mapping_config,
    resolve_columns, MappingConfigError, MappingResolutionError,
)
from src.column_identity import ColumnIdentity, parse_from_detection
from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "config" / "pipeline.json"
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"


def _cfg():
    return load_pipeline_config(CONFIG)


def _mc():
    return load_all(_cfg(), PROJECT_ROOT)


# ------------------------- chargement des fichiers ------------------------- #
def test_all_config_files_load():
    mc = _mc()
    assert len(mc.rows) == 40
    assert mc.sites == {"tbr": "1", "safo": "2"}
    assert mc.sex == {"m": "1", "f": "2"}
    assert len(mc.visits) == 16
    assert len(mc.output_columns) == 45
    assert mc.output_columns[0] == "patid"
    assert mc.output_columns[-1] == "lims_pl_samco"


def test_visits_contains_washout_variants():
    mc = _mc()
    assert mc.visits["m3[1]"] == "initiation__mois_3_arm_4"
    assert mc.visits["m18 washou[11]"] == "suivi__mois_18__si_arm_4"
    assert mc.visits["m21 washou[15]"] == "suivi__mois_21__si_arm_4"


# --------------------------- validation config ----------------------------- #
def test_validate_reference_config_ok():
    warnings = validate_mapping_config(_mc())
    assert isinstance(warnings, list)  # pas d'exception -> config valide


def _base_rows():
    return [
        MappingRow("MDFT-SAL0", "COLDA", 1, "lims_sal0_colda", False, "date", True),
        MappingRow("MDFT-SAL0", "COLTI", 1, "lims_sal0_colti", False, "time", True),
    ]


def _mc_from_rows(rows, output=None):
    return MappingConfig(
        rows=rows, sites={"tbr": "1"}, sex={"m": "1"}, visits={"m3[1]": "e"},
        output_columns=output or [r.redcap_variable for r in rows if r.active],
        allowed_data_types=["text", "categorical", "integer", "date", "time", "event"],
        technical_variables=[],
    )


def test_duplicate_redcap_variable_blocks():
    rows = _base_rows() + [MappingRow("MDFT-SAL3", "COLDA", 1, "lims_sal0_colda", False, "date", True)]
    try:
        validate_mapping_config(_mc_from_rows(rows))
        raised = False
    except MappingConfigError:
        raised = True
    assert raised


def test_duplicate_source_identity_blocks():
    rows = _base_rows() + [MappingRow("MDFT-SAL0", "COLDA", 1, "autre_var", False, "date", True)]
    try:
        validate_mapping_config(_mc_from_rows(rows, output=["lims_sal0_colda", "lims_sal0_colti", "autre_var"]))
        raised = False
    except MappingConfigError:
        raised = True
    assert raised


def test_invalid_data_type_blocks():
    rows = [MappingRow("MDFT-SAL0", "COLDA", 1, "lims_sal0_colda", False, "datetime", True)]
    try:
        validate_mapping_config(_mc_from_rows(rows))
        raised = False
    except MappingConfigError:
        raised = True
    assert raised


def test_output_column_not_produced_blocks():
    rows = _base_rows()
    try:
        validate_mapping_config(_mc_from_rows(rows, output=["lims_sal0_colda", "lims_sal0_colti", "patid"]))
        raised = False
    except MappingConfigError:
        raised = True
    assert raised   # patid n'est ni mappe ni declare technique ici


# ----------------------------- resolution ---------------------------------- #
def _ids_synth():
    return [
        ColumnIdentity(1, "MDFT-SAL0", "COLDA", 1),
        ColumnIdentity(2, "MDFT-SAL0", "COLTI", 1),
        ColumnIdentity(3, "MDFT-SAL3", "COLDA", 1),
    ]


def test_resolve_ok():
    res = resolve_columns(_base_rows(), _ids_synth())
    assert res.resolved["lims_sal0_colda"].position == 1
    assert res.resolved["lims_sal0_colti"].position == 2
    assert not res.ambiguous and not res.unresolved


def test_resolve_ambiguous_blocks():
    # regle sans group -> COLDA correspond a 2 colonnes (SAL0 et SAL3)
    rows = [MappingRow("", "COLDA", 1, "lims_colda_any", False, "date", True)]
    try:
        resolve_columns(rows, _ids_synth())
        raised = False
    except MappingResolutionError:
        raised = True
    assert raised


def test_resolve_required_unresolved_blocks():
    rows = [MappingRow("MDFT-SAL0", "INEXISTANT", 1, "obligatoire", True, "text", True)]
    try:
        resolve_columns(rows, _ids_synth())
        raised = False
    except MappingResolutionError:
        raised = True
    assert raised


def test_resolve_optional_unresolved_ok():
    rows = [MappingRow("MDFT-SAL0", "INEXISTANT", 1, "optionnelle", False, "text", True)]
    res = resolve_columns(rows, _ids_synth())
    assert res.unresolved and not res.ambiguous


def test_r2_admin_field_resolves_despite_banner_change():
    """R2 : source_group vide -> le champ admin (nom unique) reste resolu meme
    si le libelle de banniere (groupe) change dans le LIMS."""
    rows = [MappingRow("", "Sexe", 1, "lims_sexe", True, "categorical", True)]
    # groupe (banniere) volontairement different de la reference
    ids = [ColumnIdentity(27, "AUTRE BANNIERE MODIFIEE", "Sexe", 1)]
    res = resolve_columns(rows, ids)
    assert res.resolved["lims_sexe"].position == 27
    assert not res.unresolved and not res.ambiguous


def test_r2_reference_config_admin_groups_blank():
    """Les 9 champs admin a nom unique ont bien un source_group vide ;
    Date/Heure (noms repetes) gardent leur groupe."""
    mc = _mc()
    by_var = {r.redcap_variable: r for r in mc.rows}
    for v in ["lims_laboratoire", "lims_site1", "lims_essaiclin", "lims_essai_clinique",
              "lims_id_participant", "redcap_event_name", "lims_age", "lims_sexe",
              "lims_inspar"]:
        assert by_var[v].source_group == "", v
    # Date/Heure conservent le groupe (desambiguisation necessaire)
    assert by_var["lims_date_reu_en_lab"].source_group != ""
    assert by_var["lims_heure_reu_en_lab"].source_group != ""


# --------------------------- integration reelle ---------------------------- #
def test_integration_resolves_all_against_real_extraction():
    if not SAMPLE.is_file():
        print(f"[SKIP] echantillon absent : {SAMPLE}")
        return
    cfg = _cfg()
    mc = load_all(cfg, PROJECT_ROOT)
    validate_mapping_config(mc)
    grid, real, engine = read_grid(SAMPLE, cfg["sheet_name"],
                                   cfg.get("sheet_name_fallback_contains"))
    det = detect_headers(
        grid, cfg["header_detection"]["anchor_fields"],
        cfg["data_rows"]["identity_column_1based"],
        cfg["header_detection"].get("max_header_scan_rows", 20),
        cfg["header_detection"].get("min_anchor_matches", 2))
    ids = parse_from_detection(grid, det, cfg["column_identity"]["section_start_codes"])
    res = resolve_columns(mc.rows, ids)
    # les 40 regles actives se resolvent chacune a exactement une colonne
    assert res.resolved_count() == 40, (res.resolved_count(), res.unresolved, res.ambiguous)
    assert not res.ambiguous and not res.unresolved
    # verifications ciblees (positions reelles + incoherence conservee)
    assert res.resolved["lims_sal4_samcc"].position == 79
    assert res.resolved["lims_sal4_samcc"].raw_code == "MDFT-SAMCC"
    assert res.resolved["lims_date_reu_en_lab"].position == 45
    assert res.resolved["redcap_event_name"].position == 19
    print(f"[OK] 40 regles resolues (moteur {engine})")


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
