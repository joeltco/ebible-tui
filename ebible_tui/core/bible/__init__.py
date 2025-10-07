from __future__ import annotations

from ebible_tui.core.bible.parsing import parse_verses

# Facade over existing core modules (non-breaking shim)
from ebible_tui.core.bible.refs import ChapterRef
from ebible_tui.core.reader import list_books, list_chapters, read_chapter

__all__ = ['ChapterRef', 'list_books', 'list_chapters', 'read_chapter', 'parse_verses']
