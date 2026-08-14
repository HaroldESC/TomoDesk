import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class CommentLoader:
    def __init__(self, base_path: str, i18n=None):
        self.base_path = Path(base_path)
        self.i18n = i18n
        self.phrases: Dict[str, List[str]] = {}
        self._load()

    def _get_lang_file(self) -> Path:
        if self.i18n:
            lang = self.i18n.get_current_language()
            return self.base_path.parent / f"comments_{lang}.yaml"
        return self.base_path

    def _load(self) -> None:
        file_path = self._get_lang_file()
        if not file_path.exists():
            logger.warning(
                "Comments file not found: %s. Trying default: %s",
                file_path, self.base_path,
            )
            if self.base_path.exists():
                file_path = self.base_path
            else:
                self.phrases = {}
                return

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            logger.warning("Comments file is empty: %s", file_path)
            self.phrases = {}
            return

        self.phrases = data
        total = sum(len(v) for v in self.phrases.values())
        logger.info(
            "Loaded %d phrases in %d categories from %s", total, len(self.phrases), file_path.name
        )

    def get_random(
        self, category: str, replacements: Dict[str, str] = None
    ) -> Optional[str]:
        phrases = self.phrases.get(category, [])
        if not phrases:
            return None

        phrase = random.choice(phrases)

        if replacements:
            for key, value in replacements.items():
                phrase = phrase.replace(f"{{{key}}}", str(value))

        return phrase

    def has_category(self, category: str) -> bool:
        return category in self.phrases and len(self.phrases[category]) > 0

    def reload(self) -> None:
        self._load()
