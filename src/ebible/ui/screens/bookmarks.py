"""Bookmarks and colour highlights share collection navigation."""

from ebible.ui.screens.collection import CollectionScreen


class BookmarksScreen(CollectionScreen):
    kind = 'bookmarks'


class HighlightsScreen(CollectionScreen):
    kind = 'highlights'
