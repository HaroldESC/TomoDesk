# TomoDesk

> Desktop companion that merges an interactive character with an AI-powered productivity agent. Local-first, private, and customizable.

![Version](https://img.shields.io/badge/version-1.5.0-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-v1.5.0--release-yellow)
![CI](https://github.com/HaroldESC/TomoDesk/actions/workflows/ci.yml/badge.svg)

## Table of Contents

- [About](#about)
- [Prerequisites & Installation](#prerequisites--installation)
- [Usage](#usage)
- [Roadmap](ROADMAP.md)
- [Architecture](#architecture)
- [Technologies](#technologies)
- [Testing](#testing)
- [License](#license)

## About

TomoDesk is a desktop companion application that lives in your system tray and desktop overlay. It combines a conversational AI agent with an animated 2D character that reacts to your activity, helps with productivity tasks, and provides a friendly presence on your desktop.

### Key Features

- Conversational AI with local LLMs (Ollama, LM Studio, vLLM, Jan, or embedded llama.cpp)
- Multi-level memory: short-term, mid-term (SQLite), long-term and episodic (ChromaDB)
- OS event monitoring: active window, idle time, CPU/RAM usage
- Proactive comments based on system events
- Emotional state system: happiness, energy, curiosity, closeness, connection
- Notes, reminders, and semantic search
- Animated 2D character overlay with speech bubbles
- Audio-reactive dancing with beat detection (optional, requires sounddevice)
- Window-sitting: character sits on real windows (4 modes: active, mouse, closest, fixed)
- Context packs: app-aware sprite intent resolution
- Personality packs: load custom phrases and sprites from ZIP or directory
- Setup wizard: guided first-run configuration
- Privacy consent: opt-in for active window monitoring
- Credential manager: API keys stored in OS keyring (Windows Credential Manager, macOS Keychain)
- Rate limiting for LLM API calls
- ZIP validation and secure file permissions
- Singleton instance guard (prevents running two GUIs)
- System tray integration with context menu
- Bilingual: English and Spanish

## Prerequisites & Installation

### Requirements

- Python 3.12+ (Python 3.14 tested; ChromaDB may need 3.12/3.13 on some systems)
- One of:
  - [Ollama](https://ollama.com/) with a pulled model (e.g., `llama3.2:1b`)
  - An OpenAI-compatible server (LM Studio, vLLM, Jan)
  - `llama-cpp-python` (optional, CPU wheel) to run a local GGUF model embedded in the app

### Optional: embedded llama.cpp model

To use TomoDesk's self-contained local provider you need two things:

```bash
pip install -r requirements-llama.txt   # optional, pinned CPU wheel of llama-cpp-python
```

Then set `llm.provider: llama_cpp` in `config.yaml` and download a model with the
`/model download` chat command or the button in **Settings → LLM → Local model**.
The GGUF is saved to `data/models/`. See the [License](#license) note about the
default model. (`llama-cpp-python` is not part of the mandatory
`requirements.txt` so the base binary stays lean; install `requirements-llama.txt`
only if you want the embedded provider.)

### Setup

```bash
git clone https://github.com/HaroldESC/TomoDesk.git
cd TomoDesk
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

On the first run, the app auto-creates `config.yaml` from `config.example.yaml` if it is missing. To review or edit settings beforehand, copy it manually:

```bash
# Windows
Copy-Item config.example.yaml config.yaml
# macOS/Linux
cp config.example.yaml config.yaml
```

### Configuration

The default configuration lives in `config.yaml` (auto-generated from `config.example.yaml` on first run). The full schema covers 15+ sections including:

- **LLM**: provider, model, endpoint, timeout, rate limiting, llama.cpp settings
- **Memory**: short/mid/long-term toggles, ChromaDB path, episodic thresholds
- **UI**: theme, language, overlay, speech bubble, sprite, hints, sleep
- **Window-sitting**: 4 modes (active, mouse, closest, fixed), transition speed
- **Personality**: name, traits, initial emotional values
- **Personality packs**: directory, active pack
- **Context packs**: directory, active packs
- **Privacy**: consent, active window monitoring
- **Database**: SQLite path
- **Logs**: level, debug prompts
- **Modes**: proactive comments, cooldown, probability

## Usage

### CLI Mode

```bash
python main.py
```

### GUI Mode

```bash
python main.py --gui
```

### Overlay Character Mode

The overlay launches automatically with `--gui`. It provides:

- Animated character with idle, talking, happy, and sleepy animations
- Interactive speech bubble with typewriter effect
- Click to reply via inline input
- Double-click to open full chat window
- Audio-reactive dancing (enable in config)
- Window-sitting behavior

### Commands

Type `/help` in chat to see all available commands:

- `/help` — show all available commands
- `/exit`, `/quit` — exit the application
- `/clear` — clear conversation history
- `/context` — show current system prompt and context info
- `/debug [on|off]` — toggle prompt debug logging
- `/note add/list/show/delete/search` — manage notes
- `/remind in/list/cancel` — manage reminders
- `/remember importance:N <text>` — store an episodic memory
- `/memories list/search/delete/important` — browse memories
- `/proactive [on|off|focus|unfocus]` — control or view proactive comments status
- `/mood` — view emotional state
- `/episodic` — memory statistics
- `/model [status|download|uninstall|delete]` — manage the local llama.cpp GGUF model
- `/gui` — info about GUI mode

## Architecture

```
main.py                   Entry point (QThread-based async init, splash screen, singleton guard)
src/
  config/
    config.py             Configuration loader (YAML) + AppUserModelID
    paths.py              Path resolution (resource vs user/config dirs)
    credentials.py        OS keyring credential manager + .env fallback
    secure_files.py       File permission hardening (0o600 POSIX, icacls Windows)
    logging_config.py     Logging setup + SensitiveDataFilter
    i18n.py               Internationalization manager (EN/ES)
  core/
    conversation.py       Conversation engine (prompt building, LLM calls)
    context.py            Context builder for prompts
    state.py              Emotional state system (5 variables)
    events.py             OS event monitor (active window, idle, CPU/RAM)
    intents.py            Visual intent catalog (16 intents)
    visual_state_resolver.py  Intent priority resolver (agent > context > idle)
  context/
    context_pack.py       Context pack manager (app-aware sprite intents)
  llm/
    llm.py                LLM provider abstraction (Ollama, OpenAI-compatible)
    llama_cpp.py          Embedded llama.cpp provider (optional)
    download.py           GGUF model download utility
    rate_limit.py         Token-bucket rate limiter for LLM calls
    prompts.py            System prompt templates
    proactive_engine.py   Proactive comment engine (rule-based)
    proactive_policy.py   Comment trigger policies
  memory/
    memory.py             Memory manager (short-term, mid-term, long-term)
    chroma_manager.py     ChromaDB client (long-term + episodic memory)
    database.py           SQLite client (notes, reminders, interaction log)
    episodic_summarizer.py LLM-based episodic summarization
    episodic_utils.py     Milestone detection + memory suggestion helpers
  system/
    commands.py           Chat command handlers
    reminder_checker.py   Background reminder checker
    window_manager.py     Window detection for window-sitting
  personality/
    comment_loader.py     Comment YAML loader
    personality_pack.py   Personality pack loader (ZIP/directory)
    zip_security.py       ZIP archive validation (path traversal, manifest check)
  gui/
    windows/
      main_window.py      Main chat window (PySide6)
      overlay_window.py   Transparent overlay character window
      settings_dialog.py  Settings dialog (6 panels with search)
      notes_dialog.py     Notes dialog
      reminders_dialog.py Reminders dialog
      memories_dialog.py  Memories dialog
      privacy_consent.py  First-run privacy consent dialog
      setup_wizard.py     First-run setup wizard
    widgets/
      speech_bubble.py    Animated speech bubble with inline input
      chat_widget.py      Chat bubble rendering (MessageBubble QFrame)
    managers/
      tray_icon.py        System tray icon (programmatic PNG)
      hint_manager.py     Optional visual hints and tooltips
      window_sitting.py   Window-sitting controller (4 modes)
    sprites/
      sprite_manager.py   Sprite manager + VisualStateResolver bridge
      sprite_loader.py    JSON Schema-validated sprite pack loader
      sprite_models.py    Data classes (SpritePackData, AnimationClip)
      animation_controller.py  Clip player (intents, modes, overlays)
    styles/
      styles.py           UI design tokens and QSS (light/dark)
```

## Technologies

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12+, SQLite, ChromaDB (ONNX embeddings) |
| **AI** | Ollama, OpenAI-compatible API (LM Studio, vLLM, Jan), embedded llama.cpp (llama-cpp-python, optional) |
| **GUI** | PySide6 (Qt for Python) |
| **OS Interaction** | pygetwindow, psutil, ctypes |
| **Audio** | sounddevice, numpy (optional, for audio-reactive dancing) |
| **Security** | keyring (OS keyring), secure file permissions |
| **Animation** | QPropertyAnimation, QTimer-based FPS control |
| **Config** | YAML |
| **i18n** | Custom JSON-based module |
| **Testing** | pytest, pytest-mock, pytest-qt |

## Testing

Run the test suite with:

```bash
pytest
```

Some ChromaDB-dependent tests may be slow on the first run (~90MB ONNX model download to `~/.cache/chroma`). Heavy imports are lazy-loaded only when needed. Pass `-x -q` for quick smoke tests:

```bash
pytest -x -q --no-header
```

If ChromaDB tests fail with native crashes on newer Python, retry with Python 3.12 or 3.13.

## License

Distributed under the MIT License. See `LICENSE` for more information.

### Model licenses

TomoDesk downloads chat models on demand (embedded llama.cpp provider). These
models are **not** covered by the MIT license of this repository and carry
their own terms:

- The default `llama3.2` GGUF is released by Meta under the **Llama Community
  License** (<https://llama.com/license/>), which allows commercial use and
  redistribution under certain conditions. Review it before distributing or
  further developing from the model weights.
