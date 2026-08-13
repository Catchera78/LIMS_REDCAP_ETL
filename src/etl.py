"""Coeur du pipeline ETL, reutilisable (Prompts 11 & 13/R1).

`run_etl(grid, cfg, project_root)` execute toute la chaine de CALCUL sur une
grille deja lue (detection en-tetes -> identite -> Schema Guard -> mapping ->
transformations -> repeat_instance -> statut) et renvoie un EtlResult riche,
en capturant les blocages a chaque etape.

C'est le socle commun a `run_pipeline.py` (orchestration + I/O + journal +
tableau de bord) et aux tests de structure. Les effets de bord (lecture du
fichier, export CSV, rapport QC, archivage) restent hors de run_etl.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .header_parser import detect_headers, HeaderDetectionError, HeaderDetectionResult
from .column_identity import (
    parse_from_detection, find_column_by_field, ColumnIdentity, ColumnIdentityError,
)
from . import schema_guard
from .schema_guard import SchemaCheckResult
from .mapping_loader import (
    load_all, validate_mapping_config, resolve_columns,
    MappingConfig, ResolutionResult, MappingConfigError, MappingResolutionError,
)
from .transformer import Transformer, TransformResult, extract_data_rows
from .repeat_instance import assign_repeat_instances
from .redcap_exporter import compute_status, STATUS_NOT_READY


@dataclass
class EtlResult:
    ok: bool = False
    blocked_reason: Optional[str] = None

    # artefacts intermediaires (pour journalisation / export / QC)
    detection: Optional[HeaderDetectionResult] = None
    identities: List[ColumnIdentity] = field(default_factory=list)
    schema_check: Optional[SchemaCheckResult] = None
    mapping_config: Optional[MappingConfig] = None
    resolution: Optional[ResolutionResult] = None
    participant_column: Optional[ColumnIdentity] = None
    transform: Optional[TransformResult] = None

    # synthese
    schema_status: Optional[str] = None
    new_columns: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    moved_columns: int = 0
    resolved_count: int = 0
    unresolved: List[str] = field(default_factory=list)
    ambiguous: bool = False
    n_data_rows: int = 0
    n_skipped: int = 0
    n_records: int = 0
    n_errors: int = 0
    n_warnings: int = 0
    issue_codes: Dict[str, int] = field(default_factory=dict)
    final_status: Optional[str] = None
    records: List[dict] = field(default_factory=list)

    def warnings(self):
        return self.transform.warnings() if self.transform else []

    def errors(self):
        return self.transform.errors() if self.transform else []


def run_etl(grid, cfg: dict, project_root: Path,
            sheet_name_found: Optional[str] = None) -> EtlResult:
    res = EtlResult()

    # 1) en-tetes
    hd = cfg["header_detection"]
    try:
        det = detect_headers(
            grid, hd["anchor_fields"], cfg["data_rows"]["identity_column_1based"],
            hd.get("max_header_scan_rows", 20), hd.get("min_anchor_matches", 2))
    except HeaderDetectionError as exc:
        res.blocked_reason = f"en-tetes: {exc}"
        res.final_status = STATUS_NOT_READY
        return res
    res.detection = det

    res.identities = parse_from_detection(
        grid, det, cfg["column_identity"]["section_start_codes"])

    # 2) Schema Guard (ne bloque pas par exception ; statut FAIL possible)
    sg = cfg["schema_guard"]
    ref_path = Path(project_root) / sg["reference_schema_path"]
    try:
        reference = schema_guard.load_reference_schema(ref_path)
        chk = schema_guard.compare(res.identities, reference,
                                   sheet_name_found=sheet_name_found,
                                   n_columns_found=det.n_columns)
        res.schema_check = chk
        res.schema_status = chk.status
        res.new_columns = [f"{c.group}|{c.field}" for c in chk.new_columns]
        res.missing_required = [c.key for c in chk.missing_required]
        res.moved_columns = len(chk.moved_columns)
    except schema_guard.SchemaGuardError:
        res.schema_status = None

    # 3) mapping : chargement + validation + resolution
    try:
        mc = load_all(cfg, project_root)
        validate_mapping_config(mc)
        res.mapping_config = mc
        resolution = resolve_columns(mc.rows, res.identities)
    except (MappingConfigError, MappingResolutionError) as exc:
        res.blocked_reason = f"mapping: {exc}"
        res.final_status = STATUS_NOT_READY
        return res
    res.resolution = resolution
    res.resolved_count = resolution.resolved_count()
    res.unresolved = [r.redcap_variable for r in resolution.unresolved]
    res.ambiguous = bool(resolution.ambiguous)

    # 4) colonne participant (definit les lignes de donnees)
    try:
        pid = find_column_by_field(res.identities, cfg["data_rows"]["identity_field"])
    except ColumnIdentityError as exc:
        res.blocked_reason = f"participant: {exc}"
        res.final_status = STATUS_NOT_READY
        return res
    res.participant_column = pid

    data_rows = extract_data_rows(grid, det.data_start_index, pid.position)
    res.n_data_rows = len(data_rows)
    res.n_skipped = (det.n_total_rows - det.data_start_index) - len(data_rows)

    # 5) transformations + repeat_instance
    tr = Transformer(mc, cfg["transform"]).transform(data_rows, resolution.resolved)
    ri_issues = assign_repeat_instances(
        tr.records, tr.source_rows, cfg["transform"]["repeat_instance"],
        cfg["transform"].get("french_months"))
    tr.issues.extend(ri_issues)          # <-- integre les WARNING de repetition

    res.transform = tr
    res.records = tr.records
    res.n_records = len(tr.records)
    res.n_errors = len(tr.errors())
    res.n_warnings = len(tr.warnings())
    res.issue_codes = dict(Counter(i.error_code for i in tr.issues))
    res.final_status = compute_status(
        has_errors=bool(tr.errors()), has_warnings=bool(tr.warnings()),
        schema_failed=(res.schema_status == schema_guard.FAIL))
    res.ok = True
    return res
