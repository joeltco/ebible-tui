"""Colours shared between the stylesheet and Rich renderables.

Text inside a Static is rendered by Rich, which does not see Textual CSS classes.
Those styles have to be real colour values, so they live here and are kept in
step with ebible.tcss by hand.
"""

from __future__ import annotations

from typing import Final

AM: Final = '#e8e2d4'       # Amharic — primary
EN: Final = '#9db4c0'       # English — secondary
NUM: Final = '#6b6255'      # verse numbers
HIT: Final = 'bold #d9a441' # search match
MISSING: Final = 'italic #5a544a'  # untranslated marker
REF: Final = '#8a8172'      # search result reference
