from __future__ import annotations

from pathlib import Path

from ebible_tui.core.bible.assets import resolve_bible81
from ebible_tui.core.bible.refs import ChapterRef

BIBLE_DIR = resolve_bible81()


def list_books() -> list[str]:
    if not BIBLE_DIR.exists():
        return []

    def key(p: Path) -> tuple[int, str]:
        try:
            num = int(p.name.split(' ', 1)[0])
        except Exception:
            num = 9999
        return (num, p.name)

    return [p.name for p in sorted((p for p in BIBLE_DIR.iterdir() if p.is_dir()), key=key)]


def list_chapters(book_name: str) -> list[ChapterRef]:
    book_dir = BIBLE_DIR / book_name
    if not book_dir.is_dir():
        return []
    chapters: list[ChapterRef] = []
    for p in sorted(book_dir.glob('*.txt')):
        try:
            num = int(p.stem.split(' - ', 1)[1])
        except Exception:
            try:
                num = int(p.stem.split(' - ', 1)[0])
            except Exception:
                continue
        chapters.append(ChapterRef(book=book_name, chapter_num=num, path=p))
    chapters.sort(key=lambda c: c.chapter_num)
    return chapters


def read_chapter(ref: ChapterRef) -> str:
    text = ref.path.read_text(encoding='utf-8', errors='replace')
    return text.strip()
