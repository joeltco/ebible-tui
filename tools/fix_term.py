#!/usr/bin/env python3
"""Normalise a single term across already-translated English.

For one-word drift ("Didymos" vs "Didymus") a full re-translation is wasteful.
This rewrites just the term, and only where the Amharic actually contains the
source word — so a coincidental English match in an unrelated verse cannot be
hit.

Wholesale drift (a whole book transliterated) should still be re-translated;
search-and-replace across hundreds of verses hides collateral damage.

    python tools/fix_term.py --am ዲዲሞስ --from Didymos --to Didymus --dry-run
    python tools/fix_term.py --am ዲዲሞስ --from Didymos --to Didymus
    python tools/fix_term.py --from Didymos --to Didymus --book john
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--from', dest='old', required=True, help='English term to replace')
    ap.add_argument('--to', dest='new', required=True, help='replacement')
    ap.add_argument('--am', help='require this Amharic substring in the same verse')
    ap.add_argument('--book', help='restrict to one book slug')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    sql = ["SELECT v.id, b.name_en, v.chapter, v.verse, v.text_am, v.text_en"
           " FROM verse v JOIN book b ON b.id = v.book_id"
           " WHERE v.text_en IS NOT NULL AND v.text_en LIKE ?"]
    params: list[str] = [f'%{args.old}%']
    if args.am:
        sql.append('AND v.text_am LIKE ?')
        params.append(f'%{args.am}%')
    if args.book:
        sql.append('AND b.slug = ?')
        params.append(args.book)

    rows = db.execute(' '.join(sql), params).fetchall()

    # Word-boundary match so "Judah" does not rewrite inside "Judahite".
    pat = re.compile(rf'\b{re.escape(args.old)}\b')
    edits = []
    for r in rows:
        new_en = pat.sub(args.new, r['text_en'])
        if new_en != r['text_en']:
            edits.append((r['id'], new_en, f'{r["name_en"]} {r["chapter"]}:{r["verse"]}'))

    print(f'{len(rows)} verses match "{args.old}"; {len(edits)} contain it as a whole word\n')
    for _id, new_en, ref in edits[:20]:
        i = new_en.find(args.new)
        print(f'  {ref:<20} …{new_en[max(0, i - 34):i + len(args.new) + 20]}…')
    if len(edits) > 20:
        print(f'  …and {len(edits) - 20} more')

    if args.dry_run:
        print('\ndry run — nothing written')
        return 0
    if not edits:
        print('nothing to do')
        return 0

    db.executemany('UPDATE verse SET text_en = ? WHERE id = ?',
                   [(new_en, _id) for _id, new_en, _ in edits])
    db.commit()
    print(f'\nrewrote {len(edits)} verses')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
