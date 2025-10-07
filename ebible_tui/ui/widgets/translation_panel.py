from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import ListItem, ListView, Static


class TranslationPanel(Static):
    """Dedicated translation output area shown below verses (scrollable)."""

    def __init__(self) -> None:
        super().__init__(id='translation-box')
        self._current_text: str = ''
        self.body: ListView

    def compose(self) -> ComposeResult:
        yield Static('[b]Translation[/b]', id='trans-title')
        self.body = ListView(id='trans-body')
        yield self.body

    def _set_body(self, text: str) -> None:
        # Replace body with a single wrapped Static inside a ListItem
        self.body.clear()
        self.body.append(ListItem(Static(text, expand=True)))

    def set_status(self, msg: str) -> None:
        """Set temporary status message like Translating...."""
        self._current_text = msg
        self._set_body(msg)

    def set_translation(self, text: str) -> None:
        """Update with the final translated text."""
        self._current_text = text
        self._set_body(text)

    def clear(self) -> None:
        self._current_text = ''
        self.body.clear()
