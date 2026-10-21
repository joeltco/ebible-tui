"""Application services, navigation, persistence, and worker orchestration."""

import asyncio
import shutil
import subprocess
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, ClassVar, Literal

from textual import work
from textual.app import App
from textual.binding import BindingType
from textual.screen import Screen

from ebible.core.models import HighlightColour, VerseRef
from ebible.core.refs import ReferenceError, format_reference, parse_reference
from ebible.core.scripture import ScriptureStore
from ebible.core.settings import Settings, load_settings, save_settings
from ebible.core.translate.base import TranslationError
from ebible.core.translate.service import TranslationService
from ebible.core.userdata import UserDataStore
from ebible.ui.themes import THEMES

if TYPE_CHECKING:
    from ebible.ui.screens.reader import ReaderScreen


class LoadingScreen(Screen[None], inherit_bindings=False):
    """No desktop shortcuts on the transient startup screen."""


class EBibleApp(App[None], inherit_bindings=False):
    TITLE = 'eBible · መጽሐፍ ቅዱስ'
    CSS_PATH = 'ui/styles/app.tcss'
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = []

    def __init__(self, reference: VerseRef | None = None, theme_name: str | None = None) -> None:
        super().__init__()
        for theme in THEMES:
            self.register_theme(theme)
        if theme_name is not None and theme_name not in self.available_themes:
            raise ValueError(f'Unknown theme: {theme_name}')
        self.requested_reference = reference
        self.reference = reference or VerseRef(1)
        self.theme_override = theme_name
        self.settings = Settings()
        self.scripture = ScriptureStore()
        self.userdata: UserDataStore
        self.reader: ReaderScreen
        self.chapter_counts: dict[int, int] = {}
        self.ready = asyncio.Event()
        self._navigation_lock = asyncio.Lock()
        self._settings_lock = asyncio.Lock()
        self.translation_running = False
        self.last_message = ''
        if theme_name is not None:
            self.theme = theme_name

    def get_default_screen(self) -> Screen[None]:
        return LoadingScreen()

    async def on_mount(self) -> None:
        from ebible.ui.screens.reader import ReaderScreen

        self.settings, self.userdata, self.chapter_counts = await asyncio.to_thread(self._load)
        self.scripture.live_lookup = self.userdata.live_chapter
        chosen = self.theme_override or self.settings.theme
        self.theme = chosen if chosen in self.available_themes else 'meskel'
        # A CLI theme is a session override, becoming persistent only if edited in Settings.
        self.settings = replace(self.settings, theme=self.theme)
        saved = await asyncio.to_thread(self.userdata.reading_position)
        target = self.requested_reference or saved or VerseRef(1)
        self.reader = ReaderScreen()
        await self.push_screen(self.reader)
        if not await self.navigate(target):
            await self.navigate(VerseRef(1))
        self.ready.set()

    def _load(self) -> tuple[Settings, UserDataStore, dict[int, int]]:
        return load_settings(), UserDataStore(), self.scripture.chapter_counts()

    def message(self, text: str, *, error: bool = False) -> None:
        self.last_message = text
        self.notify(
            text, title='eBible', severity='error' if error else 'information', markup=False
        )

    async def navigate(self, ref: VerseRef) -> bool:
        """The single validated gate for every jump, including stored personal data."""
        async with self._navigation_lock:
            try:
                await asyncio.to_thread(self.scripture.validate_reference, ref)
            except ReferenceError as exc:
                self.message(str(exc), error=True)
                return False
            while len(self.screen_stack) > 2:
                self.pop_screen()
            self.reference = VerseRef(ref.book_id, ref.chapter, ref.verse)
            await self.reader.load_chapter()
            return True

    async def go_to(self, text: str) -> bool:
        try:
            ref = await asyncio.to_thread(
                parse_reference, text, validate=self.scripture.validate_reference
            )
        except ReferenceError as exc:
            self.last_message = str(exc)
            return False
        return await self.navigate(ref)

    async def open_page(self, name: str) -> None:
        from ebible.ui.screens.bookmarks import BookmarksScreen, HighlightsScreen
        from ebible.ui.screens.books import BooksScreen
        from ebible.ui.screens.help import HelpScreen
        from ebible.ui.screens.history import HistoryScreen
        from ebible.ui.screens.notes import NotesScreen
        from ebible.ui.screens.plans import PlansScreen
        from ebible.ui.screens.search import SearchScreen
        from ebible.ui.screens.settings import SettingsScreen

        pages = {
            'books': BooksScreen,
            'search': SearchScreen,
            'bookmarks': BookmarksScreen,
            'highlights': HighlightsScreen,
            'notes': NotesScreen,
            'history': HistoryScreen,
            'plans': PlansScreen,
            'settings': SettingsScreen,
            'help': HelpScreen,
        }
        await self.push_screen(pages[name]())

    async def update_setting(self, name: str, value: object) -> None:
        async with self._settings_lock:
            values = asdict(self.settings)
            values[name] = value
            new = Settings(**values)
            try:
                await asyncio.to_thread(save_settings, new)
            except (OSError, ValueError) as exc:
                self.message(f'Could not save settings: {exc}', error=True)
                return
            self.settings = new
            if name == 'theme':
                self.theme = new.theme
            await self.reader.refresh_reading()

    async def toggle_bookmark(self, ref: VerseRef) -> bool:
        bookmarks = await asyncio.to_thread(self.userdata.bookmarks)
        exists = any(b.ref == ref for b in bookmarks)
        await asyncio.to_thread(
            self.userdata.delete_bookmark if exists else self.userdata.add_bookmark, ref
        )
        if self.settings.haptic_feedback:
            await asyncio.to_thread(self._vibrate)
        await self.reader.refresh_reading()
        return not exists

    @staticmethod
    def _vibrate() -> None:
        executable = shutil.which('termux-vibrate')
        if executable:
            try:
                subprocess.run([executable, '-d', '20'], timeout=2, check=True, capture_output=True)
            except (OSError, subprocess.SubprocessError):
                pass  # Optional tactile feedback must not undo a saved bookmark.

    async def set_highlight(self, ref: VerseRef, colour: HighlightColour | None) -> None:
        if colour is None:
            await asyncio.to_thread(self.userdata.delete_highlight, ref)
        else:
            await asyncio.to_thread(self.userdata.set_highlight, ref, colour)
        await self.reader.refresh_reading()

    async def copy_verse(self, ref: VerseRef, language: Literal['am', 'en', 'both']) -> None:
        verse = await asyncio.to_thread(self.scripture.verse, ref)
        english = (
            '◇ Machine translation · ' if verse.english_source == 'live' else ''
        ) + verse.english
        parts = [format_reference(ref)]
        if language in ('am', 'both'):
            parts.append(verse.text_am)
        if language in ('en', 'both'):
            parts.append(english)
        text = '\n'.join(parts)
        executable = shutil.which('termux-clipboard-set')
        try:
            if executable:
                await asyncio.to_thread(
                    subprocess.run,
                    [executable],
                    input=text,
                    encoding='utf-8',
                    check=True,
                    timeout=5,
                    capture_output=True,
                )
            else:
                self.copy_to_clipboard(text)
        except (OSError, subprocess.SubprocessError) as exc:
            self.message(f'Could not copy: {exc}', error=True)
            return
        self.message('Verse copied with its reference')

    @work(group='translation', exit_on_error=False)
    async def translate_current(self) -> None:
        if self.translation_running:
            self.message('A chapter is already being translated')
            return
        self.translation_running = True
        ref = self.reference
        self.reader.update_status('Translating chapter…')
        try:
            service = TranslationService(
                self.scripture, self.userdata, self.settings.translation_backend
            )
            filled = await service.translate_chapter(ref.book_id, ref.chapter)
            self.message(
                f'{len(filled)} verses translated · machine text'
                if filled
                else 'No new translation: already available or backend is off'
            )
            if (ref.book_id, ref.chapter) == (self.reference.book_id, self.reference.chapter):
                await self.reader.refresh_reading()
        except (TranslationError, OSError, ValueError) as exc:
            self.message(str(exc), error=True)
        finally:
            self.translation_running = False
            self.reader.update_status()
