from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import ListItem, ListView, Static


class VersePanel(Static):
    """Scrollable wrapping list of verses with a small translation box below."""

    translation_text = reactive('', init=False)

    def __init__(self) -> None:
        super().__init__()
        self.list_view = ListView(id='verse-list')
        self._verses: list[tuple[int, str]] = []
        self._anim_handle: Timer | None = None
        self._anim_i = 0
        self._anim_frames = ['[    ]', '[ .  ]', '[ .. ]', '[ ...]']

    def compose(self) -> ComposeResult:
        yield Static('[b]Chapter Verses[/b]', id='vv-title')
        yield self.list_view
        with Horizontal(id='trans-box'):
            yield Static(
                self.translation_text or '[dim]Translation will appear here[/dim]', id='vv-trans'
            )

    def watch_translation_text(self, value: str) -> None:
        if not self.is_mounted:
            return
        self.query_one('#vv-trans', Static).update(
            value if value else '[dim]Translation will appear here[/dim]'
        )

    def start_anim(self) -> None:
        self._anim_i = 0
        if self._anim_handle:
            self._anim_handle.pause()
            self._anim_handle = None

        def _tick() -> None:
            frame = self._anim_frames[self._anim_i % len(self._anim_frames)]
            self._anim_i += 1
            self.translation_text = f'[dim]{frame} Translating... Please wait[/dim]'

        # update every 200ms
        self._anim_handle = self.set_interval(0.2, _tick, name='trans-anim')

    def stop_anim(self) -> None:
        if self._anim_handle:
            self._anim_handle.pause()
            self._anim_handle = None

    def populate_verses(self, verses: list[tuple[int, str]]) -> None:
        self._verses = verses
        self.list_view.clear()
        for num, text in verses:
            body = Static(f'[b]{num:02d}[/b]  {text}', expand=True)
            self.list_view.append(ListItem(body))
        if verses:
            self.list_view.index = 0

    def selected(self) -> tuple[int, str] | None:
        idx = self.list_view.index
        if idx is None or not self._verses:
            return None
        if 0 <= idx < len(self._verses):
            return self._verses[idx]
        return None
