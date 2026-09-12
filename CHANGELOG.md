# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
