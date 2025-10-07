from __future__ import annotations

from typing import Literal, NamedTuple

Lang = Literal['am', 'en']


class Verse(NamedTuple):
    num: int
    text: str


# Keep light; prefer using concrete dataclasses in submodules.
