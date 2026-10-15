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

### v1.8.0

- UI overhaul of the four small dialogs, the chat, the overlay and Settings.
  The episodic-memory dialog became a list plus read panel, the note editor lost
  its 100px cap and its silent data loss (Save after "New" overwrote the previous
  note), and the destructive buttons of all three dialogs enable only when they
  can act and explain why in a tooltip.
- Chat: message time in the bubble tooltip, day separators, an animated typing
  bubble, selectable text and a fixed follow-to-bottom autoscroll.
- The overlay no longer steals focus or swallows clicks in its transparent
  margin (its hit area follows the sprite), and the main window remembers its
  geometry between sessions.
- Visual layer aligned with `docs/Design.md`: the chat and bubble sheets moved
  into `styles.py`, an explicit button hierarchy (`danger`, `flat`, one primary
  per dialog), the §3.3 inline-input geometry, optional status-bar icons
  (`ui.status_icons`, off by default) isolated in `src/gui/styles/icons.py`, and
  a test that fails on any hex literal outside `styles.py`.
- Settings search matches the visible labels and technical aliases, twenty
  controls gained tooltips, and the small dialogs are keyboard-navigable.

### v1.7.1

- Fixed the packaged app icon: the "T" is now drawn geometrically instead of
  with a system font, because the release job runs `generate_icon.py` with
  `QT_QPA_PLATFORM=offscreen`, where Qt loads no fonts and `drawText` painted a
  missing-glyph box on every shortcut, the taskbar and the installer.
- The release build ships the embedded `llama-cpp-python` runtime by default
  and aborts the build if it is missing; `-Standard` / `--standard` build the
  light variant on purpose.
- The first-run wizard and Settings hide the local model when the binary cannot
  run it, and `/model download` explains why instead of fetching ~800 MB.
- Restored the exe's `RT_VERSION` resource and bundled
  `data/comments_{en,es}.yaml`, which the packaged app was missing.

### v1.7.0

- CLI mode without a GUI stack: `src/__init__.py` exports only `__version__`,
  `main.py` builds its init worker through a factory, and heavy dependencies
  (`ollama`, `chromadb`, `psutil`, `yaml`) are imported lazily, so
  `python main.py` runs on a machine without PySide6.
- Screen geometry moved into the `PlatformAdapter` contract
  (`primary_screen_geometry`, `screen_geometry_for_point`), removing the last
  `QGuiApplication` from `WindowManager`.
- Fixed secret redaction: `SensitiveDataFilter` attaches to the file and
  console handlers instead of the root logger, so API keys and tokens emitted
  by child loggers are redacted again.
- Startup path fixed: the proactive monitors start after their callbacks are
  wired (triggers were dropped and due reminders were deactivated unseen),
  initialization errors surface instead of hanging the splash, the configured
  theme applies immediately, and the flat/round bubble styles no longer raise
  at startup.
- Five Settings actions that called missing methods now work (clear all
  memories, vacuum database, reindex notes, play tutorial, reset hints) and
  report their failures.
- Short-term memory is lock-guarded, and `music_detected`, `coding_detected`,
  `late_night` and `system_resources` fire on state transitions with a
  cooldown instead of on every 2 s poll.
- i18n: `t()` honors `default=`, two missing keys were added, the mood tooltip
  and `/mood` are translated, and 42 unused keys were dropped.

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
- `-Full` / `--full` build variants that bundle the `llama-cpp-python` runtime
  (now the default; `-Standard` / `--standard` opt out).

### v1.3.0

- Window icon falls back to `build/assets/tomodesk.png` in development mode
  instead of showing a generic square.
- Settings sidebar navigation-width test made stable across platform font
  metrics.
- Debug mode dumps the exact prompt sent to the model (chat and proactive) to
  the log, gated by `logs.debug_prompts` and toggleable with `/debug on|off`
  or from Settings → Advanced → Logs.

### v1.2.0

- Character name is defined by the active personality pack, with a
  `resolve_pack()` helper for legacy/misaligned configs.
- Unified Tomo/TomoDesk identity: default character name is "Tomo" and the
  About dialog reads the real version dynamically.

### v1.1.0

- Packaging and distribution: PyInstaller one-dir builds with Inno Setup
  (Windows) and AppImage (Linux), plus a tag-triggered release job in CI.
- Settings redesigned with sidebar navigation, grouped pages and a search field
  that filters pages and groups.
- Sprite animation engine reworked around visual intents: explicit
  `{from}_to_{to}` transitions, timed overlays (blink, bob) and emotion
  variants conditioned on the emotional state.
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
- Animated 2D character overlay with speech bubbles, sprite animations, and window-sitting
- Personality packs (ZIP/directory) and default character pack
- Notes, reminders, and semantic search
- System tray integration and bilingual UI (EN/ES)
- Interactive tutorial with anchored contextual hints (drag, click,
  double-click, bubble, right-click), replayable from Settings → Advanced

## Planned

### AI providers and first-run experience

- Make the embedded llama.cpp provider the default on first run: ship a small
  curated GGUF so the model download becomes optional, and switch
  `config.example.yaml` away from `ollama`. The runtime already ships in the
  default build since v1.7.1, and the curated GGUF is downloaded on demand
  (license). — **Next**
- Streamline first-run so a new user gets a working local model with one click,
  with a clear side path to an external API. The wizard still needs four steps,
  a ~770 MB download and an app restart. — **Next**
- Provider UX: dynamic Settings per provider, endpoint/model validation,
  model discovery, effective-model display and per-API tips (rate limits, 429
  behavior, role-play tuning). The provider page is static today and endpoint
  validation only covers `openai_compatible`. — **Next**
- Surface the active provider (model/endpoint, never secrets) in the UI and in
  debug output, and reduce the need to restart when switching. The choice is
  already persisted reliably and secrets stay in the keyring, but the provider
  is built once at startup. — **Next**
- Extend the existing prompt dump (`logs.debug_prompts`, `/debug`, Settings
  toggle) with the provider, temperature and context length, and add real CLI
  flags (`--debug`, `--verbose`). The log-level combo in Settings is saved but
  never applied. — **Next**
- Keep Ollama as a recommended external local runtime ("bring your own") and
  review free/low-cost APIs (OpenRouter, Groq, Google AI Studio). — **Later**
- Review dual-model (small always-on + large on-demand) and hybrid/multimodal
  models, including image analysis. — **Later**

### Settings and interface

- Redesign Settings to reduce option saturation: progressive disclosure or an
  advanced mode, plus stronger grouping. Sidebar navigation and grouped pages
  shipped in v1.1.0, and v1.8.0 made the search match row labels and technical
  aliases; there is still no advanced toggle. — **Next**
- Add inline help beyond tooltips and a save indicator for automatic summaries.
  v1.8.0 added tooltips to twenty controls and made closing with pending changes
  ask for confirmation, but there is no save indicator and many controls are
  still unexplained. — **Next**
- Fix the speech-bubble tail when the character is near the left/right screen
  edge. The tail is hardcoded to the horizontal center of the bubble
  (`cx = w / 2.0`) and never receives the character's position. Fixed in v1.8.1:
  the overlay now passes the character's x to `SpeechBubble.set_tail_target()`
  and the tail clamps to the bubble body so it never lands on a rounded corner. — **Done**
- Standardize the "loading" affordance (splash, setup, thinking bubble). The
  chat gained an animated typing bubble in v1.8.0; the splash and the setup
  wizard still use their own. — **Next**
- Expand Help: keyboard shortcuts, a simple initial tutorial and an optional
  advanced (companion-style) tutorial, plus a documentation link. The initial
  tutorial with anchored hints shipped in v1.0.0 and is replayable from
  Settings; the six existing shortcuts are documented nowhere and the About
  dialog links to no site. — **Later**
- Refactor large GUI modules for maintainability: `settings_dialog.py` (~2050
  lines), `overlay_window.py` (~745) and `main_window.py` (~640) each mix
  several unrelated concerns. — **Later**
- Improve the terminal/console experience and CLI feature parity. Commands
  (`/note`, `/remind`, `/memories`, `/proactive`, `/debug`, ...) are shared
  with the GUI, but the CLI cannot edit any setting and the REPL is a bare
  `input()` loop without history or completion. — **Later**
- Explore alternative frontends (phone, tablet, book, holographic panel). — **Backlog**

### Character, animation and avatars

- Optional emotion system with mood-driven expression changes tied to the
  response. The engine supports emotion-conditioned clip variants and the
  overlay re-syncs the mood on every visual-state change, but the mood only
  reacts to user keywords and OS events (never to the reply text), the bundled
  `default` pack declares no `variants`, and the system cannot be switched
  off. — **Next**
- Richer animation states/transitions and improved sprite tooling. Clip modes,
  explicit transitions, overlays and emotion variants shipped in v1.1.0; there
  is no sprite authoring or validation tool yet. — **Next**
- Eye/head tracking that follows the cursor, designed with future avatar
  systems in mind. A `LOOKING` intent exists in the catalog but nothing
  produces it and the sprite is painted without offsets. — **Later**
- Plan character movement/roaming across the desktop. Window-sitting is
  reactive (follows a target window); there is no autonomous roaming. — **Later**
- Pluggable avatars: expand 2D formats (Live2D, VRM) and add 3D support. — **Major**
- Create first-party base characters with their own lore/personality and
  matching sprites/models. The bundled `default` pack is a placeholder without
  lore, and personality packs and sprite packs remain independent systems with
  no character-to-sprite link. — **Later**
- Grow the personality-pack catalog. — **Backlog**

### Personality, sprite and context packs

- Redesign the personality, sprite and context pack systems as one documented,
  versioned ecosystem with a consistent manifest and tooling. All three are
  JSON-manifest based but remain three loaders with three validation paths
  (personality packs have no JSON Schema, sprite packs are directory-only) and
  two distribution models. — **Next**
- Expose sounds and emotion variants from inside personality packs. Sounds
  stay reserved: `discover_sounds()` lists the files but has no consumer and the
  project has no audio playback. Emotion variants exist in sprite packs only,
  not in personality packs. — **Later**
- Pack authoring tooling (validator, template, creator utility) and a public
  catalog. — **Later**
- Pack schema versioning and compatibility guarantees across app releases. The
  three formats only compare their `-v1` string for equality, and
  `min_tomodesk_version` is declared in the bundled manifest but never checked
  against `src.__version__`. — **Later**

### Memory, emotions and relationship

- Tune memory policies from the UI: thresholds, context rules and
  short/mid/long-term toggles. Episodic thresholds and the short-term cap are
  already exposed in Settings; the CP/MP/LP toggles in `config.example.yaml`
  are never read, context rules have neither UI nor consumer, and
  `include_notes` is saved but unused. — **Next**
- Revise the affection/closeness model and persist relationship state per user
  profile. Only `closeness` is persisted today; happiness, energy, curiosity
  and connection reset on every start. — **Next**
- Add per-user profile configuration (identity, preferences, relationship). — **Next**
- Improve episodic recall ranking (today a distance cutoff plus top-N) and
  connect episodic memory to the proactive engine for session-level goals;
  `build_proactive_prompt` exists but nothing calls it. — **Next**
- Fix `has_recent_suggestion()`, which filters on a `suggestion` source that is
  never written, so the episodic suggestion repeats on every message once the
  short-term buffer grows. — **Next**
- Make emotions fully optional, including a no-AI mode for the companion. — **Later**

### Proactivity, triggers and environmental awareness

- Refine the intervention policy ("policy engine") with simple, explainable
  rules first: do not speak while the user is actively typing or spoke less
  than X minutes ago; speak on idle > Y minutes, on a prolonged context change,
  or when explicitly called. Cooldown, max-per-hour, random probability and
  Focus/DND already gate the triggers; there is no typing detection, the idle
  threshold is hardcoded to 10 minutes, the rules are not named or traced, and
  the LLM is not involved: canned pack phrases are used. Keep the LLM deciding
  *what* to say, not *when*. — **Next**
- Wire the GUI delivery callbacks before the background monitors start, so a
  proactive comment cannot consume rate-limit without being delivered while the
  window is still being built. — **Next**
- Improve application detection and per-app comments by feeding the model a
  narrow, well-defined context (visible/taskbar apps, active window, session
  duration). The prompt already receives time of day, active window, idle
  seconds and CPU/RAM; window enumeration exists in the platform adapter but is
  only used by window-sitting. — **Next**
- Contextual reminders based on activity (long stretches in distracting apps,
  windows opened but unused for a long time) — optional. — **Later**
- Pattern-based proactive suggestions (for example, offering a routine you
  repeat at a given hour) — optional. — **Backlog**
- Daily goal tracking with emotional reactions from the character — optional. — **Backlog**
- Pomodoro-style visual timer where the character changes state per phase. — **Backlog**
- Friendly, non-technical system-resource alerts. The trigger exists with
  hardcoded thresholds (CPU > 80, RAM > 85), but two of the four phrases are
  raw percentages, the thresholds are not configurable and the strings live in
  the comments files instead of the locale catalogs. — **Backlog**

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
  plan native window APIs later. Linux currently resolves to the degraded
  `NullAdapter`, so window-sitting and active-window features are disabled and
  the Wayland note is a single line in `docs/DISTRIBUTION.md`. — **Next**
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
