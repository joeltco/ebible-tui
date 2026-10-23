"""Immediate, atomic preferences with live theme and typography preview."""

from textual.app import ComposeResult
from textual.widgets import Input, Select, Static, Switch

from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import Choice, PhoneScroll, TextInput, ThemeChoice


class SettingsScreen(Page):
    def __init__(self) -> None:
        super().__init__()
        self._initializing = True

    def compose(self) -> ComposeResult:
        settings = self.eb.settings
        yield from self.heading('Make room for reading', 'Changes are saved as you make them')
        with PhoneScroll(id='settings-scroll', classes='page-scroll'):
            yield Static('APPEARANCE', classes='eyebrow', markup=False)
            yield Static('Theme', markup=False)
            yield ThemeChoice(
                self.app.available_themes,
                value=self.app.theme,
                id='setting-theme',
            )
            yield Static('Reading flow', markup=False)
            yield Choice(
                [('One verse at a time', 'lines'), ('Continuous paragraphs', 'paragraph')],
                value=settings.verse_flow,
                allow_blank=False,
                id='setting-verse_flow',
            )
            yield Static('Verse spacing', markup=False)
            yield Choice(
                [('Comfortable', 'comfortable'), ('Compact', 'compact')],
                value=settings.verse_spacing,
                allow_blank=False,
                id='setting-verse_spacing',
            )
            yield Static('Verse numbers', markup=False)
            yield Switch(settings.verse_numbers, id='setting-verse_numbers')
            yield Static('Book names', markup=False)
            yield Choice(
                [('አማርኛ', 'am'), ('English', 'en'), ('Both languages', 'both')],
                value=settings.book_name_language,
                allow_blank=False,
                id='setting-book_name_language',
            )
            yield Static('Maximum reading width · 20–240 columns', markup=False)
            yield TextInput(
                str(settings.text_max_width), type='integer', id='setting-text_max_width'
            )
            yield Static('', id='width-error', classes='error', markup=False)
            yield Static('TRANSLATION & TOUCH', classes='eyebrow', markup=False)
            yield Static('Live translation backend', markup=False)
            yield Choice(
                [
                    ('Automatic', 'auto'),
                    ('Claude', 'claude'),
                    ('Google · translate-shell', 'google'),
                    ('Off', 'off'),
                ],
                value=settings.translation_backend,
                allow_blank=False,
                id='setting-translation_backend',
            )
            yield Static('Vibrate when bookmarking · Termux', markup=False)
            yield Switch(settings.haptic_feedback, id='setting-haptic_feedback')
            yield Static(
                'Enter or tap a verse to translate. Translations last only for this session.',
                classes='page-footnote',
                markup=False,
            )

    def on_mount(self) -> None:
        self.call_after_refresh(self.finish_loading)

    def finish_loading(self) -> None:
        self._initializing = False

    async def on_select_changed(self, event: Select.Changed) -> None:
        if not self._initializing and event.select.id and event.value is not Select.NULL:
            await self.eb.update_setting(event.select.id.removeprefix('setting-'), event.value)

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        if not self._initializing and event.switch.id:
            await self.eb.update_setting(event.switch.id.removeprefix('setting-'), event.value)

    async def on_input_changed(self, event: Input.Changed) -> None:
        if self._initializing:
            return
        try:
            width = int(event.value)
            if not 20 <= width <= 240:
                raise ValueError
        except ValueError:
            self.query_one('#width-error', Static).update('Choose a width from 20 to 240.')
            return
        self.query_one('#width-error', Static).update('')
        await self.eb.update_setting('text_max_width', width)
