"""Every reader binding, plus touch routes to all destinations."""

from textual.app import ComposeResult
from textual.widgets import Button, Static

from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import PhoneScroll

HELP_TEXT = """READING
↑ / k   Previous verse
↓ / j   Next verse
← / h   Previous chapter
→ / l   Next chapter
Enter   Actions for selected verse
Tap a verse to select it and open its actions.
Scroll with a swipe or the mouse wheel.

FIND YOUR PLACE
b   Books and chapters
/   Search scripture
g   Go to a reference
m   Bookmarks
v   Highlights
n   Notes
t   History
p   Reading plans
s   Settings
?   This guide
q   Quit (reader only)

EVERYWHERE
Esc   Back / close menu
Tab   Move between controls
↑ ↓   Move through a list or menu
Enter / Space   Activate a control
Type normally in search and note fields.
Backspace / Delete   Edit text
Notes offer touch Undo / Redo and Save.
Unsaved notes ask before discarding.

YOUR TEXT
◆ Bookmark   ✎ Note   ◇ Machine translation
Dim English without ◇ is bundled text.
Untranslated passages always show a marker.

SEARCH
Ordinary words are safe as you type.
Prefix with = for advanced FTS5 expressions.
Example: ="LORD God"

THE ETHIOPIAN PSALTER
Psalm 151 is filed as Psalms 150:7-14.
No verses are added or renumbered.
"""


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
            yield Static(HELP_TEXT, id='help-text', markup=False)
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
