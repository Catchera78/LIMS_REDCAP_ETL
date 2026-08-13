"""Rapport QC (Prompt 9) : QC_Report_<date>.xlsx.

Feuilles produites :
  SUMMARY, SCHEMA, ERRORS, WARNINGS, UNKNOWN_VISITS, UNKNOWN_COLUMNS,
  DUPLICATES, MAPPING.

Chaque erreur/avertissement expose au minimum :
  error_code, severity, source_row, patid, variable, source_value, message.

Le statut global (READY / READY_WITH_WARNINGS / NOT_READY) est calcule en amont
(redcap_exporter.compute_status) et seulement reporte ici.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .transformer import Issue, SEVERITY_ERROR, SEVERITY_WARNING
from .schema_guard import SchemaCheckResult
from .column_identity import ColumnIdentity
from .mapping_loader import MappingRow
from . import xlsx_writer

ISSUE_HEADER = ["error_code", "severity", "source_row", "patid",
                "variable", "source_value", "message"]


@dataclass
class QCContext:
    input_file: str
    run_id: str
    run_datetime: str
    status: str
    n_source_rows: int
    n_skipped_rows: int
    n_participants: int
    n_output_rows: int
    issues: List[Issue] = field(default_factory=list)
    schema_result: Optional[SchemaCheckResult] = None
    resolution: Dict[str, ColumnIdentity] = field(default_factory=dict)
    mapping_rows: List[MappingRow] = field(default_factory=list)
    unknown_visit_code: str = "ERROR_UNKNOWN_VISIT"
    multiple_records_code: str = "WARNING_MULTIPLE_RECORDS_SAME_EVENT"

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]


def _issue_rows(issues: Sequence[Issue]) -> List[list]:
    rows = [list(ISSUE_HEADER)]
    for i in issues:
        rows.append([i.error_code, i.severity, i.source_row, i.patid,
                     i.variable, i.source_value, i.message])
    return rows


def _summary_sheet(ctx: QCContext) -> List[list]:
    return [
        ["Champ", "Valeur"],
        ["Fichier d'entree", ctx.input_file],
        ["Run ID", ctx.run_id],
        ["Date/heure", ctx.run_datetime],
        ["Lignes source (donnees)", ctx.n_source_rows],
        ["Lignes ignorees (legende / sans participant)", ctx.n_skipped_rows],
        ["Participants distincts", ctx.n_participants],
        ["Lignes output", ctx.n_output_rows],
        ["Erreurs", len(ctx.errors())],
        ["Avertissements", len(ctx.warnings())],
        ["STATUT FINAL", ctx.status],
    ]


def _schema_sheet(ctx: QCContext) -> List[list]:
    header = ["categorie", "source_group", "source_field", "status",
              "expected_col", "found_col", "action"]
    rows = [header]
    sr = ctx.schema_result
    if sr is None:
        rows.append(["(schema indisponible)", "", "", "", "", "", ""])
        return rows
    rows.append(["_global", "", "", sr.status, sr.n_expected, sr.n_found, ""])
    for c in sr.missing_required:
        rows.append(["missing_required", c.group, c.field, "FAIL",
                     c.position, "", "Fournir la colonne obligatoire"])
    for c in sr.missing_optional:
        rows.append(["missing_optional", c.group, c.field, "WARNING",
                     c.position, "", "Colonne optionnelle absente"])
    for rc, cur in sr.moved_columns:
        rows.append(["moved", rc.group, rc.field, "INFO",
                     rc.position, cur.position, "Deplacement (non bloquant)"])
    for cur in sr.new_columns:
        rows.append(["new_column", cur.group, cur.field, "WARNING",
                     "", cur.position, "Nouvelle colonne a verifier"])
    for cur in sr.ambiguous_columns:
        rows.append(["ambiguous", cur.group, cur.field, "WARNING",
                     "", cur.position, "Identite dupliquee"])
    return rows


def _unknown_visits_sheet(ctx: QCContext) -> List[list]:
    rows = [["visite_inconnue", "occurrences", "exemple_patid", "exemple_ligne"]]
    unk = [i for i in ctx.issues if i.error_code == ctx.unknown_visit_code]
    by_value: Dict[str, List[Issue]] = {}
    for i in unk:
        by_value.setdefault(i.source_value, []).append(i)
    for value, items in sorted(by_value.items()):
        rows.append([value or "(vide)", len(items),
                     items[0].patid, items[0].source_row])
    return rows


def _unknown_columns_sheet(ctx: QCContext) -> List[list]:
    rows = [["source_group", "source_field", "occurrence", "position"]]
    if ctx.schema_result:
        for cur in ctx.schema_result.new_columns:
            rows.append([cur.group, cur.field, cur.occurrence, cur.position])
    return rows


def _duplicates_sheet(ctx: QCContext) -> List[list]:
    rows = [["patid", "event", "nb_lignes", "source_row", "message"]]
    for i in ctx.issues:
        if i.error_code == ctx.multiple_records_code:
            # event est dans le message ; patid/nb_lignes disponibles
            rows.append([i.patid, "", i.source_value, i.source_row, i.message])
    return rows


def _mapping_sheet(ctx: QCContext) -> List[list]:
    rows = [["redcap_variable", "source_group", "source_field",
             "source_occurrence", "position", "data_type", "required", "resolue"]]
    for r in ctx.mapping_rows:
        if not r.active:
            continue
        ident = ctx.resolution.get(r.redcap_variable)
        rows.append([r.redcap_variable, r.source_group, r.source_field,
                     r.source_occurrence,
                     ident.position if ident else "",
                     r.data_type, "YES" if r.required else "NO",
                     "OUI" if ident else "NON"])
    return rows


def build_sheets(ctx: QCContext) -> List[tuple]:
    """Construit la liste (nom_feuille, lignes). Fonction pure (testable)."""
    return [
        ("SUMMARY", _summary_sheet(ctx)),
        ("SCHEMA", _schema_sheet(ctx)),
        ("ERRORS", _issue_rows(ctx.errors())),
        ("WARNINGS", _issue_rows(ctx.warnings())),
        ("UNKNOWN_VISITS", _unknown_visits_sheet(ctx)),
        ("UNKNOWN_COLUMNS", _unknown_columns_sheet(ctx)),
        ("DUPLICATES", _duplicates_sheet(ctx)),
        ("MAPPING", _mapping_sheet(ctx)),
    ]


def write_qc_report(ctx: QCContext, path: Path) -> Path:
    return xlsx_writer.write_workbook(Path(path), build_sheets(ctx))
