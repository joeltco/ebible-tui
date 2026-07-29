"""User settings, persisted to the XDG config directory.

Paths are resolved at call time rather than import time so tests can redirect
HOME without the module having already cached a real user path.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class Layout(StrEnum):
    """How the two languages share the screen."""

    PARALLEL = 'parallel'  # Amharic | English, side by side
    AMHARIC = 'amharic'    # Amharic only
    ENGLISH = 'english'    # English only

    def next(self) -> Layout:
        order = (Layout.PARALLEL, Layout.AMHARIC, Layout.ENGLISH)
        return order[(order.index(self) + 1) % len(order)]


def config_dir() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME') or (Path.home() / '.config')
    return Path(base) / 'ebible'


def config_path() -> Path:
    return config_dir() / 'settings.json'


@dataclass
class Settings:
    layout: Layout = Layout.PARALLEL
    book_id: int = 1
    chapter: int = 1
    verse_numbers: bool = True

    @classmethod
    def load(cls) -> Settings:
        path = config_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            # A corrupt settings file must never stop the reader from opening.
            return cls()
        known = set(cls.__dataclass_fields__)
        data = {k: v for k, v in raw.items() if k in known}
        if 'layout' in data:
            try:
                data['layout'] = Layout(data['layout'])
            except ValueError:
                data.pop('layout')
        return cls(**data)

    def save(self) -> None:
        path = config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = asdict(self)
            payload['layout'] = str(self.layout)
            path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        except OSError:
            # Read-only home (some Termux setups) -- losing position is survivable.
            pass
