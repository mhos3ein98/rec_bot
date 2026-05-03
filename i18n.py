# =============================================================================
# i18n.py
# Translation loader. Provides t(lang, key, **kwargs) used everywhere.
# Translations are cached in memory after first load.
# =============================================================================

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_DIR = Path(__file__).parent / "translations"


def _load(lang: str) -> dict:
    if lang not in _CACHE:
        path = _DIR / f"{lang}.json"
        if not path.exists():
            logger.warning("Translation file not found for lang=%s; falling back to en", lang)
            path = _DIR / "en.json"
        with path.open(encoding="utf-8") as f:
            _CACHE[lang] = json.load(f)
    return _CACHE[lang]


def t(lang: str, key: str, **kwargs) -> str:
    """
    Return translated string for *key* in *lang*.
    Supports optional format kwargs, e.g. t("en", "welcome", name="Ali").
    Falls back to the key itself if not found.
    """
    strings = _load(lang)
    text = strings.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
