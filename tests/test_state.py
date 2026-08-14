import time

import pytest

from src.core.state import StateManager


@pytest.fixture
def state_manager():
    config = {
        "personality": {
            "initial_happiness": 0.5,
            "initial_energy": 0.8,
            "initial_curiosity": 0.6,
            "initial_closeness": 0.1,
            "initial_connection": 0.5,
        }
    }
    return StateManager(config)


def test_initial_state(state_manager):
    state = state_manager.get_state()
    assert state["happiness"] == pytest.approx(0.5, abs=0.01)
    assert state["energy"] == pytest.approx(0.8, abs=0.01)
    assert state["closeness"] == 0.1


def test_user_message_update(state_manager):
    state_manager.update("user_message")
    state = state_manager.get_state()
    assert state["connection"] > 0.5
    assert state["happiness"] > 0.5


def test_long_conversation_update(state_manager):
    state_manager.update("long_conversation", intensity=1.0)
    state = state_manager.get_state()
    assert state["closeness"] > 0.1


def test_positive_feedback(state_manager):
    state_manager.update("positive_feedback")
    state = state_manager.get_state()
    assert state["happiness"] > 0.5
    assert state["closeness"] > 0.1


def test_negative_feedback(state_manager):
    initial_closeness = state_manager.get_state()["closeness"]
    state_manager.update("negative_feedback")
    state = state_manager.get_state()
    assert state["happiness"] < 0.5
    assert state["closeness"] >= initial_closeness


def test_explicit_ignore_at_low_closeness(state_manager):
    state_manager._state["closeness"] = 0.1
    state_manager.update("explicit_ignore", intensity=1.0)
    state = state_manager.get_state()
    assert state["closeness"] < 0.1


def test_explicit_ignore_at_high_closeness(state_manager):
    state_manager._state["closeness"] = 0.8
    state_manager.update("explicit_ignore", intensity=1.0)
    state = state_manager.get_state()
    assert state["closeness"] == 0.8


def test_clamping(state_manager):
    for _ in range(15):
        state_manager.update("positive_feedback")
    state = state_manager.get_state()
    assert state["happiness"] <= 1.0
    assert state["happiness"] >= 0.99

    state_manager._state["energy"] = 0.0
    state_manager.update("user_message", intensity=10.0)
    state = state_manager.get_state()
    assert state["energy"] >= 0.0


def test_decay(state_manager):
    initial_state = state_manager.get_state()
    state_manager._last_update = time.time() - 3600
    state = state_manager.get_state()
    assert state["energy"] < initial_state["energy"]
    assert state["closeness"] == initial_state["closeness"]


def test_prompt_instruction(state_manager):
    instruction = state_manager.get_prompt_instruction()
    assert "Tone:" in instruction
    assert len(instruction) > 10


def test_prompt_instruction_changes_with_closeness(state_manager):
    state_manager._state["closeness"] = 0.05
    low_instruction = state_manager.get_prompt_instruction()
    assert "formal" in low_instruction.lower()

    state_manager._state["closeness"] = 0.9
    high_instruction = state_manager.get_prompt_instruction()
    assert "familiar" in high_instruction.lower() or "affection" in high_instruction.lower()


def test_save_and_load_preferences(state_manager, memory_manager):
    state_manager._state["closeness"] = 0.42
    state_manager.save_to_preferences(memory_manager)

    config = {"personality": {"initial_closeness": 0.1}}
    new_manager = StateManager(config)
    assert new_manager.get_state()["closeness"] == 0.1
    new_manager.load_from_preferences(memory_manager)
    assert new_manager.get_state()["closeness"] == 0.42
