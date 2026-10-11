# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.1] - 2026-10-11

### Fixed

- The packaged app icon is drawn geometrically instead of with a system font.
  The release job runs `generate_icon.py` with `QT_QPA_PLATFORM=offscreen`,
  where Qt loads no fonts at all, so `drawText("T")` painted a missing-glyph
  box: shortcuts, the taskbar and the installer all showed a broken icon.
- The Windows executable carries its `RT_VERSION` resource again, so its file
  properties no longer read as unknown.
- `data/comments_en.yaml` and `data/comments_es.yaml` travel in the bundle, so
  a packaged install has ambient comments instead of an empty set.

### Changed

- The release build includes the embedded llama.cpp provider by default. It
  used to sit behind an opt-in flag that CI never passed, so the published
  binary offered local AI and then failed to load the model it had just
  downloaded. `build_windows.ps1 -Standard` and `build_unix.sh --standard`
  build the light variant on purpose, and `tomodesk.spec` aborts the build when
  the provider is required but missing.
- The first-run wizard and Settings no longer offer the local model when the
  binary cannot run it: the wizard disables "Local AI", the download button is
  greyed out, and `/model download` explains why instead of fetching ~800 MB.
- Messages about the missing local engine no longer tell users of a packaged
  build to run `pip install`.

## [1.7.0] - 2026-10-11

### Added

- Flat and round speech-bubble styles, implemented as visual recipes and
  selectable in Settings; unknown or stale values fall back to the dark style.
- Settings failures are surfaced with a message box instead of failing
  silently.
- `DatabaseManager.vacuum()` and `ChromaManager.clear_collection()` /
  `clear_all_collections()` to back the memory maintenance actions.
- Mood names are translated in the status-bar tooltip and in `/mood`.

### Fixed

- Secrets are redacted everywhere again: `SensitiveDataFilter` moved from the
  root logger to the file and console handlers, because records propagated
  from child loggers were bypassing it and writing API keys and tokens
  unredacted to `data/logs/tomodesk.log` and to the console.
- Short-term memory is guarded by a lock; appends from the GUI thread and the
  overlay chat workers could drop messages or hand out a torn snapshot.
- Five Settings actions that called missing methods now work: clear all
  memories, vacuum database, reindex notes, play tutorial and reset hints.
- The proactive monitors start after their callbacks are wired. They used to
  start before, so triggers were dropped silently and due reminders were
  deactivated without ever being shown.
- An error during initialization now shows a fatal dialog instead of leaving
  the splash on screen forever.
- The configured theme is applied at startup, so a dark-theme user no longer
  saw a light window until Settings re-applied it.
- Choosing the flat or round bubble style no longer raises `ValueError` at
  startup and leaves the splash hanging.
- `i18n.t()` honors its `default=` fallback again (ten call sites passed it),
  and the two keys the UI referenced but that were missing were added, so a
  raw key name is no longer shown in the bubble.
- Aborting a model download cancels it even when the worker was already
  deleted (`RuntimeError`).

### Changed

- Screen geometry moved into the `PlatformAdapter` contract
  (`primary_screen_geometry`, `screen_geometry_for_point`, reported by the new
  `screen_geometry` capability) and is implemented with the Win32 monitor
  APIs, so `WindowManager` no longer needs Qt.
- `src/__init__.py` exports only `__version__` and `main.py` builds its init
  worker through a factory, so CLI mode (`python main.py`) now runs on a
  machine without a GUI stack.
- Heavy dependencies (`ollama`, `chromadb`, `psutil`, `yaml`) are imported
  lazily inside the functions that use them.
- Shutdown flags moved out of the deps dict into a dedicated `_ShutdownState`,
  so they are no longer splatted into `MainWindow`.
- 42 unused translation keys removed from the locale files after verifying
  zero references.

### Performance

- `music_detected`, `coding_detected`, `late_night` and `system_resources`
  fire on state transitions instead of on every 2 s poll, with a cooldown for
  resources and word-boundary keyword matching, so "Unicode" or "cmdline" no
  longer count as coding.

### Tests

- The design system gained coverage (`tests/test_styles.py`): token parity
  between themes, the dark sheet really using the dark palette, and every
  generated sheet accepted by Qt.
- 24 tests that ran real work but asserted nothing now check deterministic
  invariants; `test_i18n.py` derives the version and the locale path from the
  project instead of pinning them.
- New concurrency tests for short-term memory, plus coverage for the platform
  geometry, the reminder checker, shutdown state, event throttling and the
  repaired settings actions.

### Documentation

- `AGENTS.md`, `docs/TECHNICAL_SPEC.md`, `README.md`, `docs/VISION.md` and
  `ROADMAP.md` aligned with the code (version, test count, package trees,
  removal of audio reactivity).
- The roadmap gained a v1.6.0 entry, themed `Planned` sections with target
  tiers, and an audit of every planned item against the code.

## [1.6.0] - 2026-09-22

### Added

- Platform abstraction layer `src/platform/`: `PlatformAdapter` contract with
  `WindowsAdapter` (pygetwindow + ctypes) and a degraded `NullAdapter` for
  other platforms, selected by a thread-safe `get_platform()` factory.
  `PlatformCapabilities` reports which desktop integrations are available.
- Settings → Advanced shows an `advanced_platform` group listing unavailable
  capabilities (EN/ES) and disables window-sitting and active-window privacy
  controls when window enumeration is unsupported.

### Changed

- `WindowManager` is now a Qt-aware facade over the platform adapter; its
  public dict contract and `window_sitting.py` behavior are unchanged.
- `SystemMonitor` reads idle time and the active window through the adapter
  (`None` title maps to the `"Unknown"` sentinel).
- The taskbar-entry helper duplicated across four dialogs moved to
  `src/gui/utils.py` and delegates to the adapter.
- `_restart_command()` gets its `creationflags` from the adapter.

### Fixed

- Opening the logs folder from Settings crashed on non-Windows platforms
  (`os.startfile` had no platform guard); it now uses `adapter.open_path()`.

## [1.5.0] - 2026-09-17

### Added

- Window-sitting now supports four real target modes: `active_window`,
  `mouse_window`, `closest_window` (nearest window by edge distance) and
  `fixed_spot`. The legacy `desktop` value is migrated to `fixed_spot`.
- Settings expose the four targets, four fallback corners
  (`bottom-right`, `bottom-left`, `top-right`, `top-left`) and the
  maximized/minimized behavior combos, with English and Spanish strings.
- `window_sitting` defaults added to the nested-config migration so older
  `config.yaml` files pick up the new keys.
- Single-instance guard: `main.py` takes an exclusive PID lock before creating
  the GUI, reclaims stale locks from crashed processes, and releases it before
  spawning a restart.

### Changed

- Window-sitting is re-read from the live config on every tick, and the
  Settings dialog pushes its changes to the running controller, so
  `target`, `fallback_position`, `transition_speed`, `enabled` and the
  max/min behaviors apply without restarting.
- The sitting poll interval is now 500 ms.
- The overlay always creates the sitting controller, so enabling or disabling
  it from Settings works at runtime.
- `WindowManager` reports `maximized`/`minimized` state and the native window
  handle (`hwnd`) for each window.
- `maximized_behavior` / `minimized_behavior` are defined as `0` = ignore the
  window (use the fallback) and `1` = adjust (clamp to the screen edge / sit on
  the taskbar). Both are commented in `config.example.yaml`.

### Fixed

- Window-sitting could oscillate between a target and the fallback because the
  overlay matched its own window by geometry. Own-window detection now uses the
  native HWND and returns a `SELF_TARGET` sentinel that keeps the character in
  place instead of jumping to the fallback.
- Tiny (1x1) windows and off-screen/minimized shell windows (`-32000`) are
  filtered out so they cannot be picked as targets.
- Multi-monitor with offset (non-rectangular) layouts no longer places the
  character in an off-screen gap: positions are clamped to the screen that owns
  the target.
- When a present window is ignored (for example a maximized Chrome window with
  `maximized_behavior=0`) the fallback is anchored to that window's screen, so
  the character still follows it across monitors.
- Focus and Do Not Disturb now suspend window-sitting from the menu, the tray,
  Settings and the `/proactive` command. The DND checkbox is no longer
  inverted and the value is no longer clobbered when the dialog closes.
- Settings for window-sitting are no longer delayed until the app restarts.

## [1.4.1] - 2026-09-11

### Fixed

- Closing the setup wizard after a background worker finished no longer raises
  `RuntimeError: _SizeWorker already deleted`. Workers now clear their
  reference on the `finished` signal instead of being deleted via
  `deleteLater`, so `_detach_workers` skips them safely.
- The setup wizard translation helper now forwards placeholders to `i18n.t`,
  removing the spurious "Missing placeholder ... in translation" error logs and
  the redundant outer `str.format` call for the `local_model`, `local_size`,
  `downloading_percent`, and `download_error` strings.

## [1.4.0] - 2026-09-10

### Added

- First-run setup wizard (`SetupWizard`) shown on the first launch, gated by
  the `setup.completed` flag. It lets the user choose between a local AI
  (llama.cpp), an external API, or postpone the decision.
- Local option displays the recommended GGUF model, queries its remote size
  via HTTP `HEAD`, and downloads it with a progress bar and cancellation.
- External API option validates the endpoint and model, and stores the API key
  in the OS keyring.
- Accepting the wizard persists the choice to `config.yaml` and restarts the
  app when the provider changed, so the LLM provider is rebuilt cleanly.
- Download layer gains `should_cancel` / `DownloadCancelled` and
  `remote_content_length` helpers.
- Build scripts (`build_windows.ps1`, `build_unix.sh`) accept `-Full` / `--full`
  to bundle the `llama-cpp-python` runtime (the model itself is not bundled due
  to the Llama Community License).
- `QLabel#error` style token for validation feedback.
- `setup` translations in English and Spanish locales.

### Fixed

- Window icon no longer shows as a generic square in development mode by
  falling back to `build/assets/tomodesk.png` when the PNG is not found at the
  project root.
- Settings sidebar navigation width test is now stable across platform font
  metrics by asserting against the design clamp.

### Changed

- `config.py` adds `setup.completed` defaults and the `is_setup_completed()`
  helper.
- `main.py` shows the setup wizard before creating the windows.

[1.6.0]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.6.0
[1.7.0]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.7.0
[1.7.1]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.7.1
