#!/usr/bin/env python3
"""Make bible.db safe to commit and to ship.

While translators run in parallel the database is in WAL mode, which is the right
choice then: readers do not block the writer. It is the wrong state to commit.

`store.py` opens the shipped database with `immutable=1`, which promises SQLite
the file will not change and lets it skip locking -- and makes it **ignore the
-wal file entirely**. So a database committed mid-WAL has verses that exist in
the repository and do not appear in the app. Nothing errors; the text is just
quietly absent.

`immutable=1` is still correct for shipping. A WAL-mode database opened `mode=ro`
has to create a -shm file, which fails when the package sits in a read-only
location -- the Termux and system-site-packages case store.py was written for.
The fix is not to change how the reader opens it, but to ship a database with no
sidecars at all.

Run this before any commit that includes bible.db:

    python tools/seal_db.py

It fails loudly if a translator still holds the database, because checkpointing
needs the write lock.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH, WRITE_TIMEOUT  # noqa: E402


def main() -> int:
    before = {
        p.name: p.stat().st_size
        for p in (DB_PATH.with_name(DB_PATH.name + s) for s in ('-wal', '-shm'))
        if p.exists()
    }
    if before:
        print('sidecars present: ' + ', '.join(f'{k} ({v:,}B)' for k, v in before.items()))
    else:
        print('no sidecars on disk')

    db = sqlite3.connect(DB_PATH, timeout=WRITE_TIMEOUT)
    mode = db.execute('PRAGMA journal_mode').fetchone()[0]
    print(f'journal_mode: {mode}')

    translated = db.execute('SELECT count(text_en) FROM verse').fetchone()[0]

    if mode.lower() == 'wal':
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        # DELETE mode removes the -wal and -shm files outright. Setting it needs
        # the write lock, so this raises rather than half-finishing if an agent
        # is still pushing chapters.
        new_mode = db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
        print(f'checkpointed; journal_mode now {new_mode}')
        if new_mode.lower() != 'delete':
            print('FAILED to leave WAL mode — is a translator still running?', file=sys.stderr)
            return 1
    db.close()

    # The count the reader will actually see. If this disagrees with the WAL-aware
    # count, the checkpoint did not land and committing would lose verses.
    ro = sqlite3.connect(f'file:{DB_PATH}?immutable=1', uri=True)
    visible = ro.execute('SELECT count(text_en) FROM verse').fetchone()[0]
    ro.close()

    leftover = [
        p.name for p in
        (DB_PATH.with_name(DB_PATH.name + s) for s in ('-wal', '-shm')) if p.exists()
    ]
    print(f'translated verses: {translated:,} written, {visible:,} visible to the reader')
    if leftover:
        print(f'sidecars still present: {leftover}', file=sys.stderr)
    if visible != translated:
        print(f'MISMATCH — {translated - visible:,} verses would be invisible in the app.',
              file=sys.stderr)
        return 1
    print('sealed: safe to commit')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
