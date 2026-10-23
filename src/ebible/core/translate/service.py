"""Select an on-demand backend; translate exactly one verse without persistence."""

import asyncio
import os
import shutil
from typing import Literal

from ebible.core.models import VerseRef
from ebible.core.scripture import ScriptureStore
from ebible.core.translate.base import Backend, TranslationError, validate_alignment

BackendSetting = Literal['auto', 'claude', 'google', 'off']


def select_backend(setting: BackendSetting = 'auto') -> Backend | None:
    if setting == 'auto':
        setting = (
            'claude'
            if os.environ.get('ANTHROPIC_API_KEY')
            else 'google'
            if shutil.which('trans')
            else 'off'
        )
    if setting == 'off':
        return None
    if setting == 'claude':
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise TranslationError('Set ANTHROPIC_API_KEY, then press Enter to retry.')
        from ebible.core.translate.claude import ClaudeBackend

        return ClaudeBackend()
    if setting == 'google':
        from ebible.core.translate.google import GoogleBackend

        return GoogleBackend()
    raise ValueError(f'Unknown translation backend: {setting}')


class TranslationService:
    """Stateless translation: no disk storage or cache; the UI owns session results."""

    def __init__(
        self,
        scripture: ScriptureStore,
        setting: BackendSetting = 'auto',
        *,
        backend: Backend | None = None,
        timeout: float = 45,
    ) -> None:
        self.scripture = scripture
        self.setting = setting
        self.backend = backend
        self.timeout = timeout

    async def translate_verse(self, ref: VerseRef) -> str:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._translate, ref), self.timeout)
        except TimeoutError as exc:
            raise TranslationError(
                'Translation timed out. Check your connection, then press Enter to retry.'
            ) from exc

    def _translate(self, ref: VerseRef) -> str:
        self.scripture.validate_reference(ref)
        if ref.end_verse is not None:
            raise TranslationError('Select one verse to translate.')
        backend = self.backend or select_backend(self.setting)
        if backend is None:
            raise TranslationError(
                'Set ANTHROPIC_API_KEY or install translate-shell; enable a backend in Settings.'
            )
        source = self.scripture.chapter(ref.book_id, ref.chapter)
        context = {v.verse: v.text_am for v in source}
        translated = backend.translate_verse(source.book, ref.chapter, context, ref.verse)
        validate_alignment({ref.verse: context[ref.verse]}, translated)
        return translated[ref.verse]
