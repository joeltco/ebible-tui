"""Explicit visual regression bounds for all six palettes (CIELAB Delta E 1976)."""

from math import dist

import pytest
from rich.style import Style
from textual.color import Color
from textual.theme import Theme

from ebible.ui.morph import Morph, morph_text, palette, shimmer_text
from ebible.ui.themes import THEMES, effect_colours


def lab(colour):
    # sRGB -> linear RGB -> D65 XYZ -> CIELAB. Delta E 76 is Euclidean Lab distance.
    channels = [v / 255 for v in (colour.r, colour.g, colour.b)]
    r, g, b = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    xyz = (
        (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047,
        r * 0.2126729 + g * 0.7151522 + b * 0.0721750,
        (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) / 1.08883,
    )
    x, y, z = [v ** (1 / 3) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29 for v in xyz]
    return 116 * y - 16, 500 * (x - y), 200 * (y - z)


def colours_for(theme):
    return palette(
        theme.foreground, theme.secondary, theme.accent, theme.background, effect_colours(theme)
    )


@pytest.mark.parametrize('theme', THEMES, ids=lambda theme: theme.name)
def test_edge_is_twelve_steps_bold_tinted_and_distinct(scripture, theme):
    colours = colours_for(theme)
    am = scripture.chapter(1, 1).verses[0].text_am
    text = morph_text(am, 'Explicit temporary English effect fixture.', 16, True, colours)
    edge = text.spans[:12]
    assert [(s.start, s.end) for s in edge] == [(i, i + 1) for i in range(4, 16)]
    assert len({s.style.color for s in edge}) == 12
    expected = Color.parse(theme.accent).blend(
        Color.parse('white' if theme.dark else theme.foreground), 0.6
    )
    assert edge[-1].style.color == Style(color=expected.hex).color
    # >=18 is deliberately well above just-noticeable Lab differences (~2–3).
    assert dist(lab(expected), lab(Color.parse(theme.secondary))) >= 18
    assert [s.start for s in edge if s.style.bold] == [13, 14, 15]
    backgrounds = [s.style.bgcolor for s in edge if s.style.bgcolor]
    assert len(backgrounds) == len(set(backgrounds)) == 3
    assert (
        backgrounds[-1]
        == Style(
            bgcolor=Color.parse(theme.panel).blend(Color.parse(theme.accent), 0.35).hex
        ).bgcolor
    )
    assert text.plain == 'Explicit temporary English effect fixture.'[:16] + am[16:]


@pytest.mark.parametrize('theme', THEMES, ids=lambda theme: theme.name)
def test_shimmer_has_eight_visible_steps_soft_centre_and_point_nine_period(scripture, theme):
    am = scripture.chapter(1, 1).verses[0].text_am
    colours = colours_for(theme)
    text = shimmer_text(am, 0.45, colours)
    assert text.plain == am and text.style == colours.waiting.hex
    assert text.style != colours.ink.hex  # Rest of the source is dimmed only while fetching.
    assert len(text.spans) == 8
    assert all(s.end == s.start + 1 for s in text.spans)
    assert len({s.style.color for s in text.spans}) == 4
    assert max(s.style.color == Style(color=colours.effects.glow.hex).color for s in text.spans)
    backgrounds = [s.style.bgcolor for s in text.spans if s.style.bgcolor]
    assert len(backgrounds) == 4 and len(set(backgrounds)) == 2
    assert text.spans == shimmer_text(am, 1.35, colours).spans
    assert shimmer_text(am, 0.2, colours).spans[0].start < text.spans[0].start
    assert text.spans[0].start < shimmer_text(am, 0.7, colours).spans[0].start


def test_flourish_is_one_forward_only_300ms_fade(scripture):
    state = Morph()
    state.retarget(True, 10)
    assert state.flourish(10.999) == 0
    am = scripture.chapter(1, 1).verses[0].text_am
    english = 'Explicit flourish fixture [red]literal[/red].'
    colours = colours_for(THEMES[0])
    for elapsed, strength in [(0, 1), (0.1, 2 / 3), (0.15, 0.5), (0.299, 1 / 300), (0.3, 0)]:
        now = 11 + elapsed
        assert state.flourish(now) == pytest.approx(strength)
        assert state.animating(now) == (strength > 0)
        text = morph_text(am, english, len(english), False, colours, state.flourish(now))
        assert text.plain == english and not text.spans
        actual = Color.parse(text.style)
        expected = colours.translation.blend(colours.effects.glow, strength)
        # Floating point timing may round one sRGB channel by one unit.
        assert max(abs(a - b) for a, b in zip(actual[:3], expected[:3], strict=True)) <= 1
    state.retarget(True, 12)  # Reconciliation cannot replay the pulse.
    assert state.flourish(12) == 0 and not state.animating(12)
    state.retarget(False, 12)
    assert state.flourish(12.2) == state.flourish(13) == 0
    assert not state.animating(13)
    state.retarget(True, 14)
    state.retarget(False, 14.5)  # An interrupted forward morph never finishes or pulses.
    assert state.flourish(15) == 0 and not state.animating(15)
    state.retarget(True, 16, instant=True)
    assert not state.animating(16) and state.flourish(16) == 0


def test_effect_palette_also_resolves_minimal_builtin_theme():
    for dark in (False, True):
        effect = effect_colours(Theme(name='explicit-test-fixture', primary='blue', dark=dark))
        assert isinstance(effect.glow, Color) and isinstance(effect.background, Color)
