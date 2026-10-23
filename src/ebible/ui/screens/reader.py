"""The reading surface: chapter navigation, verse cursor, and touch routes."""

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ebible.canon import BY_ID
from ebible.core.labels import count_label
from ebible.core.models import Chapter, HighlightColour, VerseRef
from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import PhoneScroll
from ebible.ui.widgets.header import HeaderBar, StatusBar
from ebible.ui.widgets.verse_view import VersePicked, VerseView


class ReaderScreen(Page):
    BINDINGS = [
        Binding('q', 'quit_reader', 'Quit'),
        Binding('down,j', 'move(1)', 'Next verse', show=False),
        Binding('up,k', 'move(-1)', 'Previous verse', show=False),
        Binding('right,l', 'chapter(1)', 'Next chapter', show=False),
        Binding('left,h', 'chapter(-1)', 'Previous chapter', show=False),
        Binding('enter', 'translate', 'Translate'),
        Binding('a', 'verse_actions', 'Verse'),
        Binding('b', "page('books')", 'Books'),
        Binding('/', "page('search')", 'Search'),
        Binding('g', 'goto', 'Go to'),
        Binding('m', "page('bookmarks')", 'Bookmarks'),
        Binding('v', "page('highlights')", 'Highlights'),
        Binding('n', "page('notes')", 'Notes'),
        Binding('t', "page('history')", 'History'),
        Binding('p', "page('plans')", 'Plans'),
        Binding('s', "page('settings')", 'Settings'),
        Binding('?', "page('help')", 'Help'),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.chapter_data: Chapter | None = None

    def compose(self) -> ComposeResult:
        self.set_class(self.app.size.width < 80, 'compact-chrome')
        yield Static('✣  e B i b l e', id='brand', markup=False)
        yield HeaderBar()
        with Horizontal(id='reader-nav'):
            yield Button('Books', id='books')
            yield Button('Search', id='search')
            yield Button('Go to', id='goto')
            yield Button('Saved', id='bookmarks')
        with PhoneScroll(id='reading-scroll', can_focus=False):
            yield VerseView()
        with Horizontal(id='reader-tools'):
            yield Button('Verse', id='verse-actions')
            yield Button('Plans', id='plans')
            yield Button('Settings', id='settings')
            yield Button('More', id='help')
        yield StatusBar(id='reading-status', markup=False)

    def _read(self) -> tuple[Chapter, set[int], dict[int, HighlightColour], set[int]]:
        ref = self.eb.reference
        chapter = self.eb.scripture.chapter(ref.book_id, ref.chapter)

        def here(position: VerseRef) -> bool:
            return (position.book_id, position.chapter) == (ref.book_id, ref.chapter)

        return (
            chapter,
            {b.ref.verse for b in self.eb.userdata.bookmarks() if here(b.ref)},
            {h.ref.verse: h.colour for h in self.eb.userdata.highlights() if here(h.ref)},
            {n.ref.verse for n in self.eb.userdata.notes() if here(n.ref)},
        )

    async def load_chapter(self) -> None:
        await self.refresh_reading()
        await asyncio.to_thread(self.eb.userdata.record_position, self.eb.reference)
        self.set_focus(None)

    async def refresh_reading(self) -> None:
        chapter, bookmarks, highlights, notes = await asyncio.to_thread(self._read)
        self.chapter_data = chapter
        name = {
            'am': chapter.book.name_am,
            'en': chapter.book.name_en,
            'both': chapter.book.display,
        }[self.eb.settings.book_name_language]
        self.query_one(HeaderBar).show_title(
            name, chapter.number, self.eb.chapter_counts[chapter.book.id]
        )
        await self.query_one(VerseView).show_chapter(chapter, bookmarks, highlights, notes)
        self.query_one('#previous-chapter', Button).disabled = (
            chapter.book.id == 1 and chapter.number == 1
        )
        self.query_one('#next-chapter', Button).disabled = (
            chapter.book.id == 81 and chapter.number == self.eb.chapter_counts[81]
        )
        self.update_status()

    def update_status(self, message: str | None = None) -> None:
        if self.chapter_data is None:
            return
        ref = self.eb.reference
        status = (
            message
            or f'{BY_ID[ref.book_id].name_en} {ref.chapter}:{ref.verse}  ·  {count_label(len(self.chapter_data), "verse")}  ·  ? Help'
        )
        self.query_one(StatusBar).update(status)

    async def select_verse(self, number: int) -> None:
        if self.chapter_data is None or number not in {v.verse for v in self.chapter_data}:
            return
        old = self.eb.reference
        self.eb.reference = VerseRef(old.book_id, old.chapter, number)
        self.query_one(VerseView).select(number)
        self.update_status()
        await asyncio.to_thread(self.eb.userdata.record_position, self.eb.reference)

    async def action_move(self, direction: int) -> None:
        if self.chapter_data is None:
            return
        numbers = [v.verse for v in self.chapter_data]
        index = numbers.index(self.eb.reference.verse)
        await self.select_verse(numbers[max(0, min(index + direction, len(numbers) - 1))])

    async def action_chapter(self, direction: int) -> None:
        ref = self.eb.reference
        book, chapter = ref.book_id, ref.chapter + direction
        if chapter < 1:
            if book == 1:
                return
            book -= 1
            chapter = self.eb.chapter_counts[book]
        elif chapter > self.eb.chapter_counts[book]:
            if book == 81:
                return
            book += 1
            chapter = 1
        await self.eb.navigate(VerseRef(book, chapter))

    async def action_page(self, name: str) -> None:
        await self.eb.open_page(name)

    async def action_goto(self) -> None:
        from ebible.ui.screens.goto import GoTo

        await self.app.push_screen(GoTo())

    async def action_translate(self) -> None:
        await self.eb.toggle_translation(self.eb.reference)

    async def action_verse_actions(self) -> None:
        from ebible.ui.screens.verse_actions import VerseActions

        await self.app.push_screen(VerseActions(self.eb.reference))

    async def on_verse_picked(self, event: VersePicked) -> None:
        event.stop()
        await self.select_verse(event.number)
        await self.action_translate()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        name = event.button.id
        if name == 'previous-chapter':
            await self.action_chapter(-1)
        elif name == 'next-chapter':
            await self.action_chapter(1)
        elif name == 'goto':
            await self.action_goto()
        elif name == 'verse-actions':
            await self.action_verse_actions()
        elif name is not None:
            await self.action_page(name)

    def action_quit_reader(self) -> None:
        self.app.exit()

    async def action_back(self) -> None:
        self.set_focus(None)

    def on_screen_resume(self) -> None:
        self.call_after_refresh(self.set_focus, None)

    async def on_resize(self) -> None:
        self.set_class(self.app.size.width < 80, 'compact-chrome')
        self.query_one(HeaderBar).call_after_refresh(self.query_one(HeaderBar).refresh_title)
        if self.chapter_data is not None:
            await self.query_one(VerseView).rebuild()
