# Roadmap

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

### v0.2 / v1.1 — Characters & interaction
- Redesigned animation system (more states, richer transitions, data-driven behaviors)
- Personality behaviors: mood-driven phrase selection and reactions
- Improved default character pack and sprite tooling
- New personality packs in the catalog

### v1.2 — Memory & context
- Better episodic summarization and recall ranking
- Tunable memory policies from the UI

### v1.3 — Packaging & distribution
- PyInstaller / Nuitka single-file builds for Windows
- Automated release workflow with pre-built binaries
- ONNX Runtime / llama.cpp backends for fully offline inference

### Backlog
- MCP integration
- Plugin/extension API for third-party characters
