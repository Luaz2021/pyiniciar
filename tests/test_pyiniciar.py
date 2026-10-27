"""Suite de pruebas unitarias para pyiniciar (state_inspector, forensic_rescue y syntax_guard)."""

from __future__ import annotations

from pathlib import Path

from pyiniciar.forensic_rescue import backup_broken_venv, rescue_from_code_imports, rescue_from_venv
from pyiniciar.state_inspector import DirectoryState, inspect_directory
from pyiniciar.syntax_guard import verify_code_compatibility


def test_empty_directory(tmp_path: Path) -> None:
    report = inspect_directory(tmp_path)
    assert report.state == DirectoryState.EMPTY


def test_not_a_venv_collision_never_touched(tmp_path: Path) -> None:
    fake_venv = tmp_path / ".venv"
    fake_venv.mkdir()
    (fake_venv / "mis_datos.txt").write_text("importante", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hola')\n", encoding="utf-8")

    report = inspect_directory(tmp_path)
    assert report.state == DirectoryState.NOT_A_VENV_COLLISION


def test_foreign_venv_from_other_user_and_forensic_rescue_requested(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("import requests\nprint('ok')\n", encoding="utf-8")
    venv_dir = tmp_path / ".venv"
    (venv_dir / "Scripts").mkdir(parents=True)
    (venv_dir / "Scripts" / "python.exe").write_text("fake", encoding="utf-8")
    (venv_dir / "pyvenv.cfg").write_text(
        "home = C:\\Users\\CompaneroInexistente\\Python311\nversion = 3.11.4\n",
        encoding="utf-8",
    )

    sp = venv_dir / "Lib" / "site-packages"
    req_di = sp / "requests-2.32.3.dist-info"
    req_di.mkdir(parents=True)
    (req_di / "METADATA").write_text("Name: requests\nVersion: 2.32.3\n\n", encoding="utf-8")
    (req_di / "REQUESTED").write_text("", encoding="utf-8")

    trans_di = sp / "urllib3-2.2.1.dist-info"
    trans_di.mkdir(parents=True)
    (trans_di / "METADATA").write_text("Name: urllib3\nVersion: 2.2.1\n\n", encoding="utf-8")

    pip_di = sp / "pip-24.0.dist-info"
    pip_di.mkdir(parents=True)
    (pip_di / "METADATA").write_text("Name: pip\nVersion: 24.0\n\n", encoding="utf-8")
    (pip_di / "REQUESTED").write_text("", encoding="utf-8")

    report = inspect_directory(tmp_path)
    assert report.state == DirectoryState.VENV_BROKEN_OR_FOREIGN
    assert report.origin_version == "3.11.4"

    rescue = rescue_from_venv(tmp_path)
    assert rescue.method == "REQUESTED"
    assert len(rescue.packages) == 1
    assert rescue.packages[0].name == "requests"
    assert rescue.packages[0].version == "2.32.3"
    assert rescue.packages[0].format_spec(exact=True) == "requests==2.32.3"
    assert rescue.packages[0].format_spec(exact=False) == "requests>=2.32.3"
    assert rescue.discarded_transitive_count == 1

    backup = backup_broken_venv(tmp_path)
    assert backup.exists()
    assert not (tmp_path / ".venv").exists()
    assert ".venv.roto-*/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")


def test_code_imports_mapping(tmp_path: Path) -> None:
    (tmp_path / "vision.py").write_text("import os\nimport cv2\nfrom bs4 import BeautifulSoup\n", encoding="utf-8")
    rescue = rescue_from_code_imports(tmp_path)
    names = [p.name for p in rescue.packages]
    assert "opencv-python" in names
    assert "beautifulsoup4" in names
    assert "os" not in names


def test_syntax_guard_detects_removed_stdlib(tmp_path: Path) -> None:
    (tmp_path / "legacy.py").write_text("import cgi\nimport distutils\nprint('legacy')\n", encoding="utf-8")
    guard = verify_code_compatibility(tmp_path, target_version=(3, 14))
    assert not guard.is_clean
    assert len(guard.removed_stdlib_warnings) == 2
