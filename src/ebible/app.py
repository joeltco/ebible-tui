"""Batch 1 bootable placeholder; reader screens and custom themes arrive in batch 2."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Footer, Header, Static

from ebible.core.models import VerseRef
from ebible.core.refs import format_reference


class EBibleApp(App[None], inherit_bindings=False):
    TITLE = 'eBible'
    SUB_TITLE = 'Ethiopian Orthodox Tewahedo Bible'
    CSS_PATH = 'ui/styles/app.tcss'
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding('q', 'quit', 'Quit'),
        Binding('escape', 'quit', 'Back', show=False),
    ]

    def __init__(self, reference: VerseRef | None = None, theme_name: str | None = None) -> None:
        super().__init__()
        self.reference = reference or VerseRef(1)
        if theme_name is not None:
            if theme_name not in self.available_themes:
                raise ValueError(f'Unknown theme: {theme_name}')
            self.theme = theme_name

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id='placeholder'):
            yield Static('eBible 2 · መጽሐፍ ቅዱስ', id='heading', markup=False)
            yield Static(
                '81 books · Amharic and English\n\nFoundation ready.\nThe reader interface arrives in batch 2.',
                markup=False,
            )
            yield Static(format_reference(self.reference, 'both'), id='reference', markup=False)
            yield Button('Quit', id='quit', variant='primary')
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'quit':
            self.exit()
