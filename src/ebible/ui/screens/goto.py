"""Reference prompt with source-valid navigation and inline errors."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Static

from ebible.ui.screens.base import Sheet
from ebible.ui.widgets.controls import PhoneScroll, TextInput


class GoTo(Sheet):
    def compose(self) -> ComposeResult:
        with PhoneScroll(classes='sheet', id='goto-dialog'):
            yield Static('OPEN A PASSAGE', classes='eyebrow', markup=False)
            yield Static('Where would you like to read?', classes='sheet-title', markup=False)
            yield TextInput(placeholder='john 3:16 · ዘፍ 1', id='reference-input')
            yield Static('', id='reference-error', classes='error', markup=False)
            with Horizontal(classes='button-row'):
                yield Button('Cancel', id='cancel')
                yield Button('Open', id='open-reference', variant='primary')

    def on_mount(self) -> None:
        self.query_one(TextInput).focus()

    async def submit(self) -> None:
        if not await self.eb.go_to(self.query_one(TextInput).value):
            self.query_one('#reference-error', Static).update(self.eb.last_message)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.submit()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == 'cancel':
            self.dismiss()
        else:
            await self.submit()
