"""Chargement et validation des mappings externalises (Prompt 4).

Fichiers :
  - lims_redcap_mapping.csv   identite LIMS (group|field|occurrence) -> variable REDCap
  - sites_mapping.csv          valeur site LIMS -> code REDCap
  - sex_mapping.csv            valeur sexe LIMS -> code REDCap
  - visits_mapping.csv         N° de Visite LIMS -> redcap_event_name
  - redcap_output_columns.csv  liste ordonnee exacte des colonnes de sortie

L'association LIMS -> REDCap passe UNIQUEMENT par l'identite metier ; aucune
position de colonne n'est utilisee. Un mapping ambigu (une regle qui pointe vers
plusieurs colonnes, ou deux regles vers la meme identite / variable) BLOQUE le
traitement.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .text_utils import normalize
from .column_identity import ColumnIdentity


class MappingConfigError(Exception):
    """Fichier de mapping invalide ou incoherent (bloquant)."""


class MappingResolutionError(Exception):
    """Impossible de resoudre le mapping contre l'extraction (bloquant)."""


# --------------------------------------------------------------------------- #
# Modeles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MappingRow:
    source_group: str
    source_field: str
    source_occurrence: int
    redcap_variable: str
    required: bool
    data_type: str
    active: bool
    notes: str = ""

    @property
    def norm_identity(self) -> tuple:
        return (normalize(self.source_group), normalize(self.source_field),
                self.source_occurrence)


@dataclass
class MappingConfig:
    rows: List[MappingRow]
    sites: Dict[str, str]
    sex: Dict[str, str]
    visits: Dict[str, str]
    output_columns: List[str]
    allowed_data_types: List[str]
    technical_variables: List[str]

    def active_rows(self) -> List[MappingRow]:
        return [r for r in self.rows if r.active]


# --------------------------------------------------------------------------- #
# Lecture CSV
# --------------------------------------------------------------------------- #
def _read_csv(path: Path) -> List[dict]:
    path = Path(path)
    if not path.is_file():
        raise MappingConfigError(f"Fichier de mapping introuvable : {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()}
                for r in reader]
    return rows


def _yesno(value: str, path: Path, ctx: str) -> bool:
    v = value.strip().upper()
    if v in ("YES", "OUI", "TRUE", "1"):
        return True
    if v in ("NO", "NON", "FALSE", "0"):
        return False
    raise MappingConfigError(f"{path.name}: valeur YES/NO invalide pour {ctx} : {value!r}")


def load_mapping(path: Path) -> List[MappingRow]:
    path = Path(path)
    rows_raw = _read_csv(path)
    required_cols = {"source_group", "source_field", "source_occurrence",
                     "redcap_variable", "required", "data_type", "active"}
    if rows_raw:
        missing = required_cols - set(rows_raw[0].keys())
        if missing:
            raise MappingConfigError(
                f"{path.name}: colonnes manquantes : {', '.join(sorted(missing))}")
    out: List[MappingRow] = []
    for n, r in enumerate(rows_raw, start=2):
        occ_raw = r.get("source_occurrence", "").strip() or "1"
        try:
            occ = int(occ_raw)
        except ValueError:
            raise MappingConfigError(
                f"{path.name} ligne {n}: source_occurrence non entier : {occ_raw!r}")
        out.append(MappingRow(
            source_group=r.get("source_group", "").strip(),
            source_field=r.get("source_field", "").strip(),
            source_occurrence=occ,
            redcap_variable=r.get("redcap_variable", "").strip(),
            required=_yesno(r.get("required", "NO"), path, f"required ligne {n}"),
            data_type=r.get("data_type", "").strip().lower(),
            active=_yesno(r.get("active", "YES"), path, f"active ligne {n}"),
            notes=r.get("notes", "").strip(),
        ))
    return out


def load_value_map(path: Path, key_col: str, val_col: str) -> Dict[str, str]:
    path = Path(path)
    rows = _read_csv(path)
    mapping: Dict[str, str] = {}
    for n, r in enumerate(rows, start=2):
        if key_col not in r or val_col not in r:
            raise MappingConfigError(
                f"{path.name}: colonnes attendues {key_col!r}/{val_col!r} absentes")
        key = r[key_col].strip()
        if not key:
            continue
        nkey = normalize(key)
        if nkey in mapping:
            raise MappingConfigError(
                f"{path.name} ligne {n}: valeur en double : {key!r} (mapping ambigu)")
        mapping[nkey] = r[val_col].strip()
    return mapping


def load_output_columns(path: Path) -> List[str]:
    path = Path(path)
    rows = _read_csv(path)
    cols = [r["redcap_variable"].strip() for r in rows if r.get("redcap_variable", "").strip()]
    return cols


def load_all(cfg: dict, base_dir: Path) -> MappingConfig:
    m = cfg["mapping"]
    base = Path(base_dir)
    rows = load_mapping(base / m["lims_redcap_mapping"])
    sites = load_value_map(base / m["sites_mapping"], "lims_value", "redcap_value")
    sex = load_value_map(base / m["sex_mapping"], "lims_value", "redcap_value")
    visits = load_value_map(base / m["visits_mapping"], "lims_visit", "redcap_event_name")
    output_columns = load_output_columns(base / m["redcap_output_columns"])
    return MappingConfig(
        rows=rows, sites=sites, sex=sex, visits=visits,
        output_columns=output_columns,
        allowed_data_types=[d.lower() for d in m.get("allowed_data_types", [])],
        technical_variables=list(m.get("technical_variables", [])),
    )


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_mapping_config(mc: MappingConfig) -> List[str]:
    """Valide la coherence des fichiers de mapping.

    Leve MappingConfigError si une erreur BLOQUANTE est detectee (mapping
    ambigu, doublon, type invalide, colonne de sortie non produite...).
    Retourne la liste des avertissements non bloquants.
    """
    errors: List[str] = []
    warnings: List[str] = []
    active = mc.active_rows()

    # champs obligatoires present + type valide
    for r in mc.rows:
        if r.active and not r.source_field:
            errors.append(f"Regle sans source_field (var {r.redcap_variable!r})")
        if r.active and not r.redcap_variable:
            errors.append(f"Regle active sans redcap_variable ({r.source_group}|{r.source_field})")
        if mc.allowed_data_types and r.data_type and r.data_type not in mc.allowed_data_types:
            errors.append(f"data_type invalide {r.data_type!r} pour {r.redcap_variable!r}")

    # doublons de variable REDCap (actives)
    seen_var: Dict[str, MappingRow] = {}
    for r in active:
        if r.redcap_variable in seen_var:
            errors.append(f"Variable REDCap en double dans le mapping : {r.redcap_variable!r}")
        else:
            seen_var[r.redcap_variable] = r

    # doublons d'identite source (mapping ambigu : deux regles -> meme colonne)
    seen_id: Dict[tuple, MappingRow] = {}
    for r in active:
        if r.norm_identity in seen_id:
            errors.append(
                f"Mapping ambigu : deux regles pointent vers la meme identite "
                f"{r.source_group}|{r.source_field}|{r.source_occurrence}")
        else:
            seen_id[r.norm_identity] = r

    # colonnes de sortie : pas de doublon, toutes produites
    seen_out = set()
    for c in mc.output_columns:
        if c in seen_out:
            errors.append(f"Colonne de sortie en double : {c!r}")
        seen_out.add(c)

    produced = {r.redcap_variable for r in active} | set(mc.technical_variables)
    for c in mc.output_columns:
        if c not in produced:
            errors.append(
                f"Colonne de sortie non produite (ni mapping actif ni technique) : {c!r}")

    # variable active absente de la liste de sortie -> avertissement
    for r in active:
        if r.redcap_variable not in mc.output_columns:
            warnings.append(
                f"Variable {r.redcap_variable!r} mappee mais absente de redcap_output_columns.csv")

    if not mc.sites:
        warnings.append("sites_mapping.csv vide")
    if not mc.sex:
        warnings.append("sex_mapping.csv vide")
    if not mc.visits:
        warnings.append("visits_mapping.csv vide")

    if errors:
        raise MappingConfigError("Configuration de mapping invalide :\n  - "
                                 + "\n  - ".join(errors))
    return warnings


# --------------------------------------------------------------------------- #
# Resolution contre une extraction
# --------------------------------------------------------------------------- #
@dataclass
class ResolutionResult:
    resolved: Dict[str, ColumnIdentity] = field(default_factory=dict)  # redcap_var -> colonne
    unresolved: List[MappingRow] = field(default_factory=list)
    ambiguous: List[tuple] = field(default_factory=list)  # (row, [positions])

    def resolved_count(self) -> int:
        return len(self.resolved)


def resolve_columns(
    rows: Sequence[MappingRow],
    identities: Sequence[ColumnIdentity],
) -> ResolutionResult:
    """Associe chaque regle active a EXACTEMENT une colonne de l'extraction.

    - 0 correspondance  -> non resolue (bloquant seulement si `required`) ;
    - 1 correspondance  -> resolue ;
    - >1 correspondance -> ambigu (toujours bloquant).

    Le champ source_group peut etre vide : la regle est alors resolue par
    (field, occurrence) seuls, a condition que ce soit unique.
    """
    result = ResolutionResult()
    for r in rows:
        if not r.active:
            continue
        nfield = normalize(r.source_field)
        ngroup = normalize(r.source_group) if r.source_group else None
        candidates = [
            i for i in identities
            if normalize(i.field) == nfield
            and i.occurrence == r.source_occurrence
            and (ngroup is None or normalize(i.group) == ngroup)
        ]
        if len(candidates) == 1:
            result.resolved[r.redcap_variable] = candidates[0]
        elif len(candidates) == 0:
            result.unresolved.append(r)
        else:
            result.ambiguous.append((r, [c.position for c in candidates]))

    problems = []
    if result.ambiguous:
        for r, pos in result.ambiguous:
            problems.append(
                f"AMBIGU : {r.source_group}|{r.source_field}|{r.source_occurrence} "
                f"-> {r.redcap_variable} correspond aux colonnes {pos}")
    req_unresolved = [r for r in result.unresolved if r.required]
    for r in req_unresolved:
        problems.append(
            f"OBLIGATOIRE non resolue : {r.source_group}|{r.source_field}"
            f"|{r.source_occurrence} -> {r.redcap_variable}")
    if problems:
        raise MappingResolutionError(
            "Resolution du mapping impossible :\n  - " + "\n  - ".join(problems))
    return result
