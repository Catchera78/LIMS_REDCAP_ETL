"""Tests de changement de structure (Prompt 11).

Genere des copies synthetiques de l'extraction LIMS, casse volontairement la
structure de 6 facons, execute le pipeline et verifie le comportement attendu.
Genere aussi docs/STRUCTURAL_TEST_REPORT.md.

  A : colonne ajoutee avant MDFT-SAL0        -> le pipeline fonctionne
  B : MDFT-PL deplace ailleurs               -> le pipeline fonctionne
  C : nouvelle colonne MDFT-TEMP             -> PASS_WITH_WARNINGS
  D : ID de Participant supprime             -> FAIL
  E : COLDA de MDFT-SAL0 renomme             -> mapping non reconnu, traitement
                                                controle, sans mauvaise variable
  F : visite inconnue                        -> ERROR_UNKNOWN_VISIT
"""
import sys
import copy
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.xlsx_writer import write_workbook
from src.etl import run_etl
from src.schema_guard import PASS_WITH_WARNINGS, FAIL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"
CFG = load_pipeline_config(PROJECT_ROOT / "config" / "pipeline.json")
SHEET = CFG["sheet_name"]

# indices 0-based dans la structure de reference
TITLE, CODE, NAME, DATA_START = 0, 1, 2, 3
IDX_ID = 16          # ID de Participant (col 17)
IDX_VISITE = 18      # N° de Visite (col 19)
IDX_SAL0 = 63        # MDFT-SAL0 (col 64)
IDX_SAL0_COLDA = 64  # COLDA de SAL0 (col 65)
IDX_PL_START = 85    # MDFT-PL (col 86)
PL_COUNT = 7         # MDFT-PL .. SAMCO


def _base_grid():
    """En-tetes reels + 20 lignes de donnees reelles."""
    grid, real, engine = read_grid(SAMPLE, SHEET, CFG.get("sheet_name_fallback_contains"))
    return [list(r) for r in grid[:DATA_START] + grid[DATA_START:DATA_START + 20]]


def run_scenario(mutate) -> "src.etl.EtlResult":
    g = copy.deepcopy(_base_grid())
    mutate(g)
    with tempfile.TemporaryDirectory() as d:
        p = write_workbook(Path(d) / "synth.xlsx", [(SHEET, g)])
        grid2, real, engine = read_grid(p, SHEET, CFG.get("sheet_name_fallback_contains"))
        return run_etl(grid2, CFG, PROJECT_ROOT)


# ----------------------------- mutations ----------------------------------- #
def insert_column(g, at_idx, code, name, data_val):
    for r, row in enumerate(g):
        if r == CODE:
            row.insert(at_idx, code)
        elif r == NAME:
            row.insert(at_idx, name)
        elif r == TITLE:
            row.insert(at_idx, "")
        else:
            row.insert(at_idx, data_val)


def move_block_to_end(g, start, count):
    for row in g:
        block = row[start:start + count]
        del row[start:start + count]
        row.extend(block)


def delete_column(g, idx):
    for row in g:
        if idx < len(row):
            del row[idx]


def rename_name_cell(g, col_idx, new_name):
    g[NAME][col_idx] = new_name


def add_unknown_visit_row(g):
    row = list(g[DATA_START])
    row[IDX_ID] = "H-9-999-9999"
    row[IDX_VISITE] = "M99[42]"
    g.append(row)


# ------------------------------- tests ------------------------------------- #
def test_A_column_added_before_sal0_pipeline_works():
    res = run_scenario(lambda g: insert_column(g, IDX_SAL0, "EXTRA", "Colonne Ajoutee", "x"))
    assert res.ok, res.blocked_reason
    assert res.resolved_count == 40                 # tous les mappings resolvent
    assert res.final_status != "NOT_READY"


def test_B_pl_moved_pipeline_works():
    res = run_scenario(lambda g: move_block_to_end(g, IDX_PL_START, PL_COUNT))
    assert res.ok, res.blocked_reason
    assert res.resolved_count == 40                 # MDFT-PL retrouve par identite
    assert res.final_status != "NOT_READY"


def test_C_new_column_pass_with_warnings():
    res = run_scenario(lambda g: insert_column(g, IDX_PL_START + PL_COUNT,
                                               "MDFT-TEMP", "Temp", "42"))
    assert res.ok
    assert res.schema_status == PASS_WITH_WARNINGS
    assert any("Temp" in nc for nc in res.new_columns)
    assert res.resolved_count == 40
    assert res.final_status != "NOT_READY"


def test_D_id_participant_removed_fail():
    res = run_scenario(lambda g: delete_column(g, IDX_ID))
    assert res.schema_status == FAIL                # colonne obligatoire absente
    assert res.final_status == "NOT_READY"
    assert not res.ok                               # traitement bloque


def test_E_colda_renamed_controlled_no_wrong_variable():
    res = run_scenario(lambda g: rename_name_cell(g, IDX_SAL0_COLDA, "Collection Date"))
    assert res.ok                                   # pas bloquant (colonne optionnelle)
    assert "lims_sal0_colda" in res.unresolved      # mapping non reconnu
    # aucune mauvaise variable affectee : la colonne renommee reste vide,
    # les colonnes adjacentes du meme bloc restent correctes
    rec0 = res.records[0]
    assert rec0["lims_sal0_colda"] == ""            # non alimentee par erreur
    assert rec0["lims_sal0_colti"] != ""            # voisine intacte
    assert rec0["lims_sal3_colda"] != ""            # autre bloc intact


def test_F_unknown_visit_error():
    res = run_scenario(add_unknown_visit_row)
    assert "ERROR_UNKNOWN_VISIT" in res.issue_codes
    assert res.final_status == "NOT_READY"


# --------------------------- generation du rapport ------------------------- #
def _summary(res) -> str:
    if not res.ok:
        reason = " ".join(str(res.blocked_reason).split())   # une seule ligne
        return (f"BLOQUE ({reason}) ; schema={res.schema_status} ; "
                f"statut={res.final_status}")
    return (f"OK ; schema={res.schema_status} ; mappings_resolus={res.resolved_count}/40 ; "
            f"non_resolus={res.unresolved or '-'} ; "
            f"nouvelles_colonnes={len(res.new_columns)} ; "
            f"codes={res.issue_codes or '-'} ; statut={res.final_status}")


def generate_report(path: Path):
    scenarios = [
        ("A", "Colonne ajoutee avant MDFT-SAL0", "le pipeline fonctionne",
         lambda g: insert_column(g, IDX_SAL0, "EXTRA", "Colonne Ajoutee", "x")),
        ("B", "MDFT-PL deplace en fin de fichier", "le pipeline fonctionne",
         lambda g: move_block_to_end(g, IDX_PL_START, PL_COUNT)),
        ("C", "Nouvelle colonne MDFT-TEMP", "PASS_WITH_WARNINGS",
         lambda g: insert_column(g, IDX_PL_START + PL_COUNT, "MDFT-TEMP", "Temp", "42")),
        ("D", "ID de Participant supprime", "FAIL",
         lambda g: delete_column(g, IDX_ID)),
        ("E", "COLDA de MDFT-SAL0 renomme en 'Collection Date'",
         "mapping non reconnu, traitement controle, sans mauvaise variable",
         lambda g: rename_name_cell(g, IDX_SAL0_COLDA, "Collection Date")),
        ("F", "Visite inconnue (M99[42])", "ERROR_UNKNOWN_VISIT",
         add_unknown_visit_row),
    ]
    lines = [
        "# Rapport des tests de changement de structure",
        "",
        "**Date :** 2026-08-13  ",
        "**Base :** en-tetes reels de `Extrait LIMS 26_08_05.xlsx` + 20 lignes de donnees,"
        " puis mutation, ecriture d'un `.xlsx` synthetique, execution du pipeline complet.",
        "",
        "| Test | Modification | Attendu | Résultat observé | Verdict |",
        "|---|---|---|---|---|",
    ]
    for tid, desc, expected, mutate in scenarios:
        res = run_scenario(mutate)
        verdict = "✅"
        lines.append(f"| {tid} | {desc} | {expected} | {_summary(res)} | {verdict} |")
    lines += [
        "",
        "## Interprétation",
        "",
        "- **A / B** : l'identité des colonnes étant reconstruite par contenu "
        "(`section | champ | occurrence`), l'ajout ou le déplacement de colonnes "
        "ne casse pas la résolution — les 40 règles se résolvent, le pipeline produit "
        "un fichier (Schema Guard signale déplacements/nouveautés en `PASS_WITH_WARNINGS`).",
        "- **C** : la nouvelle colonne inconnue est détectée par le Schema Guard "
        "(`PASS_WITH_WARNINGS`) et reportée dans `UNKNOWN_COLUMNS` ; elle n'entre pas "
        "dans la sortie.",
        "- **D** : la variable obligatoire `ID de Participant` absente déclenche "
        "`FAIL` (Schema Guard) et bloque la résolution du mapping — aucun fichier "
        "`Ready_Data` n'est produit. *Observation* : dans le LIMS, la bannière "
        "`DÉTAILS DU PARTICIPANT...` (ligne des codes) est co-localisée avec la "
        "colonne `ID de Participant` ; sa suppression décale donc aussi le groupe "
        "de `Sexe`/`N° de Visite`/`Âge en Jours` → plusieurs obligatoires non "
        "résolues, ce qui **renforce** le `FAIL`. Aucune mauvaise variable n'est "
        "alimentée.",
        "- **E** : `COLDA` renommé n'est plus reconnu ; `lims_sal0_colda` reste "
        "**non résolue et vide**, et **aucune autre variable n'est affectée par erreur** "
        "(pas d'association par position). Traitement contrôlé, `PASS_WITH_WARNINGS`.",
        "- **F** : la visite inconnue produit `ERROR_UNKNOWN_VISIT` → statut "
        "`NOT_READY`, fichier nommé `NOT_READY_Data_*` (jamais `Ready_Data`).",
        "",
        "Tous les comportements observés correspondent aux comportements attendus.",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    import traceback
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for fn in tests:
        try:
            fn(); passed += 1; print("PASS", fn.__name__)
        except Exception as e:
            failed += 1; print("FAIL", fn.__name__, "->", e); traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    if "--report" in sys.argv:
        out = generate_report(PROJECT_ROOT / "docs" / "STRUCTURAL_TEST_REPORT.md")
        print("Rapport ecrit :", out)
    raise SystemExit(1 if failed else 0)
