"""Immediate, atomic preferences with live theme and typography preview."""

import asyncio
import os
import shutil

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static, Switch

from ebible.core.credentials import CredentialError, read_saved_key, remove_key, save_key
from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import Choice, PhoneScroll, SecretInput, TextInput, ThemeChoice


class SettingsScreen(Page):
    def __init__(self) -> None:
        super().__init__()
        self._initializing = True
        self._has_saved_key = False

    def compose(self) -> ComposeResult:
        settings = self.eb.settings
        yield from self.heading(
            'Make room for reading', 'Preferences save immediately · keys use Save'
        )
        with PhoneScroll(id='settings-scroll', classes='page-scroll'):
            yield Static('APPEARANCE', classes='eyebrow', markup=False)
            yield Static('Theme', markup=False)
            yield ThemeChoice(
                self.app.available_themes,
                value=self.app.theme,
                id='setting-theme',
            )
            yield Static('Title page on launch', markup=False)
            yield Switch(settings.title_page_on_launch, id='setting-title_page_on_launch')
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
            yield Static('Reduce motion', markup=False)
            yield Switch(settings.reduce_motion, id='setting-reduce_motion')
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
            with Vertical(id='key-panel'):
                yield Static('Anthropic API key', id='key-label', markup=False)
                yield Static('Checking key source…', id='key-source', classes='muted', markup=False)
                with Vertical(id='key-saved'):
                    yield Static('', id='key-mask', markup=False)
                    with Horizontal(classes='button-row'):
                        yield Button('Replace', id='key-replace')
                        yield Button('Remove', id='key-remove')
                with Vertical(id='key-editor'):
                    yield SecretInput(id='anthropic-key-input')
                    with Horizontal(classes='button-row'):
                        yield Button('Save key', id='key-save')
                        yield Button('Cancel', id='key-cancel')
                yield Static('', id='key-error', classes='error', markup=False)
            yield Static('Vibrate when bookmarking · Termux', markup=False)
            yield Switch(settings.haptic_feedback, id='setting-haptic_feedback')
            yield Static(
                'Enter or tap a verse to translate. Translations last only for this session.',
                classes='page-footnote',
                markup=False,
            )

    async def on_mount(self) -> None:
        await self.refresh_key_status(reset_editor=True)
        self.call_after_refresh(self.finish_loading)

    def finish_loading(self) -> None:
        self._initializing = False

    async def on_select_changed(self, event: Select.Changed) -> None:
        if not self._initializing and event.select.id and event.value is not Select.NULL:
            await self.eb.update_setting(event.select.id.removeprefix('setting-'), event.value)
            if event.select.id == 'setting-translation_backend':
                await self.refresh_key_status()

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        if not self._initializing and event.switch.id:
            await self.eb.update_setting(event.switch.id.removeprefix('setting-'), event.value)

    async def on_input_changed(self, event: Input.Changed) -> None:
        if self._initializing or event.input.id != 'setting-text_max_width':
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

    async def refresh_key_status(self, *, reset_editor: bool = False) -> None:
        def read_status() -> tuple[str, str, str]:
            error = ''
            try:
                saved = read_saved_key()
            except CredentialError as exc:
                saved = None
                error = str(exc)
            if os.environ.get('ANTHROPIC_API_KEY'):
                source = 'Using key from environment'
            elif saved:
                source = 'Using saved key'
            elif shutil.which('trans') and self.eb.settings.translation_backend in (
                'auto',
                'google',
            ):
                source = 'No key — using Google translate'
            else:
                source = 'No key — no backend'
            if self.eb.settings.translation_backend in ('off', 'google') and (
                saved or os.environ.get('ANTHROPIC_API_KEY')
            ):
                source += ' · ' + (
                    'translation off'
                    if self.eb.settings.translation_backend == 'off'
                    else 'Google selected'
                )
            return saved.masked if saved else '', source, error

        masked, source, error = await asyncio.to_thread(read_status)
        self._has_saved_key = bool(masked or error)
        self.query_one('#key-mask', Static).update(masked or 'Saved key unavailable')
        self.query_one('#key-source', Static).update(source)
        self.query_one('#key-error', Static).update(error)
        if reset_editor:
            self.query_one('#anthropic-key-input', SecretInput).value = ''
            self.edit_key(not self._has_saved_key)

    def edit_key(self, editing: bool) -> None:
        self.query_one('#key-saved').display = not editing
        self.query_one('#key-editor').display = editing

    async def save_api_key(self) -> None:
        entry = self.query_one('#anthropic-key-input', SecretInput)
        try:
            await asyncio.to_thread(save_key, entry.value)
        except CredentialError as exc:
            self.query_one('#key-error', Static).update(str(exc))
            self.query_one('#key-error').scroll_visible(animate=False)
            return
        entry.value = ''
        await self.refresh_key_status(reset_editor=True)
        self.query_one('#key-replace').focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == 'anthropic-key-input':
            event.stop()
            await self.save_api_key()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action and action.startswith('key-'):
            event.stop()
            if action == 'key-save':
                await self.save_api_key()
            elif action == 'key-replace':
                self.edit_key(True)
                self.query_one('#anthropic-key-input', SecretInput).focus()
            elif action == 'key-cancel':
                await self.refresh_key_status(reset_editor=True)
            elif action == 'key-remove':
                try:
                    await asyncio.to_thread(remove_key)
                except CredentialError as exc:
                    self.query_one('#key-error', Static).update(str(exc))
                    return
                await self.refresh_key_status(reset_editor=True)
                self.query_one('#anthropic-key-input', SecretInput).focus()
        else:
            await super().on_button_pressed(event)
