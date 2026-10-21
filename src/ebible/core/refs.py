"""Resolve English/Amharic references without guessing ambiguous prefixes."""

import re
from collections.abc import Callable
from typing import Literal

from ebible.canon import BOOKS, BY_ID, Book
from ebible.core.models import VerseRef


class ReferenceError(ValueError):
    """A malformed, unknown, ambiguous, or nonexistent reference."""


# Conventional abbreviations that are not prefixes of the full English name.
_ALIASES: dict[str, str] = {
    'gn': 'genesis',
    'ge': 'genesis',
    'ex': 'exodus',
    'lv': 'leviticus',
    'nm': 'numbers',
    'num': 'numbers',
    'dt': 'deuteronomy',
    'deut': 'deuteronomy',
    'jos': 'joshua',
    'josh': 'joshua',
    'jdg': 'judges',
    'judg': 'judges',
    'ps': 'psalms',
    'psalm': 'psalms',
    'pr': 'proverbs',
    'prov': 'proverbs',
    'eccl': 'ecclesiastes',
    'song': 'song-of-songs',
    'sos': 'song-of-songs',
    'is': 'isaiah',
    'ezek': 'ezekiel',
    'ob': 'obadiah',
    'hab': 'habakkuk',
    'mt': 'matthew',
    'matt': 'matthew',
    'mk': 'mark',
    'lk': 'luke',
    'jn': 'john',
    'jhn': 'john',
    'ac': 'acts',
    'rom': 'romans',
    'phil': 'philippians',
    'phlm': 'philemon',
    'phm': 'philemon',
    'jas': 'james',
    'jm': 'james',
    'rev': 'revelation',
}
for _stem, _slug, _count in (
    ('sam', 'samuel', 2),
    ('kgs', 'kings', 2),
    ('chr', 'chronicles', 2),
    ('cor', 'corinthians', 2),
    ('thess', 'thessalonians', 2),
    ('tim', 'timothy', 2),
    ('pet', 'peter', 2),
    ('jn', 'john', 3),
    ('meq', 'meqabyan', 3),
):
    for _n in range(1, _count + 1):
        _ALIASES[f'{_n} {_stem}'] = f'{_n}-{_slug}'


def _normalize(value: str) -> str:
    value = re.sub(r'^(III|II|I)\s+', lambda m: f'{len(m[1])} ', value, flags=re.I)
    value = re.sub(r'^(\d)(?=[a-zA-Z])', r'\1 ', value)
    return ' '.join(value.casefold().replace('-', ' ').replace('.', '').split())


def _names(book: Book) -> set[str]:
    names = {book.name_en, book.slug, book.name_am}
    am = book.name_am
    for prefix in ('ኦሪት ', 'መጽሐፈ ', 'ትንቢተ ', 'ወደ '):
        if am.startswith(prefix):
            names.add(am.removeprefix(prefix))
    if am.startswith('የ'):
        names.add(am[1:])
        names.add(am[1:].split()[0])
    return {_normalize(name) for name in names}


def resolve_book(value: str) -> Book:
    name = _normalize(value)
    if not name:
        raise ReferenceError('A book name is required')
    if name in _ALIASES:
        return next(b for b in BOOKS if b.slug == _ALIASES[name])
    exact = [b for b in BOOKS if name in _names(b)]
    matches = exact or [b for b in BOOKS if any(n.startswith(name) for n in _names(b))]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ReferenceError('Ambiguous book: ' + ', '.join(b.name_en for b in matches))
    raise ReferenceError(f'Unknown book: {value}')


def parse_reference(text: str, *, validate: Callable[[VerseRef], None] | None = None) -> VerseRef:
    """Bare books/chapters select verse 1; optional store validation checks bounds.

    Parsing alone is independent of database IO. Source gaps are checked by the
    store validator rather than assuming every number up to MAX(verse) exists.
    """
    match = re.fullmatch(r'\s*(.*?)\s+([0-9]+)(?:\s*:\s*([0-9]+)(?:\s*[-–]\s*([0-9]+))?)?\s*', text)
    try:
        if match:
            name, chapter, verse, end = match.groups()
            ref = VerseRef(
                resolve_book(name).id, int(chapter), int(verse or 1), int(end) if end else None
            )
        else:
            ref = VerseRef(resolve_book(text.strip()).id)
    except ValueError as exc:
        raise ReferenceError(str(exc)) from exc
    if validate is not None:
        validate(ref)
    return ref


def format_reference(ref: VerseRef, language: Literal['am', 'en', 'both'] = 'en') -> str:
    book = BY_ID[ref.book_id]
    name = {'am': book.name_am, 'en': book.name_en, 'both': book.display}[language]
    end = f'-{ref.end_verse}' if ref.end_verse is not None else ''
    return f'{name} {ref.chapter}:{ref.verse}{end}'
