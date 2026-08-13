#!/usr/bin/env python3
"""Pipeline LIMS -> REDCap MDF — point d'entree (v1.0).

Orchestration + I/O + journal + tableau de bord autour du coeur de calcul
`src.etl.run_etl` (une seule implementation de la chaine metier, partagee avec
les tests de structure). Chaine : detection de structure -> identite des
colonnes -> Schema Guard -> mapping externalise -> transformations ->
dates/heures -> redcap_repeat_instance -> export Ready_Data -> rapport QC ->
archivage.

L'utilisateur ne voit qu'un tableau de bord (console) ; le detail complet est
ecrit dans archive/<date>/logs/run_<date>.log. Le fichier original n'est jamais
modifie. Tous les chemins sont RELATIFS a l'emplacement de ce script.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Permet l'execution directe (python run_pipeline.py) comme en module.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.config_loader import load_pipeline_config, ConfigError
from src.excel_reader import (
    find_input_xlsx, read_grid, list_sheet_names, ExcelReadError,
)
from src import schema_guard
from src import redcap_exporter
from src import qc_reporter
from src import xlsx_writer
from src import environment
from src.etl import run_etl
from src.archiver import build_run_dirs, archive_original, today_str, ArchiveError
from src.logging_setup import setup_logger
from src.dashboard import Dashboard


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pipeline LIMS -> REDCap MDF (v1.0).")
    p.add_argument("--input", type=Path, default=SCRIPT_DIR / "input",
                   help="Dossier contenant l'extraction LIMS .xlsx (defaut: input/).")
    p.add_argument("--config", type=Path, default=SCRIPT_DIR / "config" / "pipeline.json",
                   help="Fichier de configuration (defaut: config/pipeline.json).")
    p.add_argument("--archive", type=Path, default=SCRIPT_DIR / "archive",
                   help="Racine d'archivage (defaut: archive/).")
    p.add_argument("--check", action="store_true",
                   help="Verifier l'environnement (openpyxl, moteurs) et quitter.")
    return p.parse_args(argv)


def _log_etl_detail(log, result) -> None:
    """Ecrit le detail de l'execution dans le journal (fichier)."""
    det = result.detection
    if det is not None:
        log.info("-" * 58)
        log.info("Lignes d'en-tete detectees :")
        if det.code_row_index is not None:
            log.info("  - ligne CODES/groupes : ligne %d", det.code_row_index + 1)
        log.info("  - ligne NOMS de champ : ligne %d", det.name_row_index + 1)
        log.info("  - debut des donnees   : ligne %d", det.data_start_index + 1)
        log.info("  - ancres reconnues    : %s", ", ".join(det.matched_anchors))
        log.info("Nombre de colonnes     : %d", det.n_columns)
        log.info("Nombre de lignes (total onglet) : %d", det.n_total_rows)

    named = [i for i in result.identities if i.field.strip()]
    if named:
        keys = {i.key for i in named}
        log.info("Identite des colonnes  : %d colonnes (%d nommees, %d uniques)",
                 len(result.identities), len(named), len(keys))
        for ident in named[:3]:
            log.info("  ex. col %d -> %s", ident.position, ident.key)

    if result.schema_check is not None:
        log.info("-" * 58)
        schema_guard.log_result(result.schema_check, log)
        if result.schema_check.is_fail:
            log.error("Structure NON conforme (FAIL) : aucun Ready_Data ne sera produit.")

    if result.blocked_reason:
        log.error("TRAITEMENT BLOQUE : %s", result.blocked_reason)
        return

    mc = result.mapping_config
    log.info("-" * 58)
    log.info("=== MAPPING ===")
    log.info("Regles actives         : %d", len(mc.active_rows()))
    log.info("Colonnes resolues      : %d", result.resolved_count)
    log.info("Colonnes de sortie     : %d (dont %d techniques)",
             len(mc.output_columns), len(mc.technical_variables))
    if result.unresolved:
        log.warning("Regles optionnelles non resolues : %s", ", ".join(result.unresolved))

    log.info("=== TRANSFORMATION ===")
    if result.participant_column is not None:
        log.info("Colonne participant    : %s (col %d)",
                 result.participant_column.field, result.participant_column.position)
    log.info("Lignes de donnees      : %d (participant renseigne)", result.n_data_rows)
    log.info("Lignes ignorees (sans participant / legende) : %d", result.n_skipped)
    log.info("Enregistrements produits : %d", result.n_records)
    log.info("Erreurs                : %d", result.n_errors)
    log.info("Avertissements         : %d", result.n_warnings)
    for code, n in sorted(result.issue_codes.items()):
        is_err = any(i.error_code == code and i.severity == "ERROR"
                     for i in result.transform.issues)
        getattr(log, "error" if is_err else "warning")("  %s : %d", code, n)


def _export_and_qc(log, result, cfg, xlsx_name, run_dirs, run_date, db):
    """Export Ready_Data + rapport QC (statut deja calcule par run_etl)."""
    mc = result.mapping_config
    status = result.final_status
    date_token = redcap_exporter.derive_dataset_date(
        xlsx_name, today_str(cfg["export"]["run_date_format"]),
        cfg["export"]["dataset_date_pattern"])

    out_path = redcap_exporter.export(
        result.records, mc.output_columns, SCRIPT_DIR / "output",
        status, date_token, cfg["export"])
    shutil.copy2(out_path, run_dirs["output"] / out_path.name)
    db.set_status(status)
    db.output_path = f"output/{out_path.name}"
    log.info("=== EXPORT ===")
    log.info("Statut global          : %s", status)
    log.info("Fichier produit        : %s", out_path)

    participants = {r.get("patid", "") for r in result.records if r.get("patid")}
    qc_ctx = qc_reporter.QCContext(
        input_file=xlsx_name,
        run_id=f"{run_date}_{datetime.now().strftime('%H%M%S')}",
        run_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status=status,
        n_source_rows=result.n_data_rows,
        n_skipped_rows=result.n_skipped,
        n_participants=len(participants),
        n_output_rows=result.n_records,
        issues=result.transform.issues,
        schema_result=result.schema_check,
        resolution=result.resolution.resolved,
        mapping_rows=mc.rows,
        unknown_visit_code=cfg["transform"]["event_recodes"]
            ["redcap_event_name"]["error_code"],
        multiple_records_code=cfg["transform"]["repeat_instance"]
            ["multiple_warning"]["error_code"],
    )
    qc_name = cfg["export"]["qc_filename"].format(date=date_token)
    qc_path = qc_reporter.write_qc_report(qc_ctx, SCRIPT_DIR / "output" / qc_name)
    shutil.copy2(qc_path, run_dirs["qc"] / qc_path.name)
    db.qc_path = f"output/{qc_path.name}"
    log.info("Rapport QC             : %s (moteur %s)", qc_path, xlsx_writer.engine_name())


def run(argv=None) -> int:
    args = parse_args(argv)

    # Verification de l'environnement (réserve R3) : --check affiche et quitte.
    if args.check:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        print(environment.format_report())
        return 0 if environment.openpyxl_available() else 1

    try:
        cfg = load_pipeline_config(args.config)
    except ConfigError as exc:
        print(f"[ERREUR CONFIG] {exc}", file=sys.stderr)
        return 2

    date_fmt = cfg["archive"].get("date_format", "%Y-%m-%d")
    run_date = today_str(date_fmt)
    run_dirs = build_run_dirs(args.archive, run_date, cfg["archive"]["subdirs"])
    log_path = run_dirs["logs"] / f"run_{run_date}.log"
    # Console silencieuse : l'utilisateur ne voit que le tableau de bord.
    log = setup_logger(log_path, console_level=logging.CRITICAL + 10)

    db = Dashboard(log_path=str(log_path))

    log.info("=" * 58)
    log.info("        LIMS -> REDCap MDF")
    log.info("=" * 58)
    for line in environment.format_report().splitlines():
        log.info("%s", line)
    log.info("Configuration          : %s", args.config)
    # Recommandation non bloquante affichee sur le tableau de bord si besoin.
    db.note = environment.advisory()

    try:
        xlsx = find_input_xlsx(args.input)
        db.input_name = xlsx.name
        log.info("Fichier d'entree       : %s", xlsx.name)
        log.info("Onglets du classeur    : %s", list_sheet_names(xlsx))

        grid, real_sheet, engine = read_grid(
            xlsx, cfg["sheet_name"], cfg.get("sheet_name_fallback_contains"))
        log.info("Onglet analyse         : %s (moteur %s)", real_sheet, engine)

        # --- coeur de calcul commun ------------------------------------------
        result = run_etl(grid, cfg, SCRIPT_DIR, sheet_name_found=real_sheet)
        _log_etl_detail(log, result)

        # --- tableau de bord : structure / mapping / transformation ----------
        db.structure = "OK" if result.detection is not None else "FAIL"
        db.set_structure(result.schema_status)

        if result.blocked_reason:
            db.mapping = "OK" if result.mapping_config is not None else "FAIL"
            if result.resolution is None:
                db.mapping = "FAIL"
            db.set_status(result.final_status or "NOT_READY")
            db.message = result.blocked_reason
        else:
            db.mapping = "OK"
            db.transformation = "ERROR" if result.n_errors else "OK"
            db.records_source = result.n_data_rows
            db.records_output = result.n_records
            db.errors = result.n_errors
            db.warnings = result.n_warnings
            _export_and_qc(log, result, cfg, xlsx.name, run_dirs, run_date, db)

        # --- archivage (toujours ; fichier original jamais modifie) ----------
        archived = archive_original(xlsx, run_dirs["raw"])
        log.info("-" * 58)
        log.info("Copie archivee         : %s", archived)
        log.info("Fichier original NON modifie.")
        log.info("Journal                : %s", log_path)

        status = result.final_status or "NOT_READY"
        log.info("Traitement termine (statut %s).", status)
        return 0 if status in (redcap_exporter.STATUS_READY,
                               redcap_exporter.STATUS_READY_WITH_WARNINGS) else 1

    except (ExcelReadError, ArchiveError) as exc:
        db.set_status("NOT_READY")
        db.message = str(exc).splitlines()[0]
        log.error("ECHEC : %s", exc)
        return 1
    except Exception as exc:  # pragma: no cover - garde-fou
        db.set_status("NOT_READY")
        db.message = f"Erreur inattendue : {exc}"
        log.exception("ERREUR INATTENDUE : %s", exc)
        return 3
    finally:
        db.print()


if __name__ == "__main__":
    raise SystemExit(run())
