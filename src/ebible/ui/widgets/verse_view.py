"""Scripture as literal Rich Text, with an interactive line or paragraph cursor."""

from typing import TYPE_CHECKING, cast

from rich.style import Style
from rich.table import Table
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
        self.effective_layout = 'interleaved'
        self.paragraph_text = Text()

    @property
    def eb(self) -> 'EBibleApp':
        return cast('EBibleApp', self.app)

    def verse_text(self, verse: Verse, language: str, *, gutter: bool = True) -> Text:
        settings = self.eb.settings
        colours = self.app.get_css_variables()
        colours['text-muted'] = (
            Color.parse(colours['foreground']).blend(Color.parse(colours['background']), 0.4).hex
        )
        style = colours['foreground'] if language == 'am' else colours['secondary']
        text = Text(style=Style(color=style, meta={'verse': verse.verse}))
        if gutter:
            markers = ('◆' if verse.verse in self.bookmarks else '') + (
                '✎' if verse.verse in self.notes else ''
            )
            if settings.verse_numbers:
                text.append(f'{verse.verse:>2} ', style=Style(color=colours['text-muted']))
            if markers:
                text.append(markers + ' ', style=Style(color=colours['accent']))
        if language == 'am':
            text.append(verse.text_am)
        elif verse.english_source == 'placeholder':
            placeholder = (
                verse.english
                if settings.show_untranslated_placeholder
                else (
                    'Untranslated · deuterocanonical'
                    if self.chapter and self.chapter.book.deuterocanonical
                    else 'Not yet translated'
                )
            )
            text.append('◇ ' + placeholder, style=Style(color=colours['text-muted'], italic=True))
        else:
            if verse.english_source == 'live':
                text.append('◇ Machine · ', style=Style(color=colours['text-muted'], italic=True))
            text.append(verse.english)
        if verse.verse in self.highlights:
            colour = highlight_colour(self.highlights[verse.verse], self.app.current_theme.dark)
            text.stylize(Style(color=colour))
        return text

    def line_content(self, verse: Verse) -> Text | Table:
        layout = self.effective_layout
        if layout == 'parallel':
            table = Table.grid(expand=True, padding=(0, 1))
            table.add_column(ratio=1)
            table.add_column(ratio=1)
            table.add_row(self.verse_text(verse, 'am'), self.verse_text(verse, 'en', gutter=False))
            return table
        if layout == 'interleaved':
            return (
                self.verse_text(verse, 'am')
                + Text('\n')
                + self.verse_text(verse, 'en', gutter=False)
            )
        return self.verse_text(verse, 'am' if layout == 'amharic' else 'en')

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
        if self.chapter is None:
            return
        settings = self.eb.settings
        self.styles.max_width = settings.text_max_width
        self.styles.width = min(settings.text_max_width, max(1, self.app.size.width - 5))
        self.effective_layout = (
            'interleaved'
            if settings.layout == 'parallel' and self.app.size.width < 90
            else settings.layout
        )
        await self.remove_children()
        self.set_class(settings.verse_spacing == 'compact', 'compact')
        if settings.verse_flow == 'paragraph':
            await self.mount(Paragraph(id='paragraph', markup=False))
            self.update_paragraph()
        else:
            await self.mount(*(VerseLine(verse) for verse in self.chapter))
            for line in self.query(VerseLine):
                line.update(self.line_content(line.verse))
                line.set_class(line.verse.verse == self.selected, 'selected')
        self.call_after_refresh(self.reveal_selection)

    def update_paragraph(self) -> None:
        assert self.chapter is not None
        left, right = Text(), Text()
        selected_style = Style(underline=True, bold=True)
        for verse in self.chapter:
            for text, language in (
                (left, 'am' if self.effective_layout != 'english' else 'en'),
                (right, 'en'),
            ):
                part = self.verse_text(verse, language)
                if self.effective_layout == 'interleaved' and text is left:
                    part += Text(' / ') + self.verse_text(verse, 'en', gutter=False)
                if verse.verse == self.selected:
                    part.stylize(selected_style)
                text.append_text(part)
                text.append('  ')
        self.paragraph_text = left
        if self.effective_layout == 'parallel':
            table = Table.grid(expand=True, padding=(0, 1))
            table.add_column(ratio=1)
            table.add_column(ratio=1)
            table.add_row(left, right)
            self.query_one(Paragraph).update(table)
        else:
            self.query_one(Paragraph).update(left)

    def select(self, number: int) -> None:
        self.selected = number
        if self.eb.settings.verse_flow == 'paragraph':
            self.update_paragraph()
        else:
            for line in self.query(VerseLine):
                line.set_class(line.verse.verse == number, 'selected')
        self.call_after_refresh(self.reveal_selection, True)

    def reveal_selection(self, animate: bool = False) -> None:
        if self.eb.settings.verse_flow == 'paragraph':
            width = max(
                1,
                self.query_one(Paragraph).content_size.width
                - (2 if self.effective_layout == 'parallel' else 0),
            )
            if self.effective_layout == 'parallel':
                width //= 2
            lines = self.paragraph_text.wrap(self.app.console, max(1, width))
            for y, wrapped_line in enumerate(lines):
                if any(
                    span.style
                    and isinstance(span.style, Style)
                    and span.style.meta.get('verse') == self.selected
                    for span in wrapped_line.spans
                ):
                    # Reader viewport is the scrolling parent, not the auto-height column.

                    if isinstance(self.parent, VerticalScroll):
                        self.parent.scroll_to(y=y, animate=animate, duration=0.12)
                    break
        else:
            line = self.query_one(f'#verse-{self.selected}', VerseLine)
            line.scroll_visible(animate=animate, duration=0.12, top=False)
