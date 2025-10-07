import asyncio
import importlib

from ebible_tui.core import translate, translate_async
from pytest import MonkeyPatch

T = importlib.import_module('ebible_tui.core.translate')


class _EchoBackend:
    def translate(self, text: str, src: str, tgt: str, timeout_sec: float = 30.0) -> str:
        return f'{src}->{tgt}:{text.strip()}'

    async def translate_async(
        self, text: str, src: str, tgt: str, timeout_sec: float = 30.0
    ) -> str:
        await asyncio.sleep(0)
        return f'{src}->{tgt}:{text.strip()}'


def test_translate_sync_mock(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(T, 'get_backend', lambda: _EchoBackend())
    out = translate('ሰላም', 'am', 'en')
    assert out.startswith('am->en:')


def test_translate_async_mock(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(T, 'get_backend', lambda: _EchoBackend())
    out = asyncio.run(translate_async('ሰላም', 'am', 'en'))
    assert out.startswith('am->en:')
