"""Scripture as literal Rich Text, with an interactive line or paragraph cursor."""

import asyncio
from collections.abc import Callable
from time import monotonic
from typing import TYPE_CHECKING, cast

from rich.style import Style
from rich.text import Text
from textual import events
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Static

from ebible.core.models import Chapter, HighlightColour, Verse, VerseRef
from ebible.ui.morph import FRAME_INTERVAL, Morph, Palette, morph_text, palette, shimmer_text
from ebible.ui.themes import effect_colours, highlight_colour

if TYPE_CHECKING:
    from ebible.app import EBibleApp


class VersePicked(Message):
    def __init__(self, number: int) -> None:
        super().__init__()
        self.number = number


class VerseLine(Static):
    def __init__(self, verse: Verse) -> None:
        super().__init__(id=f'verse-{verse.verse}', classes='verse-line', markup=False)
        self.verse = verse

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(VersePicked(self.verse.verse))


class Paragraph(Static):
    def on_click(self, event: events.Click) -> None:
        number = event.style.meta.get('verse')
        if isinstance(number, int):
            event.stop()
            self.post_message(VersePicked(number))


class VerseView(Vertical):
    def __init__(self) -> None:
        super().__init__(id='verse-view')
        self.chapter: Chapter | None = None
        self.bookmarks: set[int] = set()
        self.highlights: dict[int, HighlightColour] = {}
        self.notes: set[int] = set()
        self.selected = 1
        self.paragraph_text = Text()
        self._rebuild_lock = asyncio.Lock()
        self.clock: Callable[[], float] = monotonic
        self.morphs: dict[VerseRef, Morph] = {}
        self.fetch_started: dict[VerseRef, float] = {}
        self.active: set[VerseRef] = set()
        self.motion_timer: Timer | None = None
        self._paragraph_parts: dict[int, Text] = {}

    def on_mount(self) -> None:
        self.motion_timer = self.set_interval(FRAME_INTERVAL, self.tick, pause=True)

    def colours(self, verse: Verse) -> Palette:
        variables = self.app.get_css_variables()
        ink = (
            highlight_colour(self.highlights[verse.verse], self.app.current_theme.dark)
            if verse.verse in self.highlights
            else variables['foreground']
        )
        return palette(
            ink,
            variables['secondary'],
            variables['accent'],
            variables['background'],
            effect_colours(self.app.current_theme),
        )

    def _sync_state(self, verse: Verse, now: float) -> None:
        ref = verse.ref
        state = self.morphs.setdefault(ref, Morph())
        pending = ref in self.eb.translating
        if pending:
            self.fetch_started.setdefault(ref, now)
        else:
            self.fetch_started.pop(ref, None)
        visible = ref in self.eb.visible_translations and ref in self.eb.translations
        state.retarget(visible, now, instant=self.eb.settings.reduce_motion)
        if not self.eb.settings.reduce_motion and (pending or state.animating(now)):
            self.active.add(ref)
        else:
            self.active.discard(ref)

    def _wake_timer(self) -> None:
        if self.motion_timer:
            if self.active and self.screen.is_current:
                self.motion_timer.resume()
            else:
                self.motion_timer.pause()

    def translation_changed(self, ref: VerseRef) -> None:
        if self.chapter is None:
            return
        for verse in self.chapter:
            if verse.ref == ref:
                self._sync_state(verse, self.clock())
                if not self._rebuild_lock.locked():
                    self.update_verses({ref})
                break
        self._wake_timer()

    def resume_motion(self) -> None:
        if self.chapter is not None and not self._rebuild_lock.locked():
            changed = self.active.copy()
            now = self.clock()
            for verse in self.chapter:
                self._sync_state(verse, now)
            self.update_verses(changed | self.active)
        self._wake_timer()

    def tick(self) -> None:
        if not self.app.is_running or self._rebuild_lock.locked():
            return
        if not self.screen.is_current:
            self._wake_timer()
            return
        changed = self.active.copy()
        now = self.clock()
        for ref in changed:
            if ref not in self.eb.translating and not self.morphs[ref].animating(now):
                self.active.discard(ref)
        self.update_verses(changed)
        self._wake_timer()

    def body_text(self, verse: Verse) -> Text:
        colours = self.colours(verse)
        ref, now = verse.ref, self.clock()
        if ref in self.eb.translating:
            if self.eb.settings.reduce_motion:
                text = Text(verse.text_am, style=colours.ink.hex)
                text.append(' · Translating…', style=colours.muted.hex)
                return text
            return shimmer_text(verse.text_am, now - self.fetch_started.get(ref, now), colours)
        english = self.eb.translations.get(ref, '')
        state = self.morphs.get(ref, Morph())
        return morph_text(
            verse.text_am,
            english,
            state.index(now, verse.text_am, english),
            state.running(now),
            colours,
            flourish=0.0 if self.eb.settings.reduce_motion else state.flourish(now),
        )

    @property
    def eb(self) -> 'EBibleApp':
        return cast('EBibleApp', self.app)

    def verse_text(self, verse: Verse) -> Text:
        colours = self.colours(verse)
        text = Text(style=Style(color=colours.ink.hex, meta={'verse': verse.verse}))
        if self.eb.settings.verse_numbers:
            text.append(f'{verse.verse:>2} ', style=Style(color=colours.muted.hex))
        state = self.morphs.get(verse.ref)
        if state and state.position(self.clock()) > 0 and verse.ref in self.eb.translations:
            text.append('◇ ', style=colours.muted.hex)
        markers = ('◆' if verse.verse in self.bookmarks else '') + (
            '✎' if verse.verse in self.notes else ''
        )
        if markers:
            text.append(markers + ' ', style=colours.accent.hex)
        text.append_text(self.body_text(verse))
        return text

    def line_content(self, verse: Verse) -> Text:
        text = self.verse_text(verse)
        if verse.ref in self.eb.translation_errors:
            text.append(
                '\n' + self.eb.translation_errors[verse.ref], style=self.colours(verse).muted.hex
            )
        return text

    def update_verses(self, refs: set[VerseRef]) -> None:
        if not refs or self.chapter is None:
            return
        if self.eb.settings.verse_flow == 'paragraph':
            self.update_paragraph(refs)
        else:
            for line in self.query(VerseLine):
                if line.verse.ref in refs:
                    line.update(self.line_content(line.verse))

    async def show_chapter(
        self,
        chapter: Chapter,
        bookmarks: set[int],
        highlights: dict[int, HighlightColour],
        notes: set[int],
    ) -> None:
        self.chapter, self.bookmarks, self.highlights, self.notes = (
            chapter,
            bookmarks,
            highlights,
            notes,
        )
        self.selected = self.eb.reference.verse
        await self.rebuild()

    async def rebuild(self) -> None:
        # Resize events and reading/settings refreshes have separate message pumps.
        async with self._rebuild_lock:
            if self.app.is_running:
                await self._rebuild_passage()

    async def _rebuild_passage(self) -> None:
        if self.chapter is None:
            return
        settings = self.eb.settings
        self.styles.max_width = settings.text_max_width
        self.styles.width = min(settings.text_max_width, max(1, self.app.size.width - 5))
        await self.remove_children()
        self.active.clear()
        now = self.clock()
        for verse in self.chapter:
            self._sync_state(verse, now)
        self.set_class(settings.verse_spacing == 'compact', 'compact')
        if settings.verse_flow == 'paragraph':
            await self.mount(Paragraph(id='paragraph', markup=False))
            if not self.app.is_running:
                return
            self.update_paragraph()
        else:
            await self.mount(*(VerseLine(verse) for verse in self.chapter))
            for line in self.query(VerseLine):
                line.update(self.line_content(line.verse))
                line.set_class(line.verse.verse == self.selected, 'selected')
        self.call_after_refresh(self.reveal_selection)
        self._wake_timer()

    def update_paragraph(self, changed: set[VerseRef] | None = None) -> None:
        assert self.chapter is not None
        if changed is None:
            self._paragraph_parts.clear()
        for verse in self.chapter:
            if changed is None or verse.ref in changed:
                part = self.line_content(verse)
                if verse.verse == self.selected:
                    part.stylize(Style(underline=True, bold=True))
                self._paragraph_parts[verse.verse] = part
        text = Text()
        for verse in self.chapter:
            text.append_text(self._paragraph_parts[verse.verse])
            text.append('  ')
        self.paragraph_text = text
        self.query_one(Paragraph).update(text)

    def select(self, number: int) -> None:
        self.selected = number
        if self._rebuild_lock.locked():
            return  # The mounting pass applies the latest cursor and schedules its reveal.
        if self.eb.settings.verse_flow == 'paragraph':
            self.update_paragraph()
        else:
            for line in self.query(VerseLine):
                line.set_class(line.verse.verse == number, 'selected')
        self.call_after_refresh(self.reveal_selection, True)

    def reveal_selection(self, animate: bool = False) -> None:
        if not self.app.is_running or self._rebuild_lock.locked():
            return  # A queued scroll may run between removal and mounting of verse widgets.
        if not animate and self.chapter and self.selected == self.chapter.verses[0].verse:
            if isinstance(self.parent, VerticalScroll):
                self.parent.scroll_home(animate=False)
            return
        if self.eb.settings.verse_flow == 'paragraph':
            paragraph = self.query_one(Paragraph)
            lines = self.paragraph_text.wrap(self.app.console, max(1, paragraph.content_size.width))
            for y, wrapped_line in enumerate(lines):
                if any(
                    span.style
                    and isinstance(span.style, Style)
                    and span.style.meta.get('verse') == self.selected
                    for span in wrapped_line.spans
                ):
                    # Reader viewport is the scrolling parent, not the auto-height column.

                    if isinstance(self.parent, VerticalScroll):
                        self.parent.scroll_to(
                            y=paragraph.virtual_region.y + y,
                            animate=animate,
                            duration=0.12,
                        )
                    break
        else:
            line = self.query_one(f'#verse-{self.selected}', VerseLine)
            line.scroll_visible(animate=animate, duration=0.12, top=False)
