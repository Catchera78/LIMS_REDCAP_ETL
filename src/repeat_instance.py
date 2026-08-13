"""Calcul de redcap_repeat_instance (Prompt 7).

Reproduit exactement la logique Stata :

    gsort patid redcap_event_name
    bys patid redcap_event_name (lims_date_reu_en_lab): gen redcap_repeat_instance = _n

soit :
  1. groupement par (patid, redcap_event_name) ;
  2. tri CHRONOLOGIQUE par lims_date_reu_en_lab (date reparsee, pas la chaine) ;
  3. numerotation 1, 2, 3...

Details fideles a Stata :
  - une date manquante est triee EN DERNIER (les valeurs manquantes Stata sont
    superieures a toute valeur) ;
  - les egalites de date sont departagees par l'ordre d'apparition (source_row)
    -> resultat DETERMINISTE (Stata, lui, laisse ces egalites arbitraires).

Un groupe de plus d'une ligne pour un meme (patid, event) produit
WARNING_MULTIPLE_RECORDS_SAME_EVENT, afin que le Data Manager verifie qu'il
s'agit bien d'une repetition attendue.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .date_parser import parse_date, DateParseError
from .transformer import Issue, SEVERITY_WARNING


def _sort_key(date_value: str, order: int,
              french_months: Optional[dict]) -> Tuple[int, int, int]:
    """Cle de tri : (present=0/manquant=1, ordinal_date, ordre_apparition)."""
    raw = (date_value or "").strip()
    if raw == "":
        return (1, 0, order)                  # manquant -> en dernier
    try:
        d = parse_date(raw, french_months)
        return (0, d.toordinal(), order)
    except DateParseError:
        return (1, 0, order)                  # date illisible -> traitee comme manquante


def assign_repeat_instances(
    records: List[dict],
    source_rows: Sequence[int],
    cfg: dict,
    french_months: Optional[dict] = None,
) -> List[Issue]:
    """Affecte redcap_repeat_instance a chaque record (mutation en place).

    Retourne la liste des avertissements (repetitions multiples).
    """
    field = cfg.get("field", "redcap_repeat_instance")
    group_by = cfg.get("group_by", ["patid", "redcap_event_name"])
    sort_by = cfg.get("sort_by", "lims_date_reu_en_lab")
    warn_spec = cfg.get("multiple_warning",
                        {"severity": SEVERITY_WARNING,
                         "error_code": "WARNING_MULTIPLE_RECORDS_SAME_EVENT"})

    # regroupement en conservant l'ordre d'apparition
    groups: Dict[tuple, List[int]] = {}
    for idx, rec in enumerate(records):
        key = tuple(rec.get(g, "") for g in group_by)
        groups.setdefault(key, []).append(idx)

    issues: List[Issue] = []
    for key, idxs in groups.items():
        # tri chronologique interne, stable par ordre d'apparition
        ordered = sorted(
            idxs,
            key=lambda i: _sort_key(records[i].get(sort_by, ""), i, french_months))
        for instance, i in enumerate(ordered, start=1):
            records[i][field] = str(instance)

        if len(idxs) > 1:
            first = min(idxs)
            patid = records[first].get("patid", "")
            event = records[first].get(group_by[-1], "")
            src = source_rows[first] if first < len(source_rows) else 0
            issues.append(Issue(
                error_code=warn_spec["error_code"],
                severity=warn_spec.get("severity", SEVERITY_WARNING),
                source_row=src,
                patid=patid,
                variable=field,
                source_value=str(len(idxs)),
                message=(f"{len(idxs)} lignes pour patid={patid} / event={event} "
                         "(repetitions a verifier)"),
            ))
    return issues
