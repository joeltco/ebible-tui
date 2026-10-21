"""Resolve paths at call time; importing this module never creates directories."""

import os
from pathlib import Path


def _xdg(variable: str, fallback: Path) -> Path:
    value = os.environ.get(variable, '')
    # XDG specifies absolute paths; empty and relative values are ignored.
    return Path(value) / 'ebible' if value and Path(value).is_absolute() else fallback / 'ebible'


def config_dir() -> Path:
    return _xdg('XDG_CONFIG_HOME', Path.home() / '.config')


def data_dir() -> Path:
    return _xdg('XDG_DATA_HOME', Path.home() / '.local' / 'share')


def settings_path() -> Path:
    return config_dir() / 'settings.json'


def user_db_path() -> Path:
    return data_dir() / 'user.db'
