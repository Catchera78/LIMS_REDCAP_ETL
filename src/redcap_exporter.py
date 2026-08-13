"""Export du fichier REDCap (Prompt 8).

Produit un CSV respectant EXACTEMENT la structure de Ready_Data_26_08_13.csv :
  - separateur ';' ;
  - UTF-8 avec BOM ;
  - fins de ligne CRLF ;
  - noms REDCap exacts, dans l'ordre exact de redcap_output_columns.csv ;
  - aucune colonne technique interne au programme.

Avant tout export, les colonnes finales sont comparees a la liste de reference
(redcap_output_columns.csv) : toute difference (manquante, en trop, doublon)
BLOQUE l'export. Statuts (voir Prompt 9) :
  - READY / READY_WITH_WARNINGS -> Ready_Data_<date>.csv
  - NOT_READY                   -> NOT_READY_Data_<date>.csv (jamais "Ready_Data")
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

STATUS_READY = "READY"
STATUS_READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
STATUS_NOT_READY = "NOT_READY"


class ExportError(Exception):
    """Colonnes finales non conformes : export bloque."""


def validate_output_columns(records: Sequence[dict],
                            expected_columns: Sequence[str]) -> None:
    """Verifie que chaque enregistrement a EXACTEMENT les colonnes attendues.

    Leve ExportError en cas de colonne manquante, en trop (technique interne)
    ou de doublon dans la liste attendue.
    """
    expected = list(expected_columns)
    exp_set = set(expected)
    if len(expected) != len(exp_set):
        dups = sorted({c for c in expected if expected.count(c) > 1})
        raise ExportError(f"Colonnes de sortie en double : {dups}")

    for i, rec in enumerate(records):
        keys = set(rec.keys())
        extra = keys - exp_set
        missing = exp_set - keys
        if extra or missing:
            raise ExportError(
                f"Enregistrement {i}: colonnes finales differentes de "
                f"redcap_output_columns.csv (manquantes={sorted(missing)}, "
                f"en trop={sorted(extra)}). Export bloque.")


def derive_dataset_date(input_name: str, run_date: str, pattern: str) -> str:
    """Retourne le jeton de date du nom de l'extraction, sinon la date d'execution."""
    if input_name:
        m = re.search(pattern, input_name)
        if m:
            return m.group(1)
    return run_date


def output_filename(status: str, date_token: str, export_cfg: dict) -> str:
    tmpl = (export_cfg["not_ready_filename"] if status == STATUS_NOT_READY
            else export_cfg["ready_filename"])
    return tmpl.format(date=date_token)


def write_csv(records: Sequence[dict],
              columns: Sequence[str],
              path: Path,
              export_cfg: dict) -> Path:
    """Ecrit le CSV (colonnes dans l'ordre exact). Ne valide pas ici : appeler
    validate_output_columns au prealable."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    delimiter = export_cfg.get("delimiter", ";")
    encoding = export_cfg.get("encoding", "utf-8-sig")
    terminator = export_cfg.get("line_terminator", "\r\n")

    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.writer(f, delimiter=delimiter, lineterminator=terminator,
                            quoting=csv.QUOTE_MINIMAL)
        writer.writerow(list(columns))
        for rec in records:
            writer.writerow([rec.get(col, "") for col in columns])
    return path


def export(records: Sequence[dict],
           columns: Sequence[str],
           out_dir: Path,
           status: str,
           date_token: str,
           export_cfg: dict) -> Path:
    """Valide les colonnes puis ecrit le fichier au bon nom selon le statut."""
    validate_output_columns(records, columns)
    fname = output_filename(status, date_token, export_cfg)
    return write_csv(records, columns, Path(out_dir) / fname, export_cfg)


def compute_status(has_errors: bool, has_warnings: bool,
                   schema_failed: bool = False) -> str:
    """Statut global minimal (formalise au Prompt 9)."""
    if has_errors or schema_failed:
        return STATUS_NOT_READY
    if has_warnings:
        return STATUS_READY_WITH_WARNINGS
    return STATUS_READY
