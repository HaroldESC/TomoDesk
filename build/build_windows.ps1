# Build de TomoDesk para Windows: PyInstaller (one-folder) + Inno Setup (.exe).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
#
# Requisitos:
#   - Python 3.12 con venv\ activado o creado (se auto-detecta venv\).
#   - Inno Setup 6 (ISCC.exe) instalado, o en PATH. Se buscan rutas comunes.
#   - pyinstaller se instala automaticamente desde build/requirements-build.txt
#     si falta.
#
# Artefactos:
#   dist\TomoDesk\                    one-folder de PyInstaller
#   dist\TomoDesk-Setup-<version>.exe instalador de Inno Setup

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-Python {
    $venvPy = Join-Path $Root "venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy) {
        return $venvPy
    }
    return "python"
}

function Get-Version {
    $init = Get-Content -LiteralPath (Join-Path $Root "src\__init__.py") -Raw
    if ($init -match '__version__\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"') {
        return $Matches[1]
    }
    throw "No se encontro __version__ en src/__init__.py"
}

function Find-ISCC {
    if (Get-Command ISCC.exe -ErrorAction SilentlyContinue) {
        return (Get-Command ISCC.exe).Source
    }
    $roots = @(
        "${env:ProgramFiles(x86)}",
        ${env:ProgramFiles},
        (Join-Path $env:LOCALAPPDATA "Programs"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages")
    )
    foreach ($root in $roots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root)) { continue }
        $cand = Get-ChildItem -LiteralPath $root -Directory -Filter "Inno Setup*" `
            -ErrorAction SilentlyContinue | ForEach-Object {
                Join-Path $_.FullName "ISCC.exe"
            }
        foreach ($c in $cand) {
            if (Test-Path -LiteralPath $c) { return $c }
        }
    }
    return $null
}

$Py = Get-Python
$Version = Get-Version
Write-Host "== Build Windows: TomoDesk $Version =="

# 1. Dependencia de build (PyInstaller)
& $Py -m pip install -q -r build/requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Fallo al instalar build deps" }

# 2. Icono + version info
& $Py build/generate_icon.py
if ($LASTEXITCODE -ne 0) { throw "Fallo generate_icon" }
& $Py build/make_version_info.py
if ($LASTEXITCODE -ne 0) { throw "Fallo make_version_info" }

# 3. PyInstaller one-folder
& $Py -m PyInstaller tomodesk.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "Fallo PyInstaller" }
if (-not (Test-Path -LiteralPath "dist\TomoDesk\TomoDesk.exe")) {
    throw "dist\TomoDesk\TomoDesk.exe no existe tras el build"
}

# 4. Inno Setup -> instalador .exe
$iscc = Find-ISCC
if (-not $iscc) {
    Write-Warning "ISCC.exe no encontrado. Instalador no generado (one-folder listo en dist\TomoDesk\)."
    Write-Warning "Instala Inno Setup 6 (https://jrsoftware.org/isinfo.php) y re-ejecuta."
} else {
    Write-Host "Inno Setup: $iscc"
    & $iscc "/DAppVersion=$Version" "build\tomodesk.iss"
    if ($LASTEXITCODE -ne 0) { throw "Fallo Inno Setup" }
}

Write-Host "== Build completado =="
Write-Host "  Version : $Version"
Write-Host "  One-dir: dist\TomoDesk\"
if ($iscc) {
    Write-Host "  Setup   : dist\TomoDesk-Setup-$Version.exe"
}