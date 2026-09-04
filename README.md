# TomoDesk

> Desktop companion that merges an interactive character with an AI-powered productivity agent. Local-first, private, and customizable.

![Version](https://img.shields.io/badge/version-1.1.0-blue)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-v1.1.0--release-yellow)
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
- Audio-reactive dancing with beat detection
- Window-sitting: character sits on real windows
- Personality packs: load custom phrases from ZIP files
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

The default configuration lives in `config.yaml` (auto-generated from `config.example.yaml` on first run). Common settings include:

- LLM provider and model (Ollama, OpenAI-compatible local servers such as LM Studio, vLLM, or Jan, or embedded llama.cpp)
- UI language (`auto`/`en`/`es`)
- Overlay behavior, speech bubble style, audio-reactive dancing, and window-sitting
- Personality packs and proactive comment resources

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

- `/note add/list/show/delete/search` — manage notes
- `/remind in/list/cancel` — manage reminders
- `/remember importance:N <text>` — store an episodic memory
- `/memories list/search/delete/important` — browse memories
- `/proactive on/off/focus/unfocus` — control proactive comments
- `/mood` — view emotional state
- `/episodic` — memory statistics
- `/model [status|download|uninstall]` — manage the local llama.cpp GGUF model
- `/gui` — info about GUI mode

## Architecture

```
main.py                   Entry point (QThread-based async init, splash screen)
src/
  config/
    config.py             Configuration loader (YAML) + AppUserModelID
    logging_config.py     Logging setup
    i18n.py               Internationalization manager (EN/ES)
  core/
    conversation.py       Conversation engine (prompt building, LLM calls)
    context.py            Context builder for prompts
    state.py              Emotional state system (5 variables)
    events.py             OS event monitor (active window, idle, CPU/RAM)
  llm/
    llm.py                LLM provider abstraction (Ollama, OpenAI-compatible)
    prompts.py            System prompt templates
    proactive_engine.py   Proactive comment engine (rule-based)
    proactive_policy.py   Comment trigger policies
  memory/
    memory.py             Memory manager (short-term, mid-term, long-term)
    chroma_manager.py     ChromaDB client (long-term + episodic memory)
    database.py           SQLite client (notes, reminders, interaction log)
    episodic_summarizer.py LLM-based episodic summarization
  system/
    commands.py           Chat command handlers
    reminder_checker.py   Background reminder checker
    window_manager.py     Window detection for window-sitting
    audio_capture.py      Audio capture for reactive dancing
  personality/
    comment_loader.py     Comment YAML loader
    personality_pack.py   Personality pack loader (ZIP/directory)
  gui/
    windows/
      main_window.py      Main chat window (PySide6)
      overlay_window.py   Transparent overlay character window
      settings_dialog.py  Settings dialog (5 panels)
      notes_dialog.py     Notes dialog
      reminders_dialog.py Reminders dialog
      memories_dialog.py  Memories dialog
    widgets/
      speech_bubble.py    Animated speech bubble with inline input
      chat_widget.py      Chat bubble rendering (MessageBubble QFrame)
    managers/
      tray_icon.py        System tray icon (programmatic PNG)
      hint_manager.py     Optional visual hints and tooltips
      window_sitting.py   Window-sitting controller
    sprites/
      sprite_manager.py   Sprite manager + VisualStateResolver bridge
      sprite_loader.py    JSON Schema-validated sprite pack loader
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
| **Audio** | sounddevice, numpy |
| **Animation** | QPropertyAnimation, QTimer-based FPS control |
| **Config** | YAML |
| **i18n** | Custom JSON-based module |
| **Testing** | pytest |

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
