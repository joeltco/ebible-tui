#!/usr/bin/env python3
"""Walk every UI screen/modal at two sizes and three themes, using temporary data."""

import argparse
import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from textual.pilot import Pilot

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.ui.screens.books import ChaptersScreen
from ebible.ui.widgets.controls import NoteArea, TextInput

SMOKE_THEMES = ('meskel', 'parchment', 'lalibela')
SMOKE_SIZES = ((50, 30), (120, 40))


def check_layout(app: EBibleApp) -> None:
    """No off-screen horizontal controls or horizontally scrolling containers."""
    for widget in app.screen.walk_children():
        if widget.display and widget.region.width:
            assert widget.region.x >= 0, f'{widget}: negative horizontal position'
            assert widget.region.right <= app.size.width, f'{widget}: clips at right edge'
            if widget.is_scrollable:
                assert widget.max_scroll_x == 0, f'{widget}: horizontal overflow'
                assert widget.styles.scrollbar_size_vertical == 1, f'{widget}: wide scrollbar'
    for node in [app, *app.screen_stack, *app.screen.walk_children()]:
        assert not any(mod in key for key in node._bindings.key_to_bindings for mod in ('ctrl+', 'alt+', 'super+')), f'{node}: desktop-only binding'


async def click(pilot: Pilot[None], selector: str) -> None:
    pilot.app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(selector), f'Could not tap {selector}'
    await pilot.pause()


async def walk(out: Path, theme: str, size: tuple[int, int]) -> list[str]:
    app = EBibleApp(theme_name=theme)
    names: list[str] = []
    async with app.run_test(size=size) as pilot:
        await asyncio.wait_for(app.ready.wait(), 10)

        async def capture(name: str) -> None:
            await pilot.pause()
            check_layout(app)
            if name == 'reader' and size[0] < 80:
                assert app.screen.query_one('#reading-scroll').content_size.height >= 24
            if size[0] < 80 and app.screen.query('.page-header'):
                assert app.screen.query_one('.page-header').region.height == 1
            if name == 'theme-picker':
                assert app.screen.query_one('#setting-theme SelectOverlay').content_size.height >= 4
            filename = f'{theme}-{size[0]}x{size[1]}-{name}.svg'
            app.save_screenshot(filename, path=str(out))
            names.append(filename)
            print(f'OK {filename}', flush=True)

        await capture('reader')
        await pilot.press('b')
        await capture('books')
        await app.push_screen(ChaptersScreen(1))
        await capture('chapters')
        await pilot.press('escape', 'escape', 'g')
        await capture('goto')
        app.screen.query_one(TextInput).value = 'ps 151'
        await click(pilot, '#open-reference')
        await capture('goto-error')
        await pilot.press('escape', 'enter')
        await capture('verse-actions')
        await click(pilot, '#bookmark-verse')
        await click(pilot, '#highlight-gold')
        await click(pilot, '#note-verse')
        # Explicit temporary smoke fixture, not app sample data or invented scripture.
        real = app.scripture.verse(VerseRef(1)).english
        app.screen.query_one(NoteArea).load_text('Temporary smoke fixture\n\n' + real)
        await capture('note-editor')
        await pilot.press('escape')
        await capture('note-discard')
        await pilot.press('escape')
        await click(pilot, '#save-note')
        await pilot.press('escape')
        for name in ('bookmarks', 'highlights', 'notes', 'history'):
            await app.open_page(name)
            await capture(name)
            if name == 'bookmarks':
                await click(pilot, '#delete-entry')
                await capture('confirm-delete')
                await pilot.press('escape')
            await pilot.press('escape')
        await pilot.press('/')
        app.screen.query_one(TextInput).value = 'LORD'
        await pilot.pause()
        await app.workers.wait_for_complete()
        await capture('search')
        app.screen.query_one(TextInput).value = '=God AND'
        await pilot.pause()
        await app.workers.wait_for_complete()
        await capture('search-error')
        await pilot.press('escape', 'p')
        await click(pilot, '#start-plan')
        await click(pilot, '#mark-read')
        app.screen.query_one('#plan-scroll').scroll_home(animate=False)
        await capture('plans')
        await click(pilot, '#start-plan')
        await capture('confirm-restart')
        await pilot.press('escape', 'escape', 's')
        await capture('settings')
        await click(pilot, '#setting-theme SelectCurrent')
        await capture('theme-picker')
        # Escape is back on every screen, including when a Select overlay is open.
        await pilot.press('escape')
        if app.screen is not app.reader:
            await pilot.press('escape')
        await pilot.press('?')
        await capture('help')
        app.screen.query_one('#help-text').scroll_visible(animate=False, top=True)
        await capture('help-bindings')
        await pilot.press('escape')
        await app.update_setting('layout', 'parallel')
        await capture('reader-parallel')
        await app.update_setting('verse_flow', 'paragraph')
        await capture('reader-paragraph')
        await app.update_setting('verse_flow', 'lines')
        await app.navigate(VerseRef(15))
        await capture('reader-untranslated')
        await pilot.press('q')
    return names


async def smoke(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with TemporaryDirectory(prefix='ebible-smoke-') as temporary:
        for theme in SMOKE_THEMES:
            for width, height in SMOKE_SIZES:
                root = Path(temporary) / f'{theme}-{width}x{height}'
                with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_DATA_HOME': str(root / 'data')}):
                    # Theme screenshots must exercise colour, even in a NO_COLOR CI shell.
                    os.environ.pop('NO_COLOR', None)
                    names.extend(await walk(out, theme, (width, height)))
    (out / 'manifest.txt').write_text('\n'.join(names) + '\n', encoding='utf-8')
    print(f'{len(names)} SVGs · {len(SMOKE_THEMES)} themes · {len(SMOKE_SIZES)} sizes · all screens and modals passed', flush=True)
    print(f'Output: {out.resolve()}', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(smoke(args.out))


if __name__ == '__main__':
    main()
