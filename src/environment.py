"""Verification de l'environnement d'execution (réserve R3).

openpyxl est recommande pour lire/ecrire les .xlsx ; en son absence, le pipeline
bascule sur un repli 100 % bibliotheque standard (fonctionnel). Ce module permet
de le VERIFIER et d'en informer l'utilisateur, sans jamais bloquer le traitement.
"""
from __future__ import annotations

import importlib.util
import sys
from typing import Optional

from .excel_reader import engine_name as excel_read_engine
from . import xlsx_writer


def _available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def openpyxl_available() -> bool:
    return _available("openpyxl")


def report() -> dict:
    return {
        "python": ".".join(str(x) for x in sys.version_info[:3]),
        "openpyxl": openpyxl_available(),
        "pytest": _available("pytest"),
        "excel_read_engine": excel_read_engine(),
        "excel_write_engine": xlsx_writer.engine_name(),
    }


def advisory() -> Optional[str]:
    """Message de recommandation si openpyxl manque, sinon None (non bloquant)."""
    if not openpyxl_available():
        return ("openpyxl absent : lecture/ecriture Excel en repli bibliotheque "
                "standard (fonctionnel). Recommande sur le poste de production : "
                "pip install -r requirements.txt")
    return None


def format_report() -> str:
    r = report()
    lines = [
        "Verification de l'environnement :",
        f"  Python               : {r['python']}",
        f"  openpyxl             : {'PRESENT' if r['openpyxl'] else 'ABSENT (recommande)'}",
        f"  pytest (tests)       : {'PRESENT' if r['pytest'] else 'ABSENT'}",
        f"  Moteur lecture xlsx  : {r['excel_read_engine']}",
        f"  Moteur ecriture xlsx : {r['excel_write_engine']}",
    ]
    adv = advisory()
    if adv:
        lines.append(f"  -> {adv}")
    else:
        lines.append("  -> Environnement optimal (openpyxl present).")
    return "\n".join(lines)
