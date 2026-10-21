#!/usr/bin/env python3
"""Show Amharic/English pairs from translated books containing an Amharic term.

How a translator checks what earlier books already settled for a word, so the
same Amharic does not acquire a second English rendering three books later.

    python tools/lookup.py ቍርባን                 # 6 hits anywhere
    python tools/lookup.py ቍርባን 20              # 20 hits
    python tools/lookup.py ቍርባን 20 exodus,leviticus
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    term = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    books = sys.argv[3].split(',') if len(sys.argv) > 3 else None

    # mode=ro, not immutable=1: translators may be writing this file right now,
    # and immutable=1 lets SQLite skip locking, which is only safe when the
    # promise it encodes -- that the file will not change -- is actually true.
    db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    sql = [
        'SELECT b.slug, v.chapter, v.verse, v.text_am, v.text_en'
        ' FROM verse v JOIN book b ON b.id = v.book_id'
        ' WHERE v.text_en IS NOT NULL AND v.text_am LIKE ?'
    ]
    params: list[object] = [f'%{term}%']
    if books:
        sql.append(f'AND b.slug IN ({",".join("?" * len(books))})')
        params += books
    sql.append('LIMIT ?')
    params.append(limit)

    n = 0
    for slug, ch, vs, am, en in db.execute(' '.join(sql), params):
        print(f'=== {slug} {ch}:{vs}')
        print('AM:', am)
        print('EN:', en)
        n += 1
    if not n:
        print('(no hits in translated text)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
