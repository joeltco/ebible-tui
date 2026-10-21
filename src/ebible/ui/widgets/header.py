"""A quiet book title between tappable chapter controls."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static


class HeaderBar(Horizontal):
    def compose(self) -> ComposeResult:
        yield Button('‹', id='previous-chapter', tooltip='Previous chapter · h / left')
        yield Static('', id='book-title', markup=False)
        yield Button('›', id='next-chapter', tooltip='Next chapter · l / right')


class StatusBar(Static):
    pass
