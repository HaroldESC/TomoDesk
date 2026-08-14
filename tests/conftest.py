import pytest
from unittest.mock import MagicMock

from src.memory.database import DatabaseManager
from src.memory.memory import MemoryManager

from tests.mock_chroma import MockChroma


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def memory_manager(tmp_path):
    db_path = tmp_path / "test_tomodesk.db"

    db = DatabaseManager(db_path)
    db.initialize()

    chroma = MockChroma()

    config = {
        "memory": {"max_short_term_messages": 20},
    }
    mem = MemoryManager(db, chroma, config)
    yield mem


@pytest.fixture
def mock_i18n():
    i18n = MagicMock()
    i18n.t = MagicMock(side_effect=lambda key, **kw: key)
    i18n.get_current_language = MagicMock(return_value="en")
    return i18n


@pytest.fixture
def mock_state_manager():
    sm = MagicMock()
    sm.get_state = MagicMock(return_value={
        "happiness": 0.7,
        "energy": 0.5,
        "curiosity": 0.6,
        "closeness": 0.3,
        "connection": 0.5,
    })
    return sm
