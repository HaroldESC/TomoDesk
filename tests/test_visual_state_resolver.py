import pytest

from src.core.intents import VisualIntent
from src.core.visual_state_resolver import IntentRequest, VisualStateResolver


def _req(intent, priority=1, one_shot=False):
    return IntentRequest(
        intent=VisualIntent(intent),
        priority=priority,
        source="test",
        one_shot=one_shot,
    )


class FakeContext:
    def __init__(self, result=None):
        self._result = result

    def resolve_event(self, event, payload=None):
        return self._result


def test_default_is_idle():
    resolver = VisualStateResolver()
    assert resolver.resolve() == VisualIntent.IDLE


def test_no_context_ignores_events():
    resolver = VisualStateResolver()
    resolver.push_event("build.success", {})
    assert resolver.resolve() == VisualIntent.IDLE


def test_agent_intent_overrides_context():
    resolver = VisualStateResolver(FakeContext(_req("WORKING_CODE", priority=2)))
    resolver.push_event("app.foreground", {"app": "Code"})
    resolver.set_agent_intent(VisualIntent.TALKING)
    assert resolver.resolve() == VisualIntent.TALKING
    resolver.set_agent_intent(None)
    assert resolver.resolve() == VisualIntent.WORKING_CODE


def test_app_foreground_sets_base():
    resolver = VisualStateResolver(FakeContext(_req("WORKING_CODE", priority=2)))
    resolver.push_event("app.foreground", {"app": "Code"})
    assert resolver.resolve() == VisualIntent.WORKING_CODE
    assert resolver.base_intent == VisualIntent.WORKING_CODE


def test_app_foreground_clears_base_when_no_match():
    resolver = VisualStateResolver(FakeContext(_req("WORKING_CODE", priority=2)))
    resolver.push_event("app.foreground", {"app": "Code"})
    assert resolver.resolve() == VisualIntent.WORKING_CODE

    resolver._context = FakeContext(None)
    resolver.push_event("app.foreground", {"app": "Discord"})
    assert resolver.resolve() == VisualIntent.IDLE
    assert resolver.base_intent is None


def test_one_shot_transient_then_clear():
    resolver = VisualStateResolver(FakeContext(_req("CELEBRATE", priority=3, one_shot=True)))
    resolver.push_event("build.success", {})
    assert resolver.has_transient()
    assert resolver.transient_intent() == VisualIntent.CELEBRATE
    assert resolver.resolve() == VisualIntent.CELEBRATE

    resolver.clear_transient()
    assert not resolver.has_transient()
    assert resolver.resolve() == VisualIntent.IDLE


def test_transient_wins_over_lower_priority_base():
    resolver = VisualStateResolver(FakeContext(_req("WORKING_CODE", priority=2)))
    resolver.push_event("app.foreground", {"app": "Code"})
    resolver.push_event("build.success", {})
    assert resolver.resolve() == VisualIntent.WORKING_CODE

    resolver._context = FakeContext(_req("CELEBRATE", priority=3, one_shot=True))
    resolver.push_event("build.success", {})
    assert resolver.resolve() == VisualIntent.CELEBRATE


def test_transient_does_not_override_higher_priority_base():
    resolver = VisualStateResolver(FakeContext(_req("WORKING_CODE", priority=5)))
    resolver.push_event("app.foreground", {"app": "Code"})

    resolver._context = FakeContext(_req("CELEBRATE", priority=1, one_shot=True))
    resolver.push_event("build.success", {})
    assert resolver.resolve() == VisualIntent.WORKING_CODE


def test_agent_pauses_transient():
    resolver = VisualStateResolver(FakeContext(_req("CELEBRATE", priority=3, one_shot=True)))
    resolver.push_event("build.success", {})
    resolver.set_agent_intent(VisualIntent.TALKING)
    assert resolver.resolve() == VisualIntent.TALKING
    resolver.set_agent_intent(None)
    assert resolver.resolve() == VisualIntent.CELEBRATE


def test_set_agent_intent_string():
    resolver = VisualStateResolver()
    resolver.set_agent_intent("sleeping")
    assert resolver.resolve() == VisualIntent.SLEEPING
    resolver.set_agent_intent("INVALID INTENT")
    assert resolver.resolve() == VisualIntent.IDLE


def test_integration_with_context_pack_manager(tmp_path):
    import json
    from src.context.context_pack import ContextPackManager

    pack_dir = tmp_path / "vscode"
    pack_dir.mkdir()
    with open(pack_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "id": "vscode",
            "name": "VS Code",
            "version": "1.0.0",
            "format": "context-pack-v1",
            "events": {
                "app.foreground": {
                    "match": {"app": ["code"]},
                    "intent": "WORKING_CODE",
                    "priority": 2,
                },
                "build.success": {
                    "intent": "CELEBRATE",
                    "priority": 3,
                    "one_shot": True,
                },
            },
        }, f)

    mgr = ContextPackManager({"context": {"active_packs": ["vscode"]}}, str(tmp_path))
    resolver = VisualStateResolver(mgr)

    resolver.push_event("app.foreground", {"app": "Visual Studio Code"})
    assert resolver.resolve() == VisualIntent.WORKING_CODE

    resolver.push_event("build.success", {})
    assert resolver.resolve() == VisualIntent.CELEBRATE
    resolver.clear_transient()
    assert resolver.resolve() == VisualIntent.WORKING_CODE

    resolver.set_agent_intent(VisualIntent.TALKING)
    assert resolver.resolve() == VisualIntent.TALKING