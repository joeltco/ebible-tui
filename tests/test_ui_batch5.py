"""Product-direction regressions; every translation response is an explicit fake fixture."""

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from rich.style import Style
from textual.widgets import OptionList, Static

from ebible.app import EBibleApp
from ebible.core.models import VerseRef
from ebible.core.settings import load_settings
from ebible.core.translate.base import AlignmentError, TranslationError
from ebible.paths import config_dir, data_dir, settings_path
from ebible.ui.widgets.verse_view import Paragraph, VerseLine, VerseView

FIXTURE = 'Explicit temporary English translation fixture [literal].'


def content(app):
    return (
        '\n'.join(w.content.plain for w in app.reader.query(VerseLine))
        if app.settings.verse_flow == 'lines'
        else app.reader.query_one(Paragraph).content.plain
    )


@pytest.mark.parametrize('flow', ['lines', 'paragraph'])
async def test_enter_tap_session_toggle_pending_navigation_and_no_disk(
    running_app, monkeypatch, flow
):
    app, pilot = running_app
    await app.update_setting('verse_flow', flow)
    await app.update_setting('reduce_motion', True)
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def fake(service, ref):
        calls.append(ref)
        started.set()
        await finish.wait()
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake, raising=False)
    assert FIXTURE not in content(app)
    assert 'translated' not in content(app).lower()
    await pilot.press('enter')
    await asyncio.wait_for(started.wait(), 2)
    try:
        assert app.screen is app.reader
        assert 'Translating…' in content(app)
        await pilot.press('enter')
        assert calls == [VerseRef(1)]
        await pilot.press('j', 'l')
        assert app.reference == VerseRef(1, 2)
        assert 'Translating…' not in content(app)
    finally:
        finish.set()
    await app.workers.wait_for_complete()
    assert app.translations == {VerseRef(1): FIXTURE}
    assert FIXTURE not in content(app)
    await app.navigate(VerseRef(1))
    await pilot.pause()
    assert '◇ ' + FIXTURE in content(app)
    first = app.scripture.verse(VerseRef(1)).text_am
    assert first not in content(app)  # Translation replaces the source in place.
    await pilot.press('enter')
    assert FIXTURE not in content(app)
    selector = '#verse-1' if flow == 'lines' else '#paragraph'
    assert await pilot.click(selector, offset=(4, 0))
    assert app.screen is app.reader
    assert FIXTURE in content(app) and calls == [VerseRef(1)]
    translated = app.reader.query_one(VerseView).body_text(app.scripture.verse(VerseRef(1)))
    assert Style.parse(str(translated.style)).color is not None
    for root in (config_dir(), data_dir()):
        for file in root.rglob('*'):
            if file.is_file():
                assert FIXTURE.encode() not in file.read_bytes()


async def test_restart_forgets_translation_and_requires_new_request(terminal_size, monkeypatch):
    calls = []

    async def fake(service, ref):
        calls.append(ref)
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake, raising=False)
    for session in range(2):
        app = EBibleApp()
        async with app.run_test(size=terminal_size) as pilot:
            await app.ready.wait()
            await pilot.pause()
            assert not app.translations and FIXTURE not in content(app)
            await pilot.press('enter')
            await app.workers.wait_for_complete()
            assert app.translations[VerseRef(1)] == FIXTURE
            assert len(calls) == session + 1


@pytest.mark.parametrize(
    'failure',
    [
        None,
        TranslationError('Translation timed out. Check your connection.'),
        AlignmentError('Explicit shifted-number fixture'),
        OSError('Explicit network failure fixture'),
    ],
)
async def test_translation_errors_are_inline_actionable_and_retryable(
    running_app, monkeypatch, failure
):
    app, pilot = running_app
    await app.update_setting('reduce_motion', True)
    if failure is None:
        await app.update_setting('translation_backend', 'off')
    else:

        async def fail(service, ref):
            raise failure

        monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fail)
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    await pilot.pause()
    assert app.screen is app.reader
    assert not app.translating and not app.translations
    message = app.translation_errors[VerseRef(1)]
    assert message in content(app)
    assert 'retry' in message or 'Settings' in message
    if failure is None:
        assert 'ANTHROPIC_API_KEY' in message and 'translate-shell' in message

    async def success(service, ref):
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', success)
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    assert not app.translation_errors and FIXTURE in content(app)


async def test_actions_a_footer_and_copy_only_session_result(running_app, monkeypatch):
    app, pilot = running_app
    copied = []
    monkeypatch.setattr(app, 'copy_to_clipboard', copied.append)
    monkeypatch.setattr('ebible.app.shutil.which', lambda _: None)
    await pilot.press('a')
    assert app.screen.__class__.__name__ == 'VerseActions'
    assert not app.screen.query('#copy-en') and not app.screen.query('#copy-both')
    assert not app.screen.query('#translate-verse')
    await pilot.click('#copy-am')
    assert app.scripture.verse(VerseRef(1)).text_am in copied[-1]
    await pilot.press('escape')

    async def fake(service, ref):
        return FIXTURE

    monkeypatch.setattr('ebible.app.TranslationService.translate_verse', fake, raising=False)
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    await pilot.press('enter')  # Hidden, but still available for copying within this session.
    await pilot.click('#verse-actions')
    assert app.screen.query('#copy-both') and not app.screen.query('#copy-en')
    await pilot.click('#copy-both')
    assert 'Genesis 1:1' in copied[-1] and FIXTURE in copied[-1]
    assert app.scripture.verse(VerseRef(1)).text_am in copied[-1]
    count = len(copied)
    await app.copy_verse(VerseRef(1), 'en')
    await app.copy_verse(VerseRef(1, 1, 2), 'both')
    assert len(copied) == count


async def test_legacy_settings_ignored_and_ui_is_amharic_only(terminal_size):
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps(
            {
                'layout': 'parallel',
                'show_untranslated_placeholder': True,
                'theme': 'parchment',
                'book_name_language': 'en',
            }
        ),
        encoding='utf-8',
    )
    settings = load_settings()
    assert settings.theme == 'parchment' and settings.book_name_language == 'en'
    assert 'layout' not in asdict(settings) and 'show_untranslated_placeholder' not in asdict(
        settings
    )
    app = EBibleApp()
    async with app.run_test(size=terminal_size) as pilot:
        await app.ready.wait()
        await pilot.pause()
        await app.navigate(VerseRef(15))
        assert not app.reader.query('#chapter-notice')
        assert 'translated' not in content(app).lower()
        await pilot.press('s')
        assert not app.screen.query('#setting-layout')
        assert not app.screen.query('#setting-show_untranslated_placeholder')
        assert app.screen.query('#setting-book_name_language')
        await pilot.press('escape', '/')
        assert not app.screen.query('#search-language')
        app.screen.query_one('#search-input').value = 'LORD'
        await pilot.pause()
        await app.workers.wait_for_complete()
        assert not app.screen.results


async def test_search_uniform_gap_and_exact_snippet_whitespace(running_app):
    from ebible.ui.screens.search import snippet_text

    app, pilot = running_app
    await pilot.press('/')
    app.screen.query_one('#search-input').value = 'እግዚአብሔር'
    await pilot.pause()
    await app.workers.wait_for_complete()
    listing = app.screen.query_one(OptionList)
    assert listing.option_count > 5
    heights = set()
    for i in range(len(app.screen.results)):
        strips = listing._get_option_render(
            listing.get_option_at_index(i), listing.get_visual_style('option-list--option')
        )
        assert listing._heights[i] == len(strips)  # The blank row must actually be allocated.
        heights.add(len(strips))
        assert not strips[-1].text.strip()
        assert strips[-2].text.strip()  # Exactly one blank row, irrespective of wrapping.
    if app.size.width == 50:
        assert len(heights) > 1
    fixture = ' \t\x01match\x02  \n trailing '  # Explicit whitespace fixture.
    assert snippet_text(fixture).plain == fixture.replace('\x01', '').replace('\x02', '')


async def test_help_and_readme_describe_current_bindings(running_app):
    app, pilot = running_app
    await pilot.press('?')
    texts = [str(w.content) for w in app.screen.query(Static)]
    assert 'Translate / hide translation' in texts
    assert 'Verse actions' in texts and 'a' in texts
    assert not any('bundled text' in t or 'placeholder' in t for t in texts)
    readme = Path('README.md').read_text(encoding='utf-8')
    assert 'Enter' in readme and '`a`' in readme and 'session' in readme
    assert 'Translate this chapter' not in readme


@pytest.mark.parametrize('flow', ['lines', 'paragraph'])
async def test_translation_rebuild_with_pending_scroll_and_cursor(running_app, monkeypatch, flow):
    app, pilot = running_app
    await app.update_setting('verse_flow', flow)
    await app.reader.select_verse(2)
    await pilot.pause()
    view = app.reader.query_one(VerseView)
    removed, release = asyncio.Event(), asyncio.Event()
    original = view.remove_children

    async def wait_after_removal():
        await original()
        removed.set()
        await release.wait()

    monkeypatch.setattr(view, 'remove_children', wait_after_removal)
    rebuilding = asyncio.create_task(view.rebuild())
    await asyncio.wait_for(removed.wait(), 2)
    try:
        # Translation refreshes and resize can remove widgets while an older scroll
        # callback or new cursor input is queued on another message pump.
        view.reveal_selection()
        view.select(3)
        view.call_after_refresh(view.reveal_selection)
        await pilot.pause()
    finally:
        release.set()
        await rebuilding
    await pilot.pause()
    assert view.selected == 3
    if flow == 'lines':
        assert view.query_one('#verse-3').has_class('selected')
    else:
        assert view.query_one(Paragraph).content.plain
