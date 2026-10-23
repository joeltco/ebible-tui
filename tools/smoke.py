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
from ebible.core.translate.base import TranslationError
from ebible.core.translate.service import TranslationService
from ebible.ui.screens.books import ChaptersScreen
from ebible.ui.widgets.controls import NoteArea, SecretInput, TextInput
from ebible.ui.widgets.verse_view import VerseView

# Deliberately fake credentials: never accepted by or sent to a real service.
SMOKE_KEYS = (
    'sk-ant-FAKE-SMOKE-NOT-REAL-1234',
    'sk-ant-FAKE-SMOKE-REPLACE-5678',
    'sk-ant-FAKE-SMOKE-ENV-9012',
    'sk-ant-INVALID FIXTURE',
)

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
        assert not any(
            mod in key
            for key in node._bindings.key_to_bindings
            for mod in ('ctrl+', 'alt+', 'super+')
        ), f'{node}: desktop-only binding'


async def click(pilot: Pilot[None], selector: str) -> None:
    pilot.app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(selector), f'Could not tap {selector}'
    await pilot.pause()


async def walk(out: Path, theme: str, size: tuple[int, int]) -> list[str]:
    app = EBibleApp(theme_name=theme)
    names: list[str] = []
    release = asyncio.Event()

    async def fixture_translate(service: TranslationService, ref: VerseRef) -> str:
        # Explicit smoke fixture, never a network call or claimed scripture translation.
        await release.wait()
        if ref.verse == 2:
            raise TranslationError(
                'Translation timed out. Check your connection, then press Enter to retry.'
            )
        return 'Temporary smoke translation fixture — session only.'

    with patch.object(TranslationService, 'translate_verse', fixture_translate):
        async with app.run_test(size=size) as pilot:
            await asyncio.wait_for(app.ready.wait(), 10)
            view = app.reader.query_one(VerseView)
            timeline = [100.0]
            view.clock = lambda: timeline[0]

            async def capture(name: str) -> None:
                await pilot.pause()
                check_layout(app)
                if name == 'reader' and size[0] < 80:
                    assert app.screen.query_one('#reading-scroll').content_size.height >= 24
                if size[0] < 80 and app.screen.query('.page-header'):
                    assert app.screen.query_one('.page-header').region.height == 1
                if name == 'theme-picker':
                    assert (
                        app.screen.query_one('#setting-theme SelectOverlay').content_size.height
                        >= 4
                    )
                filename = f'{theme}-{size[0]}x{size[1]}-{name}.svg'
                svg = app.export_screenshot()
                assert all(key not in svg for key in SMOKE_KEYS), 'Credential leaked in screenshot'
                (out / filename).write_text(svg, encoding='utf-8')
                names.append(filename)
                print(f'OK {filename}', flush=True)

            await capture('reader')
            await pilot.press('a')
            await capture('verse-actions')
            assert not app.screen.query('#copy-both')
            await pilot.press('escape')
            await pilot.press('enter')
            timeline[0] += 0.7
            view.tick()
            await capture('reader-shimmer')
            assert VerseRef(1) in app.translating
            release.set()
            await app.workers.wait_for_complete()
            timeline[0] += 0.5
            view.tick()
            await capture('reader-morph')
            timeline[0] += 0.5
            view.tick()
            await capture('reader-flourish')
            timeline[0] += 0.3
            view.tick()
            await capture('reader-translated')
            assert VerseRef(1) in app.translations
            await pilot.press('a')
            await capture('actions-translated')
            await pilot.press('escape', 'enter')
            timeline[0] += 0.5
            view.tick()
            await capture('reader-morph-reverse')
            timeline[0] += 0.5
            view.tick()
            await pilot.press('j', 'enter')
            await app.workers.wait_for_complete()
            await capture('reader-translation-error')
            assert VerseRef(1, 1, 2) in app.translation_errors
            app.translation_errors.clear()
            await app.navigate(VerseRef(1))
            await pilot.press('b')
            await capture('books')
            await app.push_screen(ChaptersScreen(1))
            await capture('chapters')
            await pilot.press('escape', 'escape', 'g')
            await capture('goto')
            app.screen.query_one(TextInput).value = 'ps 151'
            await click(pilot, '#open-reference')
            await capture('goto-error')
            await pilot.press('escape', 'a')
            await click(pilot, '#bookmark-verse')
            await click(pilot, '#highlight-gold')
            await click(pilot, '#note-verse')
            # Explicit temporary smoke fixture, not app sample data or invented scripture.
            real = app.scripture.verse(VerseRef(1)).text_am
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
            app.screen.query_one(TextInput).value = 'እግዚአብሔር'
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
            entry = app.screen.query_one(SecretInput)
            entry.value = SMOKE_KEYS[0]
            entry.scroll_visible(animate=False)
            await capture('settings-key-entry')
            await click(pilot, '#key-save')
            await capture('settings-key-saved')
            await click(pilot, '#key-replace')
            entry.value = SMOKE_KEYS[1]
            await capture('settings-key-replace')
            entry.value = SMOKE_KEYS[3]
            await click(pilot, '#key-save')
            await capture('settings-key-invalid')
            entry.value = SMOKE_KEYS[1]
            await click(pilot, '#key-save')
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': SMOKE_KEYS[2]}):
                await app.screen.refresh_key_status()
                await capture('settings-key-environment')
            await click(pilot, '#key-remove')
            await capture('settings-key-removed')
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
            await app.update_setting('verse_flow', 'paragraph')
            await capture('reader-paragraph')
            await pilot.press('enter')
            timeline[0] += 0.5
            view.tick()
            await capture('reader-paragraph-morph')
            timeline[0] += 0.5
            view.tick()
            await app.update_setting('verse_flow', 'lines')
            await app.navigate(VerseRef(15))
            await capture('reader-jubilees')
            await pilot.press('q')
    return names


async def smoke(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    with TemporaryDirectory(prefix='ebible-smoke-') as temporary:
        for theme in SMOKE_THEMES:
            for width, height in SMOKE_SIZES:
                root = Path(temporary) / f'{theme}-{width}x{height}'
                with patch.dict(
                    os.environ,
                    {'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_DATA_HOME': str(root / 'data')},
                ):
                    # Theme screenshots must exercise colour, even in a NO_COLOR CI shell.
                    os.environ.pop('NO_COLOR', None)
                    os.environ.pop('ANTHROPIC_API_KEY', None)
                    names.extend(await walk(out, theme, (width, height)))
    (out / 'manifest.txt').write_text('\n'.join(names) + '\n', encoding='utf-8')
    print(
        f'{len(names)} SVGs · {len(SMOKE_THEMES)} themes · {len(SMOKE_SIZES)} sizes · all screens and modals passed',
        flush=True,
    )
    print(f'Output: {out.resolve()}', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(smoke(args.out))


if __name__ == '__main__':
    main()
