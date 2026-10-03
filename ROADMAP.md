# Roadmap

TomoDesk follows [Semantic Versioning](https://semver.org/). This document
tracks what has shipped and what is planned. Shipped details live in
[`CHANGELOG.md`](CHANGELOG.md).

The `Planned` section is organized by theme; every item carries an orientative
target tier, not a hard commitment:

| Tier | Meaning |
|---|---|
| **Next** | Targeted for the next minor releases (`v1.7.x`). |
| **Later** | `v1.8.x`–`v1.9.x`, after the next tier lands. |
| **Major** | `v2.0.0`-class architectural or breaking work. |
| **Backlog** | Unscheduled; valuable but needs scoping. |
| **Ongoing** | Continuous work, no target version. |

## Released

### v1.6.0

- Platform abstraction layer `src/platform/`: a `PlatformAdapter` contract with
  a `WindowsAdapter` (pygetwindow + ctypes) and a degraded `NullAdapter` for
  other platforms, selected by a thread-safe factory. `PlatformCapabilities`
  reports which desktop integrations are available.
- Settings → Advanced lists unavailable capabilities and disables window-sitting
  and active-window privacy controls when window enumeration is unsupported.
- `WindowManager` became a Qt-aware facade over the adapter; `SystemMonitor`,
  the shared taskbar-entry helper and restart flags now go through it.
- Fixed opening the logs folder from Settings on non-Windows platforms.

### v1.5.0

- Window-sitting overhaul: four target modes (`active_window`, `mouse_window`,
  `closest_window`, `fixed_spot`), HWND-based own-window exclusion, shell-noise
  filtering, per-screen clamping for offset multi-monitor layouts and fallback
  anchored to the target's screen.
- Window-sitting settings (target, fallback, transition speed, max/min
  behavior) apply live without restarting, with new Settings controls and
  EN/ES strings.
- Focus and Do Not Disturb now suspend window-sitting (inverted DND checkbox
  fixed).
- Single-instance guard so two GUIs cannot share SQLite, logs and config.

### v1.4.1

- Fix `RuntimeError` when closing the setup wizard after a background worker
  finished, and stop logging missing-placeholder errors for wizard
  translations. See `CHANGELOG.md` for details.

### v1.4.0

- First-run setup wizard (`SetupWizard`) to choose between local AI
  (llama.cpp), an external API, or postpone.
- Local option displays the recommended GGUF model, probes its remote size and
  downloads it with progress and cancellation; the external option validates
  the endpoint/model and stores the API key in the OS keyring.
- `-Full` / `--full` build variants that bundle the `llama-cpp-python` runtime.

### v1.3.0

- Window icon falls back to `build/assets/tomodesk.png` in development mode
  instead of showing a generic square.
- Settings sidebar navigation-width test made stable across platform font
  metrics.

### v1.2.0

- Character name is defined by the active personality pack, with a
  `resolve_pack()` helper for legacy/misaligned configs.
- Unified Tomo/TomoDesk identity: default character name is "Tomo" and the
  About dialog reads the real version dynamically.

### v1.1.0

- Packaging and distribution: PyInstaller one-dir builds with Inno Setup
  (Windows) and AppImage (Linux), plus a tag-triggered release job in CI.
- Embedded llama.cpp provider (`llama-cpp-python`, optional) with on-demand
  GGUF model download from HuggingFace.
- SemVer versioning centralized in `src/__init__.py` and a `bump_version.py`
  script.
- Windows build fixes (restart action, tray notifications, console flash) and
  Windows-aware `auto` language detection.

### v1.0.0

- Conversational AI with local LLMs (Ollama / OpenAI-compatible: LM Studio, vLLM, Jan)
- Multi-level memory: short-term, mid-term (SQLite), long-term and episodic (ChromaDB)
- OS event monitoring (active window, idle time, CPU/RAM) and proactive comments
- Emotional state system (happiness, energy, curiosity, closeness, connection)
- Animated 2D character overlay with speech bubbles, audio-reactive dancing, and window-sitting
- Personality packs (ZIP/directory) and default character pack
- Notes, reminders, and semantic search
- System tray integration and bilingual UI (EN/ES)

## Planned

### AI providers and first-run experience

- Make the embedded llama.cpp provider the default on first run: ship a small
  curated GGUF and bundle the runtime in the standard build, keeping the model
  download explicit and optional so the base binary stays lean. — **Next**
- Streamline first-run so a new user gets a working local model with one click,
  with a clear side path to an external API. — **Next**
- Provider UX: dynamic Settings per provider, endpoint/model validation,
  model discovery, effective-model display and per-API tips (rate limits, 429
  behavior, role-play tuning). — **Next**
- Persist the chosen provider reliably and surface the active provider
  (model/endpoint, never secrets) in the UI and in debug output; reduce the
  need to restart when switching. — **Next**
- Debug mode: dump the exact prompt sent to the model and expose provider,
  temperature and context length; toggle from CLI/console and Settings. — **Next**
- Keep Ollama as a recommended external local runtime ("bring your own") and
  review free/low-cost APIs (OpenRouter, Groq, Google AI Studio). — **Later**
- Review dual-model (small always-on + large on-demand) and hybrid/multimodal
  models, including image analysis. — **Later**

### Settings and interface

- Redesign Settings to reduce option saturation: progressive disclosure or an
  advanced mode, stronger grouping and a better search. — **Next**
- Add tooltips and inline help for each control, plus save indicators for
  automatic summaries and save-on-close. — **Next**
- Fix the speech-bubble tail when the character is near the left/right screen
  edge. — **Next**
- Standardize the "loading" affordance (splash, setup, thinking bubble). — **Next**
- Expand Help: keyboard shortcuts, a simple initial tutorial and an optional
  advanced (companion-style) tutorial, plus a documentation link. — **Later**
- Refactor large GUI modules (overlay, main window) for maintainability. — **Later**
- Improve the terminal/console experience and CLI feature parity. — **Later**
- Explore alternative frontends (phone, tablet, book, holographic panel). — **Backlog**

### Character, animation and avatars

- Optional emotion system with mood-driven expression changes tied to the
  response. — **Next**
- Richer animation states/transitions and improved sprite tooling. — **Next**
- Eye/head tracking that follows the cursor, designed with future avatar
  systems in mind. — **Later**
- Plan character movement/roaming across the desktop. — **Later**
- Pluggable avatars: expand 2D formats (Live2D, VRM) and add 3D support. — **Major**
- Create first-party base characters with their own lore/personality and
  matching sprites/models. — **Later**
- Grow the personality-pack catalog. — **Backlog**

### Personality, sprite and context packs

- Redesign the personality, sprite and context pack systems as one documented,
  versioned ecosystem with a consistent manifest and tooling. — **Next**
- Expose sounds and emotion variants from inside personality packs (currently
  reserved). — **Later**
- Pack authoring tooling (validator, template, creator utility) and a public
  catalog. — **Later**
- Pack schema versioning and compatibility guarantees across app releases. — **Later**

### Memory, emotions and relationship

- Tune memory policies from the UI: thresholds, context rules and
  short/mid/long-term toggles. — **Next**
- Revise the affection/closeness model and persist relationship state per user
  profile. — **Next**
- Add per-user profile configuration (identity, preferences, relationship). — **Next**
- Improve episodic summarization and recall ranking, and connect episodic
  memory to the proactive engine for session-level goals. — **Next**
- Make emotions fully optional, including a no-AI mode for the companion. — **Later**

### Proactivity, triggers and environmental awareness

- Refine the intervention policy ("policy engine") with simple, explainable
  rules first: do not speak while the user is actively typing or spoke less
  than X minutes ago; speak on idle > Y minutes, on a prolonged context change,
  or when explicitly called. Keep the LLM deciding *what* to say, not *when*. — **Next**
- Improve application detection and per-app comments by feeding the model a
  narrow, well-defined context (visible/taskbar apps, active window, session
  duration). — **Next**
- Contextual reminders based on activity (long stretches in distracting apps,
  windows opened but unused for a long time) — optional. — **Later**
- Pattern-based proactive suggestions (for example, offering a routine you
  repeat at a given hour) — optional. — **Backlog**
- Daily goal tracking with emotional reactions from the character — optional. — **Backlog**
- Pomodoro-style visual timer where the character changes state per phase. — **Backlog**
- Friendly, non-technical system-resource alerts. — **Backlog**

### Agent (harness, tools, permissions)

- Tool/function calling with a permissioned harness: planning, execution loops,
  monitoring, validation, error handling and retries. — **Major**
- Narrow desktop actions: search files by text or voice, open programs, other
  low-intrusion operations. — **Major**
- Feed the harness with conversation and preference memory. — **Major**
- Read/connect to other apps such as notes and calendars. — **Backlog**
- Improve API-based agent usage: model discovery, per-API guidance and a
  harness design inspired by established coding agents. — **Later**
- Plugin/scripting API for custom reactions, commands and desktop automation,
  building on the pack system. — **Later**
- Voice interaction (output, and optional voice cloning). — **Later**

### Integrations (MCP and external services)

- MCP integration as the primary path for external tools and data. — **Later**
- React to calendar events (for example, encouraging the user before a
  meeting). — **Backlog**
- Read and friendly-summarize notifications (for example, email). — **Backlog**

### Platform, packaging and distribution

- Native Linux compatibility: X11 first, document Wayland limitations and
  plan native window APIs later. — **Next**
- Windows code signing (e.g., Azure Trusted Signing). — **Later**
- Native Linux packaging: Fedora RPM via COPR and Flatpak on Flathub. — **Later**
- Keep CI green on Ubuntu and Windows with tag-driven releases. — **Ongoing**
- Keep the single binary + optional model asset model; keep the base binary
  lean. — **Ongoing**

### Documentation, onboarding and website

- Improve the README, in-app guides and instructions, keeping EN/ES in sync. — **Next**
- Decide the web strategy: a standalone site or a wiki in the repository,
  depending on the intended content. — **Later**
- Document local small/quantized models accurately and update the related
  wording. — **Later**

### Long-term / experimental

- Mini-games and a separate room environment, using billboard sprites as a
  first step. — **Backlog**
- Game integrations (for example, a Minecraft companion, Phase-style). — **Backlog**
- Broader model/renderer ecosystem and community content. — **Backlog**
