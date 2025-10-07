from __future__ import annotations

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from ebible_tui.core import ChapterRef, list_books, list_chapters
from ebible_tui.core.bible.canon_en import BOOKS_EN


class NavPane(Static):
    class ChapterSelected(Message):
        BUBBLE = True

        def __init__(self, ref: ChapterRef) -> None:
            self.ref = ref
            super().__init__()

    books_view: ListView
    chapters_view: ListView

    # State fields for tracking selection and marquee scrolling
    _last_book_idx: int | None = None
    _book_label_cache: dict[int, str] = {}
    _scroll_text: str = ''
    _scroll_i: int = 0
    _scroll_width: int = 24

    def __init__(self) -> None:
        super().__init__()
        self._chapter_refs: list[ChapterRef] = []
        self._last_book_idx = None
        self._book_label_cache = {}

    def _en_title_for(self, label: str) -> str:
        # label like '01 - <name>'; prefer numeric index
        try:
            num = int(label.split(' ', 1)[0])
            return BOOKS_EN.get(num, '')
        except Exception:
            return ''

    def compose(self) -> ComposeResult:
        yield Static('[b]Books[/b]', id='nav-title')
        self.books_view = ListView(
            *[ListItem(Static(name)) for name in list_books()],
            id='books',
        )
        yield self.books_view
        yield Static(' ', id='book-en')
        yield Static('[b]Chapters[/b]', id='chapters-title')
        self.chapters_view = ListView(id='chapters')
        yield self.chapters_view

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view is self.books_view:
            item = event.item
            label_obj = item.query_one(Static).renderable
            label = getattr(label_obj, 'plain', str(label_obj))
            idx = self.books_view.index
            book_label = self._book_label_cache.get(idx, label) if idx is not None else label
            self.populate_chapters(book_label)
            event.stop()
        elif event.list_view is self.chapters_view:
            idx = self.chapters_view.index
            if idx is None or not (0 <= idx < len(self._chapter_refs)):
                return
            ref = self._chapter_refs[idx]
            self.post_message(self.ChapterSelected(ref))
            event.stop()

    def populate_chapters(self, book_name: str) -> None:
        self.chapters_view.clear()
        self._chapter_refs = list_chapters(book_name)
        for ref in self._chapter_refs:
            self.chapters_view.append(ListItem(Static(f'{ref.chapter_num:02d}')))
        if self._chapter_refs:
            self.chapters_view.index = 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view is self.books_view:
            # Restore previously highlighted item label (if any)
            try:
                prev_idx = self._last_book_idx
                if prev_idx is not None and 0 <= prev_idx < len(self.books_view.children):
                    prev_item = self.books_view.children[prev_idx]
                    if prev_idx in self._book_label_cache:
                        prev_item.query_one(Static).update(self._book_label_cache.pop(prev_idx))
            except Exception:
                pass

            # Get current highlighted label and index
            idx = self.books_view.index
            item = event.item
            label = ''
            if item is not None:
                try:
                    label_obj = item.query_one(Static).renderable
                    label = getattr(label_obj, 'plain', str(label_obj))
                except Exception:
                    label = ''

            # Cache original label for restoration
            if idx is not None:
                try:
                    if idx not in self._book_label_cache and label:
                        self._book_label_cache[idx] = label
                except Exception:
                    pass

            # Compute English name and inject into highlighted row (keep number)
            en = self._en_title_for(label)
            try:
                num_part = label.split(' ', 1)[0]
                prefix = f'{int(num_part):02d}'
            except Exception:
                prefix = label.split(' ', 1)[0] if label else ''
            shown = f'{prefix} - {en}' if en else label or ''
            if item is not None and shown:
                item.query_one(Static).update(f'[b]{shown}[/b]')

            self._last_book_idx = idx
            event.stop()
