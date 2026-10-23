"""A compact touch menu for the selected verse."""

import asyncio
from typing import Literal, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
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
                if self.ref in self.eb.translations:
                    yield Button('With translation', id='copy-both')
            yield Button('Back to reading', id='close-actions')

    async def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, lambda _: self.refresh_colours())
        await self.update_bookmark_label()

    def refresh_colours(self) -> None:
        for colour in HIGHLIGHT_COLOURS:
            # Content equality compares letters only; explicitly replace and invalidate.
            label = Text('●', style=highlight_colour(colour, self.app.current_theme.dark))
            button = self.query_one(f'#highlight-{colour}', Button)
            button.set_reactive(Button.label, Content.from_rich_text(label))
            button.mutate_reactive(Button.label)

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
                self.ref, cast(Literal['am', 'both'], name.removeprefix('copy-'))
            )
        else:
            self.dismiss()
