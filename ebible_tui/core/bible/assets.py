from __future__ import annotations

from pathlib import Path

from ebible_tui.core.config import load_config


def get_assets_dir() -> Path:
    cfg = load_config()
    if cfg.bible_dir:
        return cfg.bible_dir
    # bundled package assets fallback
    base = Path(__file__).resolve().parents[2] / 'assets'
    # UI currently expects assets/Bible81 packaged next to code
    return base  # e.g., .../core/assets


def resolve_bible81() -> Path:
    cfg = load_config()
    if cfg.bible_dir:
        return cfg.bible_dir
    return Path(__file__).resolve().parents[2] / 'assets' / 'Bible81'
