import json
import locale
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class I18nManager:
    def __init__(self, locale_dir: str = "data/locales", default_lang: str = "en"):
        self.locale_dir = Path(locale_dir)
        self.default_lang = default_lang
        self.current_lang = default_lang
        self.translations: Dict[str, Dict[str, Any]] = {}
        self._load_all_translations()

    def _load_all_translations(self) -> None:
        if not self.locale_dir.exists():
            logger.warning(f"Locale directory {self.locale_dir} does not exist. Using empty translations.")
            return

        for json_file in self.locale_dir.glob("*.json"):
            lang = json_file.stem
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)
                logger.info(f"Loaded translations for language: {lang}")
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")

    def detect_language(self, config_lang: str) -> str:
        if config_lang != "auto":
            lang = config_lang
            if lang in self.translations:
                return lang
            logger.warning(f"Configured language '{lang}' not available. Falling back to {self.default_lang}")
            return self.default_lang

        lang = self._detect_windows_lang()
        if lang:
            logger.info(f"Auto-detected language (Windows UI): {lang}")
            return lang

        lang = self._detect_posix_lang()
        if lang:
            logger.info(f"Auto-detected language (system): {lang}")
            return lang

        logger.info(f"Using default language: {self.default_lang}")
        return self.default_lang

    def _normalize_lang(self, code: Optional[str]) -> Optional[str]:
        """Normalize a locale string to a supported language code.

        Splits on '_', '-' or '.', lowercases the language part and returns it
        only if it is available in self.translations.
        """
        if not code:
            return None
        lang_part = re.split(r"[_\-.]", code)[0].strip().lower()
        if lang_part in self.translations:
            return lang_part
        return None

    def _detect_windows_lang(self) -> Optional[str]:
        """Detect the Windows UI language via the Win32 API.

        Uses GetUserDefaultLocaleName; returns a normalized supported language
        code or None when the API is unavailable (e.g. on POSIX).
        """
        try:
            import ctypes
            from ctypes import wintypes
        except (ImportError, OSError) as e:
            logger.warning(f"Windows UI language detection unavailable: {e}")
            return None

        try:
            func = ctypes.windll.kernel32.GetUserDefaultLocaleName
            func.argtypes = [wintypes.LPWSTR, ctypes.c_int]
            func.restype = ctypes.c_int
            buf = ctypes.create_unicode_buffer(85)  # LOCALE_NAME_MAX_LENGTH
            written = func(buf, len(buf))
            if written == 0:
                return None
            return self._normalize_lang(buf.value)
        except (AttributeError, OSError) as e:
            logger.warning(f"Windows UI language detection failed: {e}")
            return None

    def _detect_posix_lang(self) -> Optional[str]:
        """Detect the current system locale via locale.setlocale/getlocale."""
        try:
            locale.setlocale(locale.LC_CTYPE)
            system_locale = locale.getlocale(locale.LC_CTYPE)
        except Exception as e:
            logger.warning(f"Locale detection failed: {e}")
            return None

        if not system_locale or not system_locale[0]:
            return None
        return self._normalize_lang(system_locale[0])

    def set_language(self, lang: str) -> None:
        if lang not in self.translations:
            logger.warning(f"Language '{lang}' not available. Keeping current '{self.current_lang}'.")
            return
        self.current_lang = lang
        logger.info(f"Switched to language: {lang}")

    def t(self, key: str, **kwargs) -> str:
        parts = key.split('.')
        current = self.translations.get(self.current_lang, {})
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    break
            else:
                current = None
                break

        if current is None:
            current = self.translations.get(self.default_lang, {})
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                    if current is None:
                        break
                else:
                    current = None
                    break

        if current is None or not isinstance(current, str):
            logger.debug(f"Missing translation for key: {key}")
            return key

        try:
            return current.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing placeholder {e} in translation for key '{key}'")
            return current
        except Exception as e:
            logger.error(f"Error formatting translation '{key}': {e}")
            return current

    def get_current_language(self) -> str:
        return self.current_lang
