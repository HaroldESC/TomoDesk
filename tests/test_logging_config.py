import logging

import pytest

from src.config.logging_config import SensitiveDataFilter, _redact_sensitive


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
