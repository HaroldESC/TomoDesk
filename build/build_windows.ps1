# Build de TomoDesk para Windows: PyInstaller (one-folder) + Inno Setup (.exe).
#
# Uso:
#   powershell -ExecutionPolicy Bypass -File build\build_windows.ps1 [-Standard]
#
#   (por defecto)  instala llama-cpp-python (requirements-llama.txt) antes de
#                  empaquetar, de modo que el binario incluye el provider de IA
#                  local (llama.cpp). El modelo GGUF NO se bundlea (licencia):
#                  se descarga con el asistente de primera ejecucion o desde
#                  Ajustes.
#   -Standard      NO instala llama-cpp-python: binario mas ligero que oculta la
#                  opcion de IA local en el asistente. Solo para pruebas.
#   -Full          obsoleto; equivale al comportamiento por defecto.
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

param(
    [switch]$Standard,
    [switch]$Full
)

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

# 1b. Runtime local de IA (llama-cpp-python). Por defecto SI se incluye: el
#     asistente de primera ejecucion ofrece IA local y el binario debe poder
#     servirla. -Standard genera un binario sin ella a proposito.
if ($Full -and $Standard) {
    throw "-Full y -Standard son mutuamente excluyentes"
}
if ($Full) {
    Write-Warning "-Full es obsoleto: el build con IA local es ahora el comportamiento por defecto"
}
if ($Standard) {
    Write-Host "Build estandar (-Standard): sin llama-cpp-python, la IA local se ocultara en el asistente."
} else {
    Write-Host "Instalando llama-cpp-python (provider de IA local)..."
    & $Py -m pip install -q -r requirements-llama.txt
    if ($LASTEXITCODE -ne 0) { throw "Fallo al instalar llama-cpp-python" }
    # Hace que tomodesk.spec aborte si llama_cpp no acaba en el bundle.
    $env:TOMODESK_REQUIRE_LLAMA_CPP = "1"
}

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

# 3b. Verificacion post-build del runtime local: un release no debe salir sin el
#     provider que el asistente ofrece descargar.
$llamaBundled = Test-Path -LiteralPath "dist\TomoDesk\_internal\llama_cpp"
if ($Standard) {
    if ($llamaBundled) {
        Write-Warning "-Standard pedido pero llama_cpp acabo en el bundle"
    }
} elseif (-not $llamaBundled) {
    throw "El build debia incluir la IA local pero dist\TomoDesk\_internal\llama_cpp no existe"
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
Write-Host "  IA local: $llamaBundled"
Write-Host "  One-dir: dist\TomoDesk\"
if ($iscc) {
    Write-Host "  Setup   : dist\TomoDesk-Setup-$Version.exe"
}