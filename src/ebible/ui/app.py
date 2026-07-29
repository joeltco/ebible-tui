"""The ebible reader application."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header

from ebible.config import Settings
from ebible.data.store import Store
from ebible.ui.screens.books import BookPicker
from ebible.ui.screens.search import SearchScreen
from ebible.ui.widgets.verse_pane import VersePane

CSS_PATH = 'ebible.tcss'


class EbibleApp(App[None]):
    """Amharic / English Bible reader."""

    CSS_PATH = CSS_PATH
    TITLE = 'ebible'

    BINDINGS = [
        Binding('b', 'books', 'Books'),
        Binding('slash', 'search', 'Search'),
        Binding('t', 'toggle_layout', 'Layout'),
        Binding('n,space', 'next_chapter', 'Next'),
        Binding('p', 'prev_chapter', 'Prev'),
        Binding('v', 'toggle_numbers', 'Numbers', show=False),
        Binding('q', 'quit', 'Quit'),
    ]

    def __init__(self, store: Store | None = None) -> None:
        super().__init__()
        self.store = store or Store()
        self.settings = Settings.load()

    # ------------------------------------------------------------ lifecycle

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id='reader'):
            yield VersePane()
        yield Footer()

    def on_mount(self) -> None:
        # A settings file can outlive the database it referenced; fall back to
        # Genesis 1 rather than failing to open.
        try:
            self.store.book(self.settings.book_id)
        except Exception:
            self.settings.book_id, self.settings.chapter = 1, 1
        self._load(self.settings.book_id, self.settings.chapter)

    def on_unmount(self) -> None:
        self.settings.save()
        self.store.close()

    # ------------------------------------------------------------ loading

    def _load(self, book_id: int, chapter: int) -> None:
        book = self.store.book(book_id)
        chapter = max(1, min(chapter, book.chapter_count))
        verses = self.store.chapter(book_id, chapter)

        self.settings.book_id = book_id
        self.settings.chapter = chapter

        pane = self.query_one(VersePane)
        pane.show(book, chapter, verses, self.settings.layout, self.settings.verse_numbers)

        self.sub_title = f'{book.name_am}  {chapter} / {book.chapter_count}'

    # ------------------------------------------------------------ actions

    def action_next_chapter(self) -> None:
        nxt = self.store.next_chapter(self.settings.book_id, self.settings.chapter)
        if nxt is None:
            self.notify('End of the canon.', severity='information')
            return
        self._load(*nxt)

    def action_prev_chapter(self) -> None:
        prev = self.store.prev_chapter(self.settings.book_id, self.settings.chapter)
        if prev is None:
            self.notify('Start of the canon.', severity='information')
            return
        self._load(*prev)

    def action_toggle_layout(self) -> None:
        self.settings.layout = self.settings.layout.next()
        pane = self.query_one(VersePane)
        pane.set_layout(self.settings.layout)

        effective = pane.effective_layout
        if effective is not self.settings.layout:
            # Tell the truth about why the screen doesn't match the request.
            self.notify(
                f'{self.settings.layout} — showing {effective}, screen too narrow',
                severity='warning',
            )
        else:
            self.notify(str(self.settings.layout).capitalize())

    def action_toggle_numbers(self) -> None:
        self.settings.verse_numbers = not self.settings.verse_numbers
        self._load(self.settings.book_id, self.settings.chapter)

    def action_books(self) -> None:
        def picked(result: tuple[int, int] | None) -> None:
            if result is not None:
                self._load(*result)

        self.push_screen(BookPicker(self.store), picked)

    def action_search(self) -> None:
        def picked(result: tuple[int, int] | None) -> None:
            if result is not None:
                self._load(*result)

        self.push_screen(SearchScreen(self.store), picked)


def run() -> None:
    EbibleApp().run()
