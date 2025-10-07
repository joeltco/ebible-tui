from ebible_tui.core.bible.assets import resolve_bible81
from ebible_tui.core.bible.refs import ChapterRef


def test_chapterref_basic() -> None:
    bible_dir = resolve_bible81()
    book_dir = sorted([d for d in bible_dir.iterdir() if d.is_dir()])[0]
    chapter_file = sorted(book_dir.glob('*.txt'))[0]
    ref = ChapterRef(book=book_dir.name, chapter_num=1, path=chapter_file)
    assert ref.book
    assert ref.chapter_num >= 1
