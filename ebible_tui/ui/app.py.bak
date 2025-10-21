from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ListView, Static

from ebible_tui.core import ChapterRef, parse_verses, read_chapter, translate_async
from ebible_tui.core.bible.assets import resolve_bible81
from ebible_tui.ui.widgets.nav import NavPane
from ebible_tui.ui.widgets.titlebar import TitleBar
from ebible_tui.ui.widgets.translation_panel import TranslationPanel
from ebible_tui.ui.widgets.verse_panel import VersePanel

APP_TITLE = 'eBible · 27×81'
APP_SUBTITLE = 'Ethiopian Orthodox Bible · Live Translation'


BIBLE_DIR = resolve_bible81()


class EBibleApp(App):
    CSS_PATH = 'styles/app.tcss'

    BINDINGS = [
        ('q', 'quit', 'Quit'),
        (']', 'next_pane', 'Next'),
        ('[', 'prev_pane', 'Prev'),
        ('g', 'top', 'Top'),
        ('p', 'prev_pane', 'Prev'),
        ('n', 'next_pane', 'Next'),
        ('G', 'bottom', 'Bottom'),
    ]

    current_ref: ChapterRef | None = None
    verses: list[tuple[int, str]] = []

    def compose(self) -> ComposeResult:
        yield TitleBar(APP_TITLE, APP_SUBTITLE)
        with Horizontal():
            self.nav = NavPane()
            yield self.nav
            with Vertical():
                yield Static('[b]Verses[/b]', id='vv-title-out')
                self.verse_panel = VersePanel()
                yield self.verse_panel
                yield Static('[b]Translation[/b]', id='trans-title-out')
                self.trans_panel = TranslationPanel()
                yield self.trans_panel
        yield Static('q Quit   p prev  n next   g/G top/bot  ', id='footer')

    def action_down(self) -> None:
        self.verse_panel.list_view.action_cursor_down()

    def action_up(self) -> None:
        self.verse_panel.list_view.action_cursor_up()

    def on_nav_pane_chapter_selected(self, message: NavPane.ChapterSelected) -> None:
        self.current_ref = message.ref
        chapter_text = read_chapter(message.ref)
        self.verses = parse_verses(chapter_text)
        self.verse_panel.populate_verses(self.verses)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Enter on verses -> translate selected verse into the Translation box
        if hasattr(self, 'verse_panel') and event.list_view is getattr(
            self.verse_panel, 'list_view', None
        ):
            sel = self.verse_panel.selected()
            if not sel:
                self.bell()
                return
            _, verse_text = sel
            self.verse_panel.start_anim()
            try:
                self.trans_panel.set_status('Translating...')
            except Exception:
                pass

            async def _work() -> None:
                try:
                    out = await translate_async(verse_text, 'am', 'en', timeout_sec=180)
                    out_trim = out
                except Exception as e:
                    out_trim = f'[red]Translation error:[/red] {e}'
                finally:
                    self.verse_panel.stop_anim()
                try:
                    self.trans_panel.set_translation(out_trim)
                except Exception:
                    pass

            self.run_worker(_work(), exclusive=True, group='translate')
            event.stop()

    def _current_list(self) -> ListView | None:
        try:
            if self.verse_panel.list_view.has_focus:
                return self.verse_panel.list_view
        except Exception:
            pass
        try:
            if self.nav.chapters_view.has_focus:
                return self.nav.chapters_view
        except Exception:
            pass
        try:
            if self.nav.books_view.has_focus:
                return self.nav.books_view
        except Exception:
            pass
        return getattr(self.nav, 'books_view', None)

    def action_focus_books(self) -> None:
        try:
            self.nav.books_view.focus()
        except Exception:
            self.bell()

    def action_focus_chapters(self) -> None:
        try:
            self.nav.chapters_view.focus()
        except Exception:
            self.bell()

    def action_focus_verses(self) -> None:
        try:
            self.verse_panel.list_view.focus()
        except Exception:
            self.bell()

    def action_next_pane(self) -> None:
        try:
            if self.nav.books_view.has_focus:
                self.nav.chapters_view.focus()
            elif self.nav.chapters_view.has_focus:
                self.verse_panel.list_view.focus()
            else:
                self.nav.books_view.focus()
        except Exception:
            self.bell()

    def action_prev_pane(self) -> None:
        try:
            if self.verse_panel.list_view.has_focus:
                self.nav.chapters_view.focus()
            elif self.nav.chapters_view.has_focus:
                self.nav.books_view.focus()
            else:
                self.verse_panel.list_view.focus()
        except Exception:
            self.bell()

    def action_top(self) -> None:
        lst = self._current_list()
        if lst is None:
            self.bell()
            return
        lst.index = 0

    def action_bottom(self) -> None:
        lst = self._current_list()
        if lst is None:
            self.bell()
            return
        try:
            if lst.children:
                lst.index = len(lst.children) - 1
        except Exception:
            self.bell()


def run() -> None:
    EBibleApp().run()
