#!/usr/bin/env python3
"""Detect terminology drift between independently-translated batches.

Splitting 39,169 verses across many agents buys throughput and risks
inconsistency: the same Amharic word rendered one way in Genesis and another in
Malachi. This checks the risk rather than assuming the guide prevented it.

Method: for each watched Amharic term, look at every translated verse containing
it and count which of the expected English renderings appear. A term whose
verses split across two renderings is drift; a term whose verses show none of
them is a gap worth eyeballing.

    python tools/check_consistency.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible.data.store import DB_PATH  # noqa: E402

# (Amharic term, expected English, competing renderings that would indicate drift)
WATCHED: list[tuple[str, str, tuple[str, ...]]] = [
    ('እግዚአብሔር አምላክ', 'the LORD God', ('God God', 'the Lord God')),
    ('እግዚአብሔር', 'the LORD', ('God',)),
    ('አምላክ', 'God', ('the LORD',)),
    ('ጌታ', 'the Lord', ('the LORD', 'master')),
    ('ኢየሱስ', 'Jesus', ()),
    ('ክርስቶስ', 'Christ', ('Messiah',)),
    ('ኪዳን', 'covenant', ('testament',)),
    ('ጽድቅ', 'righteousness', ('justice',)),
    ('ኀጢአት', 'sin', ('iniquity', 'transgression')),
    ('ምሕረት', 'mercy', ('compassion', 'lovingkindness')),
    ('እምነት', 'faith', ('belief', 'trust')),
    ('ጠፈር', 'firmament', ('expanse', 'vault')),
    ('ንስሓ', 'repentance', ('repent',)),
]


def main() -> int:
    db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row

    done = db.execute('SELECT count(text_en) c FROM verse').fetchone()['c']
    print(f'checking {done:,} translated verses\n')

    print(f'{"term":<18}{"expected":<16}{"hits":>7}{"expected%":>11}  competing')
    print('-' * 78)

    problems: list[str] = []
    for am, expected, competing in WATCHED:
        rows = db.execute(
            'SELECT text_en FROM verse WHERE text_am LIKE ? AND text_en IS NOT NULL',
            (f'%{am}%',),
        ).fetchall()
        if not rows:
            continue
        n = len(rows)
        want = sum(1 for r in rows if expected.lower() in r['text_en'].lower())
        rival = {
            c: sum(1 for r in rows if c.lower() in r['text_en'].lower())
            for c in competing
        }
        rival = {k: v for k, v in rival.items() if v}
        pct = want / n * 100
        rival_s = ', '.join(f'{k}:{v}' for k, v in rival.items()) or '—'
        print(f'{am:<18}{expected:<16}{n:>7}{pct:>10.0f}%  {rival_s}')

        # `እግዚአብሔር አምላክ` legitimately contains both `እግዚአብሔር` and `አምላክ`, so the
        # substring rows overlap; only flag a term whose own rendering is scarce.
        if pct < 60 and am not in ('አምላክ', 'ጌታ'):
            problems.append(f'{am}: only {pct:.0f}% of verses use "{expected}"')

    print()
    hard = db.execute(
        "SELECT count(*) c FROM verse WHERE text_en LIKE '%God God%'"
    ).fetchone()['c']
    print(f'"God God" (must be 0): {hard}')
    if hard:
        problems.append(f'{hard} verses contain "God God"')

    # Translator notes leaking into verse text — the guide forbids these.
    leak = db.execute(
        "SELECT count(*) c FROM verse WHERE text_en LIKE '%[?]%'"
        " OR text_en LIKE '%(sic)%' OR text_en LIKE '%[translator%'"
    ).fetchone()['c']
    print(f'translator notes inside verses (must be 0): {leak}')
    if leak:
        problems.append(f'{leak} verses contain translator notes')

    print()
    if problems:
        print('POTENTIAL DRIFT:')
        for p in problems:
            print(f'  - {p}')
        return 1
    print('no drift detected on watched terms')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
