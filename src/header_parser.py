"""Detection automatique des lignes d'en-tete d'un onglet LIMS.

Fonction PURE : opere sur une grille (list[list[str]]) deja lue par
excel_reader. Aucune dependance Excel -> entierement testable.

Principe (voir docs/CURRENT_PIPELINE_AUDIT.md, section 2) :
  - l'onglet LIMS possede 3 lignes d'en-tete : titre, CODES/groupes,
    NOMS de champ ; les donnees commencent juste apres ;
  - on identifie la ligne des NOMS comme celle qui contient le plus de
    "champs d'ancrage" connus (ID de Participant, N° de Visite, Sexe...) ;
  - la ligne des CODES/groupes est la ligne juste au-dessus ;
  - une ligne est une ligne de DONNEES si sa colonne d'identite (par defaut
    la 1re) est non vide -> cela exclut le bloc de legende en bas de l'onglet.

A ce stade (Prompt 1) on ne fait AUCUN mapping metier : on decrit la structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .text_utils import normalize


class HeaderDetectionError(Exception):
    """Impossible de detecter de maniere fiable les lignes d'en-tete."""


@dataclass
class HeaderDetectionResult:
    name_row_index: int              # 0-based : ligne des NOMS de champ
    code_row_index: Optional[int]    # 0-based : ligne des CODES/groupes (ou None)
    data_start_index: int            # 0-based : 1re ligne de donnees
    n_columns: int                   # largeur (derniere colonne non vide + 1)
    n_data_rows: int                 # lignes de donnees (identite non vide)
    n_total_rows: int                # nombre total de lignes dans la grille
    matched_anchors: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name_row_index": self.name_row_index,
            "code_row_index": self.code_row_index,
            "data_start_index": self.data_start_index,
            "n_columns": self.n_columns,
            "n_data_rows": self.n_data_rows,
            "n_total_rows": self.n_total_rows,
            "matched_anchors": list(self.matched_anchors),
        }


def _last_nonempty_width(row: Sequence[str]) -> int:
    """Largeur utile d'une ligne = index de la derniere cellule non vide + 1."""
    for i in range(len(row) - 1, -1, -1):
        if str(row[i]).strip() != "":
            return i + 1
    return 0


def _count_anchor_matches(row: Sequence[str], anchors_norm: List[str]) -> List[int]:
    """Retourne les indices (dans anchors_norm) des ancres presentes dans la ligne."""
    cells_norm = {normalize(c) for c in row if str(c).strip() != ""}
    return [i for i, a in enumerate(anchors_norm) if a in cells_norm]


def detect_headers(
    grid: List[List[str]],
    anchor_fields: Sequence[str],
    identity_column_1based: int = 1,
    max_scan_rows: int = 20,
    min_anchor_matches: int = 2,
) -> HeaderDetectionResult:
    """Detecte les lignes d'en-tete et compte colonnes / lignes de donnees.

    Leve HeaderDetectionError si aucune ligne candidate ne contient assez de
    champs d'ancrage (structure inattendue) -> on ne devine jamais en silence.
    """
    if not grid:
        raise HeaderDetectionError("Grille vide : aucun contenu a analyser.")

    anchors = list(anchor_fields)
    anchors_norm = [normalize(a) for a in anchors]

    scan = min(max_scan_rows, len(grid))
    best_row = None
    best_hits: List[int] = []
    for r in range(scan):
        hits = _count_anchor_matches(grid[r], anchors_norm)
        # meilleur candidat : plus d'ancres ; a egalite, ligne la plus large
        if (len(hits) > len(best_hits)) or (
            len(hits) == len(best_hits)
            and best_row is not None
            and _last_nonempty_width(grid[r]) > _last_nonempty_width(grid[best_row])
        ):
            best_row, best_hits = r, hits

    if best_row is None or len(best_hits) < min_anchor_matches:
        raise HeaderDetectionError(
            "Ligne des noms de champ non identifiee : "
            f"{len(best_hits)} champ(s) d'ancrage trouve(s), "
            f"minimum requis = {min_anchor_matches}. "
            "La structure de l'onglet ne correspond pas a l'attendu."
        )

    name_row_index = best_row
    code_row_index = name_row_index - 1 if name_row_index > 0 else None
    data_start_index = name_row_index + 1

    # largeur : max entre ligne des noms, ligne des codes et 1re ligne de donnees
    widths = [_last_nonempty_width(grid[name_row_index])]
    if code_row_index is not None:
        widths.append(_last_nonempty_width(grid[code_row_index]))
    if data_start_index < len(grid):
        widths.append(_last_nonempty_width(grid[data_start_index]))
    n_columns = max(widths)

    id_idx = identity_column_1based - 1
    n_data_rows = 0
    for r in range(data_start_index, len(grid)):
        row = grid[r]
        cell = row[id_idx] if id_idx < len(row) else ""
        if str(cell).strip() != "":
            n_data_rows += 1

    matched = [anchors[i] for i in best_hits]
    return HeaderDetectionResult(
        name_row_index=name_row_index,
        code_row_index=code_row_index,
        data_start_index=data_start_index,
        n_columns=n_columns,
        n_data_rows=n_data_rows,
        n_total_rows=len(grid),
        matched_anchors=matched,
    )
