"""Clock-driven, reversible character reveal and literal theme-derived text effects."""

from dataclasses import dataclass
from functools import lru_cache

from rich.style import Style
from rich.text import Text
from textual.color import Color

DURATION = 1.0
FRAME_INTERVAL = 1 / 30
SHIMMER_PERIOD = 1.4
EDGE_WIDTH = 6


@dataclass
class Morph:
    origin: float = 0.0
    target: float = 0.0
    started: float = 0.0

    def position(self, now: float) -> float:
        distance = max(0.0, now - self.started) / DURATION
        if self.target > self.origin:
            return min(self.target, self.origin + distance)
        return max(self.target, self.origin - distance)

    def running(self, now: float) -> bool:
        return self.position(now) != self.target

    def retarget(self, visible: bool, now: float, *, instant: bool = False) -> None:
        target = float(visible)
        if instant:
            self.origin = self.target = target
            self.started = now
        elif target != self.target:
            self.origin = self.position(now)
            self.target, self.started = target, now

    def index(self, now: float, amharic: str, english: str) -> int:
        return int(self.position(now) * max(len(amharic), len(english)) + 1e-9)


@dataclass(frozen=True)
class Palette:
    ink: Color
    translation: Color
    accent: Color
    muted: Color


@lru_cache(maxsize=64)
def palette(ink: str, translation: str, accent: str, background: str) -> Palette:
    foreground = Color.parse(ink)
    return Palette(
        foreground,
        Color.parse(translation),
        Color.parse(accent),
        foreground.blend(Color.parse(background), 0.4),
    )


def morph_text(amharic: str, english: str, index: int, moving: bool, colours: Palette) -> Text:
    """Exactly english[:i] + amharic[i:], slicing Unicode characters, never markup."""
    index = max(0, min(index, max(len(amharic), len(english))))
    text = Text(english[:index], style=colours.translation.hex)
    if moving:
        for offset in range(max(0, index - EDGE_WIDTH), min(index, len(english))):
            strength = (offset - index + EDGE_WIDTH + 1) / EDGE_WIDTH
            text.stylize(
                Style(color=colours.translation.blend(colours.accent, strength).hex),
                offset,
                offset + 1,
            )
    text.append(amharic[index:], style=colours.muted.hex if moving else colours.ink.hex)
    return text


def shimmer_text(amharic: str, elapsed: float, colours: Palette) -> Text:
    text = Text(amharic, style=colours.ink.hex)
    width = max(6.0, len(amharic) * 0.12)
    phase = (elapsed % SHIMMER_PERIOD) / SHIMMER_PERIOD
    edge = phase * (len(amharic) + 2 * width) - width
    for offset in range(max(0, int(edge - width)), min(len(amharic), int(edge + width) + 1)):
        strength = max(0.0, 1 - abs(offset - edge) / width) * 0.55
        text.stylize(
            Style(color=colours.ink.blend(colours.accent, strength).hex), offset, offset + 1
        )
    return text
