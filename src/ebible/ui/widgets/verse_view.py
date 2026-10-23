"""Scripture as literal Rich Text, with an interactive line or paragraph cursor."""

import asyncio
from typing import TYPE_CHECKING, cast

from rich.style import Style
from rich.text import Text
from textual import events
from textual.color import Color
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ebible.core.models import Chapter, HighlightColour, Verse
from ebible.ui.themes import highlight_colour

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

    @property
    def eb(self) -> 'EBibleApp':
        return cast('EBibleApp', self.app)

    def verse_text(self, verse: Verse) -> Text:
        settings = self.eb.settings
        colours = self.app.get_css_variables()
        muted = (
            Color.parse(colours['foreground']).blend(Color.parse(colours['background']), 0.4).hex
        )
        text = Text(style=Style(color=colours['foreground'], meta={'verse': verse.verse}))
        if settings.verse_numbers:
            text.append(f'{verse.verse:>2} ', style=Style(color=muted))
        markers = ('◆' if verse.verse in self.bookmarks else '') + (
            '✎' if verse.verse in self.notes else ''
        )
        if markers:
            text.append(markers + ' ', style=Style(color=colours['accent']))
        text.append(verse.text_am)
        if verse.verse in self.highlights:
            text.stylize(
                Style(
                    color=highlight_colour(
                        self.highlights[verse.verse], self.app.current_theme.dark
                    )
                )
            )
        return text

    def translation_text(self, verse: Verse) -> Text | None:
        ref = verse.ref
        colours = self.app.get_css_variables()
        muted = (
            Color.parse(colours['foreground']).blend(Color.parse(colours['background']), 0.4).hex
        )
        if ref in self.eb.translating:
            message, colour = 'Translating…', muted
        elif ref in self.eb.translation_errors:
            message, colour = self.eb.translation_errors[ref], muted
        elif ref in self.eb.visible_translations and ref in self.eb.translations:
            message, colour = '◇ Translation · ' + self.eb.translations[ref], colours['secondary']
        else:
            return None
        return Text(message, style=Style(color=colour, meta={'verse': verse.verse}))

    def line_content(self, verse: Verse) -> Text:
        text = self.verse_text(verse)
        translated = self.translation_text(verse)
        if translated is not None:
            text.append('\n')
            text.append_text(translated)
        return text

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

    def update_paragraph(self) -> None:
        assert self.chapter is not None
        text = Text()
        for verse in self.chapter:
            part = self.verse_text(verse)
            if verse.verse == self.selected:
                part.stylize(Style(underline=True, bold=True))
            text.append_text(part)
            translated = self.translation_text(verse)
            if translated is not None:
                text.append('\n')
                text.append_text(translated)
                text.append('\n\n')
            else:
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
