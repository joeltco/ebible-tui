"""The chapter body.

Both languages render into a single Rich table rather than two independent
scroll panes. That is deliberate: independent panes drift out of sync the moment
one language wraps to a different height, and a parallel reader whose columns
don't line up is worse than no parallel view at all. One table, one scroll
position, rows aligned by construction.
"""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from ebible.config import Layout
from ebible.data.models import Book, Verse
from ebible.ui import theme

# Below this width a two-column split leaves each side too narrow to read, so the
# pane collapses to Amharic regardless of the configured layout.
MIN_PARALLEL_WIDTH = 64

UNTRANSLATED = '· not translated ·'


class VersePane(VerticalScroll):
    """Scrollable chapter text."""

    DEFAULT_CSS = """
    VersePane {
        scrollbar-size-vertical: 1;
        padding: 1 2;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._book: Book | None = None
        self._chapter = 1
        self._verses: list[Verse] = []
        self._layout: Layout = Layout.PARALLEL
        self._show_numbers = True

    def compose(self) -> ComposeResult:
        yield Static(id='verse-body')

    def show(
        self,
        book: Book,
        chapter: int,
        verses: list[Verse],
        layout: Layout,
        show_numbers: bool,
    ) -> None:
        self._book = book
        self._chapter = chapter
        self._verses = verses
        self._layout = layout
        self._show_numbers = show_numbers
        self._redraw()
        self.scroll_home(animate=False)

    def set_layout(self, layout: Layout) -> None:
        self._layout = layout
        self._redraw()

    def on_resize(self) -> None:
        # Width drives the parallel/single decision, so re-render on resize.
        self._redraw()

    @property
    def effective_layout(self) -> Layout:
        """The layout actually in use once terminal width is accounted for."""
        if self._layout is Layout.PARALLEL and self.size.width < MIN_PARALLEL_WIDTH:
            return Layout.AMHARIC
        return self._layout

    def _redraw(self) -> None:
        try:
            body = self.query_one('#verse-body', Static)
        except Exception:
            return  # not mounted yet
        if self._book is None:
            body.update('')
            return
        body.update(self._build_table(self.effective_layout))

    def _english(self, v: Verse) -> Text:
        if v.text_en is None:
            return Text(UNTRANSLATED, style=theme.MISSING)
        return Text(v.text_en, style=theme.EN)

    def _build_table(self, layout: Layout) -> Table:
        # collapse_padding defaults to True on Table.grid(), which merges the gap
        # between the number column and the text and leaves them touching.
        table = Table.grid(padding=(0, 2), collapse_padding=False, expand=True)

        if self._show_numbers:
            table.add_column(justify='right', width=4, style=theme.NUM, no_wrap=True)

        if layout is Layout.PARALLEL:
            table.add_column(ratio=1, overflow='fold')
            table.add_column(ratio=1, overflow='fold')
        else:
            table.add_column(ratio=1, overflow='fold')

        for v in self._verses:
            num = Text(str(v.verse))
            am = Text(v.text_am, style=theme.AM)
            en = self._english(v)

            if layout is Layout.PARALLEL:
                cells = [num, am, en] if self._show_numbers else [am, en]
            elif layout is Layout.ENGLISH:
                cells = [num, en] if self._show_numbers else [en]
            else:
                cells = [num, am] if self._show_numbers else [am]

            table.add_row(*cells)
            # A blank spacer row keeps verses from running together; cheaper and
            # more predictable than per-cell bottom padding on a grid.
            table.add_row(*([''] * len(cells)))

        return table
