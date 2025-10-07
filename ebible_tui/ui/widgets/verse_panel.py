from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import ListItem, ListView, Static


class VersePanel(Static):
    """Right-side verses box: title + list of verses (no translation UI here)."""

    def __init__(self) -> None:
        super().__init__()
        self.list_view = ListView(id='verse-list')
        self._verses: list[tuple[int, str]] = []

    def compose(self) -> ComposeResult:
        yield Static('[b]Chapter Verses[/b]', id='vv-title')
        yield self.list_view

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
        if idx is None or not (0 <= idx < len(self._verses)):
            return None
        return self._verses[idx]

    # no-op hooks kept for compatibility; will be removed after translator box lands
    def start_anim(self) -> None:
        return

    def stop_anim(self) -> None:
        return
