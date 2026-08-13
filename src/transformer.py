"""Transformations metier (Prompt 5) : reproduction du do-file Stata.

Produit, pour chaque ligne de donnees, un enregistrement REDCap :
  - patid = lims_id_participant
  - lims_site1 : TBR->1, SAFO->2 (via sites_mapping)
  - lims_sexe  : M->1, F->2 (via sex_mapping)
  - lims_tab_id = "LIMS" ; redcap_data_access_group = "" ;
    redcap_repeat_instrument = "labo_prlvements_biologiques_sousetude_mdf_lims"
  - redcap_event_name : N° de Visite -> event (via visits_mapping) ;
    visite inconnue -> ERROR_UNKNOWN_VISIT (jamais un event vide silencieux)
  - toutes les autres variables mappees : copie directe de la valeur source.

Non traite ici (etapes suivantes) :
  - dates/heures normalisees            -> Prompt 6 (copie brute pour l'instant)
  - redcap_repeat_instance              -> Prompt 7 (laisse vide)

Regle de valeur manquante : une valeur SOURCE vide reste vide, SANS erreur
(comportement Stata). Une valeur NON vide non reconnue declenche le code
configure (ERROR / WARNING). Une visite (vide ou inconnue) est toujours signalee
car l'event est obligatoire.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .text_utils import normalize
from .column_identity import ColumnIdentity
from .mapping_loader import MappingRow, MappingConfig
from .date_parser import (
    parse_date, format_date, parse_time, format_time,
    DateParseError, TimeParseError,
)

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"


@dataclass
class Issue:
    error_code: str
    severity: str
    source_row: int         # ligne 1-based dans l'onglet
    patid: str
    variable: str
    source_value: str
    message: str

    def as_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "severity": self.severity,
            "source_row": self.source_row,
            "patid": self.patid,
            "variable": self.variable,
            "source_value": self.source_value,
            "message": self.message,
        }


@dataclass
class TransformResult:
    records: List[dict] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    source_rows: List[int] = field(default_factory=list)  # ligne onglet par record (aligne)

    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_ERROR]

    def warnings(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == SEVERITY_WARNING]


@dataclass
class DataRow:
    """Une ligne de donnees + son numero de ligne (1-based) dans l'onglet."""
    sheet_row: int
    cells: Sequence[str]


def extract_data_rows(grid: Sequence[Sequence[str]],
                      data_start_index: int,
                      identity_column_1based: int) -> List[DataRow]:
    """Retourne les lignes de donnees (colonne d'identite non vide), avec leur
    numero de ligne 1-based dans l'onglet. Exclut le bloc de legende du bas."""
    id_idx = identity_column_1based - 1
    rows: List[DataRow] = []
    for offset in range(data_start_index, len(grid)):
        row = grid[offset]
        cell = row[id_idx] if id_idx < len(row) else ""
        if str(cell).strip() != "":
            rows.append(DataRow(sheet_row=offset + 1, cells=row))
    return rows


def _cell(row: Sequence[str], ident: ColumnIdentity) -> str:
    idx = ident.position - 1
    if 0 <= idx < len(row):
        return str(row[idx]).strip()
    return ""


class Transformer:
    def __init__(self, mapping: MappingConfig, transform_cfg: dict):
        self.mapping = mapping
        self.cfg = transform_cfg
        self.constants: Dict[str, str] = dict(transform_cfg.get("constants", {}))
        self.patid_variable: str = transform_cfg.get("patid_variable", "")
        self.value_recodes: Dict[str, dict] = transform_cfg.get("value_recodes", {})
        self.event_recodes: Dict[str, dict] = transform_cfg.get("event_recodes", {})
        self.deferred = set(transform_cfg.get("deferred_variables", []))
        self._maps = {"sites": mapping.sites, "sex": mapping.sex, "visits": mapping.visits}
        # data_type par variable REDCap (pour dates/heures)
        self.data_types: Dict[str, str] = {
            r.redcap_variable: r.data_type for r in mapping.rows}
        self.date_fmt = transform_cfg.get("date_output_format", "%d/%m/%Y")
        self.time_fmt = transform_cfg.get("time_output_format", "%H:%M")
        self.french_months = transform_cfg.get("french_months")
        self.date_invalid = transform_cfg.get(
            "date_invalid", {"severity": SEVERITY_ERROR, "error_code": "ERROR_INVALID_DATE"})
        self.time_invalid = transform_cfg.get(
            "time_invalid", {"severity": SEVERITY_WARNING, "error_code": "ERROR_INVALID_TIME"})

    def _parse_date_cell(self, value: str, variable: str, sheet_row: int, patid: str):
        raw = value.strip()
        if raw == "":
            return "", None
        try:
            return format_date(parse_date(raw, self.french_months), self.date_fmt), None
        except DateParseError:
            spec = self.date_invalid
            issue = Issue(spec["error_code"], spec["severity"], sheet_row, patid,
                          variable, raw, f"Date invalide : {raw!r}")
            return "", issue          # vide + erreur (non silencieux : issue enregistree)

    def _parse_time_cell(self, value: str, variable: str, sheet_row: int, patid: str):
        raw = value.strip()
        if raw == "":
            return "", None
        try:
            return format_time(parse_time(raw), self.time_fmt), None
        except TimeParseError:
            spec = self.time_invalid
            issue = Issue(spec["error_code"], spec["severity"], sheet_row, patid,
                          variable, raw, f"Heure invalide : {raw!r}")
            return "", issue

    # ------------------------------------------------------------------ #
    def _recode(self, spec: dict, value: str, allow_empty: bool,
                variable: str, sheet_row: int, patid: str
                ) -> Tuple[str, Optional[Issue]]:
        """Recode une valeur via une table. Retourne (valeur_sortie, issue|None)."""
        table = self._maps.get(spec["map"], {})
        raw = value.strip()
        if raw == "" and allow_empty:
            return "", None                      # manquant tolere (comme Stata)
        key = normalize(raw)
        if key in table:
            return table[key], None
        # valeur inconnue (ou vide pour un champ obligatoire type event)
        code = spec.get("error_code", "ERROR_UNKNOWN_VALUE")
        severity = spec.get("severity", SEVERITY_ERROR)
        msg = (f"Valeur non reconnue pour {variable} : {raw!r}"
               if raw else f"Valeur absente pour {variable} (obligatoire)")
        issue = Issue(code, severity, sheet_row, patid, variable, raw, msg)
        # valeur de sortie : vide pour un recode de valeur ; sentinel pour un event
        out = code if variable in self.event_recodes else ""
        return out, issue

    # ------------------------------------------------------------------ #
    def transform(self,
                  data_rows: Sequence[DataRow],
                  resolution: Dict[str, ColumnIdentity]) -> TransformResult:
        result = TransformResult()
        out_cols = self.mapping.output_columns

        for drow in data_rows:
            row = drow.cells
            # valeurs sources brutes des variables resolues
            raw: Dict[str, str] = {var: _cell(row, ident)
                                   for var, ident in resolution.items()}
            patid = raw.get(self.patid_variable, "")

            rec: Dict[str, str] = {}
            for col in out_cols:
                if col == "patid":
                    rec[col] = patid
                elif col in self.constants:
                    rec[col] = self.constants[col]
                elif col in self.deferred:
                    rec[col] = ""                       # calcule plus tard
                elif col in self.event_recodes:
                    val, issue = self._recode(
                        self.event_recodes[col], raw.get(col, ""),
                        allow_empty=False, variable=col,
                        sheet_row=drow.sheet_row, patid=patid)
                    rec[col] = val
                    if issue:
                        result.issues.append(issue)
                elif col in self.value_recodes:
                    val, issue = self._recode(
                        self.value_recodes[col], raw.get(col, ""),
                        allow_empty=True, variable=col,
                        sheet_row=drow.sheet_row, patid=patid)
                    rec[col] = val
                    if issue:
                        result.issues.append(issue)
                elif col in raw:
                    dtype = self.data_types.get(col, "text")
                    if dtype == "date":
                        val, issue = self._parse_date_cell(
                            raw[col], col, drow.sheet_row, patid)
                        rec[col] = val
                        if issue:
                            result.issues.append(issue)
                    elif dtype == "time":
                        val, issue = self._parse_time_cell(
                            raw[col], col, drow.sheet_row, patid)
                        rec[col] = val
                        if issue:
                            result.issues.append(issue)
                    else:
                        rec[col] = raw[col]              # copie directe
                else:
                    rec[col] = ""
            result.records.append(rec)
            result.source_rows.append(drow.sheet_row)

        return result
