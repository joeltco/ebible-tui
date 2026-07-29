"""UI tests that actually drive the app.

Unit tests never render markup, so a widget can pass every assertion and still
raise on screen. These run the real app through Pilot and assert on rendered
output.
"""

from __future__ import annotations

import pytest
from rich.console import Console

from ebible.config import Layout, Settings, config_path
from ebible.data.store import Store
from ebible.ui.app import EbibleApp
from ebible.ui.widgets.verse_pane import UNTRANSLATED, VersePane


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch) -> None:
    """Never touch the real ~/.config during tests."""
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'cfg'))


def render(table, width: int) -> str:
    console = Console(width=width, force_terminal=False, no_color=True)
    with console.capture() as cap:
        console.print(table)
    return cap.get()


# ------------------------------------------------------------------ config


def test_config_path_follows_xdg(tmp_path) -> None:
    assert str(tmp_path) in str(config_path())


def test_settings_roundtrip() -> None:
    s = Settings(layout=Layout.ENGLISH, book_id=40, chapter=3, verse_numbers=False)
    s.save()
    loaded = Settings.load()
    assert (loaded.layout, loaded.book_id, loaded.chapter) == (Layout.ENGLISH, 40, 3)


def test_corrupt_settings_falls_back_to_defaults() -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{not json', encoding='utf-8')
    assert Settings.load().layout is Layout.PARALLEL


def test_layout_cycles_through_all_three() -> None:
    seen = {Layout.PARALLEL}
    layout = Layout.PARALLEL
    for _ in range(3):
        layout = layout.next()
        seen.add(layout)
    assert seen == {Layout.PARALLEL, Layout.AMHARIC, Layout.ENGLISH}
    assert layout is Layout.PARALLEL  # returns to start


# ------------------------------------------------------------------ rendering


def test_verse_table_renders_both_languages() -> None:
    store = Store()
    book = store.book_by_slug('genesis')
    pane = VersePane()
    pane._book, pane._chapter = book, 1
    pane._verses = store.chapter(book.id, 1)[:2]
    pane._show_numbers = True
    out = render(pane._build_table(Layout.PARALLEL), 92)
    assert 'በመጀመሪያ' in out          # Amharic present
    assert UNTRANSLATED in out       # untranslated English marked, not blank
    assert '1' in out                # verse number present
    store.close()


def test_number_column_is_separated_from_text() -> None:
    """collapse_padding on Table.grid() glues the number to the verse."""
    store = Store()
    book = store.book_by_slug('genesis')
    pane = VersePane()
    pane._book, pane._chapter = book, 1
    pane._verses = store.chapter(book.id, 1)[:1]
    pane._show_numbers = True
    out = render(pane._build_table(Layout.AMHARIC), 60)
    assert '1በመጀመሪያ' not in out
    store.close()


# ------------------------------------------------------------------ app


@pytest.mark.asyncio
async def test_app_boots_and_navigates() -> None:
    app = EbibleApp()
    async with app.run_test(size=(100, 30)) as pilot:
        assert app.settings.chapter == 1
        await pilot.press('n')
        await pilot.pause()
        assert app.settings.chapter == 2
        await pilot.press('p')
        await pilot.pause()
        assert app.settings.chapter == 1


@pytest.mark.asyncio
async def test_parallel_collapses_on_narrow_terminal() -> None:
    app = EbibleApp()
    async with app.run_test(size=(100, 30)) as pilot:
        pane = app.query_one(VersePane)
        app.settings.layout = Layout.PARALLEL
        pane.set_layout(Layout.PARALLEL)
        await pilot.pause()
        assert pane.effective_layout is Layout.PARALLEL

        await pilot.resize_terminal(40, 24)
        await pilot.pause()
        # The request is unchanged; only what fits on screen differs.
        assert app.settings.layout is Layout.PARALLEL
        assert pane.effective_layout is Layout.AMHARIC


@pytest.mark.asyncio
async def test_modals_open_and_close() -> None:
    app = EbibleApp()
    async with app.run_test(size=(100, 30)) as pilot:
        for key in ('b', 'slash'):
            await pilot.press(key)
            await pilot.pause()
            assert app.screen.__class__.__name__ in ('BookPicker', 'SearchScreen')
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'Screen'


@pytest.mark.asyncio
async def test_navigation_at_canon_end_does_not_crash() -> None:
    app = EbibleApp()
    async with app.run_test(size=(100, 30)) as pilot:
        last = app.store.book(81)
        app._load(81, last.chapter_count)
        await pilot.pause()
        await pilot.press('n')  # past the end
        await pilot.pause()
        assert app.settings.book_id == 81
