from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    bible_dir: Path | None = None
    translator_path: Path | None = None
    timeout_sec: float = 30.0


def load_config() -> AppConfig:
    bd = os.environ.get('EBIBLE_BIBLE_DIR')
    tp = os.environ.get('EBIBLE_TRANSLATOR')
    to = float(os.environ.get('EBIBLE_TIMEOUT_SEC', '30'))
    return AppConfig(
        bible_dir=Path(bd) if bd else None, translator_path=Path(tp) if tp else None, timeout_sec=to
    )


# NOTE: UI should import from ebible_tui.core, not read env directly.
