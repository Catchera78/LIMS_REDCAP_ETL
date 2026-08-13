"""Non-regression vs Golden Dataset Stata (Prompt 10).

Compare le resultat du nouvel ETL Python au fichier Stata de reference
(Ready_Data_26_08_13.csv), cellule par cellule, et produit
regression_differences.xlsx. AUCUNE difference n'est corrigee : elles sont
seulement rapportees et classees.

Cle de comparaison : patid + redcap_event_name + redcap_repeat_instance.

Classement des differences : FORMAT, DATE, TIME, MAPPING, MISSING, EXTRA, VALUE.

Usage :
    python tests/regression/compare_with_stata.py \
        [--excel <extraction.xlsx>] [--golden <Ready_Data.csv>] [--out <xlsx>]

Sans argument : extraction ../Doc sources/Extrait LIMS 26_08_05.xlsx et Golden
../Doc sources/Ready_Data_26_08_13.csv.

NOTE : l'extraction fournie (26_08_05) et le Golden (26_08_13) ne proviennent
PAS du meme run ; des ecarts de population (lignes EXTRA/MISSING) sont donc
attendus. Pour une non-regression stricte, fournir l'extraction 26_08_13.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config_loader import load_pipeline_config
from src.excel_reader import read_grid
from src.header_parser import detect_headers
from src.column_identity import parse_from_detection, find_column_by_field
from src.mapping_loader import load_all, resolve_columns
from src.transformer import Transformer, extract_data_rows
from src.repeat_instance import assign_repeat_instances
from src.text_utils import normalize
from src.date_parser import parse_date, parse_time, DateParseError, TimeParseError
from src import xlsx_writer

KEY = ("patid", "redcap_event_name", "redcap_repeat_instance")


# --------------------------------------------------------------------------- #
# Production des enregistrements Python
# --------------------------------------------------------------------------- #
def produce_python_records(excel: Path, project_root: Path
                           ) -> Tuple[List[str], List[dict]]:
    cfg = load_pipeline_config(project_root / "config" / "pipeline.json")
    grid, real, engine = read_grid(excel, cfg["sheet_name"],
                                   cfg.get("sheet_name_fallback_contains"))
    hd = cfg["header_detection"]
    det = detect_headers(grid, hd["anchor_fields"],
                         cfg["data_rows"]["identity_column_1based"],
                         hd.get("max_header_scan_rows", 20),
                         hd.get("min_anchor_matches", 2))
    ids = parse_from_detection(grid, det, cfg["column_identity"]["section_start_codes"])
    mc = load_all(cfg, project_root)
    res = resolve_columns(mc.rows, ids)
    pid = find_column_by_field(ids, cfg["data_rows"]["identity_field"])
    data_rows = extract_data_rows(grid, det.data_start_index, pid.position)
    tr = Transformer(mc, cfg["transform"]).transform(data_rows, res.resolved)
    assign_repeat_instances(tr.records, tr.source_rows,
                            cfg["transform"]["repeat_instance"],
                            cfg["transform"].get("french_months"))
    return list(mc.output_columns), tr.records, cfg


def load_golden(path: Path) -> Tuple[List[str], List[dict]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        rows = list(reader)
    header = rows[0]
    records = [dict(zip(header, r)) for r in rows[1:]]
    return header, records


# --------------------------------------------------------------------------- #
# Comparaison
# --------------------------------------------------------------------------- #
@dataclass
class RegressionResult:
    rows_stata: int = 0
    rows_python: int = 0
    columns_stata: int = 0
    columns_python: int = 0
    cells_compared: int = 0
    cells_equal: int = 0
    cells_different: int = 0
    differences: List[list] = field(default_factory=list)      # rows for DIFFERENCES sheet
    only_stata: List[tuple] = field(default_factory=list)      # keys MISSING (in Stata only)
    only_python: List[tuple] = field(default_factory=list)     # keys EXTRA (in Python only)
    class_counts: Counter = field(default_factory=Counter)


def _key(rec: dict) -> tuple:
    return tuple((rec.get(k, "") or "").strip() for k in KEY)


def classify(variable: str, stata_val: str, python_val: str,
             date_vars: set, time_vars: set, recode_vars: set) -> Optional[str]:
    a = (stata_val or "").strip()
    b = (python_val or "").strip()
    if a == b:
        return None
    if a == "" and b != "":
        return "EXTRA"          # valeur presente cote Python seulement
    if a != "" and b == "":
        return "MISSING"        # valeur presente cote Stata seulement
    # deux valeurs non vides, differentes
    if variable in date_vars:
        try:
            if parse_date(a) == parse_date(b):
                return "FORMAT"
        except DateParseError:
            pass
        return "DATE"
    if variable in time_vars:
        try:
            if parse_time(a) == parse_time(b):
                return "FORMAT"
        except TimeParseError:
            pass
        return "TIME"
    if variable in recode_vars:
        return "MAPPING"
    # artefact d'encodage : mojibake UTF-8 lu en latin-1/cp1252 cote Stata
    # (ex. "Ã©chantillon" cote Stata vs "échantillon" cote Python) -> meme contenu
    try:
        if a.encode("latin-1").decode("utf-8") == b:
            return "FORMAT"
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    if normalize(a) == normalize(b):
        return "FORMAT"
    return "VALUE"


def compare(stata_cols: Sequence[str], stata: Sequence[dict],
            python_cols: Sequence[str], python: Sequence[dict],
            cfg: dict) -> RegressionResult:
    r = RegressionResult()
    r.rows_stata = len(stata)
    r.rows_python = len(python)
    r.columns_stata = len(stata_cols)
    r.columns_python = len(python_cols)

    common_cols = [c for c in python_cols if c in set(stata_cols)]

    # types de colonnes pour le classement (charges une seule fois)
    mrows = _mapping_rows(cfg)
    date_vars = {m.redcap_variable for m in mrows if m.data_type == "date"}
    time_vars = {m.redcap_variable for m in mrows if m.data_type == "time"}
    recode_vars = (set(cfg["transform"].get("value_recodes", {}).keys())
                   | set(cfg["transform"].get("event_recodes", {}).keys()))

    stata_by_key = {_key(rec): rec for rec in stata}
    python_by_key = {_key(rec): rec for rec in python}

    for k in stata_by_key:
        if k not in python_by_key:
            r.only_stata.append(k)
            r.class_counts["MISSING"] += 1
    for k in python_by_key:
        if k not in stata_by_key:
            r.only_python.append(k)
            r.class_counts["EXTRA"] += 1

    matched = [k for k in python_by_key if k in stata_by_key]
    for k in matched:
        srec = stata_by_key[k]
        prec = python_by_key[k]
        for col in common_cols:
            r.cells_compared += 1
            sv = (srec.get(col, "") or "").strip()
            pv = (prec.get(col, "") or "").strip()
            if sv == pv:
                r.cells_equal += 1
            else:
                r.cells_different += 1
                cls = classify(col, sv, pv, date_vars, time_vars, recode_vars)
                r.class_counts[cls] += 1
                r.differences.append([k[0], k[1], k[2], col, sv, pv, cls])
    return r


def _mapping_rows(cfg: dict):
    return load_all(cfg, PROJECT_ROOT).rows


# --------------------------------------------------------------------------- #
# Rapport
# --------------------------------------------------------------------------- #
def build_report_sheets(r: RegressionResult) -> List[tuple]:
    summary = [
        ["Metric", "Valeur"],
        ["rows_stata", r.rows_stata],
        ["rows_python", r.rows_python],
        ["columns_stata", r.columns_stata],
        ["columns_python", r.columns_python],
        ["cells_compared", r.cells_compared],
        ["cells_equal", r.cells_equal],
        ["cells_different", r.cells_different],
        ["rows_matched (cle commune)", r.rows_stata - len(r.only_stata)],
        ["rows_only_stata (MISSING)", len(r.only_stata)],
        ["rows_only_python (EXTRA)", len(r.only_python)],
    ]
    class_sheet = [["classification", "count"]]
    for cls, n in sorted(r.class_counts.items(), key=lambda x: (-x[1], str(x[0]))):
        class_sheet.append([cls, n])

    diff_header = ["patid", "redcap_event_name", "redcap_repeat_instance",
                   "variable", "stata_value", "python_value", "classification"]
    diffs = [diff_header] + r.differences

    only_s = [["patid", "redcap_event_name", "redcap_repeat_instance"]] + \
             [list(k) for k in r.only_stata]
    only_p = [["patid", "redcap_event_name", "redcap_repeat_instance"]] + \
             [list(k) for k in r.only_python]

    return [
        ("SUMMARY", summary),
        ("CLASSIFICATION", class_sheet),
        ("DIFFERENCES", diffs),
        ("ROWS_ONLY_STATA", only_s),
        ("ROWS_ONLY_PYTHON", only_p),
    ]


def write_report(r: RegressionResult, path: Path) -> Path:
    return xlsx_writer.write_workbook(Path(path), build_report_sheets(r))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Non-regression vs Golden Stata.")
    ap.add_argument("--excel", type=Path,
                    default=PROJECT_ROOT.parent / "Doc sources" / "Extrait LIMS 26_08_05.xlsx")
    ap.add_argument("--golden", type=Path,
                    default=PROJECT_ROOT.parent / "Doc sources" / "Ready_Data_26_08_13.csv")
    ap.add_argument("--out", type=Path,
                    default=PROJECT_ROOT / "output" / "regression_differences.xlsx")
    args = ap.parse_args(argv)

    if not args.excel.is_file():
        print(f"[ERREUR] extraction introuvable : {args.excel}", file=sys.stderr)
        return 1
    if not args.golden.is_file():
        print(f"[ERREUR] Golden introuvable : {args.golden}", file=sys.stderr)
        return 1

    py_cols, py_records, cfg = produce_python_records(args.excel, PROJECT_ROOT)
    st_cols, st_records = load_golden(args.golden)
    r = compare(st_cols, st_records, py_cols, py_records, cfg)
    out = write_report(r, args.out)

    print("=== NON-REGRESSION vs GOLDEN STATA ===")
    print(f"  excel  : {args.excel.name}")
    print(f"  golden : {args.golden.name}")
    print(f"  rows_stata={r.rows_stata}  rows_python={r.rows_python}")
    print(f"  columns_stata={r.columns_stata}  columns_python={r.columns_python}")
    print(f"  cells_compared={r.cells_compared}  cells_equal={r.cells_equal}  "
          f"cells_different={r.cells_different}")
    print(f"  rows_only_stata (MISSING)={len(r.only_stata)}  "
          f"rows_only_python (EXTRA)={len(r.only_python)}")
    print(f"  classification={dict(r.class_counts)}")
    print(f"  rapport : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
