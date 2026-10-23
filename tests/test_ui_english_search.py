"""Search translation uses fake backends and real Amharic scripture at both sizes."""

import asyncio

import pytest
from textual.widgets import Button, OptionList, Select, Static

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.translate.base import TranslationError
from ebible.ui.screens.search import QuerySummary
from ebible.ui.widgets.controls import TextInput


async def settle(app, pilot):
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.parametrize('submit', ['enter', 'button'])
async def test_submit_only_variants_paging_scope_refine_and_jump(running_app, monkeypatch, submit):
    app, pilot = running_app
    calls = []

    async def fake(service, query):
        calls.append(query)
        return ('ብርሃን', 'ብርሃኑ')  # Explicit fake response using Genesis word forms.

    monkeypatch.setattr('ebible.core.translate.service.TranslationService.translate_query', fake)
    await pilot.press('/')
    screen = app.screen
    entry = screen.query_one(TextInput)
    await pilot.press(*'light')
    await settle(app, pilot)
    assert calls == [] and not screen.results
    assert 'Enter or Search' in str(screen.query_one('#search-message', Static).content)
    if submit == 'enter':
        await pilot.press('enter')
    else:
        assert await pilot.click('#search-submit')
    await settle(app, pilot)
    assert app.screen is screen and calls == ['light']
    assert len(screen.results) == 40 and screen.results[0].ref == VerseRef(1, 1, 3)
    summary = screen.query_one(QuerySummary)
    assert summary.content.plain == 'Searched ብርሃን · ብርሃኑ · from “light”'
    first = screen.results
    assert await pilot.click('#search-more')
    await settle(app, pilot)
    assert len(screen.results) == 80 and screen.results[:40] == first and calls == ['light']
    assert len({r.ref for r in screen.results}) == 80
    screen.query_one('#search-scope', Select).value = 'nt'
    await settle(app, pilot)
    assert screen.results and all(r.ref.book_id >= 55 for r in screen.results)
    assert calls == ['light']
    # First term begins after "Searched "; clicking resolves its Rich metadata.
    assert await pilot.click(summary, offset=(10, 0))
    await settle(app, pilot)
    assert entry.value == 'ብርሃን' and not summary.display
    assert screen.results == app.scripture.search('ብርሃን', 'nt', limit=40)
    target = screen.results[0].ref
    await pilot.press('enter')
    await settle(app, pilot)
    assert app.screen is app.reader and app.reference == target


async def test_cache_survives_search_screen_not_restart_and_no_disk(
    running_app, monkeypatch, terminal_size
):
    app, pilot = running_app
    calls = []

    async def fake(service, query):
        calls.append(query)
        return ('ብርሃን',)

    monkeypatch.setattr('ebible.core.translate.service.TranslationService.translate_query', fake)
    from ebible.paths import config_dir, data_dir

    def personal_files():
        return {
            str(p): p.read_bytes()
            for root in (config_dir(), data_dir())
            for p in root.rglob('*')
            if p.is_file()
        }

    before = personal_files()
    for query in ('light', ' LIGHT '):
        await pilot.press('/')
        app.screen.query_one(TextInput).value = query
        await pilot.pause()
        await pilot.press('enter')
        await settle(app, pilot)
        assert app.screen.results
        await pilot.press('escape')
    assert calls == ['light'] and personal_files() == before
    assert app.query_translations == {('auto', 'light'): ('ብርሃን',)}
    restarted = EBibleApp()
    async with restarted.run_test(size=terminal_size):
        await restarted.ready.wait()
        assert not restarted.query_translations


@pytest.mark.parametrize('reduced', [False, True])
async def test_pending_shimmer_reduce_motion_dedup_scope_and_cancel(
    running_app, monkeypatch, reduced
):
    app, pilot = running_app
    await app.update_setting('reduce_motion', reduced)
    release = asyncio.Event()
    calls = []

    async def fake(service, query):
        calls.append(query)
        await release.wait()
        return ('ብርሃን',)

    monkeypatch.setattr('ebible.core.translate.service.TranslationService.translate_query', fake)
    await pilot.press('/')
    screen = app.screen
    clock = [100.0]
    screen.clock = lambda: clock[0]
    screen.query_one(TextInput).value = 'light'
    await pilot.pause()
    await pilot.press('enter')
    assert screen.pending_query == 'light' and not screen.results
    busy = screen.query_one('#search-busy', Static)
    assert busy.display and busy.region.y == screen.query_one(TextInput).region.y
    assert screen.query_one('#search-submit', Button).disabled
    clock[0] += 0.45
    screen.tick_busy()
    content = busy.content
    assert 'Translating…' == content.plain
    assert bool(content.spans) is not reduced
    await pilot.press('enter')
    screen.query_one('#search-scope', Select).value = 'nt'
    await pilot.pause()
    assert calls == ['light']
    release.set()
    await settle(app, pilot)
    assert screen.results and all(r.ref.book_id >= 55 for r in screen.results)
    assert screen.pending_query is None and not busy.display
    # A new query can be edited while fetching; its late result cannot replace the edit.
    release.clear()
    entry = screen.query_one(TextInput)
    entry.value = 'darkness'
    await pilot.pause()
    await pilot.press('enter')
    assert screen.pending_query == 'darkness'
    entry.value = 'እግዚአብሔር'
    await pilot.pause()
    release.set()
    await settle(app, pilot)
    assert screen.results == app.scripture.search('እግዚአብሔር', 'nt', limit=40)
    assert not screen.query_one(QuerySummary).display and not busy.display
    assert ('auto', 'darkness') not in app.query_translations


async def test_escape_during_query_and_mixed_raw_unchanged(running_app, monkeypatch):
    app, pilot = running_app
    release = asyncio.Event()
    calls = []

    async def fake(service, query):
        calls.append(query)
        await release.wait()
        return ('ብርሃን',)

    monkeypatch.setattr('ebible.core.translate.service.TranslationService.translate_query', fake)
    await pilot.press('/')
    screen = app.screen
    for query in ('ብርሃን light', '=God AND', '=light'):
        screen.query_one(TextInput).value = query
        await settle(app, pilot)
        await pilot.press('enter')
        await settle(app, pilot)
        assert not calls and app.screen is screen
    screen.query_one(TextInput).value = 'light'
    await pilot.pause()
    await pilot.press('enter', 'escape')
    assert app.screen is app.reader
    release.set()
    await pilot.pause()
    assert app.screen is app.reader and not app.query_translations


@pytest.mark.parametrize('failure', ['off', 'network', 'junk'])
async def test_query_errors_inline_retry_and_keyboard_refinement(running_app, monkeypatch, failure):
    app, pilot = running_app
    if failure == 'off':
        await app.update_setting('translation_backend', 'off')
    else:

        def fake(service, query):
            if failure == 'network':
                raise OSError('sk-ant-FAKE-ERROR-DO-NOT-RENDER-1234')
            raise TranslationError('No usable Amharic terms returned.')

        monkeypatch.setattr(
            'ebible.core.translate.service.TranslationService._translate_query', fake
        )
    await pilot.press('/')
    screen = app.screen
    screen.query_one(TextInput).value = 'light'
    await pilot.pause()
    await pilot.press('enter')
    await settle(app, pilot)
    message = str(screen.query_one('#search-message', Static).content)
    assert 'Settings' in message and 'sk-ant-' not in message and not screen.results
    assert not screen.query_one('#search-busy').display and not app.query_translations

    async def repaired(service, query):
        return ('ብርሃን', 'ብርሃኑ')

    monkeypatch.setattr(
        'ebible.core.translate.service.TranslationService.translate_query', repaired
    )
    await pilot.press('enter')
    await settle(app, pilot)
    assert screen.results
    summary = screen.query_one(QuerySummary)
    summary.focus()
    await pilot.press('right', 'enter')
    await settle(app, pilot)
    assert screen.query_one(TextInput).value == 'ብርሃኑ'
    assert not summary.display


async def test_translated_result_selection_jumps_to_valid_source(running_app, monkeypatch):
    app, pilot = running_app

    async def fake(service, query):
        return ('ብርሃን',)

    monkeypatch.setattr('ebible.core.translate.service.TranslationService.translate_query', fake)
    await pilot.press('/')
    screen = app.screen
    screen.query_one(TextInput).value = 'light'
    await pilot.pause()
    await pilot.press('enter')
    await settle(app, pilot)
    listing = screen.query_one('#search-results', OptionList)
    listing.focus()
    await pilot.press('enter')
    assert app.screen is app.reader and app.reference == VerseRef(1, 1, 3)
