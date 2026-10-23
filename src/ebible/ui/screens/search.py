"""Debounced worker search with literal snippets and friendly advanced-query errors."""

import asyncio
from typing import Literal, cast

from rich.padding import Padding
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, OptionList, Select, Static
from textual.widgets.option_list import Option

from ebible.core.labels import count_label
from ebible.core.models import SearchResult
from ebible.core.refs import format_reference
from ebible.core.scripture import SearchError
from ebible.ui.screens.base import Page
from ebible.ui.widgets.controls import Choice, PassageList, TextInput


def snippet_text(marked: str) -> Text:
    """Remove only FTS markers; preserve whitespace, including at SVG style boundaries."""
    text = Text()
    for part in marked.split('\x01'):
        if '\x02' in part:
            match, rest = part.split('\x02', 1)
            text.append(match, style='bold underline')
            boundary = len(rest) - len(rest.lstrip())
            # A separate non-underlined span advances the next word's SVG position.
            text.append(rest[:boundary], style='bold')
            text.append(rest[boundary:])
        else:
            text.append(part)
    return text


class SearchScreen(Page):
    def __init__(self) -> None:
        super().__init__()
        self.results: tuple[SearchResult, ...] = ()
        self.request_id = 0
        self.limit = 40

    def compose(self) -> ComposeResult:
        yield from self.heading(
            'Search scripture', 'Ordinary words · start with = for advanced FTS'
        )
        yield TextInput(placeholder='Search አማርኛ', id='search-input')
        with Horizontal(classes='filter-row'):
            yield Choice(
                [
                    ('All books', 'all'),
                    ('Old Testament', 'ot'),
                    ('New Testament', 'nt'),
                    ('Current book', 'book'),
                ],
                value='all',
                allow_blank=False,
                id='search-scope',
            )
        yield Static('Type to search', id='search-message', classes='page-subtitle', markup=False)
        yield PassageList(id='search-results')
        yield Button('Show more', id='search-more', disabled=True)

    def on_mount(self) -> None:
        self.query_one(TextInput).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        self.limit = 40
        self.queue_search()

    def on_select_changed(self, event: Select.Changed) -> None:
        self.limit = 40
        if self.is_mounted:
            self.queue_search()

    def queue_search(self) -> None:
        self.request_id += 1
        self.search(self.request_id)

    @work(exclusive=True, group='search')
    async def search(self, request: int) -> None:
        await asyncio.sleep(0.12)
        if not self.is_current:
            return
        query = self.query_one(TextInput).value
        scope = cast(
            Literal['all', 'ot', 'nt', 'book'], self.query_one('#search-scope', Select).value
        )
        try:
            results = await asyncio.to_thread(
                self.eb.scripture.search,
                query,
                scope,
                book_id=self.eb.reference.book_id,
                limit=self.limit,
            )
        except SearchError as exc:
            if request == self.request_id and self.is_current:
                self.results = ()
                self.query_one('#search-results', OptionList).clear_options()
                self.query_one('#search-message', Static).update(str(exc))
                self.query_one('#search-more', Button).disabled = True
            return
        if request != self.request_id or not self.is_current:
            return
        self.results = results
        options = []
        for i, result in enumerate(results):
            text = Text()
            text.append(format_reference(result.ref) + '\n', style='bold')
            # Plain Text spans keep scripture brackets literal; only FTS markers style a match.
            text.append_text(snippet_text(result.snippet))
            options.append(Option(Padding(text, (0, 0, 1, 0)), id=f'result-{i}'))
        self.query_one('#search-results', OptionList).clear_options().add_options(options)
        self.query_one('#search-results', OptionList).highlighted = 0 if options else None
        self.query_one('#search-message', Static).update(
            count_label(len(results), 'passage')
            if results
            else 'No passages found'
            if query.strip()
            else 'Type to search'
        )
        self.query_one('#search-more', Button).disabled = (
            len(results) < self.limit or self.limit >= 1000
        )

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            await self.eb.navigate(self.results[int(event.option_id.removeprefix('result-'))].ref)

    async def on_input_submitted(self) -> None:
        self.request_id += 1
        await self.search(self.request_id).wait()
        if self.results:
            await self.eb.navigate(self.results[0].ref)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'search-more':
            event.stop()
            self.limit = min(1000, self.limit + 40)
            self.queue_search()
        else:
            await super().on_button_pressed(event)
