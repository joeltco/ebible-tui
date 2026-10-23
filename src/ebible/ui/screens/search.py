"""Debounced worker search with literal snippets and friendly advanced-query errors."""

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import Literal, cast

from rich.padding import Padding
from rich.style import Style
from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, Input, OptionList, Select, Static
from textual.widgets.option_list import Option

from ebible.core.labels import count_label
from ebible.core.models import SearchResult
from ebible.core.refs import format_reference
from ebible.core.scripture import SearchError
from ebible.core.translate.base import TranslationError
from ebible.core.translate.query import needs_query_translation
from ebible.core.translate.service import TranslationService
from ebible.ui.morph import FRAME_INTERVAL, palette, shimmer_text
from ebible.ui.screens.base import Page
from ebible.ui.themes import effect_colours
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


class RefineQuery(Message):
    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class QuerySummary(Static, can_focus=True, inherit_bindings=False):
    """Literal term links, also reachable with Tab, arrows and Enter."""

    BINDINGS = [
        ('left', 'previous_term', 'Previous term'),
        ('right', 'next_term', 'Next term'),
        ('enter', 'refine', 'Refine term'),
    ]

    def __init__(self) -> None:
        super().__init__(id='search-translation', markup=False)
        self.variants: tuple[str, ...] = ()
        self.original = ''
        self.selected = 0

    def show_terms(self, original: str, variants: tuple[str, ...]) -> None:
        self.original, self.variants, self.selected = original, variants, 0
        self.display = bool(variants)
        self.update_terms()

    def update_terms(self) -> None:
        text = Text('Searched ')
        for i, variant in enumerate(self.variants):
            if i:
                text.append(' · ')
            text.append(
                variant,
                style=Style(
                    color=self.app.get_css_variables()['accent'],
                    underline=True,
                    bold=self.has_focus and i == self.selected,
                    meta={'variant': variant},
                ),
            )
        text.append(f' · from “{self.original}”')
        self.update(text)

    def on_focus(self) -> None:
        self.update_terms()

    def on_blur(self) -> None:
        self.update_terms()

    def action_previous_term(self) -> None:
        if self.variants:
            self.selected = (self.selected - 1) % len(self.variants)
            self.update_terms()

    def action_next_term(self) -> None:
        if self.variants:
            self.selected = (self.selected + 1) % len(self.variants)
            self.update_terms()

    def action_refine(self) -> None:
        if self.variants:
            self.post_message(RefineQuery(self.variants[self.selected]))

    def on_click(self, event: events.Click) -> None:
        variant = event.style.meta.get('variant')
        if isinstance(variant, str):
            event.stop()
            self.post_message(RefineQuery(variant))


class SearchScreen(Page):
    def __init__(self) -> None:
        super().__init__()
        self.results: tuple[SearchResult, ...] = ()
        self.request_id = 0
        self.limit = 40
        self.variants: tuple[str, ...] = ()
        self.translated_query = ''
        self.pending_query: str | None = None
        self.clock: Callable[[], float] = monotonic
        self.busy_started = 0.0
        self.busy_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield from self.heading('Search scripture', 'Type Amharic or English · = for advanced FTS')
        with Horizontal(id='search-query-row'):
            yield TextInput(placeholder='Type Amharic or English', id='search-input')
            yield Static('', id='search-busy', markup=False)
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
            yield Button('Search', id='search-submit')
        yield QuerySummary()
        yield Static(
            'Type Amharic or English', id='search-message', classes='page-subtitle', markup=False
        )
        yield PassageList(id='search-results')
        yield Button('Show more', id='search-more', disabled=True)

    def on_mount(self) -> None:
        self.busy_timer = self.set_interval(FRAME_INTERVAL, self.tick_busy, pause=True)
        self.query_one(TextInput).focus()

    def tick_busy(self) -> None:
        if self.pending_query is None or not self.is_current:
            if self.busy_timer:
                self.busy_timer.pause()
            return
        variables = self.app.get_css_variables()
        colours = palette(
            variables['foreground'],
            variables['secondary'],
            variables['accent'],
            variables['background'],
            effect_colours(self.app.current_theme),
        )
        label = 'Translating…'
        self.query_one('#search-busy', Static).update(
            Text(label, style=colours.muted.hex)
            if self.eb.settings.reduce_motion
            else shimmer_text(label, self.clock() - self.busy_started, colours)
        )

    def set_busy(self, query: str | None) -> None:
        self.pending_query = query
        self.query_one('#search-busy').display = query is not None
        self.query_one('#search-submit', Button).disabled = query is not None
        if self.busy_timer:
            self.busy_timer.pause()
            if query is not None:
                self.busy_started = self.clock()
                self.tick_busy()
                if not self.eb.settings.reduce_motion:
                    self.busy_timer.resume()

    def clear_results(self) -> None:
        self.results = ()
        self.query_one('#search-results', OptionList).clear_options()
        self.query_one('#search-more', Button).disabled = True

    def on_input_changed(self, event: Input.Changed) -> None:
        self.limit = 40
        self.variants, self.translated_query = (), ''
        self.query_one(QuerySummary).show_terms('', ())
        self.clear_results()
        self.set_busy(None)
        self.queue_search()

    def on_select_changed(self, event: Select.Changed) -> None:
        self.limit = 40
        if self.is_mounted and self.pending_query is None:
            self.clear_results()
            self.queue_search()

    def on_refine_query(self, event: RefineQuery) -> None:
        entry = self.query_one(TextInput)
        entry.value = event.value
        entry.focus()

    def queue_search(
        self, *, submit: bool = False, jump: bool = False, append: bool = False
    ) -> None:
        self.request_id += 1
        self.search(self.request_id, submit=submit, jump=jump, append=append)

    @work(exclusive=True, group='search', exit_on_error=False)
    async def search(
        self, request: int, *, submit: bool = False, jump: bool = False, append: bool = False
    ) -> None:
        if not submit:
            await asyncio.sleep(0.12)
        if not self.is_current or request != self.request_id:
            return
        query = self.query_one(TextInput).value.strip()
        translated = needs_query_translation(query)
        try:
            if translated and (not self.variants or query != self.translated_query):
                if not submit:
                    self.query_one('#search-message', Static).update(
                        'Press Enter or Search to translate English'
                    )
                    return
                key = (self.eb.settings.translation_backend, query.casefold())
                variants = self.eb.query_translations.get(key)
                if variants is None:
                    self.set_busy(query)
                    self.query_one('#search-message', Static).update('')
                    service = TranslationService(
                        self.eb.scripture, self.eb.settings.translation_backend
                    )
                    variants = await service.translate_query(query)
                    if request != self.request_id or not self.is_current:
                        return
                    self.eb.query_translations[key] = variants
                self.variants, self.translated_query = variants, query
            if request != self.request_id or not self.is_current:
                return
            scope = cast(
                Literal['all', 'ot', 'nt', 'book'], self.query_one('#search-scope', Select).value
            )
            previous = self.results if append else ()
            if translated:
                page = await asyncio.to_thread(
                    self.eb.scripture.search_substrings,
                    self.variants,
                    scope,
                    book_id=self.eb.reference.book_id,
                    limit=40,
                    offset=len(previous),
                )
                results = previous + page
            else:
                results = await asyncio.to_thread(
                    self.eb.scripture.search,
                    query,
                    scope,
                    book_id=self.eb.reference.book_id,
                    limit=self.limit,
                )
                page = results
            if request != self.request_id or not self.is_current:
                return
            self.results = results
            options = []
            for i, result in enumerate(results):
                text = Text()
                text.append(format_reference(result.ref) + '\n', style='bold')
                text.append_text(snippet_text(result.snippet))
                options.append(Option(Padding(text, (0, 0, 1, 0)), id=f'result-{i}'))
            self.query_one('#search-results', OptionList).clear_options().add_options(options)
            self.query_one('#search-results', OptionList).highlighted = (
                len(previous) if page else (0 if options else None)
            )
            self.query_one(QuerySummary).show_terms(query, self.variants if translated else ())
            self.query_one('#search-message', Static).update(
                count_label(len(results), 'passage')
                if results
                else 'No passages found'
                if query
                else 'Type Amharic or English'
            )
            self.query_one('#search-more', Button).disabled = (
                len(page) < (40 if translated else self.limit) or len(results) >= 1000
            )
            if jump and not translated and results:
                await self.eb.navigate(results[0].ref)
        except (SearchError, TranslationError) as exc:
            if request == self.request_id and self.is_current:
                self.clear_results()
                self.query_one('#search-message', Static).update(str(exc))
        except Exception:
            if request == self.request_id and self.is_current:
                self.clear_results()
                self.query_one('#search-message', Static).update(
                    'Search failed. Check your connection and translation backend in Settings, then retry.'
                )
        finally:
            if request == self.request_id and self.is_mounted:
                self.set_busy(None)

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            index = int(event.option_id.removeprefix('result-'))
            if index < len(self.results):
                await self.eb.navigate(self.results[index].ref)

    def on_input_submitted(self) -> None:
        self.submit_query(jump=True)

    def submit_query(self, *, jump: bool = False) -> None:
        if self.pending_query is None:
            self.limit = 40
            self.clear_results()
            self.queue_search(submit=True, jump=jump)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == 'search-submit':
            event.stop()
            self.submit_query()
        elif event.button.id == 'search-more':
            event.stop()
            self.limit = min(1000, self.limit + 40)
            self.query_one('#search-more', Button).disabled = True
            self.queue_search(append=bool(self.variants))
        else:
            await super().on_button_pressed(event)
