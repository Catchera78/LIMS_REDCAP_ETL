"""Configuration du logger : console (UTF-8) + fichier run_<date>.log."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def _force_utf8_stream(stream):
    """Force l'UTF-8 sur la console Windows (evite les crashs sur accents/fleche)."""
    try:
        stream.reconfigure(encoding="utf-8")  # Python 3.7+
    except Exception:  # pragma: no cover - flux non reconfigurable
        pass


def setup_logger(log_file: Path, name: str = "lims_etl",
                 level: int = logging.INFO,
                 console_level: int = logging.INFO) -> logging.Logger:
    """Cree un logger ecrivant dans log_file (detail complet) et sur la console.

    `console_level` peut etre eleve (ex. logging.CRITICAL) pour garder la console
    silencieuse : l'utilisateur ne voit alors que le tableau de bord, tout le
    detail restant dans le fichier journal.
    """
    _force_utf8_stream(sys.stdout)
    _force_utf8_stream(sys.stderr)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(console_level)
    logger.addHandler(console)

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fileh = logging.FileHandler(log_file, encoding="utf-8")
    fileh.setFormatter(fmt)
    logger.addHandler(fileh)

    return logger
