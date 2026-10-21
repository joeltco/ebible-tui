"""Shared navigation chrome and typed access to the application."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from ebible.app import EBibleApp
from ebible.ui.widgets.controls import PhoneScroll


class Page(Screen[None], inherit_bindings=False):
    BINDINGS = [
        Binding('escape', 'back', 'Back', priority=True),
        Binding('tab', 'app.focus_next', 'Next control', show=False),
    ]

    @property
    def eb(self) -> 'EBibleApp':
        return cast('EBibleApp', self.app)

    async def action_back(self) -> None:
        self.app.pop_screen()

    def heading(self, title: str, subtitle: str) -> ComposeResult:
        with Horizontal(classes='page-header'):
            yield Button('‹ Back', id='back', classes='back-button')
            yield Static(title, classes='page-title', markup=False)
        yield Static(subtitle, classes='page-subtitle', markup=False)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'back':
            event.stop()
            await self.action_back()


class Sheet(ModalScreen[None], inherit_bindings=False):
    BINDINGS = [
        Binding('escape', 'back', 'Back', priority=True),
        Binding('tab', 'app.focus_next', 'Next control', show=False),
    ]

    @property
    def eb(self) -> 'EBibleApp':
        return cast('EBibleApp', self.app)

    def action_back(self) -> None:
        self.dismiss()


class Confirm(Sheet):
    def __init__(self, question: str, confirm: Callable[[], Awaitable[None]]) -> None:
        super().__init__()
        self.question = question
        self.confirm = confirm

    def compose(self) -> ComposeResult:
        with PhoneScroll(classes='sheet', id='confirm-dialog'):
            yield Static('PLEASE CONFIRM', classes='eyebrow', markup=False)
            yield Static(self.question, classes='sheet-title', markup=False)
            with Horizontal(classes='button-row'):
                yield Button('Cancel', id='cancel')
                yield Button('Confirm', variant='warning', id='confirm')

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == 'confirm':
            self.dismiss()
            await self.confirm()
        else:
            self.dismiss()
