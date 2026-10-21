"""A wrapping chapter grid with generous touch targets."""

from textual.app import ComposeResult
from textual.containers import Grid
from textual.widgets import Button


class ChapterGrid(Grid):
    def __init__(self, count: int) -> None:
        super().__init__(id='chapter-grid')
        self.count = count

    def compose(self) -> ComposeResult:
        for chapter in range(1, self.count + 1):
            yield Button(str(chapter), id=f'chapter-{chapter}')
