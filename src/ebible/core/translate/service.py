"""Choose a backend and fill missing English in an asyncio thread worker.

The async entry point offloads every database/subprocess/network operation.
Textual callers may await it inside an async @work method in batch 2.
"""

import asyncio
import os
import shutil
from typing import Literal

from ebible.core.scripture import ScriptureStore
from ebible.core.translate.base import Backend, TranslationError, validate_alignment
from ebible.core.userdata import UserDataStore

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
            raise TranslationError('ANTHROPIC_API_KEY is required for Claude')
        from ebible.core.translate.claude import ClaudeBackend

        return ClaudeBackend()
    if setting == 'google':
        from ebible.core.translate.google import GoogleBackend

        return GoogleBackend()
    raise ValueError(f'Unknown translation backend: {setting}')


class TranslationService:
    def __init__(
        self,
        scripture: ScriptureStore,
        userdata: UserDataStore,
        setting: BackendSetting = 'auto',
        *,
        backend: Backend | None = None,
    ) -> None:
        self.scripture = scripture
        self.userdata = userdata
        self.setting = setting
        self.backend = backend

    async def translate_chapter(self, book_id: int, chapter: int) -> dict[int, str]:
        return await asyncio.to_thread(self._translate, book_id, chapter)

    def _translate(self, book_id: int, chapter: int) -> dict[int, str]:
        source = self.scripture.chapter(book_id, chapter)
        live = self.userdata.live_chapter(book_id, chapter)
        missing = {v.verse for v in source if v.text_en is None and v.verse not in live}
        if not missing:
            return {}
        backend = self.backend or select_backend(self.setting)
        if backend is None:
            return {}
        verses_am = {v.verse: v.text_am for v in source}
        translated = backend.translate_chapter(source.book, chapter, verses_am)
        validate_alignment(verses_am, translated)
        fill = {n: text for n, text in translated.items() if n in missing}
        self.userdata.save_translations(book_id, chapter, fill, backend.name)
        return fill
