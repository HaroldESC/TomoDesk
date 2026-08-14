import time

import pytest

from src.llm.proactive_policy import ProactivePolicy


def make_config(
    enabled=True, cooldown=3600, max_per_hour=5, probability=1.0
) -> dict:
    return {
        "modes": {
            "proactive_comments": enabled,
            "proactive_cooldown_seconds": cooldown,
            "max_comments_per_hour": max_per_hour,
            "comment_probability": probability,
        }
    }


def test_enabled_by_default():
    policy = ProactivePolicy(make_config())
    assert policy.can_comment("generic")


def test_disabled():
    policy = ProactivePolicy(make_config(enabled=False))
    assert not policy.can_comment("generic")


def test_cooldown():
    policy = ProactivePolicy(make_config(cooldown=3600))
    assert policy.can_comment("generic")
    policy.record_comment()
    assert not policy.can_comment("generic")


def test_cooldown_expires():
    policy = ProactivePolicy(make_config(cooldown=0))
    assert policy.can_comment("generic")


def test_focus_mode():
    policy = ProactivePolicy(make_config())
    policy.set_focus_mode(True)
    assert not policy.can_comment("generic")
    policy.set_focus_mode(False)
    assert policy.can_comment("generic")


def test_dnd_mode():
    policy = ProactivePolicy(make_config())
    policy.set_dnd_mode(True)
    assert not policy.can_comment("generic")
    policy.set_dnd_mode(False)
    assert policy.can_comment("generic")


def test_max_per_hour():
    policy = ProactivePolicy(make_config(max_per_hour=2, cooldown=0))
    assert policy.can_comment("generic")
    policy.record_comment()
    assert policy.can_comment("generic")
    policy.record_comment()
    assert not policy.can_comment("generic")


def test_random_probability():
    policy = ProactivePolicy(make_config(probability=0.0))
    assert not policy.can_comment("random")


def test_get_stats():
    policy = ProactivePolicy(make_config())
    stats = policy.get_stats()
    assert stats["enabled"] is True
    assert stats["focus_mode"] is False
    assert stats["dnd_mode"] is False
    assert stats["comments_this_hour"] == 0


def test_get_stats_after_comment():
    policy = ProactivePolicy(make_config(cooldown=0))
    policy.record_comment()
    stats = policy.get_stats()
    assert stats["comments_this_hour"] == 1


def test_clean_old_timestamps():
    policy = ProactivePolicy(make_config(max_per_hour=10, cooldown=0))
    old = time.time() - 7200
    policy._comment_timestamps = [old]
    policy._clean_old_timestamps()
    assert len(policy._comment_timestamps) == 0
