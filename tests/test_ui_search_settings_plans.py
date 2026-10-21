import asyncio
from dataclasses import replace

import pytest
from textual.widgets import Button, OptionList, Select, Static, Switch

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.settings import Settings, load_settings, save_settings
from ebible.ui.screens.base import Confirm
from ebible.ui.screens.plans import PlansScreen
from ebible.ui.screens.search import SearchScreen
from ebible.ui.widgets.controls import TextInput
from ebible.ui.widgets.verse_view import VerseView


async def finish_search(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


async def test_search_plain_raw_error_scope_language_and_jump(running_app):
    app, pilot = running_app
    await pilot.press('/')
    screen = app.screen
    assert isinstance(screen, SearchScreen)
    for query in ["john's", 'God AND', '=God AND']:
        screen.query_one(TextInput).value = query
        await finish_search(app, pilot)
        message = str(screen.query_one('#search-message', Static).content)
        assert ('not valid' in message) == query.startswith('=')
    screen.query_one(TextInput).value = 'LORD'
    screen.query_one('#search-scope', Select).value = 'nt'
    screen.query_one('#search-language', Select).value = 'en'
    await finish_search(app, pilot)
    assert screen.results and all(
        r.ref.book_id >= 55 and r.language == 'en' for r in screen.results
    )
    assert screen.query_one('#search-results', OptionList).get_option_at_index(0).prompt.spans
    assert screen.query_one('#search-results', OptionList).option_count == len(screen.results)
    target = screen.results[0].ref
    screen.query_one(TextInput).focus()
    await pilot.press('enter')
    assert app.reference == target and app.screen is app.reader


async def test_search_stale_results_and_current_book(running_app, monkeypatch):
    app, pilot = running_app
    await app.navigate(VerseRef(58, 3, 16))
    await pilot.press('/')
    screen = app.screen
    screen.query_one('#search-scope', Select).value = 'book'
    screen.query_one(TextInput).value = 'እግዚአብሔር'
    await finish_search(app, pilot)
    assert screen.results and all(r.ref.book_id == 58 for r in screen.results)
    screen.query_one(TextInput).value = 'LORD'
    screen.query_one(TextInput).value = 'zzzzzzzzzzzzzzzzzzzzzzzz'
    await finish_search(app, pilot)
    assert not screen.results
    assert screen.query_one('#search-results', OptionList).option_count == 0
    await pilot.press('escape')
    assert app.screen is app.reader


async def test_search_jump_still_validates_result(running_app):
    from ebible.core.models import SearchResult

    app, pilot = running_app
    await pilot.press('/')
    await finish_search(app, pilot)
    app.screen.results = (
        SearchResult(VerseRef(28, 151), 'Explicit invalid temporary result fixture', 'en'),
    )
    from textual.widgets.option_list import Option

    listing = app.screen.query_one('#search-results', OptionList)
    listing.clear_options().add_option(Option('Temporary invalid reference fixture', id='result-0'))
    listing.highlighted = 0
    listing.focus()
    await pilot.press('enter')
    assert app.screen.__class__.__name__ == 'SearchScreen'
    assert '150:7-14' in app.last_message


async def test_settings_live_persistence_all_controls_and_restart(terminal_size):
    app = EBibleApp()
    async with app.run_test(size=terminal_size) as pilot:
        await asyncio.wait_for(app.ready.wait(), 5)
        await pilot.press('s')
        await pilot.pause()
        screen = app.screen
        choices = {
            'theme': 'parchment',
            'layout': 'parallel',
            'verse_flow': 'paragraph',
            'verse_spacing': 'compact',
            'book_name_language': 'en',
            'translation_backend': 'off',
        }
        for field, value in choices.items():
            screen.query_one(f'#setting-{field}', Select).value = value
            await pilot.pause()
            assert getattr(load_settings(), field) == value
        assert app.theme == 'parchment'
        for field, value in {
            'verse_numbers': False,
            'show_untranslated_placeholder': False,
            'haptic_feedback': True,
        }.items():
            screen.query_one(f'#setting-{field}', Switch).value = value
            await pilot.pause()
            assert getattr(load_settings(), field) == value
        width = screen.query_one('#setting-text_max_width', TextInput)
        width.value = '0'
        await pilot.pause()
        assert '20 to 240' in str(screen.query_one('#width-error', Static).content)
        assert load_settings().text_max_width == 100
        width.value = '60'
        await pilot.pause()
        assert load_settings().text_max_width == 60
        await pilot.press('escape')
        assert app.reader.query_one(VerseView).effective_layout == (
            'parallel' if terminal_size[0] >= 90 else 'interleaved'
        )
    restored = EBibleApp()
    async with restored.run_test(size=terminal_size):
        await asyncio.wait_for(restored.ready.wait(), 5)
        assert restored.theme == 'parchment'
        assert restored.settings == load_settings()
        assert restored.settings.text_max_width == 60
        assert restored.settings.haptic_feedback


@pytest.mark.parametrize(
    'theme',
    ['meskel', 'tewahedo', 'parchment', 'lalibela', 'midnight', 'high-contrast', 'textual-light'],
)
async def test_theme_switch_via_settings(running_app, theme):
    app, pilot = running_app
    await pilot.press('s')
    await pilot.pause()
    app.screen.query_one('#setting-theme', Select).value = theme
    await pilot.pause()
    assert app.theme == theme
    await pilot.press('escape')
    assert app.screen is app.reader


async def test_invalid_persisted_theme_falls_back(terminal_size):
    save_settings(replace(Settings(), theme='no-such-theme'))
    app = EBibleApp()
    async with app.run_test(size=terminal_size):
        await asyncio.wait_for(app.ready.wait(), 5)
        assert app.theme == 'meskel'


async def test_plan_start_mark_unmark_progress_day_jump_and_restart(running_app):
    app, pilot = running_app
    await pilot.press('p')
    await pilot.pause()
    screen = app.screen
    assert isinstance(screen, PlansScreen)
    assert screen.query_one('#mark-read', Button).disabled
    assert screen.query_one('#plan-readings', OptionList).option_count == len(screen.plan.day(1))
    await tap(pilot, '#start-plan')
    await tap(pilot, '#mark-read')
    state = app.userdata.plan_progress('canon-year')
    assert state.completed_days == frozenset({1})
    assert '1-day streak' in str(screen.query_one('#plan-summary', Static).content)
    assert 'READ' in str(screen.query_one('#plan-day', Static).content)
    await tap(pilot, '#mark-read')
    assert not app.userdata.plan_progress('canon-year').completed_days
    await tap(pilot, '#mark-read')
    await tap(pilot, '#next-day')
    assert screen.view_day == 2
    await tap(pilot, '#today-day')
    assert screen.view_day == 1
    await tap(pilot, '#start-plan')
    assert isinstance(app.screen, Confirm)
    await tap(pilot, '#cancel')
    assert app.userdata.plan_progress('canon-year').completed_days == frozenset({1})
    target = VerseRef(*screen.plan.day(1)[0])
    screen.query_one('#plan-readings', OptionList).focus()
    await pilot.press('enter')
    assert app.reference == target and app.screen is app.reader
    await pilot.press('p')
    await pilot.pause()
    assert app.screen.progress.completed_days == frozenset({1})
    await tap(pilot, '#start-plan')
    await tap(pilot, '#confirm')
    assert not app.userdata.plan_progress('canon-year').completed_days
    app.screen.query_one('#plan-choice', Select).value = 'gospels-30'
    await pilot.pause()
    assert app.screen.plan_id == 'gospels-30'
    assert app.screen.plan.days == 30


async def test_plan_jump_rejects_invalid_chapter(running_app):
    from ebible.core.plans import ReadingPlan

    app, pilot = running_app
    await pilot.press('p')
    await pilot.pause()
    screen = app.screen
    screen.plans[screen.plan_id] = ReadingPlan(
        screen.plan_id, 'Explicit invalid temporary plan fixture', (((28, 151),),)
    )
    await screen.reload()
    await pilot.pause()
    screen.query_one('#plan-readings', OptionList).focus()
    await pilot.press('enter')
    assert isinstance(app.screen, PlansScreen)
    assert '150:7-14' in app.last_message


async def tap(pilot, selector):
    pilot.app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause(0.3)


async def test_search_results_are_visible_and_tappable(running_app):
    app, pilot = running_app
    await pilot.press('/')
    app.screen.query_one(TextInput).value = 'LORD'
    await finish_search(app, pilot)
    screen = app.screen
    listing = screen.query_one('#search-results', OptionList)
    assert listing.option_count == len(screen.results) > 0
    assert listing.region.height > 0
    target = screen.results[0].ref
    await pilot.click('#search-results', offset=(2, 0))
    await pilot.pause()
    assert app.screen is app.reader and app.reference == target
