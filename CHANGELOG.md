# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.4.0]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.4.0
[1.4.1]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.4.1
[1.5.0]: https://github.com/HaroldESC/TomoDesk/releases/tag/v1.5.0
