"""Read access to the compiled Bible store.

The database ships inside the package (`bible.db`, built by tools/build_db.py).
It is opened read-only in immutable mode: the reader never writes, which avoids
creating -wal/-shm files next to a package installed in a read-only location --
a real failure mode on Termux and in system site-packages.

Writes belong to the translation pipeline, which uses `open_writable()`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ebible.canon import Section
from ebible.data.models import Book, SearchHit, Stats, Verse

DB_PATH = Path(__file__).resolve().parent / 'bible.db'

# Every writer must use this, not sqlite3's 5-second default. Translators run in
# parallel, each `push` is an exclusive write, and the FTS5 sync triggers make it
# slow enough that concurrent pushes collide. On the default, a loser raises
# `database is locked` and a translated chapter is silently lost.
WRITE_TIMEOUT = 120.0


class StoreError(RuntimeError):
    pass


def _connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise StoreError(
            f'bible database not found at {path}\n'
            'Build it with:  python tools/build_db.py'
        )
    # immutable=1 promises the file will not change while open, which lets SQLite
    # skip locking entirely -- the right choice for a shipped read-only asset.
    conn = sqlite3.connect(f'file:{path}?immutable=1', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def open_writable(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Open for writing. Used by the translation pipeline, never by the UI.

    See WRITE_TIMEOUT: the long busy timeout is load-bearing under parallelism.
    """
    conn = sqlite3.connect(path, timeout=WRITE_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _to_book(r: sqlite3.Row) -> Book:
    return Book(
        id=r['id'],
        slug=r['slug'],
        name_am=r['name_am'],
        name_en=r['name_en'],
        section=Section(r['section']),
        chapter_count=r['chapter_count'],
        deuterocanonical=bool(r['deuterocanonical']),
    )


def _to_verse(r: sqlite3.Row) -> Verse:
    return Verse(
        book_id=r['book_id'],
        chapter=r['chapter'],
        verse=r['verse'],
        text_am=r['text_am'],
        text_en=r['text_en'],
    )


class Store:
    """Read-only façade over bible.db."""

    def __init__(self, path: Path = DB_PATH) -> None:
        self._db = _connect_readonly(path)
        self._books: tuple[Book, ...] = tuple(
            _to_book(r) for r in self._db.execute('SELECT * FROM book ORDER BY id')
        )
        self._by_id = {b.id: b for b in self._books}
        self._by_slug = {b.slug: b for b in self._books}

    def close(self) -> None:
        self._db.close()

    # ------------------------------------------------------------ books

    @property
    def books(self) -> tuple[Book, ...]:
        return self._books

    def book(self, book_id: int) -> Book:
        try:
            return self._by_id[book_id]
        except KeyError:
            raise StoreError(f'no such book id: {book_id}') from None

    def book_by_slug(self, slug: str) -> Book:
        try:
            return self._by_slug[slug]
        except KeyError:
            raise StoreError(f'no such book: {slug}') from None

    def books_by_section(self) -> list[tuple[Section, list[Book]]]:
        """Books grouped for the picker, preserving canonical order within a group."""
        grouped: dict[Section, list[Book]] = {}
        for b in self._books:
            grouped.setdefault(b.section, []).append(b)
        # Order sections by where they first appear in the canon, not alphabetically.
        return sorted(grouped.items(), key=lambda kv: kv[1][0].id)

    # ------------------------------------------------------------ verses

    def chapter(self, book_id: int, chapter: int) -> list[Verse]:
        rows = self._db.execute(
            'SELECT book_id, chapter, verse, text_am, text_en FROM verse'
            ' WHERE book_id = ? AND chapter = ? ORDER BY verse',
            (book_id, chapter),
        )
        return [_to_verse(r) for r in rows]

    def verse(self, book_id: int, chapter: int, verse: int) -> Verse | None:
        r = self._db.execute(
            'SELECT book_id, chapter, verse, text_am, text_en FROM verse'
            ' WHERE book_id = ? AND chapter = ? AND verse = ?',
            (book_id, chapter, verse),
        ).fetchone()
        return _to_verse(r) if r else None

    # ------------------------------------------------------------ navigation

    def next_chapter(self, book_id: int, chapter: int) -> tuple[int, int] | None:
        """Chapter after this one, rolling into the next book. None at the end."""
        book = self.book(book_id)
        if chapter < book.chapter_count:
            return (book_id, chapter + 1)
        nxt = self._by_id.get(book_id + 1)
        return (nxt.id, 1) if nxt else None

    def prev_chapter(self, book_id: int, chapter: int) -> tuple[int, int] | None:
        """Chapter before this one, rolling into the previous book. None at the start."""
        if chapter > 1:
            return (book_id, chapter - 1)
        prev = self._by_id.get(book_id - 1)
        return (prev.id, prev.chapter_count) if prev else None

    # ------------------------------------------------------------ search

    def search(self, query: str, limit: int = 200) -> list[SearchHit]:
        """Full-text search across both languages.

        The query goes to FTS5 as-is apart from quoting, so a bare word matches a
        prefix-free term in either column. Malformed FTS syntax raises
        sqlite3.OperationalError, which the caller surfaces as "no results"
        rather than crashing the UI.
        """
        q = query.strip()
        if not q:
            return []
        rows = self._db.execute(
            """
            SELECT v.book_id, b.name_am AS book_name_am, b.name_en AS book_name_en,
                   v.chapter, v.verse, v.text_am, v.text_en,
                   -- Guillemets, not brackets: the snippet is rendered through
                   -- Rich, where a literal [..] is markup and would be swallowed.
                   snippet(verse_fts, -1, '«', '»', ' … ', 12) AS snippet
            FROM verse_fts f
            JOIN verse v ON v.id = f.rowid
            JOIN book  b ON b.id = v.book_id
            WHERE verse_fts MATCH ?
            ORDER BY v.id
            LIMIT ?
            """,
            (q, limit),
        )
        return [
            SearchHit(
                book_id=r['book_id'],
                book_name_am=r['book_name_am'],
                book_name_en=r['book_name_en'],
                chapter=r['chapter'],
                verse=r['verse'],
                text_am=r['text_am'],
                text_en=r['text_en'],
                snippet=r['snippet'],
            )
            for r in rows
        ]

    # ------------------------------------------------------------ stats

    def stats(self) -> Stats:
        r = self._db.execute(
            'SELECT count(*) AS verses, count(text_en) AS translated FROM verse'
        ).fetchone()
        chapters = self._db.execute('SELECT sum(chapter_count) AS n FROM book').fetchone()['n']
        return Stats(
            books=len(self._books),
            chapters=chapters or 0,
            verses=r['verses'],
            translated=r['translated'],
        )
