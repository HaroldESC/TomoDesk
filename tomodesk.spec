# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec de TomoDesk (mode one-dir).

Se genera: ``dist/TomoDesk/`` (Windows y Linux). Los recursos de solo lectura
que ``resource_dir()`` = ``sys._MEIPASS`` necesita se añaden como ``datas``.
Los datos de usuario (db, chroma_db, logs, config.yaml, .env) NO se bundlean;
se resuelven en tiempo de ejecución contra ``%APPDATA%``/``%LOCALAPPDATA%``
o los dirs XDG (ver ``src/config/paths.py``).

Uso:
    pyinstaller tomodesdk.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = []
binaries = []
hiddenimports = []

# ── PySide6 (plugins, traducciones, binarios) ──────────────────────────────
for pkg in ("PySide6",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# ── keyring + backends (import perezoso en src/config/credentials.py) ──────
for pkg in ("keyring", "keyrings"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

# ── tokenizers (Rust .pyd + datos): importado por chromadb via
# importlib.import_module en su funcion ONNX all-MiniLM-L6-v2. modulegraph no lo
# detecta, asi que se recoge explicitamente.
for pkg in ("tokenizers",):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

# ── chromadb migrations (*.sql): cargados en runtime con importlib_resources,
# que modulegraph no ve. Se recogen todos los datos no Python del paquete.
try:
    datas += collect_data_files("chromadb")
except Exception:
    pass

# ── Importaciones perezosas (dentro de funciones) que modulegraph no ve ─────
hiddenimports += collect_submodules("chromadb") + [
    "chromadb.utils.embedding_functions",   # DefaultEmbeddingFunction (ONNX)
    "onnxruntime",                          # embebido/dependencia de chromadb
    "numpy",                                # chroma_manager._OnnxEncoder
    "huggingface_hub",                      # descarga del modelo ONNX
    "openai",                               # create_provider -> OpenAI
    "jsonschema",                           # validacion de packs/sprites
    # chromadb.execution.executor/ es un namespace package (sin __init__.py):
    # pkgutil.walk_packages no lo recorre y modulegraph no lo ve. Se listan los
    # modulos de la pila de ejecucion que chromadb instancia por string.
    "chromadb.execution.executor.abstract",
    "chromadb.execution.executor.local",
    "chromadb.execution.executor.distributed",
    "chromadb.segment.impl.manager.local",
    "chromadb.segment.impl.vector.local_hnsw",
    "chromadb.segment.impl.vector.local_persistent_hnsw",
    "chromadb.segment.impl.metadata.sqlite",
]
hiddenimports = sorted(set(hiddenimports))

# ── Excluidos (migracion Fase 0): chromadb importa torch/sentence-transformers
# via importlib.import_module("torch") para su function OpenCLIP, que no usamos.
# Excluirlos garantiza un bundle ~500MB aunque el entorno de build lo tenga.
# NOTA: "tokenizers" es dependencia real de chromadb (tokenizador del modelo
# ONNX all-MiniLM-L6-v2) y NO se excluye.
_EXCLUDES = [
    "torch",
    "torchvision",
    "torchaudio",
    "scipy",
    "sentence_transformers",
    "transformers",
    "tensorboard",
    "open_clip_torch",
    "tiktoken",
]

# ── Recursos de solo lectura embebidos en el bundle ─────────────────────────
# Los relativos coinciden con la politica de `_PATH_POLICY` en paths.py.
_RESOURCES = [
    ("config.example.yaml", "."),
    ("build/assets/tomodesk.png", "."),
    ("data/locales", "data/locales"),
    ("data/sprites/schema.json", "data/sprites"),
    ("data/sprites/default", "data/sprites/default"),
    ("data/context_packs/schema.json", "data/context_packs"),
    ("data/context_packs/vscode", "data/context_packs/vscode"),
    ("data/personality_packs/default", "data/personality_packs/default"),
]
for src, dst in _RESOURCES:
    if os.path.exists(src):
        datas.append((src, dst))

# ── Metadatos de version (Windows) ──────────────────────────────────────────
_version_info = "build/version_info.txt"
version = _version_info if os.path.exists(_version_info) else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TomoDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="build/assets/tomodesk.ico" if os.name == "nt" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TomoDesk",
)