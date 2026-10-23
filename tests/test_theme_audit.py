"""The audit's WCAG thresholds apply to exported sRGB, not palette declarations."""

import ast
import io
import re
import runpy
from pathlib import Path

import pytest
from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text
from textual.color import Color
from textual.theme import BUILTIN_THEMES

from ebible.ui.morph import Morph, morph_text, palette, settle_text, shimmer_text
from ebible.ui.screens.title import EPIGRAPH, cover_art
from ebible.ui.themes import THEMES, effect_colours, role_variables

audit = runpy.run_path('tools/audit_themes.py')
cells, contrast, rgb = (audit[name] for name in ('cells', 'contrast', 'rgb'))

FIXTURE = 'Explicit English animation fixture [bold]literal[/bold].'


def rendered(text, colours, width=50):
    console = Console(file=io.StringIO(), record=True, width=width, color_system='truecolor')
    console.print(text)
    terminal = TerminalTheme(colours.background[:3], colours.ink[:3], [])
    return cells(console.export_svg(theme=terminal))


def signature(text, colours):
    return [(c['text'], c['fg'], c['bg']) for c in rendered(text, colours)]


def on_segment(colour, first, last):
    """RGB line segment within two quantisation levels; not a broad gamut box."""
    a, b, c = first[:3], last[:3], rgb(colour)
    direction = [y - x for x, y in zip(a, b, strict=True)]
    length = sum(d * d for d in direction)
    t = (
        0
        if not length
        else sum((z - x) * d for x, z, d in zip(a, c, direction, strict=True)) / length
    )
    t = min(1, max(0, t))
    return max(abs(z - (x + t * d)) for x, z, d in zip(a, c, direction, strict=True)) <= 2


@pytest.mark.parametrize('theme', THEMES, ids=lambda t: t.name)
def test_exported_animation_frames_family_contrast_endpoints_and_boundaries(theme, scripture):
    variables = theme.to_color_system().generate() | role_variables(theme)
    colours = palette(
        variables['foreground'],
        variables['secondary'],
        variables['accent'],
        variables['background'],
        effect_colours(theme),
    )
    am = scripture.verse(EPIGRAPH).text_am
    segments = [
        (colours.ink, colours.muted),
        (colours.ink, colours.waiting),
        (colours.waiting, colours.effects.glow),
        (colours.translation, colours.effects.glow),
        (colours.effects.panel, colours.effects.glow),
        (colours.effects.panel, colours.translation),
    ]
    segments += [
        (colours.ink.blend(colours.waiting, min(1, i / 30 / 0.12)), colours.effects.glow)
        for i in range(5)
    ]
    minimum = 7 if theme.name == 'high-contrast' else 3
    frames = []
    for state in (Morph(0, 1, 0), Morph(1, 0, 0)):
        for frame in range(40):
            now = frame / 30
            frames.append(
                morph_text(
                    am,
                    FIXTURE,
                    state.index(now, am, FIXTURE),
                    state.running(now),
                    colours,
                    state.flourish(now),
                )
            )
        instant = Morph()
        instant.retarget(bool(state.target), 0, instant=True)
        reduced = morph_text(am, FIXTURE, instant.index(0, am, FIXTURE), False, colours)
        assert signature(frames[-1], colours) == signature(reduced, colours)
    for frame in range(28):
        frames.append(shimmer_text(am, frame / 30, colours))
        frames.append(shimmer_text('Translating…', frame / 30, colours))
    for frame in range(25):
        lines, _ = cover_art(50, 30, frame / 24, colours, am, 'Genesis 1', False, 0)
        frames.append(Text('\n').join(lines))
    for text in frames:
        data = rendered(text, colours)
        assert data
        for cell in data:
            assert cell['ratio'] >= minimum, (theme.name, cell)
            assert (
                any(on_segment(cell['fg'], a, b) for a, b in segments)
                or cell['fg'] == colours.accent.hex.lower()
            ), cell
    static = morph_text(am, FIXTURE, 0, False, colours)
    assert signature(shimmer_text(am, 0, colours), colours) == signature(static, colours)
    # No discontinuity when a request completes at the centre of its fetch band.
    previous = shimmer_text(am, 0.45, colours)
    assert signature(settle_text(previous, static, 0, colours, Console()), colours) == signature(
        previous, colours
    )
    assert signature(settle_text(previous, static, 1, colours, Console()), colours) == signature(
        static, colours
    )
    # Whole-verse flourish starts and finishes at rest, not at the peak colour.
    state = Morph(0, 1, 0)
    end = max(len(am), len(FIXTURE))
    rest = signature(morph_text(am, FIXTURE, end, False, colours), colours)
    for now in (1, 1.3):
        assert (
            signature(morph_text(am, FIXTURE, end, False, colours, state.flourish(now)), colours)
            == rest
        )
    # Colour continuity just before the forward/reverse boundary, on unchanged letters.
    for before, after in ((0.999, 1.0), (0.001, 0.0)):
        a = morph_text(am, FIXTURE, int(end * before), True, colours)
        b = morph_text(am, FIXTURE, int(end * after), False, colours)
        for x, y in zip(rendered(a, colours), rendered(b, colours), strict=False):
            if x['text'] == y['text']:
                assert max(abs(u - v) for u, v in zip(rgb(x['fg']), rgb(y['fg']), strict=True)) < 32


@pytest.mark.parametrize('theme', THEMES, ids=lambda t: t.name)
def test_roles_contrast_on_every_used_background(theme):
    v = theme.to_color_system().generate() | role_variables(theme)
    for fg in ('foreground', 'secondary', 'text-muted', 'text-disabled'):
        for bg in ('background', 'surface', 'panel'):
            assert contrast(v[fg][:7], v[bg][:7]) >= 4.5, (theme.name, fg, bg)
    assert contrast(v['input-selection-foreground'], v['input-selection-background']) >= 4.5
    assert contrast(v['role-border'], v['surface'][:7]) >= 3
    assert contrast(v['role-scrollbar'], v['surface'][:7]) >= 3


def test_framework_themes_with_css_alpha_values_are_supported():
    for theme in BUILTIN_THEMES.values():
        assert all(Color.parse(value) for value in role_variables(theme).values())


def colour_literals(source, suffix):
    """Reject literal colours in styling positions; annotation IDs aren't styles."""
    problems = re.findall(
        r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b|\b(?:rgb|hsl)a?\(', source
    )
    if suffix == '.tcss':
        problems += re.findall(r'(?:color|background|tint)\s*:\s*(?!transparent\b)([a-z]+)', source)
        problems += re.findall(r'ansi_[a-z_]+', source)
        return problems
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == 'Color'
            and any(isinstance(arg, ast.Constant) for arg in node.args)
        ):
            problems.append('literal Color constructor')
        values = [
            k.value
            for k in node.keywords
            if k.arg
            in (
                'style',
                'color',
                'bgcolor',
                'foreground',
                'background',
                'primary',
                'secondary',
                'accent',
            )
        ]
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            'parse',
            'stylize',
            'stylize_before',
        ):
            values += node.args[:1]
        for value in values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                words = value.value.split()
                if set(words) - {'bold', 'italic', 'underline', 'reverse', 'none'}:
                    problems.append(value.value)
    return problems


def test_no_literal_colours_or_implicit_dim_styles_outside_themes():
    for path in Path('src').rglob('*'):
        if path.suffix in ('.py', '.tcss') and path.name != 'themes.py':
            assert not colour_literals(path.read_text(encoding='utf-8'), path.suffix), path


@pytest.mark.parametrize(
    'source,suffix',
    [
        ("Text('fixture', style='bold red')", '.py'),
        ("Color.parse('blue')", '.py'),
        ("Style(color='#123456')", '.py'),
        ("Text('fixture', style='dim')", '.py'),
        ('Button { color: ansi_blue; }', '.tcss'),
        ('Button { background: red; }', '.tcss'),
        ('Button { color: #abc; }', '.tcss'),
        ('Color(255, 0, 0)', '.py'),
        ("Theme(primary='blue')", '.py'),
    ],
)
def test_colour_lint_detects_regressions(source, suffix):
    assert colour_literals(source, suffix)
