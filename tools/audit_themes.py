"""Rendered-cell colour audit. Fixture labels are diagnostics, never scripture."""

import argparse
import asyncio
import csv
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rich.cells import cell_len
from textual.containers import Horizontal
from textual.widgets import Button, Static

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.ui.morph import Morph
from ebible.ui.screens.base import Page
from ebible.ui.themes import THEMES
from ebible.ui.widgets.controls import Choice, PassageList
from ebible.ui.widgets.controls import TextInput as Input
from ebible.ui.widgets.verse_view import VerseView

NS = {'s': 'http://www.w3.org/2000/svg'}


def rgb(s):
    return tuple(int(s[i : i + 2], 16) for i in (1, 3, 5))


def contrast(a, b):
    def lum(s):
        v = [x / 255 for x in rgb(s)]
        v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return sum(x * y for x, y in zip(v, (0.2126, 0.7152, 0.0722), strict=False))

    a, b = sorted((lum(a), lum(b)))
    return (b + 0.05) / (a + 0.05)


def cells(svg):
    root = ET.fromstring(svg)
    css = root.find('s:style', NS).text
    colours = dict(re.findall(r'\.([\w-]+)\s*\{\s*fill:\s*(#[\da-fA-F]{6})', css))
    group = next(g for g in root.findall('s:g', NS) if 'clip-terminal' in g.get('clip-path', ''))
    default_bg = root.find('s:rect', NS).get('fill')
    bg = {}
    for r in group.findall('s:rect', NS):
        if not r.get('fill', '').startswith('#'):
            continue
        x = round(float(r.get('x', 0)) / 12.2)
        y = round((float(r.get('y', 0)) - 1.5) / 24.4)
        for col in range(x, x + round(float(r.get('width', 0)) / 12.2)):
            bg[col, y] = r.get('fill')
    result = []
    for t in group.findall('.//s:text', NS):
        fg = colours.get(t.get('class'))
        content = ''.join(t.itertext())
        x = round(float(t.get('x', 0)) / 12.2)
        y = round((float(t.get('y', 0)) - 20) / 24.4)
        for char in content:
            if char.strip() and fg:
                result.append(
                    {
                        'x': x,
                        'y': y,
                        'text': char,
                        'fg': fg,
                        'bg': bg.get((x, y), default_bg),
                        'ratio': contrast(fg, bg.get((x, y), default_bg)),
                    }
                )
            x += cell_len(char)
    return result


class Controls(Page):
    def compose(self):
        yield Static('Diagnostic fixture · body', id='audit-body')
        yield Static('Diagnostic fixture · secondary', classes='muted', id='audit-muted')
        yield Static('SECTION HEADING', classes='eyebrow', id='audit-heading')
        yield Static('Enter', classes='key-chip', id='audit-key')
        with Horizontal(classes='button-row'):
            yield Button('Normal', id='audit-button')
            yield Button('Primary', variant='primary', id='audit-primary')
            yield Button('Disabled', disabled=True, id='audit-disabled')
        with Horizontal(classes='button-row'):
            yield Button('Warning', variant='warning', id='audit-warning')
            yield Button('Error', variant='error', id='audit-error')
            yield Button('Success', variant='success', id='audit-success')
        yield Input(placeholder='Placeholder fixture', id='audit-placeholder')
        yield Input(value='Cursor fixture', id='audit-input')
        yield Choice(
            [('First fixture', 'a'), ('Second fixture', 'b')],
            value='a',
            allow_blank=False,
            id='audit-select',
        )
        yield PassageList('First fixture', 'Second fixture', id='audit-options')


async def probe(out, themes=THEMES):
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for theme in themes:
        with (
            TemporaryDirectory(prefix='b11-') as d,
            patch.dict(os.environ, {'XDG_CONFIG_HOME': d + '/c', 'XDG_DATA_HOME': d + '/d'}),
        ):
            os.environ.pop('NO_COLOR', None)
            app = EBibleApp(reference=VerseRef(1), theme_name=theme.name)
            async with app.run_test(size=(50, 30), notifications=True) as pilot:
                await app.ready.wait()
                view = app.reader.query_one(VerseView)
                clock = [100.0]
                view.clock = lambda clock=clock: clock[0]
                view.motion_timer.pause()

                async def snap(state, frame=None, app=app, theme=theme, pilot=pilot):
                    await pilot.pause()
                    svg = app.export_screenshot()
                    name = (
                        f'{theme.name}-{state}'
                        + (f'-{frame:03d}' if frame is not None else '')
                        + '.svg'
                    )
                    (out / name).write_text(svg, encoding='utf-8')
                    data = cells(svg)
                    for c in data:
                        matches = [
                            w
                            for w in app.screen.walk_children()
                            if w.display and w.region.contains(c['x'], c['y'])
                        ]
                        if matches:
                            w = min(matches, key=lambda w: w.region.width * w.region.height)
                            c['role'] = w.id or w.__class__.__name__
                        else:
                            c['role'] = type(app.screen).__name__
                    # Compact exact pairs, with one representative character and region.
                    unique = {}
                    for c in data:
                        unique.setdefault((c['role'], c['fg'], c['bg']), c)
                    report.append(
                        {
                            'theme': theme.name,
                            'state': state,
                            'frame': frame,
                            'svg': name,
                            'pairs': list(unique.values()),
                        }
                    )

                await snap('reader')
                view.bookmarks = {1}
                view.notes = {1}
                view.update_verses({VerseRef(1)})
                await snap('markers')
                for colour in ('gold', 'green', 'red', 'blue', 'purple'):
                    view.highlights = {1: colour, 2: colour}
                    view.update_verses({VerseRef(1), VerseRef(1, 1, 2)})
                    await snap('highlight-' + colour)
                view.highlights = {}
                view.update_verses({VerseRef(1), VerseRef(1, 1, 2)})
                app.translating.add(VerseRef(1))
                view.fetch_started[VerseRef(1)] = 100.0
                for i in range(28):
                    clock[0] = 100 + i / 30
                    view.update_verses({VerseRef(1)})
                    await snap('shimmer', i)
                app.translating.clear()
                app.translations[VerseRef(1)] = (
                    'Explicit temporary English animation fixture, used only for colour measurement.'
                )
                app.visible_translations.add(VerseRef(1))
                view.morphs[VerseRef(1)] = Morph(0, 1, 101)
                for i in range(40):
                    clock[0] = 101 + i / 30
                    view.update_verses({VerseRef(1)})
                    await snap('forward', i)
                view.morphs[VerseRef(1)] = Morph(1, 0, 103)
                for i in range(31):
                    clock[0] = 103 + i / 30
                    view.update_verses({VerseRef(1)})
                    await snap('reverse', i)
                app.visible_translations.clear()
                view.morphs[VerseRef(1)] = Morph()
                view.update_verses({VerseRef(1)})
                await app.reader.action_verse_actions()
                await snap('actions')
                await app.update_setting('theme', 'parchment' if theme.dark else 'meskel')
                await snap('switch-modal-after')
                await app.update_setting('theme', theme.name)
                await pilot.press('escape')
                await app.open_page('search')
                await snap('search')
                search = app.screen
                search.query_one(Input).cursor_blink = False
                await app.workers.wait_for_complete()
                search.clock = lambda clock=clock: clock[0]
                clock[0] = 104.0
                # set_busy uses its own clock; replace module monotonic for deterministic capture.
                with patch('ebible.ui.screens.search.monotonic', lambda clock=clock: clock[0]):
                    search.set_busy('fixture')
                    for i in range(28):
                        clock[0] = 104 + i / 30
                        search.tick_busy()
                        await snap('query-shimmer', i)
                    await app.update_setting('reduce_motion', True)
                    search.tick_busy()
                    await snap('query-pending-reduced')
                    await app.update_setting('reduce_motion', False)
                    search.set_busy(None)
                from ebible.ui.screens.search import QuerySummary

                search.query_one(QuerySummary).show_terms('light', ('ብርሃን',))
                await snap('query-final')
                await app.update_setting('reduce_motion', True)
                await snap('query-reduced')
                await app.update_setting('reduce_motion', False)
                await app.update_setting('theme', 'parchment' if theme.dark else 'meskel')
                await snap('switch-terms-after')
                await app.update_setting('theme', theme.name)
                await pilot.press('escape')
                await app.open_page('books')
                await snap('books')
                await pilot.press('escape')
                await app.push_screen(Controls())
                await snap('controls')
                for control in (
                    'audit-button',
                    'audit-primary',
                    'audit-warning',
                    'audit-error',
                    'audit-success',
                ):
                    await pilot.hover('#' + control)
                    await snap(control + '-hover')
                    app.screen.query_one('#' + control).focus()
                    await snap(control + '-focus')
                entry = app.screen.query_one('#audit-input', Input)
                entry.focus()
                entry.cursor_blink = False
                from textual.widgets._input import Selection

                entry.selection = Selection(0, 5)
                await snap('input-selection')

                entry.selection = Selection.cursor(1)
                entry._cursor_visible = True
                await snap('input-cursor')
                await pilot.click('#audit-select')
                await snap('select-overlay')
                await pilot.press('escape')
                if isinstance(app.screen, Controls):
                    await app.pop_screen()
                for severity in ('information', 'warning', 'error'):
                    app.notify(
                        'Diagnostic notification fixture',
                        title='Diagnostic title',
                        severity=severity,
                        timeout=60,
                        markup=False,
                    )
                    await snap('toast-' + severity)
                    app.clear_notifications()
                    await pilot.pause()
                await app.show_title()
                title = app.screen
                title.motion_timer.pause()
                title.clock = lambda clock=clock: clock[0]
                title.phase = 'entrance'
                title.started = 110.0
                for i in range(25):
                    clock[0] = 110 + i / 30
                    title.tick()
                    await snap('cover-entrance', i)
                await title.activate()
                title.motion_timer.pause()
                for i in range(18):
                    clock[0] = title.started + i / 30
                    title.tick()
                    await snap('cover-opening', i)
                clock[0] = title.started + 0.6
                title.tick()
                await snap('cover-open-final')
                await app.update_setting('reduce_motion', True)
                await snap('reader-reduced')
                await app.show_title()
                await snap('cover-reduced')
            (out / 'measurements.json').write_text(json.dumps(report), encoding='utf-8')
            print(theme.name, len(report), flush=True)
    return report


def summarize(out, report, png=False):
    with (out / 'pairs.csv').open('w', encoding='utf-8', newline='') as handle:
        fields = ['theme', 'state', 'frame', 'role', 'text', 'fg', 'bg', 'ratio', 'x', 'y', 'svg']
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for capture in report:
            for pair in capture['pairs']:
                writer.writerow(
                    {**pair, **{key: capture[key] for key in ('theme', 'state', 'frame', 'svg')}}
                )
    if png:
        groups = {
            'contact': (
                'controls',
                'books',
                'cover-entrance-012',
                'switch-modal-after',
                'switch-terms-after',
                'forward-030',
            ),
            'motion': (
                'shimmer-014',
                'forward-015',
                'forward-034',
                'reverse-015',
                'query-shimmer-014',
                'cover-opening-009',
            ),
        }
        for theme in THEMES:
            for group, states in groups.items():
                images = []
                for state in states:
                    svg = out / f'{theme.name}-{state}.svg'
                    if not svg.exists():
                        continue
                    target = svg.with_suffix('.png')
                    subprocess.run(
                        ['rsvg-convert', '-o', str(target), str(svg)],
                        check=True,
                        capture_output=True,
                    )
                    images.append(str(target))
                if images:
                    subprocess.run(
                        [
                            'magick',
                            'montage',
                            *images,
                            '-thumbnail',
                            '420x',
                            '-tile',
                            '3x2',
                            '-geometry',
                            '+6+6',
                            str(out / f'{theme.name}-{group}.png'),
                        ],
                        check=True,
                        capture_output=True,
                    )


def smoke_pairs(directory):
    """Include every production screen's rendered pairs, not just diagnostic controls."""
    report = []
    for path in sorted(directory.glob('*.svg')):
        theme = next((t.name for t in THEMES if path.name.startswith(t.name + '-')), None)
        if theme is None:
            continue
        data = cells(path.read_text(encoding='utf-8'))
        unique = {}
        for cell in data:
            cell['role'] = path.stem
            unique.setdefault((cell['text'], cell['fg'], cell['bg']), cell)
        report.append(
            dict(theme=theme, state='smoke', frame=None, svg=str(path), pairs=list(unique.values()))
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument(
        '--png',
        action='store_true',
        help='Render control and motion contact sheets with system librsvg/ImageMagick',
    )
    parser.add_argument(
        '--smoke', type=Path, help='Also measure every SVG in this smoke output directory'
    )
    args = parser.parse_args()
    report = asyncio.run(probe(args.out))
    if args.smoke:
        report.extend(smoke_pairs(args.smoke))
        (args.out / 'measurements.json').write_text(json.dumps(report), encoding='utf-8')
    summarize(args.out, report, args.png)


if __name__ == '__main__':
    main()
