import io
import logging

import pytest

from src.config import logging_config
from src.config.logging_config import (
    SensitiveDataFilter,
    _add_redaction_filter,
    _redact_sensitive,
    setup_logging,
)

SECRET_MESSAGE = (
    "api_key=sk-abcdef1234567890abcdef token=ghp_xxxxxxxxxxxxxxxxxxxx"
)


class TestRedactSensitive:
    def test_redacts_api_key_value(self):
        raw = "sk-1234567890abcdefghijklmn"
        redacted = _redact_sensitive(f"api_key: {raw}")
        assert "[REDACTED]" in redacted
        assert raw not in redacted

    @pytest.mark.parametrize(
        "text",
        [
            "apikey=abcdef1234567890",
            "token=abcdef1234567890",
            "secret=abcdef1234567890",
            "authorization=abcdef1234567890",
            "Bearer abcdefghijklmnopqrstuvwxyz",
            "gsk_abcdefghijklmnopqrst",
            "hf_abcdefghijklmnopqrst",
        ],
    )
    def test_redacts_common_sensitive_patterns(self, text):
        redacted = _redact_sensitive(text)
        assert "[REDACTED]" in redacted

    def test_redacts_raw_value(self):
        raw = "abcdef1234567890"
        redacted = _redact_sensitive(f"secret={raw}")
        assert raw not in redacted

    def test_leaves_plain_text_unchanged(self):
        assert _redact_sensitive("hello world") == "hello world"


class TestSensitiveDataFilter:
    def test_filter_redacts_record(self):
        record = logging.makeLogRecord(
            {
                "name": "t",
                "levelno": logging.INFO,
                "pathname": __file__,
                "lineno": 1,
                "msg": "api_key=%s",
                "args": ("sk-secret1234567890abcdef",),
            }
        )
        filt = SensitiveDataFilter()
        assert filt.filter(record) is True
        assert "[REDACTED]" in record.msg
        assert "sk-secret1234567890abcdef" not in str(record.args)


class _IsolatedLogging:
    """Estado del logging raíz preservado alrededor de una prueba."""

    def __init__(self, root: logging.Logger) -> None:
        self.root = root
        self._original_handlers = list(root.handlers)

    @property
    def added_handlers(self) -> list[logging.Handler]:
        """Handlers registrados por ``setup_logging`` durante la prueba."""
        return [h for h in self.root.handlers if h not in self._original_handlers]


@pytest.fixture
def isolated_logging(monkeypatch):
    """Aísla el estado global de logging para no contaminar otras pruebas."""
    state = _IsolatedLogging(logging.getLogger())
    original_filters = list(state.root.filters)
    original_level = state.root.level
    monkeypatch.setattr(logging_config, "_initialized", False)
    try:
        yield state
    finally:
        for handler in state.added_handlers:
            handler.close()
        state.root.handlers[:] = state._original_handlers
        state.root.filters[:] = original_filters
        state.root.setLevel(original_level)


class TestAddRedactionFilter:
    def test_attaches_filter_to_handler(self):
        handler = logging.StreamHandler(io.StringIO())
        try:
            _add_redaction_filter(handler)
            assert len(handler.filters) == 1
            assert isinstance(handler.filters[0], SensitiveDataFilter)
        finally:
            handler.close()

    def test_is_idempotent(self):
        handler = logging.StreamHandler(io.StringIO())
        try:
            _add_redaction_filter(handler)
            _add_redaction_filter(handler)
            _add_redaction_filter(handler)
            redaction_filters = [
                f for f in handler.filters if isinstance(f, SensitiveDataFilter)
            ]
            assert len(redaction_filters) == 1
        finally:
            handler.close()

    def test_attaches_to_every_handler(self):
        first = logging.StreamHandler(io.StringIO())
        second = logging.StreamHandler(io.StringIO())
        try:
            _add_redaction_filter(first, second)
            for handler in (first, second):
                assert len(handler.filters) == 1
                assert isinstance(handler.filters[0], SensitiveDataFilter)
        finally:
            first.close()
            second.close()

    def test_redacts_records_propagated_from_child_logger(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root = logging.getLogger()
        root.addHandler(handler)
        original_level = root.level
        root.setLevel(logging.DEBUG)
        try:
            _add_redaction_filter(handler)
            child = logging.getLogger("src.llm.llm")
            child.propagate = True
            child.info(SECRET_MESSAGE)
            output = stream.getvalue()
        finally:
            root.setLevel(original_level)
            root.removeHandler(handler)
            handler.close()

        assert "[REDACTED]" in output
        assert "sk-abcdef1234567890abcdef" not in output
        assert "ghp_xxxxxxxxxxxxxxxxxxxx" not in output


class TestSetupLogging:
    def test_attaches_filter_to_handlers(self, isolated_logging, tmp_path):
        setup_logging(tmp_path)
        handlers = isolated_logging.added_handlers
        assert handlers, "setup_logging no registró handlers"
        for handler in handlers:
            assert any(
                isinstance(f, SensitiveDataFilter) for f in handler.filters
            ), f"handler sin SensitiveDataFilter: {handler}"

    def test_does_not_attach_filter_to_root_logger(self, isolated_logging, tmp_path):
        setup_logging(tmp_path)
        assert not any(
            isinstance(f, SensitiveDataFilter) for f in isolated_logging.root.filters
        )

    def test_is_idempotent(self, isolated_logging, tmp_path):
        setup_logging(tmp_path)
        handlers_after_first = list(isolated_logging.root.handlers)
        filters_after_first = [list(h.filters) for h in handlers_after_first]

        setup_logging(tmp_path)

        assert isolated_logging.root.handlers == handlers_after_first
        assert [list(h.filters) for h in isolated_logging.root.handlers] == (
            filters_after_first
        )

    def test_child_logger_secrets_are_redacted_in_log_file(
        self, isolated_logging, tmp_path
    ):
        setup_logging(tmp_path)
        child = logging.getLogger("src.llm.llm")
        child.propagate = True
        child.info(SECRET_MESSAGE)

        content = (tmp_path / "tomodesk.log").read_text(encoding="utf-8")

        assert "[REDACTED]" in content
        assert "sk-abcdef1234567890abcdef" not in content
        assert "ghp_xxxxxxxxxxxxxxxxxxxx" not in content

    def test_child_logger_secrets_are_redacted_in_console_output(
        self, isolated_logging, tmp_path
    ):
        stream = io.StringIO()
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("%(message)s"))

        root = isolated_logging.root
        original_level = root.level
        root.addHandler(console_handler)
        root.setLevel(logging.DEBUG)
        try:
            setup_logging(tmp_path)
            _add_redaction_filter(console_handler)
            child = logging.getLogger("src.llm.llm")
            child.propagate = True
            child.info(SECRET_MESSAGE)
            output = stream.getvalue()
        finally:
            root.setLevel(original_level)
            root.removeHandler(console_handler)
            console_handler.close()

        assert "[REDACTED]" in output
        assert "sk-abcdef1234567890abcdef" not in output
        assert "ghp_xxxxxxxxxxxxxxxxxxxx" not in output
