"""Immutable values shared by persistence, translation, and the UI."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from ebible.canon import BY_ID, Book

EnglishSource = Literal['bundled', 'live', 'placeholder']
HighlightColour = Literal['gold', 'green', 'red', 'blue', 'purple']
HIGHLIGHT_COLOURS: tuple[HighlightColour, ...] = ('gold', 'green', 'red', 'blue', 'purple')


@dataclass(frozen=True, slots=True)
class VerseRef:
    book_id: int
    chapter: int = 1
    verse: int = 1
    end_verse: int | None = None

    def __post_init__(self) -> None:
        if self.book_id not in BY_ID:
            raise ValueError(f'Unknown book: {self.book_id}')
        if self.chapter < 1 or self.verse < 1:
            raise ValueError('Chapter and verse must be positive')
        if self.end_verse is not None and self.end_verse < self.verse:
            raise ValueError('Verse range ends before it starts')


@dataclass(frozen=True, slots=True)
class Verse:
    ref: VerseRef
    text_am: str
    text_en: str | None
    english: str
    english_source: EnglishSource

    @property
    def verse(self) -> int:
        return self.ref.verse


@dataclass(frozen=True, slots=True)
class Chapter:
    book: Book
    number: int
    verses: tuple[Verse, ...]

    def __iter__(self) -> Iterator[Verse]:
        return iter(self.verses)

    def __len__(self) -> int:
        return len(self.verses)


@dataclass(frozen=True, slots=True)
class Bookmark:
    ref: VerseRef
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Highlight:
    ref: VerseRef
    colour: HighlightColour
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Note:
    ref: VerseRef
    text: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    id: int
    ref: VerseRef
    visited_at: datetime


@dataclass(frozen=True, slots=True)
class LiveTranslation:
    ref: VerseRef
    text: str
    backend: str
    translated_at: datetime


@dataclass(frozen=True, slots=True)
class SearchResult:
    ref: VerseRef
    snippet: str
    language: Literal['am', 'en']
    # Snippets use plain control delimiters, never Rich markup. The UI can split
    # these markers and create styled Text spans without interpreting scripture.
    match_start: str = '\x01'
    match_end: str = '\x02'


@dataclass(frozen=True, slots=True)
class ScriptureStats:
    verses: int
    translated: int

    @property
    def translated_pct(self) -> float:
        return 100 * self.translated / self.verses if self.verses else 0.0


@dataclass(frozen=True, slots=True)
class PlanProgress:
    plan_id: str
    start_date: date
    completed_days: frozenset[int]
    completed_dates: frozenset[date]
