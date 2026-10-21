#!/usr/bin/env python3
"""Apply the build-time verse cleanup to an existing database, in place.

A full rebuild would be the obvious fix, but rebuilding drops every translation
already written into text_en. This applies the same transformation surgically so
translated work survives.

MUST NOT run while readers hold the database open: store.py opens it with
`immutable=1`, which promises SQLite the file will not change. Writing under that
promise is undefined behaviour. Run this only when nothing else is using the db.

    python tools/repair_artifacts.py --dry-run
    python tools/repair_artifacts.py
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH, WRITE_TIMEOUT  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_db import clean_verse  # noqa: E402

# Corruption we can detect but must not guess at: a Latin letter has *replaced* a
# Ge'ez character, so the original is unrecoverable from the file alone. Reported,
# never rewritten.
LATIN_IN_GEEZ_RE = re.compile(r'[ሀ-፿][A-Za-z]|[A-Za-z][ሀ-፿]')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=WRITE_TIMEOUT)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        'SELECT v.id, b.name_en, v.chapter, v.verse, v.text_am'
        ' FROM verse v JOIN book b ON b.id = v.book_id'
    ).fetchall()

    fixes = []
    unrepairable = []
    for r in rows:
        cleaned = clean_verse(r['text_am'], r['verse'])
        if cleaned != r['text_am']:
            fixes.append((r['id'], cleaned, r['name_en'], r['chapter'], r['verse'], r['text_am']))
        if LATIN_IN_GEEZ_RE.search(r['text_am']):
            unrepairable.append((r['name_en'], r['chapter'], r['verse'], r['text_am']))

    print(f'repairable (footnote digits): {len(fixes)}')
    for _id, new, book, ch, vs, old in fixes[:25]:
        i = next((k for k, (a, b) in enumerate(zip(old, new, strict=False)) if a != b), 0)
        print(f'  {book} {ch}:{vs}   …{old[max(0, i - 14):i + 14]}…  ->  …{new[max(0, i - 14):i + 12]}…')

    print(f'\nNOT repairable (Latin spliced into Ge\'ez): {len(unrepairable)}')
    for book, ch, vs, txt in unrepairable:
        m = LATIN_IN_GEEZ_RE.search(txt)
        i = m.start() if m else 0
        print(f'  {book} {ch}:{vs}   …{txt[max(0, i - 22):i + 22]}…')
    print('  ^ a character was replaced, not inserted. Needs the original source '
          'to fix; left untouched rather than guessed at.')

    if args.dry_run:
        print('\ndry run — nothing written')
        return 0

    db.executemany(
        'UPDATE verse SET text_am = ? WHERE id = ?',
        [(new, _id) for _id, new, *_ in fixes],
    )
    db.commit()
    print(f'\nwrote {len(fixes)} corrections')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
