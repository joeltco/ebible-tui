"""Read-only scripture queries. Each operation owns its connection for workers."""

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from ebible.canon import BOOKS, BY_ID, BY_SLUG, Book
from ebible.core.labels import count_label
from ebible.core.models import Chapter, ScriptureStats, SearchResult, Verse, VerseRef
from ebible.core.refs import ReferenceError

DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'bible.db'


@contextmanager
def open_readonly(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


class SearchError(ValueError):
    """Invalid FTS syntax or search options."""


class ScriptureStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path

    def close(self) -> None:
        """No persistent connections; retained for offline callers."""

    def books(self) -> tuple[Book, ...]:
        return BOOKS

    def book_by_slug(self, slug: str) -> Book:
        return BY_SLUG[slug]

    def chapter_counts(self) -> dict[int, int]:
        with open_readonly(self.path) as db:
            return {
                row['id']: row['chapter_count']
                for row in db.execute('SELECT id, chapter_count FROM book ORDER BY id')
            }

    def stats(self) -> ScriptureStats:
        with open_readonly(self.path) as db:
            row = db.execute('SELECT count(*) AS n FROM verse').fetchone()
            return ScriptureStats(row['n'])

    def chapter(self, book: int, chapter: int) -> Chapter:
        if book not in BY_ID or chapter < 1:
            raise ReferenceError('Unknown book or chapter')
        with open_readonly(self.path) as db:
            rows = db.execute(
                'SELECT verse, text_am FROM verse WHERE book_id=? AND chapter=? ORDER BY verse',
                (book, chapter),
            ).fetchall()
        if not rows:
            raise ReferenceError(f'No such chapter: {BY_ID[book].name_en} {chapter}')
        verses = [Verse(VerseRef(book, chapter, r['verse']), r['text_am']) for r in rows]
        return Chapter(BY_ID[book], chapter, tuple(verses))

    def verse(self, ref: VerseRef) -> Verse:
        for verse in self.chapter(ref.book_id, ref.chapter):
            if verse.verse == ref.verse:
                return verse
        raise ReferenceError(f'Verse {ref.verse} is absent from the source')

    def validate_reference(self, ref: VerseRef) -> None:
        if ref.book_id == 28 and ref.chapter == 151:
            raise ReferenceError('Psalm 151 is filed as Psalms 150:7-14 in this source.')
        with open_readonly(self.path) as db:
            count = db.execute(
                'SELECT max(chapter) FROM verse WHERE book_id=?', (ref.book_id,)
            ).fetchone()[0]
            numbers = {
                r[0]
                for r in db.execute(
                    'SELECT verse FROM verse WHERE book_id=? AND chapter=?',
                    (ref.book_id, ref.chapter),
                )
            }
        if not numbers:
            raise ReferenceError(
                f'{BY_ID[ref.book_id].name_en} has {count_label(count, "chapter")}; chapter {ref.chapter} does not exist.'
            )
        if ref.verse not in numbers or (ref.end_verse is not None and ref.end_verse not in numbers):
            raise ReferenceError(
                f'Reference endpoint is absent from the source. {BY_ID[ref.book_id].name_en} {ref.chapter} has verses {min(numbers)}–{max(numbers)}.'
            )

    def search(
        self,
        query: str,
        scope: Literal['all', 'ot', 'nt', 'book'] = 'all',
        *,
        book_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[SearchResult, ...]:
        """Plain words by default; prefix with = to opt into raw FTS5 syntax.

        Run this synchronous method in a UI worker. Snippet markers are control
        characters, not Rich markup, so literal square brackets stay literal.
        """
        if scope not in ('all', 'ot', 'nt', 'book'):
            raise SearchError('Unknown scope')
        if limit < 1 or limit > 1000 or offset < 0:
            raise SearchError('Limit must be 1–1000; offset must be nonnegative')
        if scope == 'book' and book_id not in BY_ID:
            raise SearchError('Current-book search requires a valid book_id')
        if not query.strip():
            return ()
        query = query.strip()
        if query.startswith('='):
            query = query[1:].strip()
        else:
            tokens = re.findall(r'[^\W_]+', query, flags=re.UNICODE)
            query = ' AND '.join(f'"{token}"' for token in tokens)
            if tokens:
                query += '*'
        if not query:
            return ()
        filters = {
            'all': '',
            'ot': ' AND v.book_id < 55',
            'nt': ' AND v.book_id >= 55',
            'book': ' AND v.book_id = ?',
        }
        params: list[str | int] = [query]
        if scope == 'book':
            assert book_id is not None
            params.append(book_id)
        params.extend((limit, offset))
        try:
            with open_readonly(self.path) as db:
                rows = db.execute(
                    "SELECT v.book_id, v.chapter, v.verse, snippet(verse_fts, 0, char(1), char(2), '…', 24) AS snippet "
                    'FROM verse_fts JOIN verse v ON v.id=verse_fts.rowid WHERE verse_fts MATCH ?'
                    + filters[scope]
                    + ' ORDER BY rank, v.id LIMIT ? OFFSET ?',
                    params,
                ).fetchall()
        except sqlite3.OperationalError as exc:
            raise SearchError(
                'That advanced search is not valid. Check quotes/operators, or remove = to search ordinary words.'
            ) from exc
        return tuple(
            SearchResult(
                VerseRef(r['book_id'], r['chapter'], r['verse']),
                r['snippet'],
            )
            for r in rows
        )

    def search_substrings(
        self,
        variants: tuple[str, ...],
        scope: Literal['all', 'ot', 'nt', 'book'] = 'all',
        *,
        book_id: int | None = None,
        limit: int = 40,
        offset: int = 0,
    ) -> tuple[SearchResult, ...]:
        """Literal Amharic substrings, ORed and paginated in canonical order."""
        if scope not in ('all', 'ot', 'nt', 'book'):
            raise SearchError('Unknown scope')
        if limit < 1 or limit > 1000 or offset < 0:
            raise SearchError('Limit must be 1–1000; offset must be nonnegative')
        if scope == 'book' and book_id not in BY_ID:
            raise SearchError('Current-book search requires a valid book_id')
        if not variants:
            return ()
        if len(variants) > 3 or any(not variant for variant in variants):
            raise SearchError('Use one to three nonempty variants')
        filters = {
            'all': '',
            'ot': ' AND book_id < 55',
            'nt': ' AND book_id >= 55',
            'book': ' AND book_id = ?',
        }
        params: list[str | int] = list(variants)
        if scope == 'book':
            assert book_id is not None
            params.append(book_id)
        params.extend((limit, offset))
        with open_readonly(self.path) as db:
            rows = db.execute(
                'SELECT book_id, chapter, verse, text_am FROM verse WHERE ('
                + ' OR '.join('instr(text_am, ?) > 0' for _ in variants)
                + ')'
                + filters[scope]
                + ' ORDER BY book_id, chapter, verse LIMIT ? OFFSET ?',
                params,
            ).fetchall()
        pattern = re.compile(
            '|'.join(re.escape(word) for word in sorted(set(variants), key=len, reverse=True))
        )
        results = []
        for row in rows:
            source = row['text_am']
            match = pattern.search(source)
            assert match is not None
            start = max(0, match.start() - 48)
            end = min(len(source), max(start + 180, match.end()))
            snippet = pattern.sub(lambda m: '\x01' + m[0] + '\x02', source[start:end])
            results.append(
                SearchResult(
                    VerseRef(row['book_id'], row['chapter'], row['verse']),
                    ('…' if start else '') + snippet + ('…' if end < len(source) else ''),
                )
            )
        return tuple(results)
