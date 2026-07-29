"""Full-text search across both languages.

The Input lives on this modal rather than hidden on the reader: a mounted-but-
hidden Input still captures keystrokes, which would break every single-key
binding in the app.
"""

from __future__ import annotations

import sqlite3

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option

from ebible.data.store import Store
from ebible.ui import theme

RESULT_LIMIT = 200


def _highlight(snippet: str) -> Text:
    """Render an FTS snippet, styling the «matched» spans.

    Built as a Text rather than a markup string so verse content containing
    brackets cannot be parsed as Rich markup.
    """
    out = Text()
    for chunk in snippet.split('«'):
        head, sep, tail = chunk.partition('»')
        if sep:
            out.append(head, style=theme.HIT)
            out.append(tail)
        else:
            out.append(chunk)
    return out


class SearchScreen(ModalScreen[tuple[int, int] | None]):
    """Returns (book_id, chapter) for the chosen hit, or None."""

    BINDINGS = [Binding('escape', 'dismiss_none', 'Close')]

    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self._hits: list = []

    def compose(self) -> ComposeResult:
        with Vertical(id='search'):
            yield Input(placeholder='Search Amharic or English…', id='search-input')
            yield Label('', id='search-status')
            yield OptionList(id='search-results')

    def on_mount(self) -> None:
        self.query_one('#search-input', Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._run(event.value)

    def _run(self, query: str) -> None:
        status = self.query_one('#search-status', Label)
        results = self.query_one('#search-results', OptionList)
        results.clear_options()

        query = query.strip()
        if not query:
            status.update('')
            return

        try:
            hits = self.store.search(query, limit=RESULT_LIMIT)
        except sqlite3.OperationalError:
            # FTS5 rejects its own operators used loosely (AND, ", *). Report it
            # rather than letting the exception reach the app.
            status.update(Text('Invalid search syntax.', style='warning'))
            self._hits = []
            return

        self._hits = hits
        if not hits:
            status.update(Text(f'No matches for {query!r}', style='dim'))
            return

        capped = ' (showing first 200)' if len(hits) == RESULT_LIMIT else ''
        status.update(Text(f'{len(hits)} result(s){capped}', style='dim'))

        opts = []
        for i, h in enumerate(hits):
            line = Text(f'{h.reference:<20} ', style=theme.REF)
            line.append_text(_highlight(h.snippet))
            opts.append(Option(line, id=str(i)))
        results.add_options(opts)
        results.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        hit = self._hits[int(event.option.id or 0)]
        self.dismiss((hit.book_id, hit.chapter))

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
