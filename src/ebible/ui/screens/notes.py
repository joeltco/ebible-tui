"""Markdown note editing with explicit save and discard protection."""

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ebible.core.models import VerseRef
from ebible.core.refs import format_reference
from ebible.ui.screens.base import Confirm, Page
from ebible.ui.screens.collection import CollectionScreen
from ebible.ui.widgets.controls import NoteArea


class NotesScreen(CollectionScreen):
    kind = 'notes'


class NoteEditor(Page):
    def __init__(self, ref: VerseRef) -> None:
        super().__init__()
        self.ref = ref
        self.original = ''
        self.loaded = False

    def compose(self) -> ComposeResult:
        yield from self.heading('A note in the margin', format_reference(self.ref, 'both'))
        yield Static(
            'Markdown supported · saved only on this device',
            id='note-hint',
            classes='page-subtitle',
            markup=False,
        )
        yield NoteArea(
            id='note-text',
            soft_wrap=True,
            show_line_numbers=False,
            tab_behavior='focus',
            placeholder='Write your note…',
        )
        with Horizontal(classes='button-row'):
            yield Button('Save note', id='save-note', variant='primary')
            yield Button('Undo', id='undo-note')
            yield Button('Redo', id='redo-note')

    async def on_mount(self) -> None:
        notes = await asyncio.to_thread(self.eb.userdata.notes)
        self.original = next((n.text for n in notes if n.ref == self.ref), '')
        self.query_one(NoteArea).load_text(self.original)
        self.loaded = True
        self.query_one(NoteArea).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = event.button.id
        if name == 'save-note':
            event.stop()
            text = self.query_one(NoteArea).text
            await asyncio.to_thread(self.eb.userdata.save_note, self.ref, text)
            self.original = text
            await self.eb.reader.refresh_reading()
            self.app.pop_screen()
            self.eb.message('Note saved')
        elif name in ('undo-note', 'redo-note'):
            event.stop()
            editor = self.query_one(NoteArea)
            editor.action_undo() if name == 'undo-note' else editor.action_redo()
        else:
            await super().on_button_pressed(event)

    async def action_back(self) -> None:
        if self.loaded and self.query_one(NoteArea).text != self.original:

            async def discard() -> None:
                self.app.pop_screen()

            await self.app.push_screen(Confirm('Discard your unsaved note changes?', discard))
        else:
            await super().action_back()
