"""Book and chapter picker.

Two steps rather than one long list: 81 books scroll past quickly, but a book
with 150 chapters does not. Picking the book first keeps both lists short enough
to thumb through on a phone.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ebible.data.models import Book
from ebible.data.store import Store
from ebible.ui import theme


class BookPicker(ModalScreen[tuple[int, int] | None]):
    """Returns (book_id, chapter), or None if dismissed."""

    BINDINGS = [
        Binding('escape', 'back', 'Back'),
    ]

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self._book: Book | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id='picker'):
            yield Label('Books', id='picker-title')
            yield OptionList(id='picker-list')

    def on_mount(self) -> None:
        self._show_books()

    # ------------------------------------------------------------ steps

    def _show_books(self) -> None:
        self._book = None
        self.query_one('#picker-title', Label).update('Books')
        opts: list[Option] = []
        for section, books in self.store.books_by_section():
            # A disabled Option is the section heading: it renders inline and is
            # skipped by keyboard navigation, so it reads as a divider without
            # ever becoming a selectable target.
            opts.append(Option(Text(f'── {section} ', style=theme.NUM), disabled=True))
            for b in books:
                label = Text(f'{b.name_am}   ', style=theme.AM)
                label.append(b.name_en, style=theme.EN)
                if b.deuterocanonical:
                    label.append('  ·dc', style=theme.MISSING)
                opts.append(Option(label, id=f'b{b.id}'))
        lst = self.query_one('#picker-list', OptionList)
        lst.clear_options()
        lst.add_options(opts)
        lst.focus()

    def _show_chapters(self, book: Book) -> None:
        self._book = book
        self.query_one('#picker-title', Label).update(f'{book.name_am} — chapter')
        lst = self.query_one('#picker-list', OptionList)
        lst.clear_options()
        lst.add_options(
            [Option(str(c), id=f'c{c}') for c in range(1, book.chapter_count + 1)]
        )
        lst.focus()

    # ------------------------------------------------------------ events

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id or ''
        if oid.startswith('b'):
            self._show_chapters(self.store.book(int(oid[1:])))
        elif oid.startswith('c') and self._book is not None:
            self.dismiss((self._book.id, int(oid[1:])))

    def action_back(self) -> None:
        # Escape steps back to the book list before it closes the picker.
        if self._book is not None:
            self._show_books()
        else:
            self.dismiss(None)
