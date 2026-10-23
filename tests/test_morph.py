"""Clock and colour assertions use real Amharic and explicitly marked English fixtures."""

import pytest
from rich.style import Style

from ebible.ui.morph import (
    DURATION,
    EDGE_WIDTH,
    FRAME_INTERVAL,
    Morph,
    morph_text,
    palette,
    shimmer_text,
)
from ebible.ui.themes import THEMES


@pytest.mark.parametrize(
    'english', ['Fixture.', 'Explicit temporary English fixture [bold]literal[/bold].' * 12]
)
def test_character_sequence_duration_reverse_and_interrupt(scripture, english):
    am = scripture.chapter(1, 1).verses[0].text_am
    colours = palette(
        THEMES[0].foreground, THEMES[0].secondary, THEMES[0].accent, THEMES[0].background
    )
    state = Morph()
    state.retarget(True, 10)
    indices = []
    for tick in range(31):
        now = 10 + tick * FRAME_INTERVAL
        i = state.index(now, am, english)
        indices.append(i)
        text = morph_text(am, english, i, state.running(now), colours)
        assert text.plain == english[:i] + am[i:]
    assert indices == sorted(indices)
    assert state.position(10 + DURATION) == 1 and not state.running(11)
    assert indices[-1] == max(len(am), len(english))
    state.retarget(False, 11)
    assert state.position(11.4) == pytest.approx(0.6)
    before = state.index(11.4, am, english)
    state.retarget(True, 11.4)
    assert state.index(11.4, am, english) == before
    assert state.position(11.5) == pytest.approx(0.7)
    assert state.position(11.8) == 1
    state.retarget(False, 12)
    assert state.position(13) == 0 and not state.running(13)


@pytest.mark.parametrize('theme', THEMES, ids=lambda theme: theme.name)
def test_edge_gradient_dim_suffix_and_literal_markup(scripture, theme):
    am = scripture.chapter(1, 1).verses[0].text_am
    english = 'Explicit [bold]fixture[/bold] & <literal> translation.'
    colours = palette(theme.foreground, theme.secondary, theme.accent, theme.background)
    text = morph_text(am, english, 15, True, colours)
    assert text.plain == english[:15] + am[15:]
    # The six revealed characters closest to the boundary each have their own colour.
    edge = text.spans[:EDGE_WIDTH]
    assert [(span.start, span.end) for span in edge] == [(i, i + 1) for i in range(9, 15)]
    assert len({span.style.color for span in edge}) == EDGE_WIDTH
    assert edge[-1].style.color == Style(color=theme.accent).color
    assert text.spans[-1].style == colours.muted.hex
    rest = morph_text(am, english, max(len(am), len(english)), False, colours)
    assert rest.plain == english and rest.style == colours.translation.hex
    assert not any(isinstance(span.style, Style) and span.style.bold for span in rest.spans)
    assert morph_text(am, english, 0, False, colours).plain == am


def test_shimmer_sweeps_repeats_and_never_changes_letters(scripture):
    from ebible.ui.morph import SHIMMER_PERIOD

    am = scripture.chapter(1, 1).verses[0].text_am
    theme = THEMES[0]
    colours = palette(theme.foreground, theme.secondary, theme.accent, theme.background)
    left = shimmer_text(am, SHIMMER_PERIOD * 0.3, colours)
    right = shimmer_text(am, SHIMMER_PERIOD * 0.7, colours)
    assert left.plain == right.plain == am
    assert left.spans[0].start < right.spans[0].start
    repeat = shimmer_text(am, SHIMMER_PERIOD * 1.3, colours)
    assert left.spans == repeat.spans


def test_instant_and_retarget_same_direction_does_not_restart():
    state = Morph()
    state.retarget(True, 10)
    state.retarget(True, 10.5)
    assert state.started == 10 and state.position(11) == 1
    state.retarget(False, 11.2, instant=True)
    assert state.position(11.2) == 0 and not state.running(11.2)
    state.retarget(True, 11.2, instant=True)
    assert state.position(11.2) == 1 and not state.running(11.2)


def test_literal_amharic_fixture_brackets_are_never_interpreted(scripture):
    # Explicit markup edge-case fixture based on the real Amharic verse.
    am = scripture.chapter(1, 1).verses[0].text_am + ' [red]fixture[/red]'
    theme = THEMES[0]
    colours = palette(theme.foreground, theme.secondary, theme.accent, theme.background)
    for text in (
        morph_text(am, 'English fixture', 3, True, colours),
        shimmer_text(am, 0.7, colours),
    ):
        assert '[red]fixture[/red]' in text.plain
        assert not any(span.style == 'red' for span in text.spans)
