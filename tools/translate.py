#!/usr/bin/env python3
"""Move chapters between the store and a translator.

The translator is whatever produces the English -- there is no model client in
here. `pull` writes a chapter out as numbered lines, `push` reads translated
lines back in. That keeps the pipeline honest about the one rule that matters:
verse numbers must survive the round trip exactly.

    python tools/translate.py status
    python tools/translate.py pull  genesis 1        > /tmp/gen1.txt
    python tools/translate.py push  genesis 1 < /tmp/gen1-en.txt
    python tools/translate.py next  --count 5        # what still needs doing
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible import canon  # noqa: E402
from ebible.data.store import DB_PATH, Store, open_writable  # noqa: E402

LINE_RE = re.compile(r'^(\d+)[.:]\s*(.*)$')


class TranslateError(RuntimeError):
    pass


def cmd_status() -> None:
    store = Store()
    st = store.stats()
    print(f'{st.translated:,} / {st.verses:,} verses  ({st.translated_pct:.1f}%)')

    with open_writable(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT b.slug, b.name_en, b.deuterocanonical,
                   count(*) AS total, count(v.text_en) AS done
            FROM verse v JOIN book b ON b.id = v.book_id
            GROUP BY b.id ORDER BY b.id
            """
        ).fetchall()
    pending = [r for r in rows if r['done'] < r['total']]
    complete = len(rows) - len(pending)
    print(f'{complete} / {len(rows)} books complete')
    if pending:
        print('\npending:')
        for r in pending[:12]:
            mark = ' ·dc' if r['deuterocanonical'] else ''
            print(f'  {r["slug"]:<18} {r["done"]:>5} / {r["total"]:<5}{mark}')
        if len(pending) > 12:
            print(f'  … and {len(pending) - 12} more')
    store.close()


def cmd_pull(slug: str, chapter: int) -> None:
    store = Store()
    book = store.book_by_slug(slug)
    verses = store.chapter(book.id, chapter)
    if not verses:
        raise TranslateError(f'no such chapter: {slug} {chapter}')
    print(f'# {book.name_en} {chapter}  ({book.name_am})', file=sys.stderr)
    for v in verses:
        print(f'{v.verse}. {v.text_am}')
    store.close()


def cmd_push(slug: str, chapter: int) -> None:
    store = Store()
    book = store.book_by_slug(slug)
    expected = {v.verse for v in store.chapter(book.id, chapter)}
    store.close()
    if not expected:
        raise TranslateError(f'no such chapter: {slug} {chapter}')

    incoming: dict[int, str] = {}
    for lineno, raw in enumerate(sys.stdin.read().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = LINE_RE.match(line)
        if not m:
            raise TranslateError(f'stdin:{lineno}: not a numbered verse: {line[:60]!r}')
        num, text = int(m.group(1)), m.group(2).strip()
        if not text:
            raise TranslateError(f'stdin:{lineno}: verse {num} is empty')
        if num in incoming:
            raise TranslateError(f'stdin:{lineno}: verse {num} appears twice')
        incoming[num] = text

    # Alignment is the whole ballgame: a shifted verse silently attaches the
    # wrong English to the wrong Amharic, and nothing downstream would notice.
    missing = sorted(expected - set(incoming))
    extra = sorted(set(incoming) - expected)
    if missing or extra:
        raise TranslateError(
            f'{book.name_en} {chapter}: verse mismatch — '
            f'missing={missing[:10]} unexpected={extra[:10]}'
        )

    with open_writable(DB_PATH) as db:
        db.executemany(
            'UPDATE verse SET text_en = ? WHERE book_id = ? AND chapter = ? AND verse = ?',
            [(text, book.id, chapter, num) for num, text in incoming.items()],
        )
        total = db.execute('SELECT count(text_en) AS n FROM verse').fetchone()['n']
        db.execute('UPDATE meta SET value = ? WHERE key = ?', (str(total), 'translated_count'))
    print(f'{book.name_en} {chapter}: wrote {len(incoming)} verses  ({total:,} total)')


def cmd_next(count: int) -> None:
    """List chapters still needing translation, in canonical order."""
    with open_writable(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT b.slug, v.chapter, count(*) AS verses
            FROM verse v JOIN book b ON b.id = v.book_id
            WHERE v.text_en IS NULL
            GROUP BY v.book_id, v.chapter
            ORDER BY v.book_id, v.chapter
            LIMIT ?
            """,
            (count,),
        ).fetchall()
    if not rows:
        print('nothing pending — every verse is translated')
        return
    for r in rows:
        print(f'{r["slug"]} {r["chapter"]}  ({r["verses"]} verses)')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    p_pull = sub.add_parser('pull')
    p_pull.add_argument('slug')
    p_pull.add_argument('chapter', type=int)
    p_push = sub.add_parser('push')
    p_push.add_argument('slug')
    p_push.add_argument('chapter', type=int)
    p_next = sub.add_parser('next')
    p_next.add_argument('--count', type=int, default=10)

    args = ap.parse_args()
    try:
        if args.cmd == 'status':
            cmd_status()
        elif args.cmd == 'pull':
            cmd_pull(args.slug, args.chapter)
        elif args.cmd == 'push':
            cmd_push(args.slug, args.chapter)
        elif args.cmd == 'next':
            cmd_next(args.count)
    except (TranslateError, Exception) as exc:
        if isinstance(exc, TranslateError):
            print(f'translate: {exc}', file=sys.stderr)
            return 1
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
