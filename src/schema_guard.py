"""Schema Guard : comparaison de la structure d'une extraction a une reference.

Compare les identites de colonnes (voir column_identity.py) de l'extraction
courante a `config/reference_schema.json` et rend un statut :

    PASS                 structure identique a la reference
    PASS_WITH_WARNINGS   differences non bloquantes (deplacement, nouvelle
                         colonne, colonne optionnelle absente, ambiguite non
                         critique, ecart de nombre de colonnes)
    FAIL                 une variable OBLIGATOIRE est absente, ou une ambiguite
                         empeche de reconnaitre une variable obligatoire

Regles (spec section 13) :
  - deplacement de colonne          -> WARNING (non bloquant)
  - nouvelle colonne inconnue       -> WARNING
  - colonne OPTIONNELLE absente      -> WARNING
  - colonne OBLIGATOIRE absente      -> FAIL
  - identite obligatoire ambigue     -> FAIL

Aucune transformation n'est effectuee ici ; on ne fait que constater.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .text_utils import normalize
from .column_identity import ColumnIdentity

PASS = "PASS"
PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
FAIL = "FAIL"


class SchemaGuardError(Exception):
    """Erreur de chargement / generation du schema de reference."""


# --------------------------------------------------------------------------- #
# Modele de reference
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReferenceColumn:
    position: int
    group: str
    field: str
    occurrence: int
    required: bool
    raw_code: str = ""
    raw_name: str = ""

    @property
    def key(self) -> str:
        return f"{self.group} | {self.field} | {self.occurrence}"

    @property
    def norm_key(self) -> tuple:
        return (normalize(self.group), normalize(self.field), self.occurrence)


@dataclass
class ReferenceSchema:
    sheet_name: str
    n_columns: int
    columns: List[ReferenceColumn]
    source: str = ""

    def by_norm_key(self) -> Dict[tuple, ReferenceColumn]:
        return {c.norm_key: c for c in self.columns}


# --------------------------------------------------------------------------- #
# Chargement / generation
# --------------------------------------------------------------------------- #
def load_reference_schema(path: Path) -> ReferenceSchema:
    path = Path(path)
    if not path.is_file():
        raise SchemaGuardError(
            f"Schema de reference introuvable : {path}. "
            "Generez-le avec build_reference_schema.py."
        )
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cols = [
        ReferenceColumn(
            position=int(c["position"]),
            group=c["group"],
            field=c["field"],
            occurrence=int(c["occurrence"]),
            required=bool(c["required"]),
            raw_code=c.get("raw_code", ""),
            raw_name=c.get("raw_name", ""),
        )
        for c in data["columns"]
    ]
    return ReferenceSchema(
        sheet_name=data["sheet_name"],
        n_columns=int(data["n_columns"]),
        columns=cols,
        source=data.get("generated_from", ""),
    )


def _is_required(ident: ColumnIdentity,
                 required_fields_norm: set,
                 required_keys_norm: set) -> bool:
    if normalize(ident.field) in required_fields_norm:
        return True
    if (normalize(ident.group), normalize(ident.field)) in required_keys_norm:
        return True
    return False


def build_reference_schema(
    identities: Sequence[ColumnIdentity],
    sheet_name: str,
    n_columns: int,
    required_fields: Sequence[str],
    required_field_keys: Sequence[dict],
    source: str = "",
) -> dict:
    """Construit le dictionnaire du schema de reference (a serialiser en JSON).

    Seules les colonnes NOMMEES (champ non vide) sont retenues comme
    signature de structure.
    """
    req_fields_norm = {normalize(x) for x in required_fields}
    req_keys_norm = {(normalize(k["group"]), normalize(k["field"]))
                     for k in required_field_keys}
    columns = []
    for i in identities:
        if not i.field.strip():
            continue
        columns.append({
            "position": i.position,
            "group": i.group,
            "field": i.field,
            "occurrence": i.occurrence,
            "key": i.key,
            "required": _is_required(i, req_fields_norm, req_keys_norm),
            "raw_code": i.raw_code,
            "raw_name": i.raw_name,
        })
    return {
        "sheet_name": sheet_name,
        "n_columns": n_columns,
        "generated_from": source,
        "columns": columns,
    }


# --------------------------------------------------------------------------- #
# Comparaison
# --------------------------------------------------------------------------- #
@dataclass
class SchemaCheckResult:
    status: str
    sheet_name_expected: str
    sheet_name_found: str
    n_expected: int
    n_found: int
    found: List[ColumnIdentity] = field(default_factory=list)
    missing_required: List[ReferenceColumn] = field(default_factory=list)
    missing_optional: List[ReferenceColumn] = field(default_factory=list)
    new_columns: List[ColumnIdentity] = field(default_factory=list)
    moved_columns: List[Tuple[ReferenceColumn, ColumnIdentity]] = field(default_factory=list)
    ambiguous_columns: List[ColumnIdentity] = field(default_factory=list)

    @property
    def is_fail(self) -> bool:
        return self.status == FAIL

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "n_expected": self.n_expected,
            "n_found": self.n_found,
            "missing_required": [c.key for c in self.missing_required],
            "missing_optional": [c.key for c in self.missing_optional],
            "new_columns": [c.key for c in self.new_columns],
            "moved_columns": [f"{r.key} (attendu col {r.position} -> col {c.position})"
                              for r, c in self.moved_columns],
            "ambiguous_columns": [c.key for c in self.ambiguous_columns],
        }


def compare(
    current: Sequence[ColumnIdentity],
    reference: ReferenceSchema,
    sheet_name_found: Optional[str] = None,
    n_columns_found: Optional[int] = None,
) -> SchemaCheckResult:
    """Compare les identites courantes au schema de reference."""
    ref_by_key = reference.by_norm_key()

    current_named = [i for i in current if i.field.strip()]

    # detection des identites dupliquees dans l'extraction courante
    seen: Dict[tuple, ColumnIdentity] = {}
    ambiguous: List[ColumnIdentity] = []
    for i in current_named:
        if i.norm_key in seen:
            ambiguous.append(i)
        else:
            seen[i.norm_key] = i

    missing_required: List[ReferenceColumn] = []
    missing_optional: List[ReferenceColumn] = []
    moved: List[Tuple[ReferenceColumn, ColumnIdentity]] = []
    found: List[ColumnIdentity] = []

    for rc in reference.columns:
        cur = seen.get(rc.norm_key)
        if cur is None:
            (missing_required if rc.required else missing_optional).append(rc)
        else:
            found.append(cur)
            if cur.position != rc.position:
                moved.append((rc, cur))

    new_columns = [i for i in current_named if i.norm_key not in ref_by_key]

    # une ambiguite est bloquante si elle concerne une identite obligatoire
    required_keys = {rc.norm_key for rc in reference.columns if rc.required}
    ambiguous_required = any(a.norm_key in required_keys for a in ambiguous)

    if missing_required or ambiguous_required:
        status = FAIL
    elif (missing_optional or new_columns or moved or ambiguous
          or (n_columns_found is not None and n_columns_found != reference.n_columns)):
        status = PASS_WITH_WARNINGS
    else:
        status = PASS

    return SchemaCheckResult(
        status=status,
        sheet_name_expected=reference.sheet_name,
        sheet_name_found=sheet_name_found or reference.sheet_name,
        n_expected=reference.n_columns,
        n_found=n_columns_found if n_columns_found is not None else len(current_named),
        found=found,
        missing_required=missing_required,
        missing_optional=missing_optional,
        new_columns=new_columns,
        moved_columns=moved,
        ambiguous_columns=ambiguous,
    )


def log_result(result: SchemaCheckResult, logger) -> None:
    """Ecrit dans le log toutes les rubriques demandees (spec Prompt 3)."""
    logger.info("=== SCHEMA GUARD ===")
    logger.info("Onglet attendu / trouve : %s / %s",
                result.sheet_name_expected, result.sheet_name_found)
    logger.info("Expected columns : %d", result.n_expected)
    logger.info("Found columns    : %d", result.n_found)

    def _dump(label, items, level="info"):
        getattr(logger, level)("%-18s: %d", label, len(items))
        for it in items:
            getattr(logger, level)("    - %s", it)

    _dump("Missing required", [c.key for c in result.missing_required],
          "error" if result.missing_required else "info")
    _dump("Missing optional", [c.key for c in result.missing_optional])
    _dump("New columns", [c.key for c in result.new_columns])
    _dump("Moved columns",
          [f"{r.key} (col {r.position} -> {c.position})"
           for r, c in result.moved_columns])
    _dump("Ambiguous columns", [c.key for c in result.ambiguous_columns],
          "error" if result.ambiguous_columns else "info")

    lvl = "error" if result.status == FAIL else "info"
    getattr(logger, lvl)("SCHEMA STATUS    : %s", result.status)
