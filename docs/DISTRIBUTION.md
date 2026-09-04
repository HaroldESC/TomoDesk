# TomoDesk — Plan de Distribución

> Estrategia y procedimientos para distribuir TomoDesk a distintos tipos de usuario y plataformas.

## Decisiones tomadas (2026-08-28)

1. **Formato Linux inicial**: AppImage (un único archivo portátil, sin instalación ni sandbox).
2. **LLM embebido (llama.cpp)**: descarga del modelo en el primer arranque. Un único binario; el modelo GGUF es un dato opcional, no código.
3. **Embeddings ONNX**: migración a ONNX Runtime antes del primer release para reducir el binario de ~2.2GB a ~500MB.

## Principios

- **1 binario + modelo como dato opcional.** No se mantienen varios builds de código:

  | Perfil | Qué es | Cómo se entrega |
  |---|---|---|
  | dev / avanzado | Fuente completa | Repositorio + `venv` |
  | estándar | Binario único | Ofrece descargar el modelo al primer arranque o usar Ollama/OpenAI |
  | full | Binario + modelo | Same binary; asset "full" (zip) coloca el `.gguf` en `data/models/` |

- **GitHub Releases como hub único** de artefactos (exe Windows, AppImage, asset full, tarball de fuente).
- **No subir pesos a Git**:
  - Embeddings ONNX: los entrega ChromaDB (`DefaultEmbeddingFunction`, descarga automática ~90MB en `~/.cache/chroma`).
  - LLM llama3.2:1b: GGUF Q4_K_M (~800MB) hosteado en HuggingFace. Licencia de Comunidad Llama (no MIT), distinta de la del repo.
- **Un solo repositorio** para todas las plataformas; los retos de Linux se abordan de forma incremental.

## Distribución por tipo de usuario

| Usuario | Forma | Canal |
|---|---|---|
| Dev / avanzado | Repo + venv | GitHub |
| Windows | `.exe` (PyInstaller + Inno Setup) | GitHub Releases |
| Linux | AppImage | GitHub Releases |
| Fedora nativo (futuro) | RPM vía COPR | COPR |
| Tienda (futuro) | Flatpak | Flathub |

## Fases

### Fase 0 — Migración de embeddings a ONNX ✅ (2026-08-28)

Hecho:
- Reemplazado `_SentenceTransformerEmbedding` por la función ONNX de ChromaDB (`DefaultEmbeddingFunction`, all-MiniLM-L6-v2 ONNX, 384 dims) manteniendo la LRU cache del módulo (`src/memory/chroma_manager.py`).
- Eliminado `torch` y `sentence-transformers` de `requirements.txt`.
- Impacto: binario de ~2.2GB a ~500MB. Vectores equivalentes (mismo modelo), colecciones existentes siguen válidas.

### Fase 1 — Resolver rutas y recursos ✅ (2026-08-30)

Hecho (`src/config/paths.py`):
- Separados recursos de solo lectura (`resource_dir()` → bundle en empaquetado) de datos del usuario (`user_data_dir()`, `user_config_dir()`; Windows `%LOCALAPPDATA%`/`%APPDATA%`, Linux XDG). En dev las tres bases = raíz del repo (sin cambios).
- `config.yaml` conserva rutas **relativas**; `paths.resolve(config, *keys)` las convierte al usar (política tabla en `TECHNICAL_SPEC.md` §4.6); absolutas pasan tal cual.
- Config empaquetada: `config.yaml`/`.env` en `user_config_dir()`, bootstrap desde el ejemplo embebido (`resource_dir()/config.example.yaml`).
- Packs embebidos: `bundled_dir` en `PersonalityPackManager`/`ContextPackManager` (doble origen; el usuario gana en colisión, schema de context packs cae al bundle).
- Sprite por defecto desde `resource_dir()/data/sprites`; `custom_path` resuelto contra datos de usuario. Logs → `user_data_dir()/data`. `ensure_user_dirs()` al arrancar.

### Fase 2 — PyInstaller: Windows + AppImage ✅ (2026-09-01)

Hecho:
- `tomodesk.spec` versionado (raíz): one-dir, `console=False`, `collect_all` para PySide6, keyring y tokenizers; `collect_submodules("chromadb")` + módulos de la pila de ejecución (namespace `chromadb.execution.executor` — pkgutil no lo recorre) + `collect_data_files("chromadb")` (migraciones `.sql` que chromadb carga con `importlib_resources`).
- Excluidos los pesos de la Fase 0 (`torch`, `scipy`, `sentence_transformers`, `transformers`, etc.) que chromadb intenta importar por `importlib.import_module` para su función OpenCLIP; **no** se excluye `tokenizers` (tokenizador real del modelo ONNX all-MiniLM-L6-v2).
- Recursos de solo lectura embebidos: `data/locales/`, sprites (schema + `default/`), context packs (schema + `vscode/`), personality pack `default/`, `config.example.yaml` y `tomodesk.png` (icono de ventana). Nada de datos de usuario (db, chroma_db, logs) viaja en el bundle.
- Icono programático: `build/generate_icon.py` dibuja el icono (acento `#7B85D6` + "T", estilo tray) y genera `build/assets/tomodesk.ico` (16–256px, ICO multi-PNG) y `tomodesk.png`. `build/make_version_info.py` genera `build/version_info.txt` (VSVersionInfo) desde `__version__`.
- Entry point empaquetado: el binario lanza **GUI por defecto** (poseer `--gui`); `--cli` fuerza modo consola. En modo fuente el comportamiento no cambia (`--gui` explícito sigue siendo necesario).
- Scripts de build locales: `build/build_windows.ps1` (icono → version info → PyInstaller → Inno Setup) y `build/build_unix.sh` (PyInstaller → AppDir → appimagetool). Inno Setup 6 (ISCC.exe) se auto-detecta en rutas estándar y winget.
- Validado en Windows 11 (Python 3.14 en venv): arranque GUI completo con i18n, packs, sprites, overlay, tray y ChromaDB inicializada (bbdd en `%LOCALAPPDATA%\TomoDesk\chroma_db`); degradado correcto sin Ollama. `dist\TomoDesk-Setup-1.0.0.exe` (~209 MB, LZMA2).
- `requirements-build.txt` (build, no runtime): `pyinstaller==6.22.2`.

Artefactos por build:
| Plataforma | Artefacto local |
|---|---|
| Windows | `dist\TomoDesk\` (one-folder) + `dist\TomoDesk-Setup-<version>.exe` |
| Linux | `dist\TomoDesk\` (one-folder) + `dist\TomoDesk-<version>-x86_64.AppImage` |

### Fase 3 — Provider llama.cpp + modelo descargable ✅ (2026-09-02)

Hecho:
- Nuevo provider `llama_cpp` en `create_provider` (`src/llm/llm.py`) con import perezoso de `llama-cpp-python` (wheel CPU) en `src/llm/llama_cpp.py`. Dependencia **opcional**: no está en `requirements.txt`; si falta, degrada con `LLMError`/"no instalado".
- Descarga de GGUF Q4_K_M desde HuggingFace a `data/models/` vía `src/llm/download.py` (stdlib `urllib`, sin nuevas deps, `.part` + rename).
- Descarga **manual** (decisión): comando `/model download|status|uninstall` en CLI y botón "Descargar modelo" con barra de progreso en Ajustes → LLM (QThread). No es automática.
- Config bajo `llm.llama_cpp` (`model_path`, `n_ctx`, `model_repo`, `model_file`).
- Licencia: el Llama 3.2 GGUF usa la Licencia de Comunidad Llama (no MIT); documentado en README y en el diálogo "Acerca de".
- Un único binario; el `.gguf` es un dato opcional (asset "full" lo coloca en `data/models/`); `llama-cpp-python` solo viaja en builds que lo instalen.

### Fase 4 — Job de release en CI ✅ (2026-09-03)

Hecho:
- Extendido `.github/workflows/ci.yml` con trigger por tags (`v*`) y dos jobs nuevos:
  - `release` (matrix `[windows-latest, ubuntu-22.04]`), dependiente de `test`, ejecuta `build_windows.ps1` / `build_unix.sh` y sube instalador `.exe` (Inno Setup) y `.AppImage`.
  - `publish`, dependiente de `release`, crea la GitHub Release con `softprops/action-gh-release@v2` y release notes auto-generadas.

Posteriores (opcionales): COPR, Flathub.

### Fase 5 — Gestión de versiones (2026-09-04)

La versión **SemVer** se centraliza en `src/__init__.py` (`__version__`). Todo lo demás deriva de ahí en tiempo de build: `build/version_info.txt` (lo regenera `build/make_version_info.py`), `build/tomodesk.iss` (AppVersion vía `/DAppVersion` en `build_windows.ps1`) y la GitHub Release (creada del tag `v*`).

Flujo de release:

```bash
python build/bump_version.py 1.1.0     # actualiza src/__init__.py, badges del README y version_info.txt
git commit -am "chore: Bump version to 1.1.0"
git tag -a v1.1.0
git push origin main && git push origin v1.1.0   # el tag dispara el CI release
```

- `build/bump_version.py 1.1.0`: bump en `src/__init__.py` + badges `version`/`status` del README + regenera `build/version_info.txt`. Rechaza versiones que no sean `MAJOR.MINOR.PATCH`.
- `build/bump_version.py --print`: imprime la versión actual; lo usa el guard de CI.
- **Guard de CI**: el job `release` falla si el tag (`v*`) no coincide con `v{__version__}`, evitando releases con versiones desincronizadas.
- **Criterio SemVer**: `patch` (1.0.1) solo bugs retrocompatibles; `minor` (1.1.0) funcionalidad nueva; `major` cambios incompatibles.
- Duplicados manuales a revisar en cada bump: `ROADMAP.md` (sección Released) y `docs/progress.md`.
- Los `"1.0.0"` de los manifiestos (context_pack/sprite/personality) y `min_tomodesk_version` son versiones de *esquema de packs*, no de la app: no se tocan al versionar la app.

## Gotchas conocidas

- **Wayland vs pygetwindow**: overlay / window-sitting dependen de X11; documentar "sesión X11 para máxima compatibilidad" hasta implementar soporte nativo (p.ej. KWin scripting).
- **keyring en Linux**: requiere Secret Service (KWallet/gnome-keyring); el fallback a `.env` ya existe.
- **AppImage + libfuse2**: en Fedora instalar `libfuse2`.
- **Restart/exit**: el relanzamiento usa `_restart_command()`/`_restart_process()` en `main.py` — en modo empaquetado se lanza `[sys.executable] + sys.argv[1:]` (evita duplicar la ruta del exe, que rompería `argparse`); con `CREATE_NO_WINDOW | DETACHED_PROCESS` en Windows. `os._exit` sigue tras el Popen.
- **Notificaciones de la bandeja**: se eliminó `SetCurrentProcessExplicitAppUserModelID` del arranque; Windows atribuye el nombre del exe ("TomoDesk") a las notificaciones en lugar del AUMID crudo.
- **Sin consolas fantasma**: `icacls` en `src/config/secure_files.py` se lanza con `creationflags=CREATE_NO_WINDOW` (de lo contrario Windows muestra una consola negra por cada ACL en el arranque).