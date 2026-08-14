# TomoDesk — Developer Specification

> This document contains architecture, data models, implementation details, and guidelines.

---

## 1. Project Overview

**TomoDesk** is a desktop companion and AI agent application composed of:

- A **Python backend** handling AI conversations, memory, OS event monitoring, emotional state, proactive comments, and system commands.
- A **2D character overlay** with speech bubbles, audio-reactive dancing, window-sitting, animations, and inline interaction.
- A **chat GUI** with dark/light themes, dialogs for notes/reminders/memories/settings, and tray icon integration.

**Local-first philosophy:** uses Ollama as the default LLM backend, with support for OpenAI-compatible endpoints (LM Studio, Jan, vLLM, Groq, etc.).

### Versioning

| Phase | Version | Description |
|---|---|---|
| Alpha (Phase 1) | 0.1.x | Backend agent, CLI, chat GUI, memory, emotional state |
| Beta (Phase 2) | 0.2.x | 2D character overlay, sprites, animations, audio reactivity, window-sitting, personality packs |
| Future | 0.3.x+ | Autonomous roaming, plugins, 3D avatars |

---

## 2. Technology Stack

- **Core backend**: Python 3.14+
- **GUI framework**: PySide6 6.11
  - Overlay: `QWidget` with `FramelessWindowHint`, `WindowStaysOnTopHint`, `WA_TranslucentBackground`
  - Animations: `QPropertyAnimation` with `QEasingCurve.OutCubic`
  - Rendering: `QPainter` for procedural sprites, `QPixmap` for frame-based custom sprites
- **OS interaction**: `pygetwindow` (active/mouse window detection), `psutil` (CPU/RAM), `ctypes` (idle time via `GetLastInputInfo` on Windows)
- **AI integration**: `ollama` Python client (OllamaProvider), `openai` package (OpenAICompatibleProvider for LM Studio, vLLM, Groq, etc.)
- **Memory**:
  - Short-term: in-memory list of `{role, content, timestamp}` dicts
  - Mid-term: SQLite via `DatabaseManager` (thread-safe with `threading.Lock`)
  - Long-term: ChromaDB with `sentence-transformers` (`all-MiniLM-L6-v2`, lazy-loaded)
- **Configuration**: YAML (`config.yaml`) + `.env` for secrets
- **Internationalization**: custom JSON-based i18n module (`src/config/i18n.py`) with EN/ES
- **Credential storage**: `keyring` library (Windows Credential Manager, macOS Keychain, Linux libsecret)
- **Audio**: `sounddevice` + `numpy` for audio capture and reactivity (optional, graceful fallback)
- **Logging**: Python `logging` with `SensitiveDataFilter` (redacts secrets), Catppuccin Mocha-themed splash screen
- **Tests**: `pytest` 8.3 + `pytest-mock` + `pytest-qt`

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  GUI Layer                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐  │
│  │  windows/        │  │  widgets/       │  │  managers/ │  │
│  │  - overlay       │  │  - chat_widget  │  │  - tray    │  │
│  │  - main_window   │  │  - speech_bubble│  │  - hints   │  │
│  │  - dialogs       │  │                 │  │  - sitting │  │
│  └────────┬─────────┘  └────────┬────────┘  └─────┬──────┘  │
│           │                     │                   │       │
│  ┌────────▼─────────────────────▼───────────────────▼──────┐ │
│  │  sprites/   sprite_manager + animation_manager          │ │
│  │             + sprite_loader + sprite_models             │ │
│  └─────────────────────────────────────────────────────────┘ │
│  styles/   centralized QSS per theme                        │
└──────────────────────┬──────────────────────────────────────┘
                       │ Signals / Direct calls (same process)
┌──────────────────────▼──────────────────────────────────────┐
│  Core Agent (Python)                                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐       │
│  │  core/   │  │  llm/        │  │  memory/          │       │
│  │  events  │  │  llm         │  │  memory           │       │
│  │  state   │  │  prompts     │  │  database         │       │
│  │  context │  │  proactive_* │  │  chroma_manager   │       │
│  │  conv.   │  │              │  │  episodic_*       │       │
│  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘       │
│       │               │                   │                 │
│       └───────────────┼───────────────────┘                 │
│              ┌────────▼────────┐                             │
│              │ config/         │  i18n, credentials, logging │
│              │ system/         │  commands, window_mgr, audio│
│              │ personality/    │  comment_loader, packs      │
│              └─────────────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

### Package Structure

```
src/
├── config/              # Configuration, credentials, i18n, logging
│   ├── config.py        # load_config(), save_config(), get_config_path()
│   ├── credentials.py   # CredentialManager (keyring + env)
│   ├── i18n.py          # I18nManager (translations)
│   └── logging_config.py # setup_logging(), SensitiveDataFilter
├── core/                # Core agent logic
│   ├── events.py        # EventMonitor, SystemMonitor (polling, triggers)
│   ├── state.py         # StateManager (emotional vector)
│   ├── context.py       # ContextBuilder (prompt context assembly)
│   └── conversation.py  # ConversationEngine (LLM orchestration)
├── gui/
│   ├── windows/         # Top-level windows
│   │   ├── overlay_window.py    # Transparent character overlay
│   │   ├── main_window.py       # Chat window
│   │   ├── settings_dialog.py   # 5-tab settings
│   │   ├── notes_dialog.py      # Note CRUD
│   │   ├── reminders_dialog.py  # Reminder management
│   │   └── memories_dialog.py   # Episodic memory browser
│   ├── widgets/         # Reusable widgets
│   │   ├── chat_widget.py       # MessageBubble chat area
│   │   └── speech_bubble.py     # Overlay speech bubble
│   ├── managers/        # GUI managers
│   │   ├── tray_icon.py         # System tray icon + menu
│   │   ├── hint_manager.py      # Visual cue tooltips
│   │   └── window_sitting.py    # Window-sitting controller
│   ├── sprites/         # Sprite & animation system
│   │   ├── sprite_manager.py    # Main sprite controller
│   │   ├── sprite_loader.py     # Custom sprite loader (JSON + validation)
│   │   ├── sprite_models.py     # Data classes (AnimState, SubAnimation)
│   │   ├── animation_manager.py # Data-driven animation engine
│   │   └── animation_state.py   # State constants
│   └── styles/          # Stylesheets
│       └── styles.py    # QSS: dark/light, all components
├── llm/                 # LLM abstraction
│   ├── llm.py           # LLMProvider, create_provider()
│   ├── prompts.py       # PromptBuilder
│   ├── proactive_engine.py  # Proactive comment engine
│   └── proactive_policy.py  # Rate limiting, cooldown, focus/DND
├── memory/              # Memory management
│   ├── memory.py        # MemoryManager (facade for all memory tiers)
│   ├── database.py      # DatabaseManager (SQLite, thread-safe)
│   ├── chroma_manager.py # ChromaDB + lazy embeddings
│   ├── episodic_summarizer.py # Automated LLM-based summarization
│   └── episodic_utils.py     # Milestone detection, suggestion helpers
├── personality/         # Personality packs & phrases
│   ├── comment_loader.py     # YAML comment loading (per-locale)
│   └── personality_pack.py   # PersonalityPackManager (ZIP/dir packs)
└── system/              # System utilities
    ├── commands.py      # CLI command handlers
    ├── reminder_checker.py   # Background reminder thread
    ├── window_manager.py     # Window geometry detection (pygetwindow)
    └── audio_capture.py      # AudioReactivity (sounddevice, optional)
```

### Component Responsibilities

- **EventMonitor** (core/events.py): polls active window, idle time, CPU/RAM every 2s. Detects triggers: window_change, new_app, idle, return_from_idle, session_start/end, resource_high. Fires callbacks for proactive engine.
- **StateManager** (core/state.py): maintains emotional vector `{happiness, energy, curiosity, closeness, connection}` with decay over time, event-based updates, and thread-safe access.
- **ConversationEngine** (core/conversation.py): orchestrates LLM calls — builds prompt via PromptBuilder, calls provider, stores messages, triggers episodic summarization.
- **MemoryManager** (memory/memory.py): facade for all three memory tiers. Thread-safe via DatabaseManager's Lock.
- **AnimationManager** (gui/sprites/): data-driven animation engine. Reads sprite.json definitions, supports simple/one_shot/composite states, emotional variants, and transitions.
- **ProactiveEngine** (llm/proactive_engine.py): evaluates trigger events against policy, selects phrases from comment_loader or personality pack, dispatches via callback.

---

## 4. Data Models

### 4.1 SQLite Tables

| Table | Key Fields |
|---|---|
| `user_profile` | `id`, `name`, `preferred_language`, `personality_traits`, `default_model`, `closeness`, `shown_hints` (JSON), `last_position` (JSON) |
| `notes` | `id`, `title`, `content`, `tags`, `created_at`, `updated_at` |
| `reminders` | `id`, `message`, `trigger_time`, `recurring`, `active` |
| `interaction_log` | `id`, `timestamp`, `event_type` (`user_message` / `window_change` / `idle` / `proactive_comment` / `system_event`), `data_json` |
| `episodic_log` | `id`, `timestamp`, `summary`, `importance_score` (0–1), `source` (`manual` / `auto`), `chroma_id` |

### 4.2 ChromaDB Collections

| Collection | Purpose |
|---|---|
| `personality` | Character traits and user preferences learned over time |
| `memories` | Summaries of past conversations and events (long-term semantic memory) |
| `context_rules` | Deterministic rules for reacting to specific apps/situations |
| `episodic_memory` | Summarized important life events with `importance_score` and `timestamp` |
| `notes_index` | Index of user-created notes, each with title, timestamp, tags, summary, and id for retrieval |

### 4.3 Configuration (`config.yaml`)

```yaml
database:
  sqlite_path: ./data/tomodesk.db

llm:
  provider: ollama               # ollama | openai_compatible
  model: llama3.2:1b
  endpoint: http://localhost:11434
  timeout: 60

logs:
  level: ERROR

memory:
  auto_session_summary: false
  chroma_persist_path: ./chroma_db
  embedding_model: all-MiniLM-L6-v2
  episodic_auto_threshold: 0.6
  episodic_message_threshold: 15
  include_notes: true
  long_term_enabled: true
  max_context_length: 50
  max_short_term_messages: 20
  medium_term_enabled: true
  short_term_enabled: true

modes:
  comment_probability: 0.1
  max_comments_per_hour: 2
  proactive_comments: false
  proactive_cooldown_seconds: 1800

paths:
  comments_yaml: data/comments.yaml
  locales: data/locales

personality:
  name: Tomo
  traits: "friendly, curious, helpful"
  initial_happiness: 0.5
  initial_energy: 0.8
  initial_curiosity: 0.6
  initial_closeness: 0.2
  initial_connection: 0.5

personality_packs:
  active_pack: null              # null = use default comments.yaml
  directory: data/personality_packs
  enabled: true

ui:
  theme: dark                    # dark | light
  language: auto                 # auto | en | es
  character_size: 150
  overlay_enabled: true
  overlay_opacity: 1.0
  overlay_default_position: bottom-right
  bubble_style: comic            # dark | comic
  bubble_max_lines: 5
  bubble_fade_delay_ms: 4000
  bubble_typewriter_interval_ms: 30
  hints:
    enabled: true
    delay_ms: 2000
  sleep_timeout_seconds: 300
  sleep_low_energy_enabled: true
  sprite:
    active: default
    use_custom: false
    custom_path: ''
    show_frame_labels: false

window_sitting:
  enabled: true
  target: active_window          # active_window | mouse_window | fixed_spot
  transition_speed: 0.5
  fallback_position: bottom-right
  maximized_behavior: 1
  minimized_behavior: 0
```

### 4.4 Translation Files (`data/locales/`)

JSON format with dot-notation keys, supporting `{placeholder}` via kwargs.

```json
{
  "menu": {
    "file": "File",
    "clear_chat": "Clear Chat",
    "exit": "Exit"
  },
  "chat": {
    "placeholder": "Type a message... (Enter to send)",
    "send": "Send"
  },
  "commands": {
    "help_text": "Available commands:..."
  },
  "system": {
    "error_ollama": "Cannot connect to Ollama...",
    "reminder_prefix": "REMINDER:"
  }
}
```

### 4.5 Credential Storage

API keys and secrets are **never** stored in `config.yaml`. Managed by `src/config/credentials.py`:

- **Primary**: OS keyring via the `keyring` library (Windows Credential Manager, macOS Keychain, Linux libsecret).
- **Fallback**: Environment variable (`LLM_API_KEY`, etc.).
- **Legacy fallback**: `config.yaml` for backward compatibility during first migration.

**Credentials (runtime) != Preferences (config.yaml)**

```python
class CredentialManager:
    SERVICE_NAME = "TomoDesk"
    _ENV_MAP = {"llm_api_key": "LLM_API_KEY"}

    def get_secret(name) -> str | None    # keyring -> env -> None
    def set_secret(name, value) -> bool   # keyring + return success
    def delete_secret(name)               # remove from keyring
    def migrate_from_config(config)       # legacy config.yaml -> keyring
    def has_credentials() -> bool
```

**Resolution chain**: `keyring` -> `env var` -> `config.yaml` (legacy).

**Migration**: Only occurs if no credential exists in keyring. Never overwrites existing keyring entries.

**Serialization safety**: `save_config()` in `config.py` strips all known secret keys before writing YAML.

**Log redaction**: `SensitiveDataFilter` in `logging_config.py` redacts patterns matching `api_key`, `token`, `secret`, `authorization`, `bearer`, `sk-`, `gsk_`, `hf_` from all log output.

---

## 5. Event Monitoring & Spontaneous Comments

The monitor **polls every 2 seconds:**

- Active window title
- Idle time since last input (via ctypes `GetLastInputInfo` on Windows)
- CPU and RAM usage

### Detected Triggers

| Trigger | Condition |
|---|---|
| `window_change` | Active window title changed |
| `new_app` | First window of a process in this session |
| `app_switch_frenzy` | >3 window changes in 60s |
| `idle` | Idle > 5 minutes |
| `return_from_idle` | User returns after idle |
| `session_start` | Application start |
| `long_session` | Session > 4 hours |
| `late_night` | Hour >= 22 |
| `resource_high` | CPU > 80% or RAM > 85% |

### Proactive Comment System

**Architecture (Observer Pattern):**

```
Events (from EventMonitor)
    ↓
[ProactivePolicy]  cooldown, hourly limit, probability, focus/DND
    ↓
[Personality Layer]  comment_loader.yaml OR personality pack phrases
    ↓
[Delivery Callback]  bubble text / console output
```

**Sources** (priority order):
1. Active personality pack phrases (if `personality_packs.active_pack` is set)
2. `comments_{lang}.yaml` (per-locale, loaded by `CommentLoader`)
3. Default `comments.yaml`

**Policy rules**: cooldown seconds, max comments/hour, random probability, focus/DND mode suppresses all.

---

## 6. State & Emotional Model

**Emotional vector:** `{happiness, energy, curiosity, closeness, connection}` — all `[0, 1]`.

### Dimensions

| Dimension | Behavior |
|---|---|
| `happiness` | Changes with short-term events (positive/negative feedback, conversation) |
| `energy` | Decreases with inactivity; regenerates during sleep (~0.1/min) |
| `curiosity` | Increases with new apps, conversations; decays over time |
| `closeness` | Cumulative bond; increases with positive interactions; decreases only with `explicit_ignore` when < 0.2 |
| `connection` | Recent closeness; fluctuates daily; decays naturally |

### Decay Rates (per second)

| Variable | Rate |
|---|---|
| happiness | 0.0001 |
| energy | 0.00005 |
| curiosity | 0.0002 |
| closeness | 0.0 (never decays) |
| connection | 0.00003 |

### Sleep System

- **Trigger A — System idle**: No mouse/keyboard input for `ui.sleep_timeout_seconds` (default 300). Timeout checked against `EventMonitor.get_latest().idle_time_seconds`.
- **Trigger B — Low energy**: `energy < 0.05` (configurable via `ui.sleep_low_energy_enabled`).
- **Regeneration**: During sleep, `StateManager.update("idle")` is called every 3s, restoring ~0.1 energy per minute.
- **Wake messages**: `energy >= 0.3` -> "I feel much better!"; otherwise -> "Good morning!" (i18n keys `waking_up_energized` / `waking_up`).
- **Grace period**: 15s after any interaction before low-energy check can re-trigger sleep.
- **Animation**: State transitions to `SLEEPING` (5 FPS), bubble hidden.

### Updating Events

| Event | Effect |
|---|---|
| `user_message` | happiness +0.05, energy -0.02, curiosity -0.01, connection +0.02 |
| `positive_feedback` | happiness +0.1, closeness +0.03, connection +0.05 |
| `negative_feedback` | happiness -0.1, closeness -0.03, connection -0.05 |
| `explicit_ignore` | closeness -0.1 (only if < 0.2), happiness -0.05 |
| `long_conversation` | happiness +0.03, closeness +0.01, connection +0.02 |
| `window_change` | curiosity +0.02 |
| `new_app` | curiosity +0.05 |
| `idle` | energy no change (sleep handles it) |
| `return_from_idle` | curiosity +0.03 |
| `session_start` | connection +0.02 |
| `reminder_completed` | happiness +0.03 |
| `idle` (during sleep) | energy +0.005 |

### Persistence

`closeness` is the only variable persisted between sessions (via `save_to_preferences` / `load_from_preferences` on SQLite `user_profile`).

---

## 7. Memory Implementation Details

### Short-term
List of `{role, content, timestamp}` dicts. Cleared on session end or truncated to `max_short_term_messages`.

### Mid-term
SQLite tables as defined in §4.1. User can add/edit via commands or GUI dialogs.

### Long-term (ChromaDB)
- **`memories`**: summaries inserted when conversation length > threshold or user explicitly saves.
- **`personality`**: facts and preferences learned via evidence accumulation (not solely LLM-driven).

### Episodic Memory

| Trigger | Mechanism |
|---|---|
| Manual | `/remember <text>` -> stored with `importance=0.8` (or user-specified `importance:N`) |
| Automatic | After long conversation (message count > `episodic_message_threshold`, default 15) or end-of-session, LLM generates summary + importance. Saved if >= `episodic_auto_threshold` (default 0.6) |
| Suggested | `suggest_memory_from_conversation()` detects milestones via keyword matching |

Episodic entries are retrieved into the prompt via semantic search (max distance < 1.5). Sections: `[Important Memories]` (score >= 0.8) and `[Things I Know About You]` (score < 0.8).

### Embeddings

SentenceTransformer (`all-MiniLM-L6-v2`) loaded lazily via `_SentenceTransformerEmbedding.__call__()` with double-checked locking. First query triggers torch + ONNX model load (~80MB). `ChromaManager.ensure_loaded()` for explicit precaching.

**Mock for tests**: `tests/mock_chroma.py` provides in-memory ChromaDB replacement.

---

## 8. LLM Interface & Provider Abstraction

```python
class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt, system_message, history, context) -> str: ...
    @abstractmethod
    def generate_stream(self, prompt, system_message, history, context) -> Generator[str]: ...
    @abstractmethod
    def is_available(self) -> bool: ...
```

**Implementations:**

| Provider | File | Backend |
|---|---|---|
| `OllamaProvider` | `src/llm/llm.py` | Ollama Python client |
| `OpenAICompatibleProvider` | `src/llm/llm.py` | `openai` package (LM Studio, vLLM, Groq, Jan) |

**Provider factory:**

```python
# src/llm/llm.py
def create_provider(config: Dict, api_key: str | None = None) -> LLMProvider:
    """
    api_key is passed explicitly from CredentialManager.
    It is NOT read from config["llm"]["api_key"].
    """
```

**Config schema:**

```yaml
llm:
  provider: ollama               # ollama | openai_compatible
  model: llama3.2:1b
  endpoint: http://localhost:11434
  timeout: 60
```

---

## 9. Prompt Construction

Assembled in order by `PromptBuilder`:

1. **System message:** personality + emotional state + tone instructions from StateManager
2. **Current context:** time, active window, idle time (from ContextBuilder)
3. **Relevant episodic memories:** semantic search filtered by < 1.5 distance, separated by importance
4. **Relevant notes:** if `include_notes` is true and semantic search finds matches
5. **Recent conversation:** short-term memory
6. **User input** (or null for proactive comments)

---

## 10. Animation System (Subfase 2.9)

### Data-driven Architecture

Animation data is defined in JSON per sprite and validated against `data/sprites/schema.json` (JSON Schema via `jsonschema`).

### Files

| File | Purpose |
|---|---|
| `data/sprites/schema.json` | JSON Schema for sprite definitions |
| `data/sprites/default/sprite.json` | Default procedural sprite definition |
| `src/gui/sprites/sprite_loader.py` | `SpriteLoader` — loads sprite.json, validates against schema, loads frames |
| `src/gui/sprites/sprite_models.py` | `AnimState`, `SubAnimation` data classes |
| `src/gui/sprites/animation_state.py` | State name constants (`IDLE`, `TALKING`, `SLEEPING`, `HAPPY`) |
| `src/gui/sprites/animation_manager.py` | `AnimationManager` — state machine, transitions, frame timing |
| `src/gui/sprites/sprite_manager.py` | `SpriteManager` — facade for overlay; manages timer, state transitions |

### State Types

| Type | Behavior |
|---|---|
| `simple` | Loops through frames indefinitely |
| `one_shot` | Plays once, then auto-returns to previous state |
| `composite` | Weighted random sub-animations (e.g., blink during idle) |

### Emotional Variants

Each state can define `variants` with per-emotion frame overrides. Example:

```json
"variants": {
  "happiness>0.7": {"frames": ["happy_idle_1", "happy_idle_2"]},
  "energy<0.3": {"frames": ["tired_idle_1"]}
}
```

### Transitions

Defined in `sprite.json` under `"transitions"` key. Each transition can have its own frames and durations for smooth blending between states.

### Default Procedural Sprite

When no `sprite.json` is found for the active sprite, `SpriteLoader._procedural_frame()` generates a cat-like character using QPainter (ears, big eyes with highlights, blush, body, expressions per state).

### Custom Sprites

Users can provide `data/sprites/<name>/sprite.json` with frame images. Loaded from the `frames/` subdirectory. Selected via Settings -> Personaje -> Sprite, or by setting `ui.sprite.active` in config.

---

## 11. Interaction Layers (UI Specification)

### Overlay Window (src/gui/windows/overlay_window.py)

- Transparent, borderless, always-on-top (`Tool` window flag, no taskbar entry)
- Draggable via mouse (click+drag vs click distinguished by 5px threshold)
- Position persisted in `user_profile` via JSON
- Double-click opens main chat window
- Right-click context menu: Chat, Notes, Reminders, Memories, Settings, Exit

### Speech Bubble (src/gui/widgets/speech_bubble.py)

- Appears above the character; follows overlay position
- Typewriter effect (progressive text reveal, configurable interval)
- "Thinking..." indicator during LLM generation
- Fade-out on configurable delay (`bubble_fade_delay_ms`, default 4s)
- Supports dark and comic styles
- Screen-edge detection: if bubble would go off-screen, it repositions
- Inline input field: click on bubble -> show text input -> Enter to send -> hide
- Escape to cancel, drag-aware click detection (no false positives)

### Chat Widget (src/gui/widgets/chat_widget.py)

- `QScrollArea` + `QHBoxLayout`-wrapped `MessageBubble(QFrame)` per message
- Plain text `QLabel` with `setWordWrap(True)` for reliable sizing
- Role-based colors (user vs assistant) via QSS
- No manual height calculations or timers
- Fallback `_bubble_max_width()` of 400px when widget not yet sized

### Main Window (src/gui/windows/main_window.py)

- Menu bar: Character Name (Toggle overlay, Focus mode, Clear, Exit), Conversation (Notes, Reminders, Memories), Settings, Help (Guide, About)
- Status bar: humanized emotional state messages (distant, tired, radiant, curious, listening, sleeping) with exact values on hover, focus/DND indicator
- Theme toggle in Settings (dark/light) propagates to all windows

### Dialogs (src/gui/windows/)
- **Settings**: 5 tabs (Apariencia, Personaje, Mente, Comportamiento, Avanzado) with scroll areas
- **Notes**: CRUD, list view
- **Reminders**: Create/cancel, list view
- **Memories**: List/search/delete episodic memories
- All dialogs force independent taskbar entry on Windows via `SetWindowLongW` + `WS_EX_APPWINDOW`

### Tray Icon (src/gui/managers/tray_icon.py)

- 32x32 multi-size icon, retry timer for visibility
- Context menu: Show Chat, Notes, Reminders, Memories, Settings, Focus Mode, Exit
- Welcome notification on first show
- Window minimize -> hides to tray; close -> hides to tray (unless quitting)

### HintManager (src/gui/managers/hint_manager.py)

Shows one-time visual tooltips teaching overlay interaction:
- Hover 1.5s: "Drag me!" + "Click me!"
- After click 0.8s: "Double-click to chat!"
- First bubble: "Click the bubble to type!"
- First right-click: "Right-click for more options!"
- Persisted in user_profile under `shown_hints` (JSON array)

### Taskbar Entry Fix (Windows)

`_force_taskbar_entry()` in each dialog calls Win32 `SetWindowLongW` with `WS_EX_APPWINDOW` to force independent taskbar entries. Guard: `sys.platform != "win32"`.

---

## 12. Audio-Reactive Dancing

### Component: `src/system/audio_capture.py`

| Aspect | Detail |
|---|---|
| Capture | RMS from system/microphone via `sounddevice.InputStream` |
| Smoothing | Factor 0.9 (exponential moving average) |
| Beat detection | RMS > smooth * 1.5 threshold |
| Emotional gating | `emotional` mode: full dance only when energy>0.6 and happiness>0.6. Also `always` and `off` |
| FPS impact | Configurable via `audio_reactive.update_interval_ms` |
| Privacy | No audio stored or transmitted. One-time notice on first run. |
| Graceful fallback | If `sounddevice` unavailable, runs in dummy mode (volume always 0.0) |

```yaml
# In config.yaml, injected at runtime
audio_reactive:
  enabled: true
  source: system       # system | microphone
  mode: emotional      # emotional | always | off
  sensitivity: 1.0
  max_volume: 1.0
  update_interval_ms: 200
  beat_threshold: 1.5
```

---

## 13. Window-Sitting

### Components

| File | Class | Role |
|---|---|---|
| `src/system/window_manager.py` | `WindowManager` | Window geometry via `pygetwindow`, taskbar detection |
| `src/gui/managers/window_sitting.py` | `WindowSittingController` | QTimer-driven movement with `QPropertyAnimation` |

### Behavior

| Mode | Description |
|---|---|
| `active_window` | Sits on top of the currently active window |
| `mouse_window` | Sits on window under the mouse cursor |
| `fixed_spot` | Stays at configured fallback position |

- Polls every 500ms via QTimer
- Movement uses `QPropertyAnimation` with `OutCubic` easing
- Drag pauses sitting for 5s (`QTimer.singleShot(5000)`)
- Focus/DND disables sitting -> moves to fallback position
- Taskbar auto-hide detection: if <5px visible, use screen-edge strip
- Multi-monitor aware
- Graceful fallback: if `pygetwindow` unavailable, returns None

### Config

```yaml
window_sitting:
  enabled: true
  target: active_window
  transition_speed: 0.5
  fallback_position: bottom-right
  maximized_behavior: 1
  minimized_behavior: 0
```

---

## 14. Personality Packs

### Format

| Format | Use case |
|---|---|
| ZIP | Distribution, drag-and-drop installation |
| Loose directory | Development, advanced modding |

### Structure

```
MyPersonality/
  manifest.yaml           # metadata
  phrases/                # YAML phrases per trigger type
    greeting.yaml
    idle.yaml
    proactive.yaml
  sounds/                 # optional: .wav, .ogg
    notification.wav
  sprites/                # optional (reserved)
  emotions_mapping.yaml   # optional (reserved)
```

### Manifest

```yaml
name: "Tomo Feliz"
author: "UsuarioX"
version: "1.0"
min_tomodesk_version: "0.2.0"
type: "personality"       # personality | sound_pack | sprite_pack
replaces: []              # optional: overrides default phrases
```

### Integration

| Feature | Status |
|---|---|
| Phrase loading (priority over comments.yaml) | Implemented |
| Drag-and-drop ZIP installation on overlay | Implemented |
| Pack listing in Settings UI | Implemented |
| Active pack switching from Settings (no restart) | Implemented |
| Sound playback | Reserved |
| Emotion mapping | Reserved |
| Custom sprites within packs | Reserved |

---

## 15. Theme System & Styles

Centralized in `src/gui/styles/styles.py`:

```python
def get_style_set(theme: str) -> dict:
    # Returns {main, dialog, overlay_menu} QSS strings
```

| Aspect | Detail |
|---|---|
| Themes | `dark` (Catppuccin Mocha), `light` |
| Chat bubbles | Individual `QFrame` with `border-radius` via QSS, not HTML tables |
| Dialog styling | Each dialog accepts `styles=` parameter |
| Overlay menu | Uses `self._styles["overlay_menu"]` |
| Propagation | `ChatWidget.set_theme()` updates container + all existing MessageBubble widgets |
| Persistence | `ui.theme` in config.yaml |

---

## 16. Sleep System

Two triggers, independent but composable:

### System Idle Sleep

- Polls `EventMonitor.get_latest().idle_time_seconds` every 3s
- Configurable via `ui.sleep_timeout_seconds` (default 300)
- No own timer; reuses existing EventMonitor data
- Wakes on any user interaction (click, keyboard, mouse movement)

### Low Energy Sleep

- Checks `state_manager.get("energy")` every 3s
- Triggers when `energy < 0.05`
- 15s grace period after any interaction prevents rapid cycling
- During sleep, calls `state_manager.update("idle")` every 3s for energy regeneration (~0.1/min)

### Animation During Sleep

- State transitions to `SLEEPING`
- Frame rate drops to ~5 FPS
- Speech bubble hidden
- Window-sitting and audio reactivity suspended

---

## 17. Startup Optimization (Phase 3)

Startup time reduced from ~52s to ~13s (dominated by torch + sentence-transformers).

| Technique | Detail |
|---|---|
| Lazy embeddings | SentenceTransformer loaded on first ChromaDB query, not at init |
| Deferred audio | `sounddevice.query_devices()` moved to `QTimer.singleShot(0)` |
| Background LLM check | `engine.check_availability()` in daemon thread after GUI visible |
| Parallel init | `ThreadPoolExecutor(max_workers=5)` for I18n, DB, Chroma, Packs |
| Lazy imports | All heavy packages imported locally inside functions, not at module level |
| QThread init | `_InitWorker(QThread)` runs `_initialize()` in background |
| Splash screen | Translucent "Cargando..." shown immediately after QApplication creation |

**Data flow:**

```
QApplication -> Splash -> _InitWorker.start() -> app.exec() (event loop live)
    -> background _initialize() -> signal _on_init_complete
    -> OverlayWindow + MainWindow + TrayIcon
    -> LLM check (background thread)
```

---

## 18. i18n Specification

### Module: `src/config/i18n.py`

```python
class I18nManager:
    def __init__(self, locale_dir: str, default_lang: str = "en"):
        # Load all JSON files from locale_dir

    def set_language(self, lang: str) -> None:
        # Switch active language

    def detect_language(self, config_lang: str) -> str:
        # If "auto", use system locale
        # Map system locale to supported languages (en, es)
        # Fallback to "en"

    def t(self, key: str, **kwargs) -> str:
        # Dot-notation key lookup (e.g., "menu.file")
        # Replace {placeholder} with kwargs
        # Fallback to key if missing
```

### Supported Languages

| Code | File | Region |
|---|---|---|
| `en` | `data/locales/en.json` | English |
| `es` | `data/locales/es.json` | Spanish |

### Keys (partial)

- `menu.char.*` — Character name menus
- `menu.conversation.*` — Notes, Reminders, Memories
- `menu.help.*` — Interaction guide, About
- `status.*` — Humanized emotional labels (sleeping, distant, tired, radiant, curious, listening)
- `chat.*` — Placeholder, send, system messages
- `commands.*` — All command responses
- `hints.*` — Interaction guide tooltips
- `sprite_delete.*` — Sprite deletion UI

**Rule**: All user-facing strings go through `i18n.t()`. No hardcoded strings in GUI or commands.

---

## 19. Thread Safety

| Module | Strategy |
|---|---|
| `DatabaseManager` | `threading.Lock` on execute/commit; all memory calls use public methods |
| `StateManager` | Lock on state read/write + decay calculation inside lock |
| `OverlayWindow` | Qt signals for cross-thread: `_bubble_text_signal`, `_assistant_response_signal`, `_bubble_thinking_signal` |
| `EpisodicSummarizer` | Runs in `threading.Thread` (daemon), signals result back via engine |
| `ConversationEngine.chat_stream` | Runs in `threading.Thread` (daemon) to not block GUI |
| `EventMonitor` | Daemon thread with polling loop |
| `ReminderChecker` | Daemon thread with polling loop |
| `ProactiveEngine` | Daemon thread for random timer |

---

## 20. Key Bugfixes & Audits (Post-Fase 2 Summary)

### Critical/High

| ID | Area | Fix |
|---|---|---|
| C1 | events.py | Logger before try/except (NameError) |
| C2 | overlay_window + main | `_assistant_response_signal` for thread-safe message updates |
| C3 | database.py | `threading.Lock`, `execute()`/`commit()` methods, auto-migration for `chroma_id` |
| C4 | state.py | All decay calculation inside `with self._lock` |
| C5 | settings_dialog + config | `get_config_path()`, atomic YAML writes |
| C6 | config + settings + .env | API key via `python-dotenv`, never written to config.yaml |

### Notable Fixes

- Chat widget: Replaced HTML QTextEdit with plain-text QLabel + row wrappers (fixes sizing)
- Taskbar entry: Win32 `WS_EX_APPWINDOW` for modal dialogs on Windows
- Splash delay: Moved all heavy imports to local scope (~11.5s saved)
- "Not responding": `_InitWorker(QThread)` prevents GUI thread blocking
- Sprite animation: Blink restored (audio reactivity no longer resets idle timer)
- Tray icon GC: Assigned to `_tray_icon` in main.py
- Bubble fade: `_fade_timer.stop()` on inline input open
- Session start cooldown: `can_comment("session_start")` returns True unconditionally

---

## 21. Coding Guidelines for Agent

- **Python 3.14+**, type hints and docstrings are mandatory.
- Use `pathlib` for all paths; no hardcoded strings.
- All user-facing strings through `i18n.t()`.
- **Package structure** (actual layout, not flat):

```
src/
  config/       config.py, credentials.py, i18n.py, logging_config.py
  core/         events.py, state.py, context.py, conversation.py
  gui/
    windows/    overlay_window, main_window, settings_dialog, notes/reminders/memories
    widgets/    chat_widget, speech_bubble
    managers/   tray_icon, hint_manager, window_sitting
    sprites/    sprite_manager, sprite_loader, animation_manager, animation_state, sprite_models
    styles/     styles.py
  llm/          llm.py, prompts.py, proactive_engine.py, proactive_policy.py
  memory/       memory.py, database.py, chroma_manager.py, episodic_*.py
  personality/  comment_loader.py, personality_pack.py
  system/       commands.py, reminder_checker.py, window_manager.py, audio_capture.py
```

- API keys go through `CredentialManager`. Never hardcode or store in config.yaml.
- Use `save_config()` for all YAML writes; never call `yaml.dump()` directly.
- Log errors; never crash on external service failure.
- GUI thread safety: use Qt Signals for cross-thread communication; never call GUI methods from background threads.
- Test with `pytest`. Use `MockChroma` instead of real ChromaDB in tests.
- Use `mock_i18n` (MagicMock) fixture for tests that don't need real translations.
- Heavy imports (torch, chromadb, sentence-transformers) must be local, never at module level.

---

## 22. Next Steps for Development

- ✅ Phase 1 (Alpha 0.1.x) — complete
- ✅ Phase 2 (Beta 0.2.x) — complete
- 📦 First public release preparation: cleanup, documentation, CI/CD, packaging

### Repository Structure

```
README.md           — GitHub public overview
ROADMAP.md          — GitHub public milestones
config.yaml         — User configuration
main.py             — Entry point (CLI / GUI)
data/
  locales/          — i18n JSON files (en, es)
  comments.yaml     — Proactive comment phrases (default)
  comments_en.yaml  — English phrases
  comments_es.yaml  — Spanish phrases
  sprites/          — Sprite definitions + schemas
    schema.json
    default/sprite.json
    GUIDE.md
  personality_packs/ — User-installed packs
    example_tomo/
    LinVT/
    GUIDE.md
tests/              — pytest suite
docs/
  TECHNICAL_SPEC.md — This document
  README_ES.md      — Human vision guide (personal reference)
  progress.md       — Changelog (gitignored)
```

## 23. Security Model

### 23.1 Credential Management (see also §4.5)

- Secrets are stored in the OS keyring via `keyring` (`CredentialManager`, service `TomoDesk`).
- Resolution chain: **keyring → env var → config.yaml (legacy, migrated once)**.
- `save_config()` strips secret keys before writing YAML; config is written atomically (temp file + replace).
- GUI stores/removes keys through `CredentialManager`; the input field uses password echo mode.

### 23.2 Privacy & Consent (`privacy` config section)

```yaml
privacy:
  consent_asked: false
  monitor_active_window: true
```

- On first GUI launch, `PrivacyConsentDialog` (`src/gui/windows/privacy_consent.py`) asks the user
  whether TomoDesk may read the active window title. The choice is persisted via `consent_asked`
  and `monitor_active_window`.
- When `monitor_active_window` is `false`:
  - `SystemMonitor.poll()` reports `active_window = "Unknown"`.
  - `ContextBuilder.build_context()` omits the `Active window:` line.
  - The setting can be toggled at any time from Settings → Behavior → Privacy.
- Window titles are stored locally in `interaction_log` and may be sent to the configured LLM.

### 23.3 Secure File Permissions (`src/config/secure_files.py`)

`secure_file(path)` is best-effort and never raises:

- POSIX: `chmod 0o600`.
- Windows: `icacls /inheritance:r /grant:r <user>:F`.

Applied to: `config.yaml` (on load and save), `.env` (on load), and the SQLite database file
(on initialize).

### 23.4 LLM Endpoint Validation

`validate_llm_endpoint(url) -> bool` (in `src/config/config.py`) accepts only `http`/`https` URLs
with a non-empty host.

- Enforced in `create_provider()` for `openai_compatible` providers (lazy import to avoid circular
  imports) and in the Settings dialog before saving.
- `llm.max_requests_per_minute` (default `60`) configures rate limiting.

### 23.5 Rate Limiting (`src/llm/rate_limit.py`)

Token-bucket `RateLimiter` (stdlib only, thread-safe). Both `OllamaProvider` and
`OpenAICompatibleProvider` call `self._throttle()` before each `generate()`/`generate_stream()`.
Disabled when `max_requests_per_minute <= 0`.

### 23.6 ZIP / Personality Pack Validation (`src/personality/zip_security.py`)

`validate_zip_archive(path)` centralizes the safety checks used by both the overlay drag & drop and
the pack loader:

- Max size 50 MB (`MAX_PACK_ZIP_SIZE`).
- Must contain `manifest.yaml`.
- Rejects path traversal (`..`, absolute paths, backslash separators) via `is_safe_zip_member`.

Pack names loaded from manifests are sanitized (`_safe_pack_name`): control characters stripped,
whitespace trimmed, max 100 chars, fallback to directory/stem name.

### 23.7 Other Hardening

- **Log redaction**: `SensitiveDataFilter` (see §4.5) redacts credential-like patterns from all logs.
- **Memory import validation**: imported episodic memories are validated (summary string, numeric
  importance in `[0,1]`, string source); invalid entries are skipped with a warning.
- **Cache keys**: `sha256` instead of `md5` for embedding and query cache keys in `chroma_manager.py`.
- **Clean shutdown**: GUI exit calls `_graceful_shutdown(deps)` (stops proactive engine, reminder
  checker and event monitor, persists preferences) before closing the DB. Background loops use a
  `threading.Event` and `Event.wait(timeout)` instead of `time.sleep` so `stop()` wakes them
  immediately and `join` is bounded to 1s. The session summary runs in a daemon thread with a
  bounded 0.5s wait; `save_to_preferences` is guarded to run once per shutdown. The process exits
  with `os._exit(ret)` after `_close_db()` (which commits pending WAL transactions).

### 23.8 Out of Scope / Future Work

- Data-at-rest encryption of SQLite and ChromaDB (currently plaintext on disk).
- Certificate pinning (relying on the provider's default TLS handling).
