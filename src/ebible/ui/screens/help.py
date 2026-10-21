"""Every reader binding, plus touch routes to all destinations."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import PhoneScroll

KEY_GROUPS = (
    (
        'READING',
        (
            ('↑ / k', 'Previous verse'),
            ('↓ / j', 'Next verse'),
            ('← / h', 'Previous chapter'),
            ('→ / l', 'Next chapter'),
            ('Enter', 'Actions for selected verse'),
        ),
        'Tap a verse for its actions. Scroll with a swipe or mouse wheel.',
    ),
    (
        'FIND YOUR PLACE',
        (
            ('b', 'Books and chapters'),
            ('/', 'Search scripture'),
            ('g', 'Go to a reference'),
            ('m', 'Bookmarks'),
            ('v', 'Highlights'),
            ('n', 'Notes'),
            ('t', 'History'),
            ('p', 'Reading plans'),
            ('s', 'Settings'),
            ('?', 'This guide'),
            ('q', 'Quit · reader only'),
        ),
        '',
    ),
    (
        'EVERYWHERE',
        (
            ('Esc', 'Back / close menu'),
            ('Tab', 'Next control'),
            ('↑ / ↓', 'Move through a list'),
            ('Enter / Space', 'Activate a control'),
            ('Backspace', 'Delete preceding text'),
            ('Delete', 'Delete following text'),
        ),
        'Type normally in search and notes. Notes offer touch Undo, Redo and Save. Unsaved changes ask before discarding.',
    ),
)

REFERENCE_GROUPS = (
    (
        'YOUR TEXT',
        '◆ Bookmark   ✎ Note\n◇ Machine translation\nDim English without ◇ is bundled text. Untranslated passages have a notice or placeholder.',
    ),
    (
        'SEARCH',
        'Ordinary words are safe as you type. Prefix with = for advanced FTS5 expressions.\nExample: ="LORD God"',
    ),
    (
        'THE ETHIOPIAN PSALTER',
        'Psalm 151 is filed as Psalms 150:7-14. No verses are added or renumbered.',
    ),
)


class KeyRow(Horizontal):
    def __init__(self, key: str, description: str) -> None:
        super().__init__(classes='key-row')
        self.key, self.description = key, description

    def compose(self) -> ComposeResult:
        yield Static(self.key, classes='key-chip', markup=False)
        yield Static(self.description, classes='key-description', markup=False)


class HelpScreen(Page):
    def compose(self) -> ComposeResult:
        yield from self.heading(
            'A companion to your reading', 'Every action is also available by touch'
        )
        with PhoneScroll(classes='page-scroll'):
            yield Static('YOUR LIBRARY', classes='eyebrow', markup=False)
            for name, label in [
                ('books', 'Books & chapters'),
                ('search', 'Search scripture'),
                ('bookmarks', 'Bookmarks'),
                ('highlights', 'Highlights'),
                ('notes', 'Notes'),
                ('history', 'Reading history'),
                ('plans', 'Reading plans'),
                ('settings', 'Settings'),
            ]:
                yield Button(label, id=f'help-{name}', classes='help-link')
            yield Button('Go to reference', id='help-goto', classes='help-link')
            with Vertical(id='help-text'):
                for title, rows, note in KEY_GROUPS:
                    yield Static(title, classes='eyebrow', markup=False)
                    for key, description in rows:
                        yield KeyRow(key, description)
                    if note:
                        yield Static(note, classes='help-note', markup=False)
                for title, note in REFERENCE_GROUPS:
                    yield Static(title, classes='eyebrow', markup=False)
                    yield Static(note, classes='help-note', markup=False)
            yield Button('Quit eBible', id='help-quit')

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        name = event.button.id or ''
        if name == 'help-quit':
            event.stop()
            self.app.exit()
        elif name == 'help-goto':
            event.stop()
            await self.eb.reader.action_goto()
        elif name.startswith('help-'):
            event.stop()
            await self.eb.open_page(name.removeprefix('help-'))
        else:
            await super().on_button_pressed(event)
