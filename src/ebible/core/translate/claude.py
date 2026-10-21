"""Optional Anthropic backend; no SDK import or client creation until a request."""

import importlib
from collections.abc import Mapping, Sequence
from importlib.resources import files
from typing import Protocol, cast

from ebible.canon import Book
from ebible.core.translate.base import TranslationError, parse_numbered_lines

MODEL = 'claude-sonnet-5-5'
APP_ADDENDUM = (
    '\n\nIn-app output contract (overrides requests for a summary): '
    'Return numbered verse lines only, one line per original verse. '
    'No summary, no commentary, no headings, and no uncertainty report in this response. '
    'Preserve every original verse number and follow the guide for faithful rendering.'
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

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def translate_chapter(
        self, book: Book, chapter: int, verses_am: Mapping[int, str]
    ) -> dict[int, str]:
        if not verses_am:
            return {}
        client = self._client
        if client is None:
            try:
                sdk = importlib.import_module('anthropic')
            except ImportError as exc:
                raise TranslationError('Install ebible[claude] to use the Claude backend') from exc
            client = cast(Client, sdk.Anthropic(timeout=120.0, max_retries=0))
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=16384,
                system=files('ebible.core.translate')
                .joinpath('TRANSLATION_GUIDE.md')
                .read_text(encoding='utf-8')
                + APP_ADDENDUM,
                messages=[
                    {
                        'role': 'user',
                        'content': f'{book.name_en} {chapter} ({book.name_am})\n\n'
                        + '\n'.join(f'{n}. {text}' for n, text in sorted(verses_am.items())),
                    }
                ],
            )
            if response.stop_reason != 'end_turn':
                raise TranslationError(f'Incomplete Claude response: {response.stop_reason}')
            text = '\n'.join(block.text for block in response.content if block.type == 'text')
            return parse_numbered_lines(text, verses_am)
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(f'Claude request failed: {exc}') from exc
        finally:
            if self._client is None:
                client.close()
