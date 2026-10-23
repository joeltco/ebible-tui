#!/usr/bin/env python3
"""Reproduce the Amharic-only database, preserving all source rows exactly.

Usage: python tools/strip_english.py SOURCE --out DESTINATION
SOURCE may be DESTINATION: replacement is atomic and occurs only after validation.
The old English database is recoverable from git at e1564db; never retain a tree copy.
"""

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / 'src/ebible/data/schema.sql'


def strip_english(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as old:
        books = old.execute('SELECT * FROM book ORDER BY id').fetchall()
        verses = old.execute(
            'SELECT id,book_id,chapter,verse,text_am FROM verse ORDER BY id'
        ).fetchall()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.amharic-', suffix='.db', dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        db = sqlite3.connect(temporary)
        try:
            db.execute('PRAGMA page_size=4096')
            db.executescript(SCHEMA.read_text(encoding='utf-8'))
            db.executemany('INSERT INTO book VALUES (?,?,?,?,?,?,?)', books)
            db.executemany('INSERT INTO verse VALUES (?,?,?,?,?)', verses)
            db.executemany(
                'INSERT INTO meta VALUES (?,?)',
                [
                    ('schema_version', '2'),
                    ('book_count', str(len(books))),
                    ('chapter_count', str(len({(v[1], v[2]) for v in verses}))),
                    ('verse_count', str(len(verses))),
                ],
            )
            db.execute("INSERT INTO verse_fts(verse_fts) VALUES ('rebuild')")
            db.execute("INSERT INTO verse_fts(verse_fts,rank) VALUES ('integrity-check',1)")
            assert db.execute('SELECT * FROM book ORDER BY id').fetchall() == books
            assert db.execute('SELECT * FROM verse ORDER BY id').fetchall() == verses
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            db.commit()
            db.execute('VACUUM')
        finally:
            db.close()
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    strip_english(args.source, args.out)
    print(f'Amharic-only database: {args.out} ({args.out.stat().st_size:,} bytes)')
