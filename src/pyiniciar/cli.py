"""Interfaz de linea de comandos en espanol para pyiniciar (alias: pythoniniciar, pyini)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pyiniciar import __version__
from pyiniciar.forensic_rescue import (
    backup_broken_venv,
    ensure_gitignore_rules,
    rescue_from_code_imports,
    rescue_from_venv,
)
from pyiniciar.state_inspector import DirectoryState, inspect_directory
from pyiniciar.syntax_guard import verify_code_compatibility
from pyiniciar.uv_bridge import detect_entry_point, get_shell_path_Export_command, run_uv


def _ask(prompt: str, default: str = "1", non_interactive: bool = False) -> str:
    if non_interactive or not sys.stdin.isatty():
        return default
    try:
        ans = input(f"{prompt} [{default}]: ").strip()
        return ans if ans else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def _extract_major_minor(version_str: str | None) -> str | None:
    if not version_str:
        return None
    parts = version_str.strip().split(".")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{parts[1]}"
    return None


def cmd_nuevo(target_dir: Path, non_interactive: bool = False) -> int:
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    project_name = target_dir.name

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"[INFO] Inicializando proyecto en: '{project_name}'")
    print(f"[INFO] Python detectado en tu equipo: {py_ver}")
    print("[PREGUNTA] Que plantilla quieres usar?")
    print("  [1] Script basico (main.py limpio - Por defecto)")
    print("  [2] Estructura modular (carpeta src/ + tests/)")
    print("  [3] API Web (FastAPI + Uvicorn)")
    choice = _ask("Selecciona una opcion", default="1", non_interactive=non_interactive)

    run_uv(["init", "--no-workspace", "--vcs", "git"], cwd=target_dir, check=False)
    ensure_gitignore_rules(target_dir)

    main_file = target_dir / "main.py"
    if choice == "2":
        pkg_name = project_name.lower().replace("-", "_").replace(" ", "_")
        pkg_dir = target_dir / "src" / pkg_name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text('"""Modulo principal."""\n', encoding="utf-8")
        (pkg_dir / "main.py").write_text(
            f'def main() -> None:\n    print("Proyecto modular {project_name} activo.")\n\n\nif __name__ == "__main__":\n    main()\n',
            encoding="utf-8",
        )
        tests_dir = target_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        (tests_dir / "test_base.py").write_text("def test_ok() -> None:\n    assert True\n", encoding="utf-8")
    elif choice == "3":
        main_file.write_text(
            'from fastapi import FastAPI\nimport uvicorn\n\napp = FastAPI(title="'
            + project_name
            + '")\n\n\n@app.get("/")\ndef raiz() -> dict[str, str]:\n    return {"estado": "ok", "proyecto": "'
            + project_name
            + '"}\n\n\nif __name__ == "__main__":\n    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)\n',
            encoding="utf-8",
        )
        run_uv(["add", "fastapi", "uvicorn"], cwd=target_dir, check=False)
    else:
        if not main_file.exists():
            main_file.write_text(
                f'def main() -> None:\n    print("Hola desde {project_name} con pyiniciar!")\n\n\nif __name__ == "__main__":\n    main()\n',
                encoding="utf-8",
            )

    run_uv(["venv"], cwd=target_dir, check=False)
    print("[OK] Creado pyproject.toml y .gitignore (protegiendo .venv y temporales).")
    print("[OK] Entorno virtual (.venv) creado y listo.")
    print("\nPara ejecutar tu proyecto escribe: pyini start")
    return 0


def cmd_reparar(root: Path, non_interactive: bool = False) -> int:
    report = inspect_directory(root)
    local_mm = f"{sys.version_info.major}.{sys.version_info.minor}"

    if report.state == DirectoryState.NOT_A_VENV_COLLISION:
        print(f"[ALERTA] {report.reason}")
        return 1

    if report.state == DirectoryState.VENV_BROKEN_OR_FOREIGN:
        print("[AVISO] Se detecto una carpeta .venv, pero pertenece a otro equipo o esta corrupta:")
        print(f"        - Motivo: {report.reason}")
        if report.origin_home:
            print(f"        - Origen detectado: {report.origin_home} ({report.origin_os}, Python {report.origin_version or '?'})")
        print(f"        - Tu sistema actual: Python {sys.version.split()[0]}")

        print("\n[INFO] Iniciando rescate forense de librerias desde .venv...")
        rescue = rescue_from_venv(root)
        if rescue.packages:
            print("[OK] Librerias principales rescatadas:")
            for pkg in rescue.packages:
                ver_label = f" ({pkg.version})" if pkg.version else ""
                print(f"     - {pkg.name}{ver_label}")
            if rescue.discarded_transitive_count > 0:
                print(
                    f"     (Se descartaron {rescue.discarded_transitive_count} sub-dependencias internas para no ensuciar tu proyecto)."
                )
        else:
            print("[INFO] No se detectaron librerias externas instaladas en el .venv antiguo.")

        origin_mm = _extract_major_minor(report.origin_version)
        exact_pins = True
        selected_python = local_mm

        if origin_mm and origin_mm != local_mm:
            print(f"\n[PREGUNTA] El proyecto original usaba Python {origin_mm} y tu tienes {local_mm}. Como procedemos?")
            print(f"  [1] Descargar y usar Python {origin_mm} aislado para este proyecto (100% seguro, recomendado)")
            print(f"  [2] Actualizar el entorno a tu Python {local_mm} (verificando compatibilidad del codigo)")
            ans = _ask("Selecciona una opcion", default="1", non_interactive=non_interactive)
            if ans == "2":
                exact_pins = False
                selected_python = local_mm
                print(f"\n[INFO] Verificando compatibilidad del codigo con Python {local_mm}...")
                guard = verify_code_compatibility(root)
                if guard.is_clean:
                    print(f"[OK] Sintaxis y librerias estandar verificadas en {guard.checked_files} archivos .py (0 errores).")
                else:
                    for issue in guard.syntax_issues:
                        print(f"[AVISO] Error de sintaxis en {issue.file}:{issue.line} -> {issue.message}")
                    for warn in guard.removed_stdlib_warnings:
                        print(f"[AVISO] {warn}")
            else:
                exact_pins = True
                selected_python = origin_mm

        backup_path = backup_broken_venv(root)
        print(f"[OK] Entorno antiguo respaldado en '{backup_path.name}' (ignorado en Git).")

        if not (root / "pyproject.toml").is_file():
            run_uv(["init", "--no-workspace", "--python", selected_python], cwd=root, check=False)

        run_uv(["venv", "--python", selected_python], cwd=root, check=False)
        specs = [pkg.format_spec(exact=exact_pins) for pkg in rescue.packages]
        if specs:
            run_uv(["add", *specs], cwd=root, check=False)
        elif (root / "requirements.txt").is_file():
            run_uv(["pip", "install", "-r", "requirements.txt"], cwd=root, check=False)
        else:
            run_uv(["sync"], cwd=root, check=False)

        print("[OK] Nuevo entorno .venv reconstruido y listo.")
        print("\nTodo listo. Escribe 'pyini start' para arrancar.")
        return 0

    if report.state == DirectoryState.CODE_WITHOUT_VENV:
        print("[INFO] Codigo Python detectado sin entorno virtual (.venv).")
        if report.has_pyproject:
            print("[INFO] Encontrado pyproject.toml. Sincronizando entorno con uv...")
            run_uv(["sync"], cwd=root, check=False)
            print("[OK] Proyecto listo para correr con 'pyini start'.")
            return 0
        if report.has_requirements:
            print("[INFO] Encontrado requirements.txt. Creando entorno e instalando paquetes...")
            run_uv(["venv"], cwd=root, check=False)
            run_uv(["pip", "install", "-r", "requirements.txt"], cwd=root, check=False)
            print("[OK] Proyecto listo para correr con 'pyini start'.")
            return 0

        rescue = rescue_from_code_imports(root)
        if rescue.packages:
            names = [p.name for p in rescue.packages]
            print(f"[INFO] Librerias externas detectadas en los archivos .py: {', '.join(names)}")
            ans = _ask("Quieres crear el entorno e instalarlas automaticamente? (s/n)", default="s", non_interactive=non_interactive)
            run_uv(["init", "--no-workspace"], cwd=root, check=False)
            run_uv(["venv"], cwd=root, check=False)
            if ans.lower().startswith("s") or ans.lower().startswith("y"):
                run_uv(["add", *names], cwd=root, check=False)
        else:
            run_uv(["init", "--no-workspace"], cwd=root, check=False)
            run_uv(["venv"], cwd=root, check=False)

        ensure_gitignore_rules(root)
        print("[OK] Entorno .venv creado. Escribe 'pyini start' para arrancar.")
        return 0

    print("[OK] El entorno .venv ya esta sano y listo para usarse.")
    return 0


def cmd_start(root: Path, explicit_file: str | None = None, extra_args: list[str] | None = None) -> int:
    report = inspect_directory(root)
    if report.state in {DirectoryState.VENV_BROKEN_OR_FOREIGN, DirectoryState.CODE_WITHOUT_VENV}:
        cmd_reparar(root)

    entry = detect_entry_point(root, explicit_file)
    if not entry:
        print("[ERROR] No se encontro ningun archivo .py principal para ejecutar.")
        print("        Crea un 'main.py' o especifica el archivo: pyini start mi_archivo.py")
        return 1

    rel_entry = entry.relative_to(root) if entry.is_relative_to(root) else entry
    print(f"[INFO] Ejecutando {rel_entry} con uv run...")
    print("-" * 55)
    cmd = ["run", str(entry)]
    if extra_args:
        cmd.extend(extra_args)
    proc = run_uv(cmd, cwd=root, check=False)
    return proc.returncode


def cmd_add(root: Path, packages: list[str]) -> int:
    if not packages:
        print("[ERROR] Indica al menos una libreria. Ejemplo: pyini add requests")
        return 1
    if not (root / "pyproject.toml").is_file():
        run_uv(["init", "--no-workspace"], cwd=root, check=False)
    ensure_gitignore_rules(root)
    proc = run_uv(["add", *packages], cwd=root, check=False)
    if proc.returncode == 0:
        print(f"[OK] Libreria(s) instalada(s) y registrada(s) en pyproject.toml: {', '.join(packages)}")
    return proc.returncode


def cmd_estado(root: Path) -> int:
    report = inspect_directory(root)
    print("=======================================================")
    print(f"   ESTADO DEL PROYECTO ({root.name}) - pyiniciar v{__version__}")
    print("=======================================================")
    print(f"  Estado general : {report.state.value}")
    print(f"  Detalle        : {report.reason}")
    print(f"  Archivos .py   : {len(report.python_files)}")
    print(f"  pyproject.toml : {'Si' if report.has_pyproject else 'No'}")
    print(f"  requirements   : {'Si' if report.has_requirements else 'No'}")
    if report.origin_version or report.origin_os:
        print(f"  Venv detectado : Python {report.origin_version or '?'} ({report.origin_os or '?'})")
    print("=======================================================")
    return 0


def cmd_limpiar(root: Path) -> int:
    removed = 0
    for item in root.glob(".venv.roto-*"):
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
            print(f"[OK] Eliminado respaldo antiguo: {item.name}")
            removed += 1
    for pycache in root.rglob("__pycache__"):
        if pycache.is_dir() and ".venv" not in pycache.parts:
            shutil.rmtree(pycache, ignore_errors=True)
            removed += 1
    print(f"[OK] Limpieza completada ({removed} elementos eliminados).")
    return 0


def print_help() -> None:
    print(
        f"""pyiniciar (alias: pythoniniciar, pyini) v{__version__}
Inicializador, diagnosticador y rescatador forense de entornos Python sobre uv.

Uso:
  pyini                      Modo autopiloto: analiza la carpeta y crea, repara o arranca.
  pyini nuevo [carpeta]      Inicializa un proyecto nuevo con plantilla interactiva.
  pyini start [archivo.py]   Ejecuta el proyecto sin activar .venv manualmente.
  pyini add <librerias...>   Instala librerias y las registra en pyproject.toml.
  pyini reparar              Rescata dependencias de un .venv roto (USB/ZIP) y lo reconstruye.
  pyini estado               Muestra una radiografia de salud del proyecto y su entorno.
  pyini limpiar              Elimina respaldos .venv.roto-* y carpetas __pycache__.

Atajo de PATH para tu terminal actual:
  {get_shell_path_Export_command()}
"""
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    non_interactive = False
    if "-y" in args or "--yes" in args:
        non_interactive = True
        args = [a for a in args if a not in {"-y", "--yes"}]

    cwd = Path.cwd()

    if not args:
        report = inspect_directory(cwd)
        if report.state == DirectoryState.EMPTY:
            return cmd_nuevo(cwd, non_interactive=non_interactive)
        if report.state in {DirectoryState.VENV_BROKEN_OR_FOREIGN, DirectoryState.CODE_WITHOUT_VENV}:
            return cmd_reparar(cwd, non_interactive=non_interactive)
        return cmd_start(cwd)

    sub = args[0].lower()
    rest = args[1:]

    if sub in {"-h", "--help", "ayuda", "help"}:
        print_help()
        return 0
    if sub in {"-v", "--version", "version"}:
        print(f"pyiniciar v{__version__}")
        return 0
    if sub in {"nuevo", "init", "new"}:
        target = cwd / rest[0] if rest else cwd
        return cmd_nuevo(target, non_interactive=non_interactive)
    if sub in {"start", "correr", "run", "ejecutar"}:
        explicit = rest[0] if rest else None
        extra = rest[1:] if len(rest) > 1 else None
        return cmd_start(cwd, explicit_file=explicit, extra_args=extra)
    if sub in {"add", "instalar", "install"}:
        return cmd_add(cwd, rest)
    if sub in {"reparar", "repair", "fix"}:
        return cmd_reparar(cwd, non_interactive=non_interactive)
    if sub in {"estado", "status", "doctor"}:
        return cmd_estado(cwd)
    if sub in {"limpiar", "clean"}:
        return cmd_limpiar(cwd)

    print(f"[ERROR] Comando desconocido: '{sub}'. Usa 'pyini ayuda' para ver la lista de comandos.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
