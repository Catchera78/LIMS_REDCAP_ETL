#!/usr/bin/env python3
"""Genere config/reference_schema.json a partir d'une extraction de reference.

A relancer uniquement lorsque la structure LIMS de reference change (validation
Data Manager). Usage :

    python build_reference_schema.py "chemin/vers/Extrait LIMS.xlsx"

Sans argument, utilise l'extraction de reference dans ../Doc sources/.
Le fichier original n'est jamais modifie.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers
from src.column_identity import parse_from_detection
from src.schema_guard import build_reference_schema

DEFAULT_SAMPLE = SCRIPT_DIR.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx"


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    sample = Path(argv[0]) if argv else DEFAULT_SAMPLE
    if not sample.is_file():
        print(f"[ERREUR] Extraction introuvable : {sample}", file=sys.stderr)
        return 1

    cfg = load_pipeline_config(SCRIPT_DIR / "config" / "pipeline.json")
    grid, real_sheet, engine = read_grid(
        sample, cfg["sheet_name"], cfg.get("sheet_name_fallback_contains"))
    hd = cfg["header_detection"]
    det = detect_headers(
        grid, hd["anchor_fields"], cfg["data_rows"]["identity_column_1based"],
        hd.get("max_header_scan_rows", 20), hd.get("min_anchor_matches", 2))
    identities = parse_from_detection(
        grid, det, cfg["column_identity"]["section_start_codes"])

    sg = cfg["schema_guard"]
    schema = build_reference_schema(
        identities=identities,
        sheet_name=real_sheet,
        n_columns=det.n_columns,
        required_fields=sg["required_fields"],
        required_field_keys=sg.get("required_field_keys", []),
        source=sample.name,
    )

    out = SCRIPT_DIR / sg["reference_schema_path"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    n_req = sum(1 for c in schema["columns"] if c["required"])
    print(f"[OK] Schema ecrit : {out}")
    print(f"     onglet={real_sheet!r} moteur={engine} "
          f"colonnes={schema['n_columns']} nommees={len(schema['columns'])} "
          f"obligatoires={n_req}")
    print("     Obligatoires :")
    for c in schema["columns"]:
        if c["required"]:
            print(f"       - {c['key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
