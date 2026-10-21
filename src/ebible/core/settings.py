"""Validated settings, forgiving reads, atomic UTF-8 JSON writes."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal

from ebible.paths import settings_path


@dataclass(frozen=True, slots=True)
class Settings:
    theme: str = 'meskel'
    layout: Literal['amharic', 'english', 'interleaved', 'parallel'] = 'interleaved'
    verse_flow: Literal['lines', 'paragraph'] = 'lines'
    verse_numbers: bool = True
    verse_spacing: Literal['compact', 'comfortable'] = 'comfortable'
    book_name_language: Literal['am', 'en', 'both'] = 'both'
    text_max_width: int = 100
    translation_backend: Literal['auto', 'claude', 'google', 'off'] = 'auto'
    show_untranslated_placeholder: bool = True
    haptic_feedback: bool = False


_CHOICES: dict[str, set[str]] = {
    'layout': {'amharic', 'english', 'interleaved', 'parallel'},
    'verse_flow': {'lines', 'paragraph'},
    'verse_spacing': {'compact', 'comfortable'},
    'book_name_language': {'am', 'en', 'both'},
    'translation_backend': {'auto', 'claude', 'google', 'off'},
}


def _valid(name: str, value: object, default: object) -> bool:
    if type(value) is not type(default):
        return False
    if name in _CHOICES:
        return isinstance(value, str) and value in _CHOICES[name]
    if name == 'theme':
        return isinstance(value, str) and bool(value.strip()) and len(value) <= 100
    if name == 'text_max_width':
        return isinstance(value, int) and 20 <= value <= 240
    return True


def load_settings(path: Path | None = None) -> Settings:
    target = path if path is not None else settings_path()
    defaults = Settings()
    try:
        raw = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return defaults
    if not isinstance(raw, dict):
        return defaults
    values = asdict(defaults)
    for field in fields(defaults):
        value = raw.get(field.name)
        if _valid(field.name, value, values[field.name]):
            values[field.name] = value
    return Settings(**values)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    values = asdict(settings)
    defaults = asdict(Settings())
    if any(not _valid(k, v, defaults[k]) for k, v in values.items()):
        raise ValueError('Invalid settings')
    target = path if path is not None else settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', dir=target.parent, prefix='.settings-', delete=False
        ) as handle:
            temp = Path(handle.name)
            json.dump(values, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
