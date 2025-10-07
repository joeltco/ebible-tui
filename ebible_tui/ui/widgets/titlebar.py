from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static


class TitleBar(Static):
    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Static(f'[bold white]{self._title}[/]  [dim]{self._subtitle}[/]', id='titlebar')
