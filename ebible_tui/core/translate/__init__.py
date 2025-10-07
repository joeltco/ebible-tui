from __future__ import annotations

# Google-backed translation (via translate-shell)
from ebible_tui.core.translate.backend_google import GoogleBackend, TranslationError  # re-export


def get_backend() -> GoogleBackend:
    return GoogleBackend()


def translate(text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str:
    return get_backend().translate(text, src, tgt, timeout_sec)


async def translate_async(text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str:
    return await get_backend().translate_async(text, src, tgt, timeout_sec)


__all__ = ['translate', 'translate_async', 'TranslationError', 'get_backend']
