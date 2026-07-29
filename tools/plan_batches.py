#!/usr/bin/env python3
"""Partition untranslated chapters into balanced work batches.

Batches are sized by verse count, not chapter count -- chapters range from 1 to
176 verses, so splitting by chapter produces wildly uneven work. A batch never
spans two books, which keeps each agent in one voice and one context.

    python tools/plan_batches.py --target 500
    python tools/plan_batches.py --target 500 --exclude genesis:1-5,matthew:1-3
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH  # noqa: E402


def parse_exclude(spec: str) -> set[tuple[str, int]]:
    """'genesis:1-5,matthew:1-3' -> {('genesis',1), ..., ('matthew',3)}"""
    out: set[tuple[str, int]] = set()
    for part in filter(None, (s.strip() for s in spec.split(','))):
        slug, _, rng = part.partition(':')
        for piece in rng.split('+'):
            if '-' in piece:
                lo, hi = piece.split('-')
                out.update((slug, c) for c in range(int(lo), int(hi) + 1))
            elif piece:
                out.add((slug, int(piece)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--target', type=int, default=500, help='verses per batch')
    ap.add_argument('--exclude', default='', help='slug:1-5,slug:7 chapters to skip')
    args = ap.parse_args()

    skip = parse_exclude(args.exclude)

    db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        SELECT b.slug, b.name_en, b.deuterocanonical, v.chapter, count(*) AS verses
        FROM verse v JOIN book b ON b.id = v.book_id
        WHERE v.text_en IS NULL
        GROUP BY v.book_id, v.chapter
        ORDER BY v.book_id, v.chapter
        """
    ).fetchall()

    batches: list[dict] = []
    cur: dict | None = None
    for r in rows:
        if (r['slug'], r['chapter']) in skip:
            continue
        # Start a new batch at a book boundary or once the target is reached.
        if cur is None or cur['slug'] != r['slug'] or cur['verses'] >= args.target:
            cur = {
                'slug': r['slug'],
                'name': r['name_en'],
                'dc': bool(r['deuterocanonical']),
                'chapters': [],
                'verses': 0,
            }
            batches.append(cur)
        cur['chapters'].append(r['chapter'])
        cur['verses'] += r['verses']

    total = sum(b['verses'] for b in batches)
    for i, b in enumerate(batches, 1):
        ch = b['chapters']
        span = f'{ch[0]}-{ch[-1]}' if len(ch) > 1 else str(ch[0])
        mark = ' dc' if b['dc'] else ''
        print(f'{i}\t{b["slug"]}\t{span}\t{b["verses"]}{mark}')
    print(
        f'\n# {len(batches)} batches, {total:,} verses, '
        f'avg {total // max(len(batches), 1)} verses/batch',
        file=sys.stderr,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
