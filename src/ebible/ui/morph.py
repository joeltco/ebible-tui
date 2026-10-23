"""Clock-driven, reversible character reveal and literal theme-derived text effects."""

from dataclasses import dataclass
from functools import lru_cache

from rich.style import Style
from rich.text import Text
from textual.color import Color

from ebible.ui.themes import EffectColours

DURATION = 1.0
FRAME_INTERVAL = 1 / 30
SHIMMER_PERIOD = 0.9
SHIMMER_WIDTH = 8
EDGE_WIDTH = 12
FLOURISH_DURATION = 0.3


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

    def flourish(self, now: float) -> float:
        # Instant swaps have origin == target; reverse never flourishes.
        if self.target != 1.0 or self.origin >= 1.0:
            return 0.0
        elapsed = now - (self.started + (1 - self.origin) * DURATION)
        if elapsed < -1e-9 or elapsed >= FLOURISH_DURATION - 1e-9:
            return 0.0
        return 1 - max(0.0, elapsed) / FLOURISH_DURATION

    def animating(self, now: float) -> bool:
        return self.running(now) or self.flourish(now) > 0

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
    waiting: Color
    effects: EffectColours


@lru_cache(maxsize=64)
def palette(
    ink: str, translation: str, accent: str, background: str, effects: EffectColours
) -> Palette:
    foreground = Color.parse(ink)
    return Palette(
        foreground,
        Color.parse(translation),
        Color.parse(accent),
        foreground.blend(Color.parse(background), 0.4),
        foreground.blend(Color.parse(background), 0.18),
        effects,
    )


def morph_text(
    amharic: str, english: str, index: int, moving: bool, colours: Palette, flourish: float = 0.0
) -> Text:
    """Exactly english[:i] + amharic[i:], slicing Unicode characters, never markup."""
    index = max(0, min(index, max(len(amharic), len(english))))
    rest = colours.translation.blend(colours.effects.glow, max(0.0, min(1.0, flourish)))
    text = Text(english[:index], style=rest.hex)
    if moving:
        for offset in range(max(0, index - EDGE_WIDTH), min(index, len(english))):
            strength = (offset - index + EDGE_WIDTH + 1) / EDGE_WIDTH
            centre = max(0.0, (offset - index + 4) / 3)
            text.stylize(
                Style(
                    color=colours.translation.blend(colours.effects.glow, strength).hex,
                    bold=True if centre else None,
                    bgcolor=colours.effects.panel.blend(colours.effects.background, centre).hex
                    if centre
                    else None,
                ),
                offset,
                offset + 1,
            )
    text.append(amharic[index:], style=colours.muted.hex if moving else colours.ink.hex)
    return text


def shimmer_text(amharic: str, elapsed: float, colours: Palette) -> Text:
    text = Text(amharic, style=colours.waiting.hex)
    phase = (elapsed % SHIMMER_PERIOD) / SHIMMER_PERIOD
    start = round(phase * (len(amharic) + SHIMMER_WIDTH)) - SHIMMER_WIDTH
    for offset in range(max(0, start), min(len(amharic), start + SHIMMER_WIDTH)):
        distance = abs(offset - (start + (SHIMMER_WIDTH - 1) / 2))
        strength = min(1.0, (SHIMMER_WIDTH / 2 - distance) / 3)
        centre = min(1.0, max(0.0, 2 - distance))
        text.stylize(
            Style(
                color=colours.waiting.blend(colours.effects.glow, strength).hex,
                bold=True if centre else None,
                bgcolor=colours.effects.panel.blend(colours.effects.background, centre).hex
                if centre
                else None,
            ),
            offset,
            offset + 1,
        )
    return text
