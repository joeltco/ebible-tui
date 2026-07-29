#!/usr/bin/env python3
"""Compile assets/Bible81/*.txt into the shipped SQLite store.

Source layout:  assets/Bible81/<id> - <amharic name>/<seq> - <chapter>.txt
Verse lines:    "<n>. <text>"  -- audited clean across all 39,169 lines, so the
                parser is strict: anything unexpected aborts the build rather
                than being silently skipped.

Usage:  python tools/build_db.py [--assets DIR] [--out FILE]
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ebible import canon  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = REPO / 'assets' / 'Bible81'
DEFAULT_OUT = REPO / 'src' / 'ebible' / 'data' / 'bible.db'
SCHEMA = REPO / 'src' / 'ebible' / 'data' / 'schema.sql'

DIR_RE = re.compile(r'^(\d+)\s*-\s*(.+)$')
CHAPTER_RE = re.compile(r'^\d+\s*-\s*(\d+)$')
VERSE_RE = re.compile(r'^(\d+)[.:]\s*(.*)$')

# The source was scraped from a page with superscript footnote markers, and those
# marker digits were inlined into the words they annotated -- 'አቤል2ን' (Abel),
# 'አብርሃም26' (Abraham). The values ascend monotonically through the canon, which
# is what identifies them as markers rather than content: Amharic writes numbers
# either as Ge'ez numerals or spelled out, never as ASCII digits welded mid-word.
FOOTNOTE_DIGITS_RE = re.compile(r'(?<=[ሀ-፿])\d+')


def clean_verse(text: str) -> str:
    """Strip scrape artifacts. Assets stay pristine; this runs at build time."""
    return FOOTNOTE_DIGITS_RE.sub('', text)


class BuildError(RuntimeError):
    pass


def book_dirs(assets: Path) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for d in assets.iterdir():
        if not d.is_dir():
            continue
        m = DIR_RE.match(d.name)
        if not m:
            raise BuildError(f'unparseable book directory: {d.name}')
        out[int(m.group(1))] = d
    return out


def chapter_files(book_dir: Path) -> list[tuple[int, Path]]:
    """Return (chapter_number, path), ordered by chapter."""
    found: list[tuple[int, Path]] = []
    for p in book_dir.glob('*.txt'):
        m = CHAPTER_RE.match(p.stem)
        if not m:
            raise BuildError(f'unparseable chapter file: {p}')
        found.append((int(m.group(1)), p))
    found.sort()
    return found


def parse_verses(path: Path) -> list[tuple[int, str]]:
    verses: list[tuple[int, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = VERSE_RE.match(line)
        if not m:
            raise BuildError(f'{path}:{lineno}: not a verse line: {line[:60]!r}')
        verses.append((int(m.group(1)), clean_verse(m.group(2).strip())))
    return verses


def build(assets: Path, out: Path) -> None:
    if not assets.is_dir():
        raise BuildError(f'assets directory not found: {assets}')

    dirs = book_dirs(assets)
    unknown = sorted(set(dirs) - {b.id for b in canon.BOOKS})
    absent = sorted({b.id for b in canon.BOOKS} - set(dirs))
    if unknown or absent:
        raise BuildError(f'canon/asset mismatch: on-disk-only={unknown} canon-only={absent}')

    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    db = sqlite3.connect(out)
    db.executescript(SCHEMA.read_text(encoding='utf-8'))

    total_verses = 0
    total_chapters = 0
    verse_id = 0

    for book in canon.BOOKS:
        chapters = chapter_files(dirs[book.id])
        if not chapters:
            raise BuildError(f'{book.name_en}: no chapter files')

        expected = list(range(1, len(chapters) + 1))
        if [c for c, _ in chapters] != expected:
            raise BuildError(
                f'{book.name_en}: chapter numbers not contiguous 1..{len(chapters)}; '
                f'got {[c for c, _ in chapters][:12]}'
            )

        db.execute(
            'INSERT INTO book (id, slug, name_am, name_en, section, chapter_count,'
            ' deuterocanonical) VALUES (?,?,?,?,?,?,?)',
            (book.id, book.slug, book.name_am, book.name_en, str(book.section),
             len(chapters), int(book.deuterocanonical)),
        )

        for chapter_no, path in chapters:
            verses = parse_verses(path)
            if not verses:
                raise BuildError(f'{book.name_en} {chapter_no}: no verses in {path}')
            rows = []
            for verse_no, text in verses:
                verse_id += 1
                rows.append((verse_id, book.id, chapter_no, verse_no, text))
            db.executemany(
                'INSERT INTO verse (id, book_id, chapter, verse, text_am)'
                ' VALUES (?,?,?,?,?)',
                rows,
            )
            total_verses += len(rows)
            total_chapters += 1

    db.executemany(
        'INSERT INTO meta (key, value) VALUES (?,?)',
        [
            ('schema_version', '1'),
            ('book_count', str(len(canon.BOOKS))),
            ('chapter_count', str(total_chapters)),
            ('verse_count', str(total_verses)),
            ('translated_count', '0'),
        ],
    )
    db.commit()
    db.execute('VACUUM')
    db.close()

    size_mb = out.stat().st_size / 1_048_576
    print(f'books    {len(canon.BOOKS)}')
    print(f'chapters {total_chapters}')
    print(f'verses   {total_verses}')
    print(f'output   {out}  ({size_mb:.1f} MB)')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assets', type=Path, default=DEFAULT_ASSETS)
    ap.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    try:
        build(args.assets, args.out)
    except BuildError as exc:
        print(f'build failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
