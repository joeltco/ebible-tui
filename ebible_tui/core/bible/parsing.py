from __future__ import annotations

import re

# Match lines like: "1. text" or "1) text" or "1 text"
_LINE_RE = re.compile(r'^\s*(\d{1,3})[\.\)]?\s+(.*\S)\s*$', re.UNICODE)


def parse_verses(text: str) -> list[tuple[int, str]]:
    verses: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        num = int(m.group(1))
        body = m.group(2).strip()
        verses.append((num, body))
    return verses
