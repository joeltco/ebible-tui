"""Ethiopian canon order with live filtering and a tappable chapter grid."""

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from ebible.canon import BOOKS, BY_ID, Section
from ebible.core.models import VerseRef
from ebible.ui.screens.base import Page
from ebible.ui.widgets.chapter_grid import ChapterGrid
from ebible.ui.widgets.controls import PassageList, PhoneScroll, TextInput


class BooksScreen(Page):
    def compose(self) -> ComposeResult:
        yield from self.heading('The library', '81 books · Ethiopian Orthodox Tewahedo canon')
        yield TextInput(placeholder='Find a book · English or አማርኛ', id='book-filter')
        yield PassageList(id='book-list')
        yield Static('Choose a book, then a chapter', classes='page-footnote', markup=False)

    def on_mount(self) -> None:
        self.filter_books('')
        self.query_one(TextInput).focus()

    def filter_books(self, query: str) -> None:
        options: list[Option] = []
        matches = [
            b for b in BOOKS if query.casefold() in f'{b.name_en} {b.name_am} {b.slug}'.casefold()
        ]
        previous_section: Section | None = None
        for book in matches:
            if book.section != previous_section:
                options.append(
                    Option(Text(book.section.value.upper(), style='bold'), disabled=True)
                )
                previous_section = book.section
            text = Text(book.name_am + '\n')
            text.append(
                f'{book.name_en}  ·  {self.eb.chapter_counts[book.id]} chapters'
                + ('  ◇' if book.deuterocanonical else ''),
                style='dim',
            )
            text.append('\n')
            options.append(Option(text, id=f'book-{book.id}'))
        listing = self.query_one(OptionList)
        listing.clear_options().add_options(options)
        listing.highlighted = next(
            (i for i, option in enumerate(options) if not option.disabled), None
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_books(event.value)

    def on_input_submitted(self) -> None:
        self.query_one(OptionList).focus()

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            await self.app.push_screen(ChaptersScreen(int(event.option_id.removeprefix('book-'))))


class ChaptersScreen(Page):
    def __init__(self, book_id: int) -> None:
        super().__init__()
        self.book_id = book_id

    def compose(self) -> ComposeResult:
        book = BY_ID[self.book_id]
        yield from self.heading(book.name_en, book.name_am)
        with PhoneScroll(classes='page-scroll'):
            yield Static('CHOOSE A CHAPTER', classes='eyebrow', markup=False)
            yield ChapterGrid(self.eb.chapter_counts[self.book_id])

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = event.button.id or ''
        if name.startswith('chapter-'):
            event.stop()
            await self.eb.navigate(VerseRef(self.book_id, int(name.removeprefix('chapter-'))))
        else:
            await super().on_button_pressed(event)
