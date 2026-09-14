# Roadmap

## Released: v1.4.1

- Fix `RuntimeError` when closing the setup wizard after a background worker
  finished, and stop logging missing-placeholder errors for wizard
  translations. See `CHANGELOG.md` for details.

## Released: v1.4.0

- First-run setup wizard (`SetupWizard`) to choose between local AI
  (llama.cpp), an external API, or postpone.
- Local option displays the recommended GGUF model, probes its remote size and
  downloads it with progress and cancellation; the external option validates
  the endpoint/model and stores the API key in the OS keyring.
- `-Full` / `--full` build variants that bundle the `llama-cpp-python` runtime.

## Released: v1.3.0

- Window icon falls back to `build/assets/tomodesk.png` in development mode
  instead of showing a generic square.
- Settings sidebar navigation-width test made stable across platform font
  metrics.

## Released: v1.2.0

- Character name is defined by the active personality pack, with a
  `resolve_pack()` helper for legacy/misaligned configs.
- Unified Tomo/TomoDesk identity: default character name is "Tomo" and the
  About dialog reads the real version dynamically.

## Released: v1.1.0

- Packaging and distribution: PyInstaller one-dir builds with Inno Setup
  (Windows) and AppImage (Linux), plus a tag-triggered release job in CI.
- Embedded llama.cpp provider (`llama-cpp-python`, optional) with on-demand
  GGUF model download from HuggingFace.
- SemVer versioning centralized in `src/__init__.py` and a `bump_version.py`
  script.
- Windows build fixes (restart action, tray notifications, console flash) and
  Windows-aware `auto` language detection.

## Released: v1.0.0

- Conversational AI with local LLMs (Ollama / OpenAI-compatible: LM Studio, vLLM, Jan)
- Multi-level memory: short-term, mid-term (SQLite), long-term and episodic (ChromaDB)
- OS event monitoring (active window, idle time, CPU/RAM) and proactive comments
- Emotional state system (happiness, energy, curiosity, closeness, connection)
- Animated 2D character overlay with speech bubbles, audio-reactive dancing, and window-sitting
- Personality packs (ZIP/directory) and default character pack
- Notes, reminders, and semantic search
- System tray integration and bilingual UI (EN/ES)

## Planned

### Next

- Better episodic summarization and recall ranking, plus tunable memory
  policies from the UI
- Mood-driven phrase selection and richer animation states/transitions
- More personality packs in the catalog and improved sprite tooling

### Backlog

- Dual-model architecture: a small always-loaded model for monitoring and
  classification plus a large on-demand model with predictive preload
- Plugin/scripting API for third-party characters, custom reactions, commands
  and desktop automation
- MCP integration
- Voice interaction (output, and optional voice cloning)
- Windows code signing (e.g. Azure Trusted Signing)
- Native Linux packaging: Fedora RPM via COPR and Flatpak on Flathub
