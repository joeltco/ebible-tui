from ebible_tui.core import list_books, list_chapters, read_chapter


def test_assets_present_and_readable() -> None:
    books = list_books()
    assert isinstance(books, list) and books, 'Bible81 assets not found or empty'
    chapters = list_chapters(books[0])
    assert chapters, f'No chapters listed for {books[0]}'
    txt = read_chapter(chapters[0])
    assert isinstance(txt, str) and len(txt) > 0
