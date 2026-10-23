"""Cover regression tests: real scripture, exact cells, actual Pilot input, fake time."""

import asyncio
from dataclasses import replace

import pytest
from rich.cells import cell_len
from textual.widgets import Switch

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.settings import Settings, load_settings, save_settings
from ebible.ui.screens.title import (
    ENTRANCE_DURATION,
    OPEN_DURATION,
    ORNAMENTS,
    Cover,
    TitleScreen,
    cover_art,
)
from ebible.ui.themes import THEMES

SIZES = ((40, 20), (50, 30), (74, 30), (120, 40))


async def ready(app, pilot):
    await asyncio.wait_for(app.ready.wait(), 5)
    await pilot.pause()


def freeze(screen, elapsed=0.0):
    screen.clock = lambda: 100.0 + elapsed
    screen.started = 100.0
    screen.motion_timer.pause()
    screen.tick()


@pytest.mark.parametrize('size', SIZES)
async def test_default_launch_db_epigraph_continue_and_return(size):
    app = EBibleApp()
    async with app.run_test(size=size) as pilot:
        await ready(app, pilot)
        title = app.screen
        assert isinstance(title, TitleScreen)
        assert title.continuing is False
        assert app.epigraph == app.scripture.verse(VerseRef(28, 118, 105)).text_am
        # Source follows the Ethiopian/Septuagint Psalm numbering, not English 119.
        assert len(app.scripture.chapter(28, 119)) == 7
        freeze(title)
        title.finish_entrance()
        lines, targets = title.art()
        assert 'Begin' in '\n'.join(line.plain for line in lines)
        assert 'Psalms 118:105' in '\n'.join(line.plain for line in lines)
        assert '119' not in '\n'.join(line.plain for line in lines)
        x, y, _, _ = targets[0]
        await pilot.click(Cover, offset=(x, y))
        assert title.phase == 'opening'
        freeze(title, OPEN_DURATION)
        await pilot.pause()
        assert app.screen is app.reader
        assert app.reference == VerseRef(1)
        await pilot.press('c')
        assert isinstance(app.screen, TitleScreen)
        app.screen.finish_entrance()
        await pilot.press('escape')
        assert app._exit


@pytest.mark.parametrize('reference,enabled', [(None, False), (VerseRef(58, 3, 16), True)])
async def test_launch_bypasses_cover(reference, enabled):
    save_settings(Settings(title_page_on_launch=enabled))
    app = EBibleApp(reference=reference)
    async with app.run_test() as pilot:
        await ready(app, pilot)
        assert app.screen is app.reader
        assert app.reference == (reference or VerseRef(1))


async def test_saved_position_reduce_motion_settings_and_help(userdata):
    ref = VerseRef(58, 3, 16)
    userdata.record_position(ref)
    save_settings(Settings(reduce_motion=True))
    app = EBibleApp()
    async with app.run_test(size=(40, 20)) as pilot:
        await ready(app, pilot)
        title = app.screen
        assert title.continuing
        assert title.progress == 1 and title.phase == 'rest'
        assert 'John 3:16' in '\n'.join(line.plain for line in title.art()[0])
        assert title.motion_timer._active.is_set() is False
        await pilot.press('enter')
        assert app.screen is app.reader and app.reference == ref
        await pilot.press('s')
        setting = app.screen.query_one('#setting-title_page_on_launch', Switch)
        setting.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(setting)
        assert load_settings().title_page_on_launch is False
        await pilot.press('escape', '?')
        link = app.screen.query_one('#help-cover')
        link.scroll_visible(animate=False)
        await pilot.pause()
        await pilot.click(link)
        assert isinstance(app.screen, TitleScreen)
    restarted = EBibleApp()
    async with restarted.run_test() as pilot:
        await ready(restarted, pilot)
        assert restarted.screen is restarted.reader and restarted.reference == ref


@pytest.mark.parametrize(
    'index,name,key',
    [
        (1, 'BooksScreen', 'b'),
        (2, 'SearchScreen', '/'),
        (3, 'PlansScreen', 'p'),
        (4, 'SettingsScreen', 's'),
    ],
)
async def test_links_tap_keyboard_and_escape(index, name, key):
    save_settings(Settings(reduce_motion=True))
    app = EBibleApp()
    async with app.run_test(size=(40, 20)) as pilot:
        await ready(app, pilot)
        title = app.screen
        x, y, _, _ = title.art()[1][index]
        await pilot.click(Cover, offset=(x, y))
        assert type(app.screen).__name__ == name
        await pilot.press('escape')
        assert app.screen is title
        await pilot.press(key)
        assert type(app.screen).__name__ == name
        await pilot.press('escape')
        title.selected = 0
        await pilot.press(*(['tab'] * index), 'enter')
        assert type(app.screen).__name__ == name


@pytest.mark.parametrize('kind', ['key', 'tap'])
async def test_animation_skip_consumes_input_and_reveals_reader(kind):
    app = EBibleApp()
    async with app.run_test(size=(50, 30)) as pilot:
        await ready(app, pilot)
        title = app.screen
        title.phase = 'entrance'
        freeze(title, 0.1)
        assert title.progress < 1
        if kind == 'key':
            await pilot.press('x')
        else:
            await pilot.click(Cover, offset=(25, 10))
        assert title.phase == 'rest' and title.progress == 1
        assert app.screen is title
        freeze(title)
        await pilot.press('enter')
        freeze(title, 0.3)
        assert title.wipe_offset == 25
        await pilot.pause()
        assert title.query_one(Cover).region.x == 25
        assert title.query_one(Cover).size.width == 25
        # Left half of reader is visibly present, not a second invented page.
        svg = app.export_screenshot()
        assert 'Genesis' in svg or 'ኦሪት' in svg
        if kind == 'key':
            await pilot.press('j')
        else:
            await pilot.click(Cover, offset=(1, 1))
        assert app.screen is app.reader
        assert app.reference.verse == 1 and not app.translating


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('theme', [theme.name for theme in THEMES])
async def test_all_frames_width_safe_theme_colours_and_timing(size, theme):
    app = EBibleApp(theme_name=theme)
    async with app.run_test(size=size) as pilot:
        await ready(app, pilot)
        title = app.screen
        assert all(cell_len(glyph) == 1 for glyph in ORNAMENTS)
        assert title.colours().effects.glow != title.colours().effects.panel
        title.phase = 'entrance'
        for step in range(25):
            freeze(title, step * ENTRANCE_DURATION / 24)
            lines, targets = title.art()
            assert len(lines) == size[1]
            assert all(cell_len(line.plain) == size[0] for line in lines)
            assert all(
                0 <= x1 < x2 <= size[0] and 0 <= y1 < y2 <= size[1] for x1, y1, x2, y2 in targets
            )
        assert title.phase == 'rest' and title.progress == 1
        # Every reveal frame crops exact cells and keeps a highlighted turning edge.
        await title.activate()
        for step in range(12):
            freeze(title, step * OPEN_DURATION / 12)
            await pilot.pause()
            cover = title.query_one(Cover)
            text = cover.render()
            assert all(cell_len(line) == cover.size.width for line in text.plain.splitlines())
            assert cover.region.right == size[0]
            if step:
                assert any(
                    span.style.bgcolor for span in text.spans if hasattr(span.style, 'bgcolor')
                )
        freeze(title, OPEN_DURATION)
        await pilot.pause()
        assert app.screen is app.reader
        assert not any(
            mod in key
            for node in [app, title, cover]
            for key in node._bindings.key_to_bindings
            for mod in ('ctrl+', 'alt+')
        )


async def test_timer_pauses_off_screen_and_resume_retains_position():
    app = EBibleApp()
    async with app.run_test() as pilot:
        await ready(app, pilot)
        title = app.screen
        clock = [100.0]
        title.clock = lambda: clock[0]
        title.phase = 'entrance'
        title.started = 99.8
        title.tick()
        progress = title.progress
        await app.open_page('books')
        clock[0] += 10
        title.tick()
        assert title.progress == progress
        assert not title.motion_timer._active.is_set()
        await pilot.press('escape')
        title.tick()
        assert title.progress == pytest.approx(progress)


def test_literal_text_no_markup_and_setting_validation(tmp_path):
    from ebible.ui.morph import palette
    from ebible.ui.themes import effect_colours

    theme = THEMES[0]
    colours = palette(
        theme.foreground, theme.secondary, theme.accent, theme.background, effect_colours(theme)
    )
    # Explicit synthetic text fixture, never scripture or a translation.
    text = '[bold]literal fixture[/bold]'
    lines, _ = cover_art(50, 30, 1, colours, text, 'Genesis 1', False, 0)
    assert text in '\n'.join(line.plain for line in lines)
    path = tmp_path / 'settings.json'
    assert Settings().title_page_on_launch
    path.write_text('{"title_page_on_launch": "false"}', encoding='utf-8')
    assert load_settings(path).title_page_on_launch
    save_settings(replace(Settings(), title_page_on_launch=False), path)
    assert not load_settings(path).title_page_on_launch


async def test_tap_on_revealed_reader_only_skips_and_close_is_tappable():
    app = EBibleApp()
    async with app.run_test(size=(50, 30)) as pilot:
        await ready(app, pilot)
        title = app.screen
        freeze(title)
        title.finish_entrance()
        await title.activate()
        freeze(title, 0.4)
        await pilot.pause()
        await pilot.click(title, offset=(3, 4))
        assert app.screen is app.reader
        assert not app.translating and app.reference == VerseRef(1)
        await pilot.press('c')
        title = app.screen
        title.finish_entrance()
        x, y, _, _ = title.art()[1][5]
        await pilot.click(Cover, offset=(x, y))
        assert app._exit


async def test_epigraph_and_settings_loaded_off_ui_thread(monkeypatch):
    import threading

    from ebible.core.scripture import ScriptureStore

    thread = threading.get_ident()
    seen = []
    read_verse = ScriptureStore.verse

    def verse(store, ref):
        if ref == VerseRef(28, 118, 105):
            seen.append(threading.get_ident())
        return read_verse(store, ref)

    monkeypatch.setattr(ScriptureStore, 'verse', verse)
    app = EBibleApp()
    async with app.run_test() as pilot:
        await ready(app, pilot)
        assert len(seen) == 1 and seen[0] != thread
        # Both preferences and epigraph come from the existing single background load.
        assert app.epigraph and app.settings.title_page_on_launch


def test_entrance_draws_from_corners_and_title_brightens():
    from ebible.ui.morph import palette
    from ebible.ui.themes import effect_colours

    theme = THEMES[0]
    colours = palette(
        theme.foreground, theme.secondary, theme.accent, theme.background, effect_colours(theme)
    )
    frames = [
        cover_art(50, 30, p, colours, 'Explicit text fixture', 'Genesis 1', False, 0)[0]
        for p in (0, 0.25, 0.6, 1)
    ]
    # At zero only the corners; each side grows from both ends before the title appears.
    assert frames[0][1].plain.count('═') == 0
    assert 0 < frames[1][1].plain.count('═') < frames[2][1].plain.count('═')
    assert frames[1][1].plain[2] == '═' and frames[1][1].plain[-3] == '═'
    from rich.console import Console

    console = Console()
    index = frames[0][6].plain.index('መ')
    initial = frames[0][6].get_style_at_offset(console, index)
    middle = frames[2][6].get_style_at_offset(console, index)
    final = frames[3][6].get_style_at_offset(console, index)
    assert initial.color.get_truecolor() == colours.effects.panel.rich_color.get_truecolor()
    assert initial.color != middle.color != final.color
    assert final.bold
