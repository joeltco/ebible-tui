"""Ethiopian-inspired palettes; colour literals live here, never in the stylesheet."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from textual.color import Color
from textual.theme import Theme

from ebible.core.models import HighlightColour

THEMES = (
    Theme(
        name='meskel',
        primary='#c9a65c',
        secondary='#b5aa92',
        accent='#e0bd73',
        foreground='#e8dfcc',
        background='#171914',
        surface='#20231c',
        panel='#2b2e24',
        success='#a6bb86',
        warning='#d6b269',
        error='#dc9385',
        dark=True,
    ),
    Theme(
        name='tewahedo',
        primary='#8ab28a',
        secondary='#acb9a0',
        accent='#d8b665',
        foreground='#e1e6d7',
        background='#111d19',
        surface='#1a2a23',
        panel='#26382d',
        success='#9bc997',
        warning='#dfc279',
        error='#e39280',
        dark=True,
    ),
    Theme(
        name='parchment',
        primary='#795327',
        secondary='#675d4b',
        accent='#9a482f',
        foreground='#302a21',
        background='#f5eedc',
        surface='#eee4cd',
        panel='#e3d5b9',
        success='#3b633c',
        warning='#775619',
        error='#a1362c',
        dark=False,
    ),
    Theme(
        name='lalibela',
        primary='#c78d76',
        secondary='#bbae9f',
        accent='#e3b192',
        foreground='#e9dfd5',
        background='#231d1b',
        surface='#302724',
        panel='#40332d',
        success='#a3b18c',
        warning='#d9b579',
        error='#ee9e8b',
        dark=True,
    ),
    Theme(
        name='midnight',
        primary='#8b91a4',
        secondary='#9498aa',
        accent='#a7a0ba',
        foreground='#b8bbc7',
        background='#0c1018',
        surface='#121823',
        panel='#1c2331',
        success='#849e92',
        warning='#b3a37d',
        error='#be8d91',
        dark=True,
    ),
    Theme(
        name='high-contrast',
        primary='#ffffff',
        secondary='#dddddd',
        accent='#ffdf70',
        foreground='#ffffff',
        background='#000000',
        surface='#111111',
        panel='#222222',
        success='#a7ffb0',
        warning='#ffe280',
        error='#ffabab',
        dark=True,
    ),
)

_DARK_HIGHLIGHTS: dict[HighlightColour, str] = {
    'gold': '#e4c56e',
    'green': '#a5d9a3',
    'red': '#f1a69a',
    'blue': '#a6c8ef',
    'purple': '#d6b1eb',
}
_LIGHT_HIGHLIGHTS: dict[HighlightColour, str] = {
    'gold': '#70500c',
    'green': '#285c30',
    'red': '#972e26',
    'blue': '#235283',
    'purple': '#703b89',
}


def highlight_colour(colour: HighlightColour, dark: bool) -> str:
    return (_DARK_HIGHLIGHTS if dark else _LIGHT_HIGHLIGHTS)[colour]


def ordered_theme_names(available: Mapping[str, Theme]) -> tuple[str, ...]:
    custom = tuple(theme.name for theme in THEMES if theme.name in available)
    return custom + tuple(name for name in available if name not in custom)


@dataclass(frozen=True)
class EffectColours:
    glow: Color
    background: Color
    panel: Color


def effect_colours(theme: Theme) -> EffectColours:
    """Keep every effect in the palette's family, with light/dark polarity."""
    return _effect_colours(
        theme.accent or theme.primary,
        theme.panel or theme.surface or theme.background or ('black' if theme.dark else 'white'),
        theme.foreground or ('white' if theme.dark else 'black'),
        theme.dark,
    )


@lru_cache(maxsize=64)
def _effect_colours(accent: str, panel: str, foreground: str, dark: bool) -> EffectColours:
    colour, base = Color.parse(accent), Color.parse(panel)
    peak = colour.blend(Color.parse('white' if dark else foreground), 0.6)
    return EffectColours(peak, base.blend(colour, 0.35), base)
