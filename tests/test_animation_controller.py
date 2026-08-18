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

from src.core.intents import VisualIntent
from src.gui.sprites.animation_controller import AnimationController
from src.gui.sprites.sprite_models import AnimationClip, ClipFrame, SpritePackData


def _pixmap(size=64):
    pix = QPixmap(size, size)
    pix.fill()
    return pix


def _clip(name, mode="loop", durations=(100, 100), **kw):
    frames = [ClipFrame(file=f"{name}_{i}.png", duration_ms=d)
              for i, d in enumerate(durations)]
    return AnimationClip(name=name, mode=mode, frames=frames, **kw)


def _pack(intent_map=None, fallbacks=None, clips=None, transitions=None):
    clips = clips or {}
    intent_map = intent_map or {VisualIntent.IDLE.value: "idle"}
    return SpritePackData(
        id="test", name="Test", version="1.0.0",
        assets={"image_format": "png", "frame_width": 64, "frame_height": 64},
        intent_map=intent_map,
        fallbacks=fallbacks or {},
        clips=clips,
        transitions=transitions or {},
    )


def _frames(clips):
    cache = {}
    for name, clip in clips.items():
        cache[name] = [_pixmap() for _ in range(len(clip.frames))]
    return cache


def _base_clips():
    return {
        "idle": _clip("idle", durations=(4000,)),
        "talking": _clip("talking"),
        "sleeping": _clip("sleeping", mode="hold", durations=(1000,),
                          interruptible=False),
        "happy": _clip("happy", mode="once", durations=(150, 150),
                       return_to=VisualIntent.IDLE.value),
    }


def _base_intent_map():
    return {
        VisualIntent.IDLE.value: "idle",
        VisualIntent.TALKING.value: "talking",
        VisualIntent.SLEEPING.value: "sleeping",
        VisualIntent.CELEBRATE.value: "happy",
    }


def _make_controller(intent_map=None, fallbacks=None, clips=None,
                     transitions=None):
    clips = clips if clips is not None else _base_clips()
    pack = _pack(intent_map or _base_intent_map(), fallbacks, clips, transitions)
    return AnimationController(pack, _frames(clips))


class TestInitialState:
    def test_initial_intent_idle(self):
        ctrl = _make_controller()
        assert ctrl.current_intent == VisualIntent.IDLE.value
        assert ctrl.current_clip_name == "idle"
        assert ctrl.current_frame_index == 0

    def test_initial_pixmap(self):
        ctrl = _make_controller()
        pix = ctrl.get_current_pixmap()
        assert isinstance(pix, QPixmap)
        assert not pix.isNull()


class TestRequestIntent:
    def test_request_talking(self):
        ctrl = _make_controller()
        assert ctrl.request_intent(VisualIntent.TALKING) is True
        assert ctrl.current_intent == VisualIntent.TALKING.value
        assert ctrl.current_clip_name == "talking"

    def test_accepts_plain_string(self):
        ctrl = _make_controller()
        assert ctrl.request_intent("TALKING") is True
        assert ctrl.current_clip_name == "talking"

    def test_unknown_intent_falls_back_to_idle(self):
        ctrl = _make_controller()
        assert ctrl.request_intent("DANCING") is True
        assert ctrl.current_clip_name == "idle"

    def test_fallback_chain(self):
        clips = {
            "idle": _clip("idle", durations=(4000,)),
            "thinking": _clip("thinking"),
        }
        ctrl = _make_controller(
            intent_map={VisualIntent.IDLE.value: "idle",
                        VisualIntent.THINKING.value: "thinking"},
            fallbacks={VisualIntent.WORKING_CODE.value: VisualIntent.THINKING.value},
            clips=clips,
        )
        assert ctrl.request_intent(VisualIntent.WORKING_CODE) is True
        assert ctrl.current_clip_name == "thinking"

    def test_fallback_to_idle_when_no_clip(self):
        ctrl = _make_controller(fallbacks={VisualIntent.WORKING_CODE.value: VisualIntent.IDLE.value})
        assert ctrl.request_intent(VisualIntent.WORKING_CODE) is True
        assert ctrl.current_clip_name == "idle"


class TestAdvancement:
    def test_loop_advances_and_wraps(self):
        ctrl = _make_controller()
        ctrl.request_intent(VisualIntent.TALKING)
        assert ctrl.current_frame_index == 0
        ctrl.update(101)
        assert ctrl.current_frame_index == 1
        ctrl.update(101)
        assert ctrl.current_frame_index == 0

    def test_once_completes_and_returns(self):
        ctrl = _make_controller()
        ctrl.request_intent(VisualIntent.CELEBRATE)
        assert ctrl.current_clip_name == "happy"
        ctrl.update(160)
        assert ctrl.current_frame_index == 1
        ctrl.update(160)
        assert ctrl.current_clip_name == "idle"

    def test_hold_stays_on_last_frame(self):
        ctrl = _make_controller()
        ctrl.request_intent(VisualIntent.SLEEPING)
        ctrl.update(1100)
        assert ctrl.current_frame_index == 0

    def test_set_speed_multiplier(self):
        ctrl = _make_controller()
        ctrl.set_speed(2.0)
        ctrl.request_intent(VisualIntent.TALKING)
        ctrl.update(60)
        assert ctrl.current_frame_index == 1


class TestNonInterruptible:
    def test_sleeping_queues_intent(self):
        ctrl = _make_controller()
        ctrl.request_intent(VisualIntent.SLEEPING)
        result = ctrl.request_intent(VisualIntent.TALKING)
        assert result is False
        assert ctrl.current_clip_name == "sleeping"
        # advance until queued intent applies (hold clip never advances, so
        # force to idle to verify queue is drained)
        ctrl.force_intent(VisualIntent.IDLE)
        ctrl.update(101)
        assert ctrl.current_clip_name == "idle"


class TestVariants:
    def _variant_clips(self):
        clips = _base_clips()
        clips["idle_tired"] = _clip("idle_tired", durations=(1000,))
        clips["idle"].variants = {
            "tired": {"condition": {"energy": [0.0, 0.3]},
                      "clip": "idle_tired"},
        }
        return clips

    def test_variant_applied(self):
        ctrl = _make_controller(clips=self._variant_clips())
        ctrl.request_intent(VisualIntent.IDLE, {"energy": 0.1})
        pix = ctrl.get_current_pixmap()
        assert not pix.isNull()
        assert ctrl._variant_clip_name == "idle_tired"

    def test_variant_not_applied_when_condition_not_met(self):
        ctrl = _make_controller(clips=self._variant_clips())
        ctrl.request_intent(VisualIntent.IDLE, {"energy": 0.9})
        assert ctrl._variant_clip_name is None


class TestOverlays:
    def test_blink_overlay_fires_and_returns(self):
        clips = _base_clips()
        clips["blink"] = AnimationClip(
            name="blink", mode="timed", interval_ms=4000,
            frames=[ClipFrame(file="blink_0.png", duration_ms=100)],
        )
        clips["idle"].overlays = ["blink"]
        ctrl = _make_controller(clips=clips)
        ctrl.update(3999)
        assert ctrl._overlay_clip is None
        ctrl.update(2)
        assert ctrl._overlay_clip is not None
        assert ctrl.current_clip_name == "idle"
        pix = ctrl.get_current_pixmap()
        assert not pix.isNull()
        # overlay finishes -> back to base
        ctrl.update(101)
        assert ctrl._overlay_clip is None


class TestTransitions:
    def test_specific_transition_plays_then_switches(self):
        clips = _base_clips()
        transitions = {"idle_to_talking": {"frames": ["talking"], "frame_durations": [200]}}
        ctrl = _make_controller(clips=clips, transitions=transitions)
        ctrl.request_intent(VisualIntent.TALKING)
        assert ctrl._transition_frames is not None
        assert ctrl.current_clip_name == "idle"
        ctrl.update(201)
        assert ctrl.current_clip_name == "idle"
        ctrl.update(201)
        assert ctrl.current_clip_name == "talking"

    def test_force_intent_clears_transition(self):
        clips = _base_clips()
        transitions = {"idle_to_talking": {"frames": ["talking"], "frame_durations": [200]}}
        ctrl = _make_controller(clips=clips, transitions=transitions)
        ctrl.request_intent(VisualIntent.TALKING)
        ctrl.force_intent(VisualIntent.TALKING)
        assert ctrl._transition_frames is None
        assert ctrl.current_clip_name == "talking"