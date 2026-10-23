import asyncio
from dataclasses import replace

import pytest
from textual.widgets import Button, OptionList, Static

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.settings import save_settings
from ebible.ui.screens.books import ChaptersScreen
from ebible.ui.screens.goto import GoTo
from ebible.ui.screens.reader import ReaderScreen
from ebible.ui.screens.verse_actions import VerseActions
from ebible.ui.themes import THEMES, highlight_colour
from ebible.ui.widgets.controls import TextInput
from ebible.ui.widgets.verse_view import VerseLine, VerseView


def assert_phone_bindings(app):
    for node in [app, *app.screen_stack, *app.screen.walk_children()]:
        assert not any(
            mod in key
            for key in node._bindings.key_to_bindings
            for mod in ('ctrl+', 'alt+', 'super+')
        ), node


def assert_no_horizontal_overflow(app):
    for widget in app.screen.walk_children():
        if widget.display and widget.region.width:
            assert widget.region.x >= 0, widget
            assert widget.region.right <= app.size.width, (widget, widget.region)
            if widget.is_scrollable:
                assert widget.max_scroll_x == 0, widget


async def test_reader_navigation_selection_touch_and_boundaries(running_app):
    app, pilot = running_app
    assert isinstance(app.screen, ReaderScreen)
    assert app.reference == VerseRef(1)
    assert_phone_bindings(app)
    assert_no_horizontal_overflow(app)
    assert app.screen.query_one('#previous-chapter', Button).disabled
    await pilot.press('j', 'down', 'k')
    assert app.reference == VerseRef(1, 1, 2)
    assert app.reader.query_one('#verse-2', VerseLine).has_class('selected')
    await pilot.press('a')
    assert isinstance(app.screen, VerseActions)
    await pilot.press('escape')
    assert app.screen is app.reader
    await pilot.click('#verse-2')
    assert app.screen is app.reader
    await app.workers.wait_for_complete()
    assert app.reference in app.translation_errors
    await pilot.press('escape', 'right')
    assert app.reference == VerseRef(1, 2)
    await pilot.click('#previous-chapter')
    assert app.reference == VerseRef(1)
    await pilot.press('left')
    assert app.reference == VerseRef(1)
    await app.navigate(VerseRef(1, 50))
    await pilot.press('l')
    assert app.reference == VerseRef(2)
    await pilot.press('h')
    assert app.reference == VerseRef(1, 50)
    await app.navigate(VerseRef(81, app.chapter_counts[81]))
    await pilot.press('right')
    assert app.reference.book_id == 81
    assert app.screen.query_one('#next-chapter', Button).disabled
    await pilot.press('escape')
    assert not app._exit
    await pilot.press('q')
    assert app._exit


@pytest.mark.parametrize(
    ('key', 'screen_name'),
    [
        ('b', 'BooksScreen'),
        ('/', 'SearchScreen'),
        ('m', 'BookmarksScreen'),
        ('v', 'HighlightsScreen'),
        ('n', 'NotesScreen'),
        ('t', 'HistoryScreen'),
        ('p', 'PlansScreen'),
        ('s', 'SettingsScreen'),
        ('?', 'HelpScreen'),
        ('g', 'GoTo'),
        ('a', 'VerseActions'),
    ],
)
async def test_every_route_escape_and_no_modifiers(running_app, key, screen_name):
    app, pilot = running_app
    await pilot.press(key)
    await pilot.pause()
    assert app.screen.__class__.__name__ == screen_name
    assert_phone_bindings(app)
    assert_no_horizontal_overflow(app)
    if screen_name not in ('GoTo', 'SearchScreen', 'BooksScreen', 'SettingsScreen'):
        await pilot.press('q')
        assert not app._exit
    await pilot.press('escape')
    assert app.screen is app.reader
    await pilot.press('a')
    assert isinstance(app.screen, VerseActions)


async def test_books_keep_canon_order_and_amharic_filter(running_app):
    app, pilot = running_app
    await pilot.press('b')
    listing = app.screen.query_one(OptionList)
    ids = [
        listing.get_option_at_index(i).id
        for i in range(listing.option_count)
        if not listing.get_option_at_index(i).disabled
    ]
    assert ids == [f'book-{i}' for i in range(1, 82)]
    assert any(listing.get_option_at_index(i).disabled for i in range(listing.option_count))
    await pilot.pause()
    rendered = app.export_screenshot()
    assert 'LAW' in rendered and 'Genesis' in rendered
    app.screen.query_one(TextInput).value = 'ዘፍ'
    await pilot.pause()
    assert listing.option_count == 2
    listing.focus()
    await pilot.press('enter')
    assert isinstance(app.screen, ChaptersScreen)
    assert len(app.screen.query('#chapter-grid Button')) == 50
    assert_no_horizontal_overflow(app)
    await pilot.click('#chapter-2')
    assert app.reference == VerseRef(1, 2)
    await pilot.press('b')
    await app.push_screen(ChaptersScreen(28))
    await pilot.pause()
    assert len(app.screen.query('#chapter-grid Button')) == 150
    await pilot.press('escape')
    assert app.screen.__class__.__name__ == 'BooksScreen'


async def test_goto_validation_and_psalm_151_guidance(running_app):
    app, pilot = running_app
    await pilot.press('g')
    assert isinstance(app.screen, GoTo)
    for text, error in [
        ('john 99', '21 chapters'),
        ('ps 151', '150:7-14'),
        ('john 3:999', 'endpoint'),
    ]:
        app.screen.query_one(TextInput).value = text
        await pilot.press('enter')
        assert isinstance(app.screen, GoTo)
        assert error in str(app.screen.query_one('#reference-error', Static).content)
        assert app.reference == VerseRef(1)
    app.screen.query_one(TextInput).value = 'ዘፍ 2:3'
    await pilot.press('enter')
    assert app.reference == VerseRef(1, 2, 3)
    assert app.screen is app.reader
    assert not await app.navigate(VerseRef(28, 151))
    assert '150:7-14' in app.last_message
    assert app.reference == VerseRef(1, 2, 3)


async def test_theme_registration_and_centered_column(running_app):
    app, pilot = running_app
    assert {theme.name for theme in THEMES} <= set(app.available_themes)
    for theme in THEMES:
        assert all(
            getattr(theme, field)
            for field in (
                'primary',
                'secondary',
                'accent',
                'foreground',
                'background',
                'surface',
                'panel',
                'success',
                'warning',
                'error',
            )
        )
    assert highlight_colour('gold', True) != highlight_colour('gold', False)
    await app.update_setting('text_max_width', 40)
    await pilot.pause()
    view = app.reader.query_one(VerseView)
    assert view.size.width <= 40
    assert abs(view.region.x - (app.size.width - view.size.width) / 2) <= 1
    await app.update_setting('verse_numbers', False)
    assert not view.verse_text(app.reader.chapter_data.verses[0]).plain.startswith(' 1 ')
    await app.update_setting('verse_spacing', 'compact')
    assert view.has_class('compact')
    await app.update_setting('book_name_language', 'en')
    assert 'ኦሪት' not in str(app.reader.query_one('#book-title', Static).content)


async def test_resume_and_invalid_saved_position(terminal_size, userdata):
    userdata.record_position(VerseRef(58, 3, 16))
    app = EBibleApp()
    async with app.run_test(size=terminal_size) as pilot:
        await asyncio.wait_for(app.ready.wait(), 5)
        assert app.reference == VerseRef(58, 3, 16)
        await pilot.press('j')
    resumed = EBibleApp()
    async with resumed.run_test(size=terminal_size):
        await asyncio.wait_for(resumed.ready.wait(), 5)
        assert resumed.reference == VerseRef(58, 3, 17)
    userdata.record_position(VerseRef(28, 151))
    fallback = EBibleApp()
    async with fallback.run_test(size=terminal_size):
        await asyncio.wait_for(fallback.ready.wait(), 5)
        assert fallback.reference == VerseRef(1)
        assert '150:7-14' in fallback.last_message


async def test_cli_reference_and_theme_override_saved_defaults(terminal_size, userdata):
    from ebible.core.settings import Settings, load_settings

    save_settings(replace(Settings(), theme='parchment'))
    userdata.record_position(VerseRef(1, 2))
    app = EBibleApp(VerseRef(58, 3, 16), theme_name='lalibela')
    async with app.run_test(size=terminal_size):
        await asyncio.wait_for(app.ready.wait(), 5)
        assert app.reference == VerseRef(58, 3, 16)
        assert app.theme == 'lalibela'
        assert load_settings().theme == 'parchment'


async def test_paragraph_tap_and_cursor_scroll(running_app):
    app, pilot = running_app
    await app.update_setting('verse_flow', 'paragraph')
    await pilot.pause()
    await pilot.click('#paragraph', offset=(4, 0))
    assert app.screen is app.reader
    await app.workers.wait_for_complete()
    assert app.reference in app.translation_errors
    await pilot.press('escape')
    await app.navigate(VerseRef(28, 118))  # Long Amharic chapter scrolls at both sizes.
    await app.reader.select_verse(150)
    await pilot.pause()
    await pilot.wait_for_scheduled_animations()
    assert app.reader.query_one('#reading-scroll').scroll_y > 0
    assert app.reference.verse == 150


async def test_tab_navigation_and_button_activation(running_app):
    app, pilot = running_app
    assert app.focused is None
    await pilot.press('tab')
    assert isinstance(app.focused, Button)
    await pilot.press('b')
    before = app.focused
    await pilot.press('tab')
    assert app.focused is not before
    await pilot.press('escape', 'a')
    assert isinstance(app.screen, VerseActions)
    initial = app.focused
    await pilot.press('tab')
    assert app.focused is not initial
    assert_phone_bindings(app)


def test_only_one_theme_variable_stylesheet():
    import re
    from pathlib import Path

    sheets = list(Path('src/ebible').rglob('*.tcss'))
    assert len(sheets) == 1
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b', sheets[0].read_text(encoding='utf-8'))
