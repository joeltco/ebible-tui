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
from textual.theme import Theme

from ebible.core.models import HighlightColour, VerseRef
from ebible.core.refs import ReferenceError, format_reference, parse_reference
from ebible.core.scripture import ScriptureStore
from ebible.core.settings import Settings, load_settings, save_settings
from ebible.core.translate.base import AlignmentError, TranslationError
from ebible.core.translate.cache import TranslationCache
from ebible.core.translate.service import BackendSetting, TranslationService
from ebible.core.userdata import UserDataStore
from ebible.ui.themes import THEMES, ordered_theme_names, role_variables

if TYPE_CHECKING:
    from ebible.ui.screens.reader import ReaderScreen


class LoadingScreen(Screen[None], inherit_bindings=False):
    """No desktop shortcuts on the transient startup screen."""


class EBibleApp(App[None], inherit_bindings=False):
    TITLE = 'eBible · መጽሐፍ ቅዱስ'
    CSS_PATH = 'ui/styles/app.tcss'
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = []

    def get_css_variables(self) -> dict[str, str]:
        variables = super().get_css_variables()
        return {**variables, **role_variables(self.current_theme, variables)}

    @property
    def available_themes(self) -> dict[str, Theme]:
        themes = super().available_themes
        return {name: themes[name] for name in ordered_theme_names(themes)}

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
        self.epigraph = ''
        self.has_saved_position = False
        self.ready = asyncio.Event()
        self._navigation_lock = asyncio.Lock()
        self._settings_lock = asyncio.Lock()
        self.translations: dict[VerseRef, str] = {}
        self.translation_cache = TranslationCache()
        self.query_translations: dict[tuple[BackendSetting, str], tuple[str, ...]] = {}
        self.visible_translations: set[VerseRef] = set()
        self.translating: set[VerseRef] = set()
        self.translation_errors: dict[VerseRef, str] = {}
        self.last_message = ''
        if theme_name is not None:
            self.theme = theme_name

    def get_default_screen(self) -> Screen[None]:
        return LoadingScreen()

    async def on_mount(self) -> None:
        from ebible.ui.screens.reader import ReaderScreen

        (
            self.settings,
            self.userdata,
            self.chapter_counts,
            saved,
            self.epigraph,
        ) = await asyncio.to_thread(self._load)
        chosen = self.theme_override or self.settings.theme
        self.theme = chosen if chosen in self.available_themes else 'meskel'
        # A CLI theme is a session override, becoming persistent only if edited in Settings.
        self.settings = replace(self.settings, theme=self.theme)
        self.has_saved_position = saved is not None
        target = self.requested_reference or saved or VerseRef(1)
        try:
            await asyncio.to_thread(self.scripture.validate_reference, target)
        except ReferenceError as exc:
            self.message(str(exc), error=True)
            target = VerseRef(1)
        self.reference = VerseRef(target.book_id, target.chapter, target.verse)
        self.reader = ReaderScreen()
        await self.push_screen(self.reader)
        if self.settings.title_page_on_launch and self.requested_reference is None:
            await self.show_title(continuing=self.has_saved_position)
        await self.reader.load_chapter()
        self.ready.set()

    def _load(self) -> tuple[Settings, UserDataStore, dict[int, int], VerseRef | None, str]:
        from ebible.ui.screens.title import EPIGRAPH

        userdata = UserDataStore()
        return (
            load_settings(),
            userdata,
            self.scripture.chapter_counts(),
            userdata.reading_position(),
            self.scripture.verse(EPIGRAPH).text_am,
        )

    async def show_title(self, *, continuing: bool = True) -> None:
        from ebible.ui.screens.title import TitleScreen

        while len(self.screen_stack) > 2:
            self.pop_screen()
        await self.push_screen(TitleScreen(continuing=continuing))

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

    async def copy_verse(self, ref: VerseRef, language: Literal['am', 'both']) -> None:
        verse = await asyncio.to_thread(self.scripture.verse, ref)
        if language not in ('am', 'both') or (language == 'both' and ref not in self.translations):
            self.message(
                'Translate this verse first; Amharic copy is always available.', error=True
            )
            return
        parts = [format_reference(ref), verse.text_am]
        if language == 'both':
            parts.append('◇ Translation · ' + self.translations[ref])
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

    async def toggle_translation(self, ref: VerseRef) -> None:
        if ref in self.translating:
            return
        if ref in self.visible_translations:
            self.visible_translations.remove(ref)
        else:
            self.visible_translations.add(ref)
            self.translation_errors.pop(ref, None)
            if ref not in self.translations:
                self.translating.add(ref)
                self.translate_verse(ref)
        await self.refresh_translation(ref)

    async def refresh_translation(self, ref: VerseRef) -> None:
        from ebible.ui.widgets.verse_view import VerseView

        if self.is_running and (ref.book_id, ref.chapter) == (
            self.reference.book_id,
            self.reference.chapter,
        ):
            self.reader.query_one(VerseView).translation_changed(ref)

    @work(group='translation', exit_on_error=False)
    async def translate_verse(self, ref: VerseRef) -> None:
        try:
            service = TranslationService(
                self.scripture, self.settings.translation_backend, cache=self.translation_cache
            )
            self.translations[ref] = await service.translate_verse(ref)
        except AlignmentError:
            self.translation_errors[ref] = (
                'Translation did not match this verse. Press Enter to retry or change backend in Settings.'
            )
        except TranslationError as exc:
            self.translation_errors[ref] = str(exc) + (
                ' Press Enter to retry.'
                if 'retry' not in str(exc) and 'Settings' not in str(exc)
                else ''
            )
        except Exception:
            self.translation_errors[ref] = (
                'Translation failed. Check your connection and backend in Settings, then press Enter to retry.'
            )
        finally:
            self.translating.discard(ref)
        if ref in self.translation_errors:
            self.visible_translations.discard(ref)
        await self.refresh_translation(ref)
