# Instalador universal de 1 linea para pyiniciar en Windows (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   INSTALADOR DE PYINICIAR (pyiniciar / pyini) - WINDOWS  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$localBin = "$HOME\.local\bin"
if (-not ($env:Path -split ";" | Where-Object { $_ -eq $localBin })) {
    $env:Path = "$localBin;$env:Path"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] Instalando el motor base 'uv'..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$localBin;$env:Path"
}

Write-Host "[INFO] Instalando pyiniciar desde GitHub..." -ForegroundColor Yellow
& uv tool install --force "git+https://github.com/Luaz2021/pyiniciar.git"
& uv tool update-shell | Out-Null

Write-Host ""
Write-Host "[OK] pyiniciar (comandos: pyiniciar, pythoniniciar, pyini) instalado con exito." -ForegroundColor Green
Write-Host "[INFO] Para usarlo en esta misma ventana sin reiniciarla, ejecuta:" -ForegroundColor Cyan
Write-Host '       $env:Path = "$HOME\.local\bin;$env:Path"' -ForegroundColor White
