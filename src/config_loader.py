"""Chargement de la configuration du pipeline (config/pipeline.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ConfigError(Exception):
    """Erreur de configuration (fichier manquant ou cle absente)."""


def load_pipeline_config(config_path: Path) -> Dict[str, Any]:
    """Charge et valide a minima la configuration du pipeline.

    Verifie la presence des cles indispensables a l'etape Prompt 1.
    """
    config_path = Path(config_path)
    if not config_path.is_file():
        raise ConfigError(f"Fichier de configuration introuvable : {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration JSON invalide ({config_path}) : {exc}") from exc

    required = ["sheet_name", "header_detection", "data_rows", "archive"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise ConfigError(
            f"Cles de configuration manquantes dans {config_path.name} : {', '.join(missing)}"
        )

    hd = cfg["header_detection"]
    if not hd.get("anchor_fields"):
        raise ConfigError(
            "config.header_detection.anchor_fields ne doit pas etre vide "
            "(champs d'ancrage necessaires a la detection des en-tetes)."
        )
    return cfg
