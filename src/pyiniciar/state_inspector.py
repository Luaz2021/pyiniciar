"""Inspector determinista del estado de salud del directorio y del entorno .venv."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DirectoryState(str, Enum):
    EMPTY = "EMPTY"
    CODE_WITHOUT_VENV = "CODE_WITHOUT_VENV"
    VENV_HEALTHY = "VENV_HEALTHY"
    VENV_BROKEN_OR_FOREIGN = "VENV_BROKEN_OR_FOREIGN"
    NOT_A_VENV_COLLISION = "NOT_A_VENV_COLLISION"


@dataclass
class VenvReport:
    state: DirectoryState
    reason: str
    origin_home: str | None = None
    origin_version: str | None = None
    origin_os: str | None = None
    python_files: list[Path] = field(default_factory=list)
    has_pyproject: bool = False
    has_requirements: bool = False


IGNORED_DIRS = {".venv", "venv", ".git", "__pycache__", "node_modules", ".idea", ".vscode"}


def find_project_python_files(root: Path) -> list[Path]:
    py_files: list[Path] = []
    for item in root.rglob("*.py"):
        parts = set(item.relative_to(root).parts)
        if parts & IGNORED_DIRS or any(p.startswith(".venv") for p in parts):
            continue
        py_files.append(item)
    return sorted(py_files)


def parse_pyvenv_cfg(cfg_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        content = cfg_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return data

    for line in content.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip().lower()] = value.strip()
    return data


def inspect_directory(root: Path, smoke_timeout: float = 10.0) -> VenvReport:
    root = root.resolve()
    entries = [p for p in root.iterdir() if p.name not in {".git", ".DS_Store", "Thumbs.db"}]
    py_files = find_project_python_files(root)
    has_pyproject = (root / "pyproject.toml").is_file()
    has_requirements = (root / "requirements.txt").is_file()
    venv_dir = root / ".venv"

    if not entries:
        return VenvReport(
            state=DirectoryState.EMPTY,
            reason="El directorio esta vacio.",
        )

    if not venv_dir.exists():
        if not py_files and not has_pyproject and not has_requirements:
            return VenvReport(
                state=DirectoryState.EMPTY,
                reason="No hay codigo Python ni archivos de configuracion todavia.",
            )
        return VenvReport(
            state=DirectoryState.CODE_WITHOUT_VENV,
            reason="Se encontro codigo o configuracion sin carpeta .venv.",
            python_files=py_files,
            has_pyproject=has_pyproject,
            has_requirements=has_requirements,
        )

    cfg_path = venv_dir / "pyvenv.cfg"
    if not cfg_path.is_file():
        return VenvReport(
            state=DirectoryState.NOT_A_VENV_COLLISION,
            reason="Existe una carpeta '.venv', pero no contiene 'pyvenv.cfg'. No se tocara por seguridad.",
            python_files=py_files,
            has_pyproject=has_pyproject,
            has_requirements=has_requirements,
        )

    cfg = parse_pyvenv_cfg(cfg_path)
    origin_home = cfg.get("home")
    origin_version = cfg.get("version") or cfg.get("version_info")

    win_python = venv_dir / "Scripts" / "python.exe"
    posix_python = venv_dir / "bin" / "python"

    if win_python.exists():
        origin_os = "Windows"
    elif posix_python.exists() or posix_python.is_symlink():
        origin_os = "macOS / Linux"
    else:
        origin_os = "Desconocido"

    is_windows_host = os.name == "nt"
    expected_bin = win_python if is_windows_host else posix_python

    if not expected_bin.exists():
        return VenvReport(
            state=DirectoryState.VENV_BROKEN_OR_FOREIGN,
            reason=f"El entorno .venv fue creado en {origin_os} y no coincide con tu sistema actual.",
            origin_home=origin_home,
            origin_version=origin_version,
            origin_os=origin_os,
            python_files=py_files,
            has_pyproject=has_pyproject,
            has_requirements=has_requirements,
        )

    if not origin_home or not Path(origin_home).exists():
        return VenvReport(
            state=DirectoryState.VENV_BROKEN_OR_FOREIGN,
            reason=f"La ruta base del entorno ('{origin_home}') pertenece a otra maquina o usuario.",
            origin_home=origin_home,
            origin_version=origin_version,
            origin_os=origin_os,
            python_files=py_files,
            has_pyproject=has_pyproject,
            has_requirements=has_requirements,
        )

    try:
        proc = subprocess.run(
            [str(expected_bin), "-c", "import sys; print(sys.prefix)"],
            capture_output=True,
            text=True,
            timeout=smoke_timeout,
            check=False,
        )
        if proc.returncode != 0:
            return VenvReport(
                state=DirectoryState.VENV_BROKEN_OR_FOREIGN,
                reason="El ejecutable de Python dentro de .venv fallo al arrancar.",
                origin_home=origin_home,
                origin_version=origin_version,
                origin_os=origin_os,
                python_files=py_files,
                has_pyproject=has_pyproject,
                has_requirements=has_requirements,
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return VenvReport(
            state=DirectoryState.VENV_BROKEN_OR_FOREIGN,
            reason=f"El ejecutable de .venv no respondio correctamente ({exc.__class__.__name__}).",
            origin_home=origin_home,
            origin_version=origin_version,
            origin_os=origin_os,
            python_files=py_files,
            has_pyproject=has_pyproject,
            has_requirements=has_requirements,
        )

    return VenvReport(
        state=DirectoryState.VENV_HEALTHY,
        reason="El entorno .venv esta sano y operativo.",
        origin_home=origin_home,
        origin_version=origin_version,
        origin_os=origin_os,
        python_files=py_files,
        has_pyproject=has_pyproject,
        has_requirements=has_requirements,
    )
