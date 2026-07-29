"""Row types returned by the store.

These are plain frozen dataclasses rather than sqlite3.Row wrappers so the UI
never touches a database cursor and the store can be swapped without touching
widget code.
"""

from __future__ import annotations

from dataclasses import dataclass

from ebible.canon import Section


@dataclass(frozen=True, slots=True)
class Book:
    id: int
    slug: str
    name_am: str
    name_en: str
    section: Section
    chapter_count: int
    deuterocanonical: bool

    @property
    def display(self) -> str:
        return f'{self.name_am}  ·  {self.name_en}'


@dataclass(frozen=True, slots=True)
class Verse:
    book_id: int
    chapter: int
    verse: int
    text_am: str
    text_en: str | None

    @property
    def translated(self) -> bool:
        """False means no English has been generated for this verse yet.

        Distinct from an empty string, which would indicate a translation bug.
        """
        return self.text_en is not None


@dataclass(frozen=True, slots=True)
class SearchHit:
    book_id: int
    book_name_am: str
    book_name_en: str
    chapter: int
    verse: int
    text_am: str
    text_en: str | None
    snippet: str

    @property
    def reference(self) -> str:
        return f'{self.book_name_en} {self.chapter}:{self.verse}'


@dataclass(frozen=True, slots=True)
class Stats:
    books: int
    chapters: int
    verses: int
    translated: int

    @property
    def translated_pct(self) -> float:
        return (self.translated / self.verses * 100) if self.verses else 0.0
