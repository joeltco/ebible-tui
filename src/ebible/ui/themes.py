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
    base: Color
    minimum: float


def effect_colours(theme: Theme) -> EffectColours:
    """Keep every effect in the palette's family, with light/dark polarity."""
    return _effect_colours(
        theme.accent or theme.primary,
        theme.panel or theme.surface or theme.background or ('black' if theme.dark else 'white'),
        theme.foreground or ('white' if theme.dark else 'black'),
        theme.dark,
        theme.background or ('black' if theme.dark else 'white'),
        theme.name == 'high-contrast',
    )


@lru_cache(maxsize=64)
def _effect_colours(
    accent: str, panel: str, foreground: str, dark: bool, background: str, high_contrast: bool
) -> EffectColours:
    colour, base = Color.parse(accent), Color.parse(panel)
    peak = colour.blend(Color.parse('white' if dark else foreground), 0.6)
    minimum = 7.1 if high_contrast else 3.1
    tint = readable(base.blend(colour, 0.35), (peak,), base, minimum)
    return EffectColours(peak, tint, base, Color.parse(background), minimum)


def contrast(first: Color, second: Color) -> float:
    """WCAG sRGB relative-luminance contrast, before terminal quantisation."""

    def luminance(colour: Color) -> float:
        channels = [channel / 255 for channel in colour[:3]]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    low, high = sorted((luminance(first), luminance(second)))
    return (high + 0.05) / (low + 0.05)


@lru_cache(maxsize=1024)
def readable(colour: Color, backgrounds: tuple[Color, ...], target: Color, minimum: float) -> Color:
    """Smallest 1/255 blend toward a theme anchor that clears every background."""
    for step in range(256):
        candidate = colour.blend(target, step / 255)
        if all(contrast(candidate, background) >= minimum for background in backgrounds):
            return candidate
    return target


def effect_muted(ink: Color, background: Color, effects: EffectColours) -> Color:
    return readable(ink.blend(background, 0.4), (background, effects.panel), ink, effects.minimum)


def entrance_colour(colour: Color, colours: EffectColours, progress: float) -> Color:
    """Fade from readable quiet ink, never from invisible text, in either polarity."""
    start = readable(colours.panel, (colours.panel, colours.base), colour, colours.minimum)
    return start.blend(colour, max(0.0, min(1.0, progress)))


@lru_cache(maxsize=64)
def _roles(
    primary: str,
    secondary: str,
    accent: str,
    ink: str,
    background: str,
    surface: str,
    panel: str,
    selection: str,
    high_contrast: bool,
) -> dict[str, str]:
    primary_c, secondary_c, accent_c, ink_c, base, surface_c, panel_c = map(
        Color.parse, (primary, secondary, accent, ink, background, surface, panel)
    )
    minimum = 7.1 if high_contrast else 4.6
    backgrounds = (base, surface_c, panel_c, base.blend(primary_c, 0.22).blend(ink_c, 0.05))
    secondary_c = readable(secondary_c, backgrounds, ink_c, minimum)
    border = readable(panel_c, (base, surface_c), primary_c, 3.1)
    thumb = readable(surface_c.blend(primary_c, 0.5), (surface_c,), primary_c, 3.1)
    colour, _, alpha = selection.partition(' ')
    selected = Color.parse(colour)
    if alpha.endswith('%'):
        selected = selected.with_alpha(float(alpha[:-1]) / 100)
    selected = surface_c.blend(ink_c, 0.05).blend(selected.with_alpha(1), selected.a)
    selected = readable(selected, (ink_c,), surface_c, minimum)
    return {
        'secondary': secondary_c.hex,
        'text-muted': secondary_c.hex,
        'text-disabled': secondary_c.hex,
        'role-border': border.hex,
        'role-scrollbar': thumb.hex,
        'input-selection-background': selected.hex,
        'input-selection-foreground': ink_c.hex,
    }


def role_variables(theme: Theme, variables: Mapping[str, str] | None = None) -> dict[str, str]:
    """Own the few framework defaults that failed the rendered audit; retain base hues."""
    generated = variables if variables is not None else theme.to_color_system().generate()
    return _roles(
        generated['primary'],
        generated['secondary'],
        generated['accent'],
        generated['foreground'],
        generated['background'],
        generated['surface'],
        generated['panel'],
        generated['input-selection-background'],
        theme.name == 'high-contrast',
    ).copy()
