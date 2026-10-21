"""A quiet book title between tappable chapter controls."""

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static


class HeaderBar(Horizontal):
    def __init__(self) -> None:
        super().__init__()
        self.book_name = ''
        self.chapter = 1
        self.chapter_count = 1

    def compose(self) -> ComposeResult:
        yield Button('‹', id='previous-chapter', tooltip='Previous chapter · h / left')
        yield Static('', id='book-title', markup=False)
        yield Button('›', id='next-chapter', tooltip='Next chapter · l / right')

    def show_title(self, name: str, chapter: int, count: int) -> None:
        self.book_name, self.chapter, self.chapter_count = name, chapter, count
        self.refresh_title()

    def refresh_title(self) -> None:
        title = self.query_one('#book-title', Static)
        if self.app.size.width < 80:
            suffix = f' {self.chapter}/{self.chapter_count}'
            # Reserve the chapter position even when the book name needs an ellipsis.
            text = Text(self.book_name, no_wrap=True, overflow='ellipsis')
            text.truncate(max(1, title.size.width - len(suffix)), overflow='ellipsis')
            text.append(suffix)
        else:
            text = Text(f'{self.book_name}\nCHAPTER {self.chapter}  /  {self.chapter_count}')
        title.update(text)

    def on_resize(self) -> None:
        self.call_after_refresh(self.refresh_title)


class StatusBar(Static):
    pass
