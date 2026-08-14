import os

import pytest
from PySide6.QtGui import QPixmap

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("DISPLAY", "") == "" and os.name != "nt",
        reason="GUI tests require a display server"
    ),
    pytest.mark.usefixtures("qapp"),
]

from src.gui.sprites.animation_manager import AnimationManager, AnimationState


def _make_pixmap(size=150, color=None):
    pix = QPixmap(size, size)
    pix.fill()
    return pix


def _make_frames(*names: str, count: int = 1) -> list:
    return [_make_pixmap() for _ in range(count)]


@pytest.fixture
def default_config():
    return {
        "name": "test",
        "frame_width": 150,
        "frame_height": 150,
        "states": {
            "idle": {
                "type": "simple",
                "frames": ["idle/f0.png"],
                "frame_durations": [500],
                "loop": True,
                "interruptible": True,
            },
            "talking": {
                "type": "simple",
                "frames": ["talk/f0.png", "talk/f1.png"],
                "frame_durations": [100, 100],
                "loop": True,
                "interruptible": True,
            },
            "sleeping": {
                "type": "simple",
                "frames": ["sleep/f0.png"],
                "frame_durations": [1000],
                "loop": True,
                "interruptible": True,
            },
            "happy": {
                "type": "one_shot",
                "frames": ["happy/f0.png", "happy/f1.png"],
                "frame_durations": [150, 150],
                "loop": False,
                "interruptible": True,
                "exit_transition": "idle",
            },
        },
    }


@pytest.fixture
def default_frames(default_config):
    cache = {}
    for state_name, cfg in default_config["states"].items():
        cache[state_name] = _make_frames(count=len(cfg["frames"]))
    return cache


class TestAnimationManager:
    def test_initial_state(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        assert am.current_state_name == AnimationState.IDLE
        assert am.current_frame_index == 0

    def test_request_state(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        result = am.request_state(AnimationState.TALKING)
        assert result
        assert am.current_state_name == AnimationState.TALKING
        assert am.current_frame_index == 0

    def test_unknown_state(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        result = am.request_state("nonexistent")
        assert not result
        assert am.current_state_name == AnimationState.IDLE

    def test_frame_advancement(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        am.request_state(AnimationState.TALKING)
        assert am.current_frame_index == 0
        # advance past first frame
        am.update(101)
        assert am.current_frame_index == 1
        # advance past second frame (loop back)
        am.update(101)
        assert am.current_frame_index == 0

    def test_one_shot_completes_and_exits(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        am.request_state(AnimationState.HAPPY)
        assert am.current_state_name == AnimationState.HAPPY
        # advance past both frames (150ms each)
        am.update(160)
        assert am.current_frame_index == 1
        am.update(160)
        assert am.current_state_name == AnimationState.IDLE

    def test_force_state_clears_transition(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        am.request_state(AnimationState.SLEEPING)
        am.force_state(AnimationState.IDLE)
        assert am.current_state_name == AnimationState.IDLE
        assert am._transition_frames is None
        assert am._pending_state is None

    def test_set_frame_speed(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        am.set_frame_speed(2.0)
        assert am._base_speed == 2.0
        am.set_frame_speed(0.0)
        assert am._base_speed == 0.01

    def test_get_current_pixmap_returns_pixmap(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        pix = am.get_current_pixmap()
        assert isinstance(pix, QPixmap)
        assert not pix.isNull()

    def test_force_state(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        am.force_state(AnimationState.SLEEPING)
        assert am.current_state_name == AnimationState.SLEEPING

    def test_get_current_state_name(self, default_config, default_frames):
        am = AnimationManager(default_config, default_frames)
        assert am.get_current_state_name() == AnimationState.IDLE


class TestAnimationManagerComposite:
    @pytest.fixture
    def composite_config(self):
        return {
            "name": "composite_test",
            "frame_width": 150,
            "frame_height": 150,
            "states": {
                "idle": {
                    "type": "composite",
                    "animations": [
                        {
                            "name": "blink",
                            "frames": ["idle/blink/f0.png", "idle/blink/f1.png"],
                            "frame_durations": [4000, 100],
                            "loop": True,
                            "weight": 10,
                            "cooldown_ms": 0,
                        },
                        {
                            "name": "look",
                            "frames": ["idle/look/f0.png"],
                            "frame_durations": [2000],
                            "loop": True,
                            "weight": 3,
                            "cooldown_ms": 5000,
                        },
                    ],
                },
            },
        }

    @pytest.fixture
    def composite_frames(self, composite_config):
        cache = {}
        states = composite_config["states"]
        for state_name, cfg in states.items():
            if cfg["type"] == "composite":
                for sub in cfg.get("animations", []):
                    key = f"{state_name}/{sub['name']}"
                    cache[key] = _make_frames(count=len(sub["frames"]))
        return cache

    def test_composite_picks_sub_animation(self, composite_config, composite_frames):
        am = AnimationManager(composite_config, composite_frames)
        state = am.get_current_state()
        assert state.type == "composite"
        # After first update, a sub-animation should be picked
        am.update(1)
        assert state.current_sub_anim is not None
        assert state.current_sub_anim.name in ("blink", "look")

    def test_get_current_pixmap_composite(self, composite_config, composite_frames):
        am = AnimationManager(composite_config, composite_frames)
        am.update(1)
        pix = am.get_current_pixmap()
        assert isinstance(pix, QPixmap)
        assert not pix.isNull()


class TestAnimationManagerVariants:
    @pytest.fixture
    def variant_config(self):
        return {
            "name": "variant_test",
            "frame_width": 150,
            "frame_height": 150,
            "states": {
                "idle": {
                    "type": "simple",
                    "frames": ["idle/f0.png"],
                    "frame_durations": [500],
                    "loop": True,
                    "interruptible": True,
                    "variants": {
                        "sleepy": {
                            "condition": {"energy": [0.0, 0.3]},
                            "frame_durations": [1000],
                        },
                    },
                },
                "talking": {
                    "type": "simple",
                    "frames": ["talk/f0.png"],
                    "frame_durations": [100],
                    "loop": True,
                    "interruptible": True,
                },
            },
        }

    @pytest.fixture
    def variant_frames(self, variant_config):
        cache = {}
        for state_name, cfg in variant_config["states"].items():
            cache[state_name] = _make_frames(count=len(cfg["frames"]))
        # Add variant frames
        cache["idle/sleepy"] = _make_frames(count=1)
        return cache

    def test_variant_applied(self, variant_config, variant_frames):
        am = AnimationManager(variant_config, variant_frames)
        # Transition to talking first, then back to idle with low energy
        am.request_state("talking")
        am.request_state("idle", {"energy": 0.1})
        state = am.get_current_state()
        assert state.active_durations == [1000]

    def test_variant_not_applied_when_condition_not_met(self, variant_config, variant_frames):
        am = AnimationManager(variant_config, variant_frames)
        am.request_state("idle", {"energy": 0.5})
        state = am.get_current_state()
        assert state.active_durations == [500]

    def test_unknown_state_in_request_returns_false(self, variant_config, variant_frames):
        am = AnimationManager(variant_config, variant_frames)
        result = am.request_state("nonexistent", {"energy": 0.9})
        assert not result


class TestAnimationStateConstants:
    def test_constants_are_strings(self):
        assert AnimationState.IDLE == "idle"
        assert AnimationState.IDLE_ANIM == "idle_anim"
        assert AnimationState.TALKING == "talking"
        assert AnimationState.SLEEPING == "sleeping"
        assert AnimationState.HAPPY == "happy"
