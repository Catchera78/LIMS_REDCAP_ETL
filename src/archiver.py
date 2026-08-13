"""Archivage du fichier LIMS original (copie, jamais deplacement/modification)."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class ArchiveError(Exception):
    """Erreur lors de l'archivage."""


def build_run_dirs(archive_root: Path, run_date: str, subdirs: List[str]) -> Dict[str, Path]:
    """Cree archive/<run_date>/{raw,output,qc,logs} et renvoie les chemins."""
    archive_root = Path(archive_root)
    base = archive_root / run_date
    result: Dict[str, Path] = {"base": base}
    base.mkdir(parents=True, exist_ok=True)
    for sub in subdirs:
        d = base / sub
        d.mkdir(parents=True, exist_ok=True)
        result[sub] = d
    return result


def archive_original(source_file: Path, raw_dir: Path) -> Path:
    """Copie le fichier original dans raw_dir SANS le modifier.

    Utilise shutil.copy2 (preserve les metadonnees). Le fichier source reste
    intact. Retourne le chemin de la copie.
    """
    source_file = Path(source_file)
    raw_dir = Path(raw_dir)
    if not source_file.is_file():
        raise ArchiveError(f"Fichier a archiver introuvable : {source_file}")
    raw_dir.mkdir(parents=True, exist_ok=True)

    dest = raw_dir / source_file.name
    if dest.resolve() == source_file.resolve():
        raise ArchiveError(
            "La source et la destination d'archivage sont identiques : "
            "le fichier original ne doit pas etre place dans archive/."
        )
    shutil.copy2(source_file, dest)
    return dest


def today_str(date_format: str = "%Y-%m-%d") -> str:
    return datetime.now().strftime(date_format)
