"""Tableau de bord console (Prompt 12).

Affichage propre et lisible pour l'utilisateur qui double-clique
RUN_LIMS_REDCAP.bat. Le detail complet reste dans le journal (fichier log) ;
la console ne montre que ce tableau de bord.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

_BAR = "=" * 42
_TITLE = "         LIMS -> REDCap MDF"
_LABEL_WIDTH = 24

STRUCTURE_MARK = {"PASS": "OK", "PASS_WITH_WARNINGS": "WARNING", "FAIL": "FAIL"}
STATUS_MARK = {"READY": "OK", "READY_WITH_WARNINGS": "WARNING", "NOT_READY": "ERROR"}


def _row(label: str, value) -> str:
    dots = "." * max(1, _LABEL_WIDTH - len(label))
    return f"{label}{dots} {value}"


@dataclass
class Dashboard:
    input_name: Optional[str] = None
    structure: str = "-"
    mapping: str = "-"
    transformation: str = "-"
    qc: str = "-"
    records_source: Optional[int] = None
    records_output: Optional[int] = None
    errors: Optional[int] = None
    warnings: Optional[int] = None
    status: str = "NOT_READY"
    output_path: Optional[str] = None
    qc_path: Optional[str] = None
    log_path: Optional[str] = None
    message: Optional[str] = None
    note: Optional[str] = None

    def set_structure(self, schema_status: Optional[str]) -> None:
        if schema_status:
            self.structure = STRUCTURE_MARK.get(schema_status, schema_status)

    def set_status(self, status: str) -> None:
        self.status = status
        self.qc = STATUS_MARK.get(status, status)

    def render(self) -> str:
        def num(v):
            return "-" if v is None else str(v)

        lines = [
            "",
            _BAR,
            _TITLE,
            _BAR,
            "",
            "Input:",
            self.input_name or "(aucun)",
            "",
            _row("Structure", self.structure),
            _row("Mapping", self.mapping),
            _row("Transformation", self.transformation),
            _row("QC", self.qc),
            "",
            _row("Records source", num(self.records_source)),
            _row("Records output", num(self.records_output)),
            _row("Errors", num(self.errors)),
            _row("Warnings", num(self.warnings)),
            "",
            "STATUS:",
            self.status,
        ]
        if self.output_path:
            lines += ["", "Output:", self.output_path]
        if self.qc_path:
            lines += ["", "QC:", self.qc_path]
        if self.log_path:
            lines += ["", "Log:", self.log_path]
        if self.note:
            lines += ["", "Note:", self.note]
        if self.message:
            lines += ["", "Message:", self.message]
        lines.append("")
        return "\n".join(lines)

    def print(self) -> None:
        print(self.render())
