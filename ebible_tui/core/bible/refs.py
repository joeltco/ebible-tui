from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChapterRef:
    book: str
    chapter_num: int
    path: Path
