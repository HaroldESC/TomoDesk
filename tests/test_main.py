import json
from pathlib import Path

from main import _init_pack_manager


def _make_pack(directory, folder, name):
    pack_path = Path(directory) / folder
    pack_path.mkdir(parents=True, exist_ok=True)
    (pack_path / "manifest.json").write_text(json.dumps({
        "name": name,
        "format": "personality-pack-v1",
        "type": "personality",
    }), encoding="utf-8")


def _config(tmp_path, active=None, enabled=True):
    return {
        "personality": {"name": "Tomo"},
        "personality_packs": {
            "enabled": enabled,
            "active_pack": active,
            "directory": str(tmp_path),
        },
    }


class TestInitPackManager:
    def test_name_normalized_from_active_pack(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Lin"
        assert cfg["personality"]["name"] == "Lin"

    def test_legacy_folder_ref_normalized(self, tmp_path):
        _make_pack(tmp_path, "default", "Tomo")
        cfg = _config(tmp_path, active="Default")
        pm = _init_pack_manager(cfg)
        assert pm._active_pack == "Tomo"
        assert cfg["personality"]["name"] == "Tomo"

    def test_disabled_pack_keeps_manual_name(self, tmp_path):
        _make_pack(tmp_path, "Lin", "Lin")
        cfg = _config(tmp_path, active="Lin", enabled=False)
        pm = _init_pack_manager(cfg)
        assert pm._active_pack is None
        assert cfg["personality"]["name"] == "Tomo"


class TestInitWorker:
    """The init thread must report failures instead of hanging the splash."""

    def test_run_reports_error_instead_of_raising(self, monkeypatch):
        import main

        def _boom(_config):
            raise ValueError("Invalid LLM endpoint")

        monkeypatch.setattr(main, "_initialize", _boom)
        worker = main._InitWorker({"llm": {}})
        received = []
        worker.error.connect(received.append)
        worker.finished.connect(lambda deps: received.append(("finished", deps)))

        worker.run()

        assert received == ["Invalid LLM endpoint"]

    def test_run_emits_deps_on_success(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "_initialize", lambda cfg: {"ok": True})
        worker = main._InitWorker({"llm": {}})
        errors = []
        done = []
        worker.error.connect(errors.append)
        worker.finished.connect(done.append)

        worker.run()

        assert errors == []
        assert done == [{"ok": True}]

    def test_run_does_not_emit_finished_after_error(self, monkeypatch):
        import main

        monkeypatch.setattr(main, "_initialize", lambda cfg: 1 / 0)
        worker = main._InitWorker({"llm": {}})
        events = []
        worker.finished.connect(lambda d: events.append("finished"))
        worker.error.connect(lambda m: events.append("error"))

        worker.run()

        assert events == ["error"]


class TestProviderLabel:
    """Every configured provider needs a human-readable error label."""

    def test_labels_by_provider(self):
        import main

        cases = {
            "ollama": "Ollama",
            "openai_compatible": "OpenAI",
            "llama_cpp": "llama.cpp",
            "custom": "custom",
        }
        for provider, expected in cases.items():
            config = {"llm": {"provider": provider, "endpoint": "http://x"}}
            label = main._provider_label(config)
            assert expected in label, f"{provider} -> {label}"

    def test_unknown_provider_returns_name(self):
        import main

        assert main._provider_label({"llm": {"provider": "weird"}}) == "weird"