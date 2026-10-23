"""Disposable on-device store of finished verse translations, for instant re-display.

Translation still happens only on request; this file just remembers the answer. It lives in
the XDG cache directory, apart from personal data, and any failure degrades to a miss.
"""

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

from ebible.core.models import VerseRef
from ebible.paths import translation_cache_path

_SCHEMA = (
    'CREATE TABLE IF NOT EXISTS verse_translation (backend TEXT NOT NULL, book_id INTEGER NOT NULL, '
    'chapter INTEGER NOT NULL, verse INTEGER NOT NULL, source_sha TEXT NOT NULL, text TEXT NOT NULL '
    'CHECK(length(trim(text))>0), PRIMARY KEY(backend, book_id, chapter, verse, source_sha))'
)


def _sha(source_am: str) -> str:
    # Keyed by the Amharic text too, so a changed source never shows a stale translation.
    return hashlib.sha256(source_am.encode('utf-8')).hexdigest()


class TranslationCache:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or translation_cache_path()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=2)
        connection.execute(_SCHEMA)
        return connection

    def get(self, backend: str, ref: VerseRef, source_am: str) -> str | None:
        if not self.path.exists():
            return None
        try:
            with closing(self._connect()) as db:
                row = db.execute(
                    'SELECT text FROM verse_translation WHERE backend=? AND book_id=? AND chapter=? '
                    'AND verse=? AND source_sha=?',
                    (backend, ref.book_id, ref.chapter, ref.verse, _sha(source_am)),
                ).fetchone()
        except sqlite3.Error:
            return None
        return row[0] if row and isinstance(row[0], str) and row[0].strip() else None

    def put(self, backend: str, ref: VerseRef, source_am: str, text: str) -> None:
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    'INSERT OR REPLACE INTO verse_translation VALUES (?, ?, ?, ?, ?, ?)',
                    (backend, ref.book_id, ref.chapter, ref.verse, _sha(source_am), text),
                )
        except (sqlite3.Error, OSError):
            pass
