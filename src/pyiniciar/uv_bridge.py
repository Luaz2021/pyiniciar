"""Puente de ejecucion de uv y utilidades multiplataforma de PATH y arranque."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pyiniciar.state_inspector import find_project_python_files


def find_uv_executable() -> str:
    uv_bin = shutil.which("uv")
    if uv_bin:
        return uv_bin

    scripts_dir = Path(sys.executable).parent
    for candidate in (scripts_dir / "uv.exe", scripts_dir / "uv"):
        if candidate.is_file():
            return str(candidate)

    raise RuntimeError(
        "No se encontro el binario 'uv'. Instalalo con: pip install uv"
    )


def run_uv(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    uv_bin = find_uv_executable()
    return subprocess.run(
        [uv_bin, *args],
        cwd=str(cwd),
        text=True,
        check=check,
    )


def get_shell_path_Export_command(bin_dir: Path | None = None) -> str:
    if bin_dir is None:
        bin_dir = Path.home() / ".local" / "bin"

    if os.name == "nt":
        return f'$env:Path = "{bin_dir};$env:Path"'
    shell = os.environ.get("SHELL", "")
    if "fish" in shell:
        return f'fish_add_path "{bin_dir}"'
    return f'export PATH="{bin_dir}:$PATH"'


def detect_entry_point(root: Path, explicit_file: str | None = None) -> Path | None:
    if explicit_file:
        target = root / explicit_file
        return target if target.is_file() else None

    preferred_names = ["main.py", "app.py", "run.py", "start.py", "index.py", "server.py"]
    for name in preferred_names:
        candidate = root / name
        if candidate.is_file():
            return candidate

    for candidate in root.glob("src/*/main.py"):
        if candidate.is_file():
            return candidate

    py_files = find_project_python_files(root)
    files_with_main_guard: list[Path] = []
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                segment = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                if "__main__" in segment and "__name__" in segment:
                    files_with_main_guard.append(py_file)
                    break

    if files_with_main_guard:
        return files_with_main_guard[0]
    if len(py_files) == 1:
        return py_files[0]
    return None
