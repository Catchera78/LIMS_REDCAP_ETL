"""Utilitaires texte partages (normalisation, stringification de cellules).

Aucune donnee metier ici : uniquement des helpers techniques.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, date, time


def normalize(text: str) -> str:
    """Normalise une chaine pour comparaison tolerante :
    - suppression des accents,
    - casefold (minuscule agressif),
    - espaces multiples reduits, trim.

    Sert a comparer noms d'onglet et champs d'ancrage sans dependre
    des accents ou de la casse.
    """
    if text is None:
        return ""
    s = str(text)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = " ".join(s.split())
    return s


def cell_to_str(value) -> str:
    """Convertit une valeur de cellule (openpyxl ou stdlib) en chaine.

    - None -> "" ;
    - datetime/date/time -> ISO (utile seulement pour l'affichage/QC, pas
      pour la transformation qui sera traitee plus tard) ;
    - float entier (ex. 2.0) -> "2" pour eviter les artefacts d'affichage ;
    - sinon str().
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return str(value)
