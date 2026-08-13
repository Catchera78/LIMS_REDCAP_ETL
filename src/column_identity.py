"""Identite metier stable des colonnes LIMS (Prompt 2).

Reconstruit, pour chaque colonne de l'onglet LIMS, une identite
    section (groupe) + champ + occurrence
a partir des DEUX lignes d'en-tete (codes / noms). Objectif : ne JAMAIS
identifier une colonne par sa position, et ne jamais utiliser un nom simple
et repete (COLDA, COLTI, Date, Heure...) comme identifiant seul.

Principe (voir docs/CURRENT_PIPELINE_AUDIT.md, sections 2 et 4) :
  - Zone echantillons (blocs MDFT) : une colonne dont le CODE (ligne des codes)
    figure dans `section_start_codes` ouvre une nouvelle SECTION
    (ex. MDFT-SAL0). Toutes les colonnes suivantes appartiennent a cette
    section jusqu'au code de section suivant. Le GROUPE d'une colonne est donc
    la section courante -> `MDFT-SAL0 | COLDA | 1`, `MDFT-SAL3 | COLDA | 1`...
  - Zone administrative (colonnes de gauche) : les bannieres de section sont
    fusionnees dans l'Excel (valeur uniquement sur la 1re colonne). On les
    reporte automatiquement (forward-fill) -> le GROUPE est la banniere
    (ex. `Reçu en Lab | Date | 1` distinct de `Capture | Date | 1`).
  - Le CHAMP est le nom (ligne des noms) ; a defaut le code brut.
  - L'OCCURRENCE est le rang (1..n) de la paire (groupe, champ) rencontree de
    gauche a droite : elle differencie d'eventuels doublons a l'interieur d'une
    meme section.

L'identite (groupe, champ, occurrence) ne depend que du CONTENU des en-tetes
et de l'ordre relatif : inserer une colonne AVANT une variable ne change pas
son identite. AUCUN mapping REDCap n'est fait ici.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .text_utils import normalize
from .header_parser import HeaderDetectionResult


class ColumnIdentityError(Exception):
    """Erreur d'identification de colonne (introuvable ou ambigue)."""


@dataclass(frozen=True)
class ColumnIdentity:
    position: int          # 1-based, POUR TRACABILITE UNIQUEMENT (jamais pour l'identite)
    group: str             # section / banniere
    field: str             # nom de champ
    occurrence: int        # rang de (group, field) de gauche a droite (1..n)
    raw_code: str = ""     # valeur brute de la ligne des codes (tracabilite)
    raw_name: str = ""     # valeur brute de la ligne des noms (tracabilite)

    @property
    def key(self) -> str:
        """Cle metier lisible et stable."""
        return f"{self.group} | {self.field} | {self.occurrence}"

    @property
    def norm_key(self) -> tuple:
        """Cle normalisee (comparaison tolerante accents/casse)."""
        return (normalize(self.group), normalize(self.field), self.occurrence)

    def as_dict(self) -> dict:
        return {
            "position": self.position,
            "group": self.group,
            "field": self.field,
            "occurrence": self.occurrence,
            "key": self.key,
            "raw_code": self.raw_code,
            "raw_name": self.raw_name,
        }


def _row(grid: List[List[str]], idx: Optional[int], n_columns: int) -> List[str]:
    """Retourne la ligne idx completee/tronquee a n_columns (cellules stripees)."""
    if idx is None or idx < 0 or idx >= len(grid):
        return [""] * n_columns
    row = list(grid[idx])
    row = [str(c).strip() for c in row]
    if len(row) < n_columns:
        row.extend([""] * (n_columns - len(row)))
    return row[:n_columns]


def parse_column_identities(
    grid: List[List[str]],
    code_row_index: Optional[int],
    name_row_index: int,
    n_columns: int,
    section_start_codes: Sequence[str],
) -> List[ColumnIdentity]:
    """Construit l'identite de chaque colonne (0..n_columns-1)."""
    code = _row(grid, code_row_index, n_columns)
    name = _row(grid, name_row_index, n_columns)

    section_norms = {normalize(s) for s in section_start_codes}

    # Report automatique (forward-fill) des bannieres de la ligne des codes,
    # utilise UNIQUEMENT tant qu'aucune section d'echantillon n'a demarre.
    banner: List[str] = []
    last = ""
    for c in range(n_columns):
        if code[c]:
            last = code[c]
        banner.append(last)

    identities: List[ColumnIdentity] = []
    seen: Dict[tuple, int] = {}
    current_section: Optional[str] = None

    for c in range(n_columns):
        raw_code = code[c]
        raw_name = name[c]

        if raw_code and normalize(raw_code) in section_norms:
            current_section = raw_code

        if current_section is not None:
            group = current_section
        else:
            group = banner[c]

        field = raw_name if raw_name else raw_code

        gk = (normalize(group), normalize(field))
        seen[gk] = seen.get(gk, 0) + 1
        occ = seen[gk]

        identities.append(ColumnIdentity(
            position=c + 1,
            group=group,
            field=field,
            occurrence=occ,
            raw_code=raw_code,
            raw_name=raw_name,
        ))
    return identities


def parse_from_detection(
    grid: List[List[str]],
    detection: HeaderDetectionResult,
    section_start_codes: Sequence[str],
) -> List[ColumnIdentity]:
    """Variante pratique a partir d'un HeaderDetectionResult."""
    return parse_column_identities(
        grid=grid,
        code_row_index=detection.code_row_index,
        name_row_index=detection.name_row_index,
        n_columns=detection.n_columns,
        section_start_codes=section_start_codes,
    )


def find_column(
    identities: Sequence[ColumnIdentity],
    group: str,
    field: str,
    occurrence: int = 1,
) -> ColumnIdentity:
    """Localise une colonne par son identite metier (tolerant accents/casse).

    Leve ColumnIdentityError si 0 ou >1 correspondance (jamais de choix
    silencieux d'une mauvaise variable).
    """
    target = (normalize(group), normalize(field), occurrence)
    matches = [i for i in identities if i.norm_key == target]
    if not matches:
        raise ColumnIdentityError(
            f"Colonne introuvable : {group} | {field} | {occurrence}"
        )
    if len(matches) > 1:
        pos = ", ".join(str(m.position) for m in matches)
        raise ColumnIdentityError(
            f"Colonne ambigue : {group} | {field} | {occurrence} "
            f"correspond a plusieurs positions ({pos})"
        )
    return matches[0]


def find_column_by_field(
    identities: Sequence[ColumnIdentity],
    field: str,
    occurrence: int = 1,
) -> ColumnIdentity:
    """Localise une colonne par son seul nom de champ (tolerant accents/casse).

    Utile pour un champ globalement unique (ex. 'ID de Participant'). Leve
    ColumnIdentityError si 0 ou >1 correspondance -> jamais de choix silencieux.
    """
    target = normalize(field)
    matches = [i for i in identities
               if normalize(i.field) == target and i.occurrence == occurrence]
    if not matches:
        raise ColumnIdentityError(f"Champ introuvable : {field!r}")
    if len(matches) > 1:
        pos = ", ".join(str(m.position) for m in matches)
        raise ColumnIdentityError(
            f"Champ ambigu : {field!r} present a plusieurs positions ({pos}) ; "
            "precisez le groupe.")
    return matches[0]


def duplicate_field_keys(identities: Sequence[ColumnIdentity]) -> List[str]:
    """Retourne les cles (group|field) presentes plusieurs fois (occurrence>1).

    Informatif : signale les champs repetes a l'interieur d'une meme section
    (utile au Schema Guard / QC). L'occurrence garantit malgre tout l'unicite
    de la cle complete.
    """
    counts: Dict[str, int] = {}
    for i in identities:
        gk = f"{normalize(i.group)}|{normalize(i.field)}"
        counts[gk] = counts.get(gk, 0) + 1
    return sorted(k for k, n in counts.items() if n > 1)


def to_records(identities: Sequence[ColumnIdentity]) -> List[dict]:
    return [i.as_dict() for i in identities]
