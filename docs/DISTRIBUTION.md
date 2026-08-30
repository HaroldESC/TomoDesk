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

### Fase 2 — PyInstaller: Windows + AppImage
- `.spec` con `collect_all` para PySide6 y binarios nativos (chromadb/duckdb/onnxruntime, keyring).
- Windows: one-folder + Inno Setup → `.exe`.
- Linux: one-folder → appimagetool → AppImage (+ `.desktop` con icono). Deps Qt ya instaladas en CI.

### Fase 3 — Provider llama.cpp + modelo descargable
- Nuevo provider `llama_cpp` en `create_provider` (`src/llm/llm.py`), import perezoso de `llama-cpp-python` (wheel CPU, versión pinneada), ruta del modelo en config.
- Descarga de GGUF Q4_K_M al primer arranque desde HuggingFace a `data/models/`.
- Un único binario; asset "full" opcional.

### Fase 4 — Job de release en CI
- Extender `.github/workflows/ci.yml` con job disparado por tag: build matrix `[windows-latest, ubuntu-22.04]` → upload a GitHub Releases.
- Posteriores (opcionales): COPR, Flathub.

## Gotchas conocidas

- **Wayland vs pygetwindow**: overlay / window-sitting dependen de X11; documentar "sesión X11 para máxima compatibilidad" hasta implementar soporte nativo (p.ej. KWin scripting).
- **keyring en Linux**: requiere Secret Service (KWallet/gnome-keyring); el fallback a `.env` ya existe.
- **AppImage + libfuse2**: en Fedora instalar `libfuse2`.
- **Restart/exit**: `sys.executable` en `main.py` y `os._exit` son compatibles con binarios congelados.