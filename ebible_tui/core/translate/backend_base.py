from __future__ import annotations

import abc


class TranslatorBackend(abc.ABC):
    @abc.abstractmethod
    def translate(self, text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str: ...

    @abc.abstractmethod
    async def translate_async(
        self, text: str, src: str, tgt: str, timeout_sec: float = 30.0
    ) -> str: ...
