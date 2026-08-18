import pytest

from src.core.intents import (
    OFFICIAL_INTENTS,
    VisualIntent,
    is_official,
    normalize_intent,
)


class TestVisualIntent:
    def test_official_catalog_size(self):
        assert len(OFFICIAL_INTENTS) == 16

    def test_idle_is_default_first(self):
        assert VisualIntent.IDLE == "IDLE"

    def test_core_intents_exist(self):
        for name in ("IDLE", "TALKING", "LISTENING", "THINKING", "SLEEPING",
                     "CELEBRATE", "SURPRISED", "CONFUSED", "WORKING_CODE",
                     "WORKING_ART", "READING", "WRITING", "GAMING", "WAITING",
                     "LOOKING", "NOTIFICATION"):
            assert name in OFFICIAL_INTENTS


class TestNormalizeIntent:
    def test_member_passthrough(self):
        assert normalize_intent(VisualIntent.TALKING) is VisualIntent.TALKING

    def test_uppercase(self):
        assert normalize_intent("TALKING") is VisualIntent.TALKING

    def test_lowercase(self):
        assert normalize_intent("talking") is VisualIntent.TALKING

    def test_mixed_case_and_spaces(self):
        assert normalize_intent(" Working_Code ") is VisualIntent.WORKING_CODE

    def test_unknown_returns_none(self):
        assert normalize_intent("dancing") is None

    def test_none_returns_none(self):
        assert normalize_intent(None) is None

    def test_non_string_returns_none(self):
        assert normalize_intent(42) is None


class TestIsOfficial:
    def test_official_member(self):
        assert is_official(VisualIntent.IDLE)

    def test_official_string(self):
        assert is_official("CELEBRATE")

    def test_custom_intent(self):
        assert not is_official("CUSTOM_INTENT")