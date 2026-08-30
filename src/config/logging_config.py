import logging
import re
import sys
from pathlib import Path

from src.config.paths import log_dir as default_log_dir


_initialized = False


_SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r'(api_key["\']?\s*[:=]\s*)["\']?[^"\';\s,}\]]+', r'\1[REDACTED]'),
    (r'(apikey["\']?\s*[:=]\s*)["\']?[^"\';\s,}\]]+', r'\1[REDACTED]'),
    (r'(authorization["\']?\s*[:=]\s*)["\']?[^"\';\s,}\]]+', r'\1[REDACTED]'),
    (r'(bearer\s+)[a-zA-Z0-9_\-.\/]{16,}', r'\1[REDACTED]'),
    (r'(token["\']?\s*[:=]\s*)["\']?[^"\';\s,}\]]+', r'\1[REDACTED]'),
    (r'(secret["\']?\s*[:=]\s*)["\']?[^"\';\s,}\]]+', r'\1[REDACTED]'),
    (r'(sk-[a-zA-Z0-9]{20,})', '[REDACTED]'),
    (r'(gsk_[a-zA-Z0-9]{20,})', '[REDACTED]'),
    (r'(hf_[a-zA-Z0-9]{20,})', '[REDACTED]'),
]


def _redact_sensitive(text: str) -> str:
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_sensitive(record.msg)
        if record.args:
            record.args = tuple(
                _redact_sensitive(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def _add_redaction_filter(root_logger: logging.Logger) -> None:
    has_filter = any(
        isinstance(f, SensitiveDataFilter)
        for f in root_logger.filters
    )
    if not has_filter:
        root_logger.addFilter(SensitiveDataFilter())


def setup_logging(log_dir: Path | None = None) -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    if log_dir is None:
        log_dir = default_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tomodesk.log"

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError):
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

    _add_redaction_filter(root_logger)
