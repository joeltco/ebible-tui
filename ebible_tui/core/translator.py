# Compatibility shim: translator moved under ebible_tui.core.translate
from __future__ import annotations

from ebible_tui.core.translate import TranslationError, translate, translate_async  # noqa: F401

__all__ = ['translate', 'translate_async', 'TranslationError']
