"""A compact touch menu for the selected verse."""

import asyncio
from typing import Literal, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ebible.core.models import HIGHLIGHT_COLOURS, HighlightColour, VerseRef
from ebible.core.refs import format_reference
from ebible.ui.screens.base import Sheet
from ebible.ui.themes import highlight_colour
from ebible.ui.widgets.controls import PhoneScroll


class VerseActions(Sheet):
    def __init__(self, ref: VerseRef) -> None:
        super().__init__()
        self.ref = ref

    def compose(self) -> ComposeResult:
        with PhoneScroll(classes='sheet', id='verse-menu'):
            yield Static('KEEP · REFLECT · SHARE', classes='eyebrow', markup=False)
            yield Static(format_reference(self.ref, 'both'), classes='sheet-title', markup=False)
            with Horizontal(classes='button-row'):
                yield Button('Bookmark', id='bookmark-verse')
                yield Button('Write note', id='note-verse')
            yield Static('HIGHLIGHT', classes='eyebrow', markup=False)
            with Horizontal(classes='swatches'):
                for colour in HIGHLIGHT_COLOURS:
                    label = Text('●', style=highlight_colour(colour, self.app.current_theme.dark))
                    yield Button(label, id=f'highlight-{colour}', tooltip=colour.title())
                yield Button('×', id='highlight-clear', tooltip='Remove highlight')
            yield Static('COPY WITH REFERENCE', classes='eyebrow', markup=False)
            with Horizontal(classes='button-row'):
                yield Button('አማርኛ', id='copy-am')
                yield Button('English', id='copy-en')
                yield Button('Both', id='copy-both')
            yield Button('Translate this chapter', id='translate-verse')
            yield Static('Live English is marked ◇ Machine.', classes='muted', markup=False)
            yield Button('Back to reading', id='close-actions')

    async def on_mount(self) -> None:
        await self.update_bookmark_label()

    async def update_bookmark_label(self) -> None:
        marked = any(b.ref == self.ref for b in await asyncio.to_thread(self.eb.userdata.bookmarks))
        self.query_one('#bookmark-verse', Button).label = '◆ Bookmarked' if marked else 'Bookmark'
        colours = await asyncio.to_thread(self.eb.userdata.highlights)
        selected = next((h.colour for h in colours if h.ref == self.ref), None)
        for colour in HIGHLIGHT_COLOURS:
            self.query_one(f'#highlight-{colour}', Button).variant = (
                'primary' if colour == selected else 'default'
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        name = event.button.id or ''
        if name == 'bookmark-verse':
            await self.eb.toggle_bookmark(self.ref)
            await self.update_bookmark_label()
        elif name.startswith('highlight-'):
            colour = name.removeprefix('highlight-')
            await self.eb.set_highlight(
                self.ref, None if colour == 'clear' else cast(HighlightColour, colour)
            )
            await self.update_bookmark_label()
        elif name == 'note-verse':
            from ebible.ui.screens.notes import NoteEditor

            await self.app.push_screen(NoteEditor(self.ref))
        elif name.startswith('copy-'):
            await self.eb.copy_verse(
                self.ref, cast(Literal['am', 'en', 'both'], name.removeprefix('copy-'))
            )
        elif name == 'translate-verse':
            self.dismiss()
            self.eb.translate_current()
        else:
            self.dismiss()
