"""Motor de rescate forense de dependencias desde entornos .venv corruptos o codigo suelto."""

from __future__ import annotations

import ast
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

from pyiniciar.state_inspector import find_project_python_files

EXCLUDED_ENV_PACKAGES = {"pip", "setuptools", "wheel", "distribute", "pkg_resources", "pkg-resources"}

COMMON_IMPORT_TO_PACKAGE: dict[str, str] = {
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "jwt": "PyJWT",
    "serial": "pyserial",
    "usb": "pyusb",
    "gi": "PyGObject",
    "wx": "wxPython",
    "Crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "fitz": "PyMuPDF",
    "psycopg2": "psycopg2-binary",
    "MySQLdb": "mysqlclient",
    "OpenGL": "PyOpenGL",
    "attr": "attrs",
    "magic": "python-magic",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "telegram": "python-telegram-bot",
    "discord": "discord.py",
    "nacl": "PyNaCl",
    " dns": "dnspython",
    "dns": "dnspython",
    " socks": "PySocks",
    "socks": "PySocks",
    "websocket": "websocket-client",
    "slugify": "python-slugify",
    "babel": "Babel",
}


@dataclass
class RescuedPackage:
    name: str
    version: str | None = None

    def format_spec(self, exact: bool = True) -> str:
        if not self.version:
            return self.name
        op = "==" if exact else ">="
        return f"{self.name}{op}{self.version}"


@dataclass
class RescueResult:
    packages: list[RescuedPackage]
    discarded_transitive_count: int
    method: str  # "REQUESTED", "RECORD_AST", "AST_ONLY"


def _normalize_pkg_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def extract_project_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    py_files = find_project_python_files(root)
    local_module_names = {p.stem for p in py_files}
    for p in py_files:
        if p.parent != root:
            local_module_names.add(p.parent.name)

    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top and top not in local_module_names:
                        imports.add(top)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top and top not in local_module_names:
                    imports.add(top)
    return imports


def _find_site_packages_dirs(venv_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    win_sp = venv_dir / "Lib" / "site-packages"
    if win_sp.is_dir():
        candidates.append(win_sp)

    lib_dir = venv_dir / "lib"
    if lib_dir.is_dir():
        for child in lib_dir.glob("python*/site-packages"):
            if child.is_dir():
                candidates.append(child)
    return candidates


def _parse_metadata(dist_info: Path) -> tuple[str | None, str | None]:
    meta_file = dist_info / "METADATA"
    if not meta_file.is_file():
        return None, None

    name: str | None = None
    version: str | None = None
    try:
        for line in meta_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                break
            if line.startswith("Name:") and not name:
                name = line.partition(":")[2].strip()
            elif line.startswith("Version:") and not version:
                version = line.partition(":")[2].strip()
            if name and version:
                break
    except OSError:
        return None, None
    return name, version


def _extract_top_modules_from_dist_info(dist_info: Path) -> set[str]:
    modules: set[str] = set()
    record_file = dist_info / "RECORD"
    if record_file.is_file():
        try:
            for line in record_file.read_text(encoding="utf-8", errors="replace").splitlines():
                path_part = line.split(",")[0].strip()
                if not path_part or path_part.startswith(".."):
                    continue
                first_seg = path_part.split("/")[0].split("\\")[0]
                if first_seg.endswith(".dist-info") or first_seg.endswith(".data") or first_seg == "__pycache__":
                    continue
                if first_seg.endswith(".py"):
                    modules.add(first_seg[:-3])
                else:
                    modules.add(first_seg)
        except OSError:
            pass

    top_level_file = dist_info / "top_level.txt"
    if top_level_file.is_file():
        try:
            for line in top_level_file.read_text(encoding="utf-8", errors="replace").splitlines():
                clean = line.strip()
                if clean:
                    modules.add(clean)
        except OSError:
            pass

    return modules


def rescue_from_venv(root: Path) -> RescueResult:
    venv_dir = root / ".venv"
    sp_dirs = _find_site_packages_dirs(venv_dir)
    dist_infos: list[Path] = []
    for sp in sp_dirs:
        dist_infos.extend(sorted(sp.glob("*.dist-info")))

    all_pkgs: list[tuple[RescuedPackage, bool, set[str]]] = []
    for di in dist_infos:
        name, version = _parse_metadata(di)
        if not name or _normalize_pkg_name(name) in EXCLUDED_ENV_PACKAGES:
            continue
        has_requested = (di / "REQUESTED").is_file()
        top_mods = _extract_top_modules_from_dist_info(di)
        all_pkgs.append((RescuedPackage(name=name, version=version), has_requested, top_mods))

    requested_pkgs = [pkg for pkg, req, _ in all_pkgs if req]
    if requested_pkgs:
        discarded = len(all_pkgs) - len(requested_pkgs)
        return RescueResult(
            packages=requested_pkgs,
            discarded_transitive_count=max(0, discarded),
            method="REQUESTED",
        )

    project_imports = extract_project_imports(root)
    matched_pkgs: list[RescuedPackage] = []
    seen_names: set[str] = set()

    for pkg, _, top_mods in all_pkgs:
        norm_name = _normalize_pkg_name(pkg.name)
        if norm_name in seen_names:
            continue
        if (project_imports & top_mods) or (pkg.name in project_imports) or (norm_name.replace("-", "_") in project_imports):
            matched_pkgs.append(pkg)
            seen_names.add(norm_name)

    if matched_pkgs or all_pkgs:
        discarded = len(all_pkgs) - len(matched_pkgs)
        return RescueResult(
            packages=matched_pkgs,
            discarded_transitive_count=max(0, discarded),
            method="RECORD_AST",
        )

    return rescue_from_code_imports(root)


def rescue_from_code_imports(root: Path) -> RescueResult:
    stdlib_names: set[str] = set(getattr(sys, "stdlib_module_names", set())) | set(sys.builtin_module_names)
    raw_imports = extract_project_imports(root)
    third_party_imports = sorted(imp for imp in raw_imports if imp not in stdlib_names and not imp.startswith("_"))

    packages: list[RescuedPackage] = []
    seen: set[str] = set()
    for imp in third_party_imports:
        pkg_name = COMMON_IMPORT_TO_PACKAGE.get(imp, imp)
        norm = _normalize_pkg_name(pkg_name)
        if norm not in seen and norm not in EXCLUDED_ENV_PACKAGES:
            packages.append(RescuedPackage(name=pkg_name, version=None))
            seen.add(norm)

    return RescueResult(
        packages=packages,
        discarded_transitive_count=0,
        method="AST_ONLY",
    )


def backup_broken_venv(root: Path) -> Path:
    venv_dir = root / ".venv"
    stamp = dt.date.today().strftime("%Y%m%d")
    backup_target = root / f".venv.roto-{stamp}"
    counter = 1
    while backup_target.exists():
        counter += 1
        backup_target = root / f".venv.roto-{stamp}-{counter}"

    venv_dir.rename(backup_target)
    ensure_gitignore_rules(root)
    return backup_target


def ensure_gitignore_rules(root: Path) -> None:
    gitignore = root / ".gitignore"
    required_entries = [".venv/", ".venv.roto-*/", "__pycache__/", "*.pyc"]
    existing_text = ""
    if gitignore.is_file():
        try:
            existing_text = gitignore.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing_text = ""

    existing_lines = {line.strip() for line in existing_text.splitlines()}
    missing = [entry for entry in required_entries if entry not in existing_lines]
    if not missing:
        return

    block = "\n".join(missing) + "\n"
    if existing_text and not existing_text.endswith("\n"):
        existing_text += "\n"
    gitignore.write_text(existing_text + block, encoding="utf-8")
