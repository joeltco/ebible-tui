"""Optional Anthropic backend; no SDK import or client creation until a request."""

import importlib
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Protocol, cast

from ebible.canon import Book
from ebible.core.credentials import active_key
from ebible.core.translate.base import TranslationError, parse_numbered_lines
from ebible.core.translate.query import QUERY_PROMPT, parse_query_variants

MODEL = 'claude-sonnet-5-5'
APP_ADDENDUM = (
    '\n\nIn-app output contract (overrides requests for a summary): '
    'Translate ONLY the requested target verse. Return exactly one numbered line: N. text. '
    'No summary, no commentary, no headings, and no uncertainty report in this response. '
    'Preserve the requested verse number and follow the guide for faithful rendering.'
)


class ContentBlock(Protocol):
    @property
    def type(self) -> str: ...

    @property
    def text(self) -> str: ...


class Response(Protocol):
    @property
    def content(self) -> Sequence[ContentBlock]: ...

    @property
    def stop_reason(self) -> str | None: ...


class Messages(Protocol):
    def create(
        self, *, model: str, max_tokens: int, system: str, messages: list[dict[str, str]]
    ) -> Response: ...


class Client(Protocol):
    @property
    def messages(self) -> Messages: ...

    def close(self) -> None: ...


class ClaudeBackend:
    name = 'claude'

    def __init__(self, client: Client | None = None, *, api_key: str | None = None) -> None:
        self._client = client
        self._api_key = api_key

    def translate_verse(
        self, book: Book, chapter: int, verses_am: Mapping[int, str], target: int
    ) -> dict[int, str]:
        if target not in verses_am:
            raise TranslationError('Target verse is missing from chapter context')
        content = (
            f'{book.name_en} {chapter} ({book.name_am})\n\n'
            + '\n'.join(f'{n}. {text}' for n, text in sorted(verses_am.items()))
            + f'\n\nThe chapter above is context only. Translate ONLY verse {target}. Return only: {target}. translation'
        )
        return parse_numbered_lines(self._request(None, content, 4096), {target: verses_am[target]})

    def translate_query(self, query: str) -> tuple[str, ...]:
        return parse_query_variants(self._request(QUERY_PROMPT, query, 256))

    def _request(self, system: str | None, content: str, max_tokens: int) -> str:
        client = self._client
        try:
            if client is None:
                try:
                    sdk = importlib.import_module('anthropic')
                except ImportError:
                    raise TranslationError(
                        'Install ebible[claude] to use the Claude backend'
                    ) from None
                key = active_key() if self._api_key is None else None
                api_key = self._api_key if self._api_key is not None else key.value if key else None
                if not api_key:
                    raise TranslationError(
                        'Add an Anthropic API key in Settings or set ANTHROPIC_API_KEY.'
                    )
                try:
                    client = cast(
                        Client, sdk.Anthropic(api_key=api_key, timeout=30.0, max_retries=0)
                    )
                except Exception:
                    raise TranslationError(
                        'Could not start Claude. Check the API key in Settings.'
                    ) from None
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=max_tokens,
                    system=system
                    if system is not None
                    else files('ebible.core.translate')
                    .joinpath('TRANSLATION_GUIDE.md')
                    .read_text(encoding='utf-8')
                    + APP_ADDENDUM,
                    messages=[{'role': 'user', 'content': content}],
                )
            except Exception:
                raise TranslationError(
                    'Claude request failed. Check your connection and API key in Settings, then press Enter to retry.'
                ) from None
            if response.stop_reason != 'end_turn':
                raise TranslationError('Incomplete Claude response. Press Enter to retry.')
            text = '\n'.join(block.text for block in response.content if block.type == 'text')
            return text
        finally:
            if self._client is None and client is not None:
                try:
                    client.close()
                except Exception:
                    pass  # Cleanup exceptions must not expose SDK authentication details.
