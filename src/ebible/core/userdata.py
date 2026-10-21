"""Versioned personal SQLite data, isolated from the immutable scripture store.

Connections are short-lived and local to each call, allowing the same store to
be used by UI and translation workers without sharing SQLite connections.
"""

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

from ebible.core.models import (
    HIGHLIGHT_COLOURS,
    Bookmark,
    Highlight,
    HighlightColour,
    HistoryEntry,
    LiveTranslation,
    Note,
    PlanProgress,
    VerseRef,
)
from ebible.core.plans import ReadingPlan
from ebible.paths import user_db_path

SCHEMA_VERSION = 2
_REF_COLUMNS = 'book_id INTEGER NOT NULL CHECK(book_id BETWEEN 1 AND 81), chapter INTEGER NOT NULL CHECK(chapter > 0), verse INTEGER NOT NULL CHECK(verse > 0)'
_KEY = 'PRIMARY KEY(book_id, chapter, verse)'
_MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        f'CREATE TABLE bookmark ({_REF_COLUMNS}, created_at TEXT NOT NULL, {_KEY})',
        f"CREATE TABLE highlight ({_REF_COLUMNS}, colour TEXT NOT NULL CHECK(colour IN ('gold','green','red','blue','purple')), created_at TEXT NOT NULL, {_KEY})",
        f'CREATE TABLE note ({_REF_COLUMNS}, text TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, {_KEY})',
        f'CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, {_REF_COLUMNS}, visited_at TEXT NOT NULL)',
        f'CREATE TABLE reading_position (id INTEGER PRIMARY KEY CHECK(id=1), {_REF_COLUMNS}, updated_at TEXT NOT NULL)',
        'CREATE TABLE plan (plan_id TEXT PRIMARY KEY, start_date TEXT NOT NULL, total_days INTEGER NOT NULL CHECK(total_days>0))',
        'CREATE TABLE plan_progress (plan_id TEXT NOT NULL REFERENCES plan(plan_id) ON DELETE CASCADE, day INTEGER NOT NULL CHECK(day>0), completed_on TEXT NOT NULL, PRIMARY KEY(plan_id, day))',
    ),
    2: (
        f'CREATE TABLE live_translation ({_REF_COLUMNS}, text TEXT NOT NULL CHECK(length(trim(text))>0), backend TEXT NOT NULL, translated_at TEXT NOT NULL, {_KEY})',
    ),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _key(ref: VerseRef) -> tuple[int, int, int]:
    if ref.end_verse is not None:
        raise ValueError('Personal data requires a single verse, not a range')
    return ref.book_id, ref.chapter, ref.verse


def _ref(row: sqlite3.Row) -> VerseRef:
    return VerseRef(row['book_id'], row['chapter'], row['verse'])


class UserDataStore:
    def __init__(self, path: Path | None = None, *, history_limit: int = 200) -> None:
        if history_limit < 1:
            raise ValueError('History limit must be positive')
        self.path = path if path is not None else user_db_path()
        self.history_limit = history_limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _migrate(self) -> None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError(
                    f'User database version {version} is newer than supported {SCHEMA_VERSION}'
                )
            for target in range(version + 1, SCHEMA_VERSION + 1):
                for statement in _MIGRATIONS[target]:
                    db.execute(statement)
                db.execute(f'PRAGMA user_version={target}')

    def add_bookmark(self, ref: VerseRef) -> None:
        with self._connect() as db:
            db.execute('INSERT OR IGNORE INTO bookmark VALUES (?, ?, ?, ?)', (*_key(ref), _now()))

    def bookmarks(self) -> tuple[Bookmark, ...]:
        with self._connect() as db:
            return tuple(
                Bookmark(_ref(r), datetime.fromisoformat(r['created_at']))
                for r in db.execute('SELECT * FROM bookmark ORDER BY book_id, chapter, verse')
            )

    def set_highlight(self, ref: VerseRef, colour: HighlightColour) -> None:
        if colour not in HIGHLIGHT_COLOURS:
            raise ValueError('Unknown highlight colour')
        with self._connect() as db:
            db.execute(
                'INSERT INTO highlight VALUES (?, ?, ?, ?, ?) ON CONFLICT(book_id,chapter,verse) DO UPDATE SET colour=excluded.colour',
                (*_key(ref), colour, _now()),
            )

    def highlights(self) -> tuple[Highlight, ...]:
        with self._connect() as db:
            return tuple(
                Highlight(
                    _ref(r),
                    cast(HighlightColour, r['colour']),
                    datetime.fromisoformat(r['created_at']),
                )
                for r in db.execute('SELECT * FROM highlight ORDER BY book_id, chapter, verse')
            )

    def save_note(self, ref: VerseRef, text: str) -> None:
        timestamp = _now()
        with self._connect() as db:
            db.execute(
                'INSERT INTO note VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(book_id,chapter,verse) DO UPDATE SET text=excluded.text, updated_at=excluded.updated_at',
                (*_key(ref), text, timestamp, timestamp),
            )

    def notes(self) -> tuple[Note, ...]:
        with self._connect() as db:
            return tuple(
                Note(
                    _ref(r),
                    r['text'],
                    datetime.fromisoformat(r['created_at']),
                    datetime.fromisoformat(r['updated_at']),
                )
                for r in db.execute(
                    'SELECT * FROM note ORDER BY updated_at DESC, book_id, chapter, verse'
                )
            )

    def _delete(self, table: str, ref: VerseRef) -> None:
        # Only internal constant table names reach this method.
        with self._connect() as db:
            db.execute(f'DELETE FROM {table} WHERE book_id=? AND chapter=? AND verse=?', _key(ref))

    def delete_bookmark(self, ref: VerseRef) -> None:
        self._delete('bookmark', ref)

    def delete_highlight(self, ref: VerseRef) -> None:
        self._delete('highlight', ref)

    def delete_note(self, ref: VerseRef) -> None:
        self._delete('note', ref)

    def record_position(self, ref: VerseRef) -> None:
        key, timestamp = _key(ref), _now()
        with self._connect() as db:
            db.execute(
                'INSERT INTO reading_position VALUES (1, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET book_id=excluded.book_id, chapter=excluded.chapter, verse=excluded.verse, updated_at=excluded.updated_at',
                (*key, timestamp),
            )
            last = db.execute('SELECT * FROM history ORDER BY id DESC LIMIT 1').fetchone()
            if last is None or _ref(last) != ref:
                db.execute(
                    'INSERT INTO history(book_id,chapter,verse,visited_at) VALUES (?, ?, ?, ?)',
                    (*key, timestamp),
                )
            else:
                db.execute('UPDATE history SET visited_at=? WHERE id=?', (timestamp, last['id']))
            db.execute(
                'DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT ?)',
                (self.history_limit,),
            )

    def reading_position(self) -> VerseRef | None:
        with self._connect() as db:
            row = db.execute('SELECT * FROM reading_position WHERE id=1').fetchone()
            return _ref(row) if row else None

    def history(self) -> tuple[HistoryEntry, ...]:
        with self._connect() as db:
            return tuple(
                HistoryEntry(r['id'], _ref(r), datetime.fromisoformat(r['visited_at']))
                for r in db.execute('SELECT * FROM history ORDER BY id DESC')
            )

    def delete_history(self, entry_id: int) -> None:
        with self._connect() as db:
            db.execute('DELETE FROM history WHERE id=?', (entry_id,))

    def start_plan(self, plan: ReadingPlan, start: date) -> None:
        """Explicitly (re)start a plan, clearing its former progress."""
        with self._connect() as db:
            db.execute('DELETE FROM plan WHERE plan_id=?', (plan.id,))
            db.execute('INSERT INTO plan VALUES (?, ?, ?)', (plan.id, start.isoformat(), plan.days))

    def complete_day(self, plan_id: str, day: int, *, on: date | None = None) -> None:
        with self._connect() as db:
            plan = db.execute('SELECT * FROM plan WHERE plan_id=?', (plan_id,)).fetchone()
            if plan is None or not 1 <= day <= plan['total_days']:
                raise ValueError('Unknown plan or day outside its schedule')
            when = on or date.today()
            if when < date.fromisoformat(plan['start_date']):
                raise ValueError('Completion cannot precede the plan start')
            db.execute(
                'INSERT OR IGNORE INTO plan_progress VALUES (?, ?, ?)',
                (plan_id, day, when.isoformat()),
            )

    def uncomplete_day(self, plan_id: str, day: int) -> None:
        with self._connect() as db:
            db.execute('DELETE FROM plan_progress WHERE plan_id=? AND day=?', (plan_id, day))

    def plan_progress(self, plan_id: str) -> PlanProgress | None:
        with self._connect() as db:
            plan = db.execute('SELECT * FROM plan WHERE plan_id=?', (plan_id,)).fetchone()
            if plan is None:
                return None
            rows = db.execute(
                'SELECT day, completed_on FROM plan_progress WHERE plan_id=?', (plan_id,)
            ).fetchall()
            return PlanProgress(
                plan_id,
                date.fromisoformat(plan['start_date']),
                frozenset(r['day'] for r in rows),
                frozenset(date.fromisoformat(r['completed_on']) for r in rows),
            )

    def save_translations(
        self, book_id: int, chapter: int, translations: Mapping[int, str], backend: str
    ) -> None:
        """Commit a validated batch atomically. Service verifies source alignment."""
        if not backend.strip():
            raise ValueError('Translation provenance is required')
        rows = []
        for verse, text in translations.items():
            ref = VerseRef(book_id, chapter, verse)
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Translation text cannot be empty')
            rows.append((*_key(ref), text, backend, _now()))
        with self._connect() as db:
            db.executemany(
                'INSERT INTO live_translation VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(book_id,chapter,verse) DO UPDATE SET text=excluded.text, backend=excluded.backend, translated_at=excluded.translated_at',
                rows,
            )

    def live_chapter(self, book_id: int, chapter: int) -> dict[int, str]:
        with self._connect() as db:
            return {
                r['verse']: r['text']
                for r in db.execute(
                    'SELECT verse,text FROM live_translation WHERE book_id=? AND chapter=?',
                    (book_id, chapter),
                )
            }

    def live_translation(self, ref: VerseRef) -> LiveTranslation | None:
        with self._connect() as db:
            row = db.execute(
                'SELECT * FROM live_translation WHERE book_id=? AND chapter=? AND verse=?',
                _key(ref),
            ).fetchone()
            return (
                LiveTranslation(
                    ref, row['text'], row['backend'], datetime.fromisoformat(row['translated_at'])
                )
                if row
                else None
            )

    def delete_translation(self, ref: VerseRef) -> None:
        self._delete('live_translation', ref)
