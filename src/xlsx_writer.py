"""Ecriture d'un classeur XLSX multi-feuilles.

Strategie a deux niveaux (comme excel_reader) :
  1. openpyxl si disponible (recommande) ;
  2. sinon, repli 100 % bibliotheque standard (zipfile + XML, chaines inline).

Le repli produit un .xlsx valide (ouvrable par Excel et par excel_reader).
Une "feuille" = (nom, lignes) ; une ligne = liste de valeurs (str/int/float).
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List, Sequence, Tuple, Union
from xml.sax.saxutils import escape

Cell = Union[str, int, float, None]
Sheet = Tuple[str, List[List[Cell]]]

try:
    import openpyxl  # type: ignore
    _HAVE_OPENPYXL = True
except Exception:  # pragma: no cover
    _HAVE_OPENPYXL = False


def _col_letter(idx0: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA ..."""
    s = ""
    n = idx0 + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def _safe_sheet_name(name: str, used: set) -> str:
    # Excel : <= 31 caracteres, sans []:*?/\
    clean = "".join(c for c in str(name) if c not in "[]:*?/\\")[:31] or "Feuille"
    base = clean
    i = 1
    while clean.lower() in used:
        suffix = f"_{i}"
        clean = base[:31 - len(suffix)] + suffix
        i += 1
    used.add(clean.lower())
    return clean


def write_workbook(path: Path, sheets: Sequence[Sheet]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if _HAVE_OPENPYXL:
        return _write_openpyxl(path, sheets)
    return _write_stdlib(path, sheets)


def _write_openpyxl(path: Path, sheets: Sequence[Sheet]) -> Path:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    used = set()
    for name, rows in sheets:
        ws = wb.create_sheet(title=_safe_sheet_name(name, used))
        for row in rows:
            ws.append(["" if c is None else c for c in row])
    wb.save(path)
    return path


# --------------------------- repli bibliotheque standard ------------------- #
_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _is_number(v: Cell) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cell_xml(ref: str, value: Cell) -> str:
    if value is None or value == "":
        return f'<c r="{ref}"/>'
    if _is_number(value):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(rows: List[List[Cell]]) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetData>']
    for r, row in enumerate(rows, start=1):
        cells = "".join(_cell_xml(f"{_col_letter(c)}{r}", val)
                        for c, val in enumerate(row))
        out.append(f'<row r="{r}">{cells}</row>')
    out.append('</sheetData></worksheet>')
    return "".join(out)


def _write_stdlib(path: Path, sheets: Sequence[Sheet]) -> Path:
    used = set()
    named = [(_safe_sheet_name(n, used), rows) for n, rows in sheets]
    n = len(named)

    overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, n + 1))
    content_types = _CT.format(sheet_overrides=overrides)

    sheet_tags = "".join(
        f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (name, _) in enumerate(named, start=1))
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                f'<sheets>{sheet_tags}</sheets></workbook>')

    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(
                f'<Relationship Id="rId{i}" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, n + 1))
            + '</Relationships>')

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        for i, (_, rows) in enumerate(named, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet_xml(rows))
    return path


def engine_name() -> str:
    return "openpyxl" if _HAVE_OPENPYXL else "stdlib"
