"""Backend contract and strict alignment checks shared by all translators."""

import re
from collections.abc import Mapping
from typing import Protocol

from ebible.canon import Book


class TranslationError(RuntimeError):
    """Translation unavailable, failed, truncated, or misaligned."""


class AlignmentError(TranslationError):
    """Output must match each original verse number exactly once."""


class Backend(Protocol):
    @property
    def name(self) -> str: ...

    def translate_verse(
        self, book: Book, chapter: int, verses_am: Mapping[int, str], target: int
    ) -> dict[int, str]: ...


def validate_alignment(verses_am: Mapping[int, str], translated: Mapping[int, str]) -> None:
    if any(type(n) is not int or n < 1 for n in (*verses_am, *translated)):
        raise AlignmentError('Verse numbers must be positive integers')
    if set(verses_am) != set(translated):
        raise AlignmentError(
            f'Verse mismatch: missing={sorted(set(verses_am) - set(translated))}, extra={sorted(set(translated) - set(verses_am))}'
        )
    if any(not isinstance(text, str) or not text.strip() for text in translated.values()):
        raise AlignmentError('Empty translation')


def parse_numbered_lines(text: str, verses_am: Mapping[int, str]) -> dict[int, str]:
    text = text.strip()
    wrapper = re.fullmatch(r'```(?:[\w-]+)?[ \t]*\r?\n(.*?)\r?\n```', text, flags=re.DOTALL)
    if wrapper:
        text = wrapper[1]
    translated: dict[int, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\s*([0-9]+)\.\s+(.+?)\s*', line)
        if match is None:
            raise AlignmentError('Expected one numbered line per verse; no commentary or wrapping')
        number = int(match[1])
        if number in translated:
            raise AlignmentError(f'Duplicate verse: {number}')
        translated[number] = match[2]
    validate_alignment(verses_am, translated)
    return translated
