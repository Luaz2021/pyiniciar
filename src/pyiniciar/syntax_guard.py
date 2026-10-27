"""Guardian de compatibilidad de sintaxis y modulos de la libreria estandar al cambiar de version de Python."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from pyiniciar.forensic_rescue import extract_project_imports
from pyiniciar.state_inspector import find_project_python_files

REMOVED_STDLIB_BY_VERSION: dict[str, tuple[int, int, str]] = {
    "asynchat": (3, 12, "Usa asyncio en su lugar."),
    "asyncore": (3, 12, "Usa asyncio en su lugar."),
    "distutils": (3, 12, "Usa setuptools o packaging."),
    "imp": (3, 12, "Usa importlib."),
    "smtpd": (3, 12, "Usa aiosmtpd."),
    "aifc": (3, 13, "Modulo multimedia legacy eliminado en Python 3.13 (PEP 594)."),
    "audioop": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "cgi": (3, 13, "Eliminado en Python 3.13. Usa urllib.parse o multipart."),
    "cgitb": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "chunk": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "crypt": (3, 13, "Eliminado en Python 3.13. Usa hashlib o bcrypt."),
    "imghdr": (3, 13, "Eliminado en Python 3.13. Usa Pillow o filetype."),
    "mailcap": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "msilib": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "nis": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "nntplib": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "ossaudiodev": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "pipes": (3, 13, "Eliminado en Python 3.13. Usa subprocess."),
    "sndhdr": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "spwd": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "sunau": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
    "telnetlib": (3, 13, "Eliminado en Python 3.13. Usa telnetlib3."),
    "uu": (3, 13, "Eliminado en Python 3.13. Usa base64."),
    "xdrlib": (3, 13, "Eliminado en Python 3.13 (PEP 594)."),
}


@dataclass
class SyntaxIssue:
    file: Path
    line: int | None
    message: str


@dataclass
class GuardReport:
    checked_files: int
    syntax_issues: list[SyntaxIssue] = field(default_factory=list)
    removed_stdlib_warnings: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.syntax_issues and not self.removed_stdlib_warnings


def verify_code_compatibility(root: Path, target_version: tuple[int, int] | None = None) -> GuardReport:
    if target_version is None:
        target_version = (sys.version_info.major, sys.version_info.minor)

    py_files = find_project_python_files(root)
    syntax_issues: list[SyntaxIssue] = []

    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            compile(source, str(py_file), "exec")
        except SyntaxError as exc:
            syntax_issues.append(
                SyntaxIssue(
                    file=py_file.relative_to(root),
                    line=exc.lineno,
                    message=exc.msg or "Error de sintaxis",
                )
            )

    imports = extract_project_imports(root)
    current_stdlib: set[str] = set(getattr(sys, "stdlib_module_names", set()))
    removed_warnings: list[str] = []

    for imp in sorted(imports):
        if imp in REMOVED_STDLIB_BY_VERSION:
            rem_major, rem_minor, hint = REMOVED_STDLIB_BY_VERSION[imp]
            if target_version >= (rem_major, rem_minor) and imp not in current_stdlib:
                removed_warnings.append(
                    f"El modulo estandar '{imp}' fue eliminado en Python {rem_major}.{rem_minor}. {hint}"
                )

    return GuardReport(
        checked_files=len(py_files),
        syntax_issues=syntax_issues,
        removed_stdlib_warnings=removed_warnings,
    )
