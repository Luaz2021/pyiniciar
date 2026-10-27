# 🚀 pyiniciar (`pyini` / `pythoniniciar`)

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Motor](https://img.shields.io/badge/Impulsado%20por-uv-DE5FE9?logo=rust&logoColor=white)
![Plataformas](https://img.shields.io/badge/OS-Windows%20%7C%20macOS%20%7C%20Linux-success)
![Politica](https://img.shields.io/badge/PRs-Cerrados%20(Solo%20Lectura)-critical)

**`pyiniciar`** (con sus alias **`pyini`** y **`pythoniniciar`**) es una herramienta CLI multiplataforma en español diseñada para eliminar por completo la fricción de crear proyectos en Python, ejecutar código sin activar entornos virtuales a mano (`npm start` para Python) y **reparar entornos `.venv` corruptos** cuando compartes carpetas por USB, ZIP de Moodle o entre distintos sistemas operativos.

---

## ⚡ Instalación en 1 Línea (Windows, macOS y Linux)

No necesitas instalar nada previamente: el instalador configura automáticamente el motor `uv` (si no lo tienes) y registra los comandos **`pyiniciar`**, **`pythoniniciar`** y **`pyini`**.

### 🪟 En Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/Luaz2021/pyiniciar/main/install.ps1 | iex
```

### 🍎🐧 En macOS o Linux (Terminal)
```bash
curl -fsSL https://raw.githubusercontent.com/Luaz2021/pyiniciar/main/install.sh | sh
```

### 📦 Alternativa vía `pip` o `uv` (si ya tienes Python instalado)
```bash
pip install git+https://github.com/Luaz2021/pyiniciar.git
# o directamente con uv:
uv tool install git+https://github.com/Luaz2021/pyiniciar.git
```

> **Nota para tu terminal abierta:** Una vez instalado, si no quieres cerrar y volver a abrir tu ventana de terminal actual, pega la línea que te mostrará el instalador en pantalla (`$env:Path = "$HOME\.local\bin;$env:Path"` en PowerShell o `export PATH="$HOME/.local/bin:$PATH"` en macOS/Linux).

---

## 🛠️ Catálogo de Comandos

Puedes usar indistinctamente **`pyini`**, **`pyiniciar`** o **`pythoniniciar`**:

| Comando corto | Equivalente largo | Qué hace exactamente |
| :--- | :--- | :--- |
| **`pyini`** | `pyiniciar` | **Modo Autopiloto:** Analiza la carpeta actual y decide automáticamente si crear, reparar o arrancar el proyecto. |
| **`pyini nuevo`** | `pyiniciar nuevo` | Crea la estructura del proyecto (`main.py`, `pyproject.toml`, `.gitignore`, `.venv`). |
| **`pyini start`** | `pyiniciar correr` | Ejecuta tu código al instante sin activar el `.venv` a mano (estilo `npm start`). |
| **`pyini add <lib>`** | `pyiniciar instalar <lib>` | Instala una o más librerías en el entorno y las guarda en `pyproject.toml`. |
| **`pyini reparar`** | `pyiniciar reparar` | Fuerza el rescate forense de un `.venv` dañado o traído por USB y lo reconstruye. |
| **`pyini estado`** | `pyiniciar estado` | Muestra una radiografía del proyecto: versión de Python, salud del `.venv` y paquetes. |
| **`pyini limpiar`** | `pyiniciar limpiar` | Borra los respaldos antiguos `.venv.roto-*` y las carpetas `__pycache__`. |

---

## 💻 Casos Prácticos en Consola

### 1. Carpeta vacía abierta en VS Code / Antigravity IDE
Abres tu carpeta vacía en el editor, abres la terminal integrada y escribes:

```text
> pyini nuevo

[INFO] Inicializando proyecto en: 'mi-proyecto'
[INFO] Python detectado en tu equipo: 3.14.5
[PREGUNTA] Que plantilla quieres usar?
  [1] Script basico (main.py limpio - Por defecto)
  [2] Estructura modular (carpeta src/ + tests/)
  [3] API Web (FastAPI + Uvicorn)
Selecciona una opcion [1]: 1

[OK] Creado pyproject.toml y .gitignore (protegiendo .venv y temporales).
[OK] Entorno virtual (.venv) creado y listo.

Para ejecutar tu proyecto escribe: pyini start
```

### 2. Instalar librerías y arrancar (`pyini add` y `pyini start`)
```text
> pyini add requests
[OK] Libreria(s) instalada(s) y registrada(s) en pyproject.toml: requests

> pyini start
[INFO] Ejecutando main.py con uv run...
-------------------------------------------------------
Hola desde mi-proyecto con pyiniciar!
```

### 3. El "Pendrive / ZIP de compañero" con `.venv` roto o de otro Sistema Operativo
Si un compañero te pasa su carpeta por USB con su `.venv` adentro (creado en otra ruta de Windows o en un Mac/Linux) y sin `requirements.txt`, solo entras a la carpeta y escribes `pyini`:

```text
> pyini

[AVISO] Se detecto una carpeta .venv, pero pertenece a otro equipo o esta corrupta:
        - Origen detectado: /Users/carlos/Python311 (macOS / Linux, Python 3.11.4)
        - Tu sistema actual: Python 3.14.5

[INFO] Iniciando rescate forense de librerias desde .venv...
[OK] Librerias principales rescatadas:
     - pandas (2.2.2)
     - matplotlib (3.9.0)
     (Se descartaron 24 sub-dependencias internas para no ensuciar tu proyecto).

[PREGUNTA] El proyecto original usaba Python 3.11 y tu tienes 3.14. Como procedemos?
  [1] Descargar y usar Python 3.11 aislado para este proyecto (100% seguro, recomendado)
  [2] Actualizar el entorno a tu Python 3.14 (verificando compatibilidad del codigo)
Selecciona una opcion [1]: 2

[INFO] Verificando compatibilidad del codigo con Python 3.14...
[OK] Sintaxis y librerias estandar verificadas en 4 archivos .py (0 errores).
[OK] Entorno antiguo respaldado en '.venv.roto-20261027' (ignorado en Git).
[OK] Nuevo entorno .venv reconstruido y listo.
```

---

## 🧠 Arquitectura Interna

1. **Inspector de Estado Determinista (`state_inspector.py`):** Verifica la identidad real de `.venv/pyvenv.cfg` (nunca toca una carpeta `.venv` que no tenga `pyvenv.cfg`), comprueba la coherencia de binarios entre SOs (`Scripts/python.exe` vs `bin/python`), audita la ruta `home` y ejecuta un smoke test con timeout de 10 segundos.
2. **Motor de Rescate Forense (`forensic_rescue.py`):** Extrae los paquetes instalados leyendo directamente `site-packages/*.dist-info` en disco sin necesitar que el binario corrupto funcione. Filtra paquetes principales mediante el estándar **PEP 376 (`REQUESTED`)** y cruce de `RECORD` con el árbol `ast` de imports para descartar sub-dependencias transitivas de otro sistema operativo.
3. **Guardián de Versión (`syntax_guard.py`):** Al actualizar de versión de Python, compila en memoria (`compile()`) sin ensuciar con `__pycache__` y verifica contra `sys.stdlib_module_names` si algún módulo de la librería estándar fue eliminado en la nueva versión (ej. `distutils`, `cgi`, `imp`).

---

## 🔒 Política de Repositorio (Open Source de Solo Lectura — No Pull Requests)

Este proyecto es **100% Open Source** bajo licencia MIT: puedes descargarlo, usarlo en tus clases o proyectos y estudiarlo libremente.

Sin embargo, **este repositorio NO acepta Pull Requests, modificaciones externas ni ramas de terceros** para garantizar la estabilidad absoluta del código y evitar que cambios externos rompan su funcionamiento. Cualquier Pull Request abierto por cuentas externas es cerrado automáticamente por el guardián de GitHub Actions.

---

## 🏆 Créditos y Arquitectura

- **Autor:** Alexander Martinez ([@Luaz2021](https://github.com/Luaz2021))
- **Motor Base:** Basado en [**`uv`**](https://github.com/astral-sh/uv) (Astral) para la gestión ultrarrápida de entornos y versiones de Python aisladas.
- **Arquitectura y Estructuración:** Estructurado por **Agent-Nova-Gemini** (con auditoría cruzada de diseño v2.1).
