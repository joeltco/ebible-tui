"""Shared personal-collection list with explicit deletion confirmation."""

import asyncio
from collections.abc import Callable
from typing import Literal

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from ebible.core.labels import count_label
from ebible.core.models import Bookmark, Highlight, HistoryEntry, Note
from ebible.core.refs import format_reference
from ebible.ui.screens.base import Confirm, Page
from ebible.ui.widgets.controls import PassageList

CollectionKind = Literal['bookmarks', 'highlights', 'notes', 'history']
Entry = Bookmark | Highlight | Note | HistoryEntry


COLLECTION_LABELS = {
    'bookmarks': ('bookmark', 'bookmarks'),
    'highlights': ('highlight', 'highlights'),
    'notes': ('note', 'notes'),
    'history': ('history entry', 'history entries'),
}


class CollectionScreen(Page):
    kind: CollectionKind = 'bookmarks'

    def __init__(self) -> None:
        super().__init__()
        self.entries: tuple[Entry, ...] = ()

    def compose(self) -> ComposeResult:
        yield from self.heading(
            'Your reading', 'Passages kept, thoughts gathered, places revisited'
        )
        with Horizontal(classes='collection-tabs'):
            for kind, label in [
                ('bookmarks', 'Marks'),
                ('highlights', 'Colours'),
                ('notes', 'Notes'),
                ('history', 'History'),
            ]:
                yield Button(
                    label, id=f'tab-{kind}', variant='primary' if self.kind == kind else 'default'
                )
        yield Static(self.kind.title(), classes='eyebrow', markup=False)
        yield Static('', id='collection-message', classes='page-subtitle', markup=False)
        yield PassageList(id='collection-list')
        with Horizontal(classes='button-row'):
            yield Button('Open', id='open-entry', variant='primary')
            if self.kind == 'notes':
                yield Button('Edit note', id='edit-entry')
            yield Button('Delete', id='delete-entry')

    async def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, lambda _: self.refresh_colours())
        await self.reload()

    def refresh_colours(self) -> None:
        listing = self.query_one(OptionList)
        selected, scroll = listing.highlighted, listing.scroll_y
        self.show_entries()
        listing.highlighted = selected
        listing.scroll_to(y=scroll, animate=False)

    async def reload(self) -> None:
        loaders: dict[str, Callable[[], tuple[Entry, ...]]] = {
            'bookmarks': self.eb.userdata.bookmarks,
            'highlights': self.eb.userdata.highlights,
            'notes': self.eb.userdata.notes,
            'history': self.eb.userdata.history,
        }
        self.entries = await asyncio.to_thread(loaders[self.kind])
        self.show_entries()

    def show_entries(self) -> None:
        options = []
        for index, entry in enumerate(self.entries):
            text = Text(format_reference(entry.ref) + '\n', style='bold')
            detail = (
                entry.text.replace('\n', ' ')[:180]
                if isinstance(entry, Note)
                else entry.colour.title() + ' highlight'
                if isinstance(entry, Highlight)
                else entry.visited_at.astimezone().strftime('%d %b · %H:%M')
                if isinstance(entry, HistoryEntry)
                else entry.created_at.astimezone().strftime('Kept on %d %b %Y')
            )
            text.append(detail + '\n', style=self.app.get_css_variables()['secondary'])
            options.append(Option(text, id=f'entry-{index}'))
        self.query_one(OptionList).clear_options().add_options(options)
        self.query_one('#collection-message', Static).update(
            count_label(len(options), *COLLECTION_LABELS[self.kind])
            if options
            else f'No {self.kind} yet. Keep a passage from its verse menu.'
            if self.kind != 'history'
            else 'Your reading history will appear here.'
        )
        for button in self.query('.button-row Button'):
            button.disabled = not bool(options)
        if options:
            self.query_one(OptionList).highlighted = 0

    def selected_entry(self) -> Entry | None:
        index = self.query_one(OptionList).highlighted
        return self.entries[index] if index is not None and index < len(self.entries) else None

    async def open_selected(self) -> None:
        entry = self.selected_entry()
        if entry:
            await self.eb.navigate(entry.ref)

    async def on_option_list_option_selected(self) -> None:
        await self.open_selected()

    async def delete_selected(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            return

        async def remove() -> None:
            if isinstance(entry, HistoryEntry):
                await asyncio.to_thread(self.eb.userdata.delete_history, entry.id)
            else:
                delete = {
                    'bookmarks': self.eb.userdata.delete_bookmark,
                    'highlights': self.eb.userdata.delete_highlight,
                    'notes': self.eb.userdata.delete_note,
                }[self.kind]
                await asyncio.to_thread(delete, entry.ref)
            await self.reload()
            await self.eb.reader.refresh_reading()

        await self.app.push_screen(
            Confirm(
                f'Delete this {COLLECTION_LABELS[self.kind][0]} at {format_reference(entry.ref)}?',
                remove,
            )
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = event.button.id or ''
        if name.startswith('tab-'):
            event.stop()
            from ebible.ui.screens.bookmarks import BookmarksScreen, HighlightsScreen
            from ebible.ui.screens.history import HistoryScreen
            from ebible.ui.screens.notes import NotesScreen

            pages = {
                'bookmarks': BookmarksScreen,
                'highlights': HighlightsScreen,
                'notes': NotesScreen,
                'history': HistoryScreen,
            }
            self.app.switch_screen(pages[name.removeprefix('tab-')]())
        elif name == 'open-entry':
            event.stop()
            await self.open_selected()
        elif name == 'delete-entry':
            event.stop()
            await self.delete_selected()
        elif name == 'edit-entry':
            event.stop()
            entry = self.selected_entry()
            if entry:
                from ebible.ui.screens.notes import NoteEditor

                await self.app.push_screen(NoteEditor(entry.ref))
        else:
            await super().on_button_pressed(event)

    async def on_screen_resume(self) -> None:
        if self.is_mounted and self.query('#collection-list'):
            await self.reload()
