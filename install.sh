#!/usr/bin/env sh
# Instalador universal de 1 linea para pyiniciar en macOS y Linux
set -e

echo "=========================================================="
echo "   INSTALADOR DE PYINICIAR (pyiniciar / pyini) - POSIX    "
echo "=========================================================="

export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "[INFO] Instalando el motor base 'uv'..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "[INFO] Instalando pyiniciar desde GitHub..."
uv tool install --force "git+https://github.com/Luaz2021/pyiniciar.git"
uv tool update-shell >/dev/null 2>&1 || true

echo ""
echo "[OK] pyiniciar (comandos: pyiniciar, pythoniniciar, pyini) instalado con exito."
echo "[INFO] Para usarlo en esta misma terminal sin reiniciarla, ejecuta:"
echo '       export PATH="$HOME/.local/bin:$PATH"'
