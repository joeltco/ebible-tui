"""Select an on-demand backend; translate exactly one verse, remembering finished results."""

import asyncio
import shutil
from typing import Literal

from ebible.core.credentials import CredentialError, active_key
from ebible.core.models import VerseRef
from ebible.core.scripture import ScriptureStore
from ebible.core.translate.base import Backend, TranslationError, validate_alignment
from ebible.core.translate.cache import TranslationCache
from ebible.core.translate.query import QUERY_ENABLE_HINT, parse_query_variants

BackendSetting = Literal['auto', 'claude', 'google', 'off']


def select_backend(setting: BackendSetting = 'auto') -> Backend | None:
    try:
        key = active_key() if setting in ('auto', 'claude') else None
    except CredentialError:
        raise TranslationError('Cannot read saved key. Replace or remove it in Settings.') from None
    if setting == 'auto':
        setting = 'claude' if key else 'google' if shutil.which('trans') else 'off'
    if setting == 'off':
        return None
    if setting == 'claude':
        if key is None:
            raise TranslationError('Add an Anthropic API key in Settings or set ANTHROPIC_API_KEY.')
        from ebible.core.translate.claude import ClaudeBackend

        return ClaudeBackend(api_key=key.value)
    if setting == 'google':
        from ebible.core.translate.google import GoogleBackend

        return GoogleBackend()
    raise ValueError(f'Unknown translation backend: {setting}')


class TranslationService:
    """Translate on request; a finished verse is kept in the optional device cache."""

    def __init__(
        self,
        scripture: ScriptureStore,
        setting: BackendSetting = 'auto',
        *,
        backend: Backend | None = None,
        timeout: float = 45,
        cache: TranslationCache | None = None,
    ) -> None:
        self.scripture = scripture
        self.cache = cache
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
                'Add an Anthropic key in Settings (or set ANTHROPIC_API_KEY), or install translate-shell; enable a backend in Settings.'
            )
        source = self.scripture.chapter(ref.book_id, ref.chapter)
        context = {v.verse: v.text_am for v in source}
        if self.cache and (saved := self.cache.get(backend.name, ref, context[ref.verse])):
            return saved
        translated = backend.translate_verse(source.book, ref.chapter, context, ref.verse)
        validate_alignment({ref.verse: context[ref.verse]}, translated)
        if self.cache:
            self.cache.put(backend.name, ref, context[ref.verse], translated[ref.verse])
        return translated[ref.verse]

    async def translate_query(self, query: str) -> tuple[str, ...]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._translate_query, query), self.timeout
            )
        except TimeoutError:
            raise TranslationError(
                'Query translation timed out. Check your connection and retry. ' + QUERY_ENABLE_HINT
            ) from None
        except TranslationError as exc:
            message = str(exc)
            raise TranslationError(
                message if QUERY_ENABLE_HINT in message else message + ' ' + QUERY_ENABLE_HINT
            ) from None
        except Exception:
            raise TranslationError(
                'Query translation failed. Check your connection and retry. ' + QUERY_ENABLE_HINT
            ) from None

    def _translate_query(self, query: str) -> tuple[str, ...]:
        backend = self.backend or select_backend(self.setting)
        if backend is None:
            raise TranslationError('English search needs a translation backend.')
        return parse_query_variants('\n'.join(backend.translate_query(query)))
