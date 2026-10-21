import asyncio
import subprocess

from ebible.core.models import VerseRef
from ebible.core.translate.base import TranslationError
from ebible.ui.widgets.verse_view import VerseView


async def test_copy_osc52_all_languages_and_machine_provenance(running_app, monkeypatch):
    app, _ = running_app
    monkeypatch.setattr('ebible.app.shutil.which', lambda name: None)
    copied = []
    monkeypatch.setattr(app, 'copy_to_clipboard', copied.append)
    verse = app.scripture.verse(VerseRef(1))
    for language in ('am', 'en', 'both'):
        await app.copy_verse(VerseRef(1), language)
        assert 'Genesis 1:1' in copied[-1]
        assert (verse.text_am in copied[-1]) == (language != 'en')
        assert (verse.english in copied[-1]) == (language != 'am')
    # Explicit temporary translation fixture; text comes from the real bundled DB.
    app.userdata.save_translations(15, 1, {1: verse.english}, 'fixture')
    await app.copy_verse(VerseRef(15), 'en')
    assert '◇ Machine translation' in copied[-1]
    await app.copy_verse(VerseRef(15, 1, 2), 'en')
    assert 'Not yet translated' in copied[-1]


async def test_termux_clipboard_and_haptic_workers(running_app, monkeypatch):
    import threading

    app, _ = running_app
    calls = []
    monkeypatch.setattr('ebible.app.shutil.which', lambda name: '/fixture/' + name)

    def run(command, **kwargs):
        calls.append((command, kwargs, threading.get_ident()))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr('ebible.app.subprocess.run', run)
    await app.copy_verse(VerseRef(1), 'am')
    command, options, thread_id = calls.pop()
    assert command == ['/fixture/termux-clipboard-set']
    assert options['encoding'] == 'utf-8' and options['timeout'] == 5
    assert thread_id != threading.get_ident()
    await app.toggle_bookmark(VerseRef(1))
    assert not calls
    await app.update_setting('haptic_feedback', True)
    await app.toggle_bookmark(VerseRef(1))
    assert calls[-1][0] == ['/fixture/termux-vibrate', '-d', '20']
    assert calls[-1][2] != threading.get_ident()

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired('fixture', 1)

    monkeypatch.setattr('ebible.app.subprocess.run', fail)
    await app.toggle_bookmark(VerseRef(1))
    assert app.userdata.bookmarks()
    await app.copy_verse(VerseRef(1), 'both')
    assert 'Could not copy' in app.last_message


async def test_translation_worker_refreshes_marked_live_english(running_app, monkeypatch):
    app, pilot = running_app
    await app.navigate(VerseRef(15))
    english = app.scripture.verse(VerseRef(1)).english

    async def translate(service, book, chapter):
        await asyncio.to_thread(
            service.userdata.save_translations, book, chapter, {1: english}, 'fixture'
        )
        return {1: english}

    monkeypatch.setattr('ebible.app.TranslationService.translate_chapter', translate)
    await pilot.press('enter')
    button = app.screen.query_one('#translate-verse')
    button.scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click('#translate-verse')
    await app.workers.wait_for_complete()
    assert '1 verse translated' in app.last_message
    assert not app.translation_running
    view = app.reader.query_one(VerseView)
    assert '◇ Machine' in view.verse_text(app.reader.chapter_data.verses[0], 'en').plain


async def test_translation_error_and_concurrent_navigation(running_app, monkeypatch):
    app, _ = running_app
    started, finish = asyncio.Event(), asyncio.Event()

    async def waiting(service, book, chapter):
        started.set()
        await finish.wait()
        raise TranslationError('Temporary test fixture: translation unavailable')

    monkeypatch.setattr('ebible.app.TranslationService.translate_chapter', waiting)
    worker = app.translate_current()
    await started.wait()
    assert app.translation_running
    await app.navigate(VerseRef(58, 3, 16))
    await app.translate_current().wait()
    assert 'already being translated' in app.last_message
    finish.set()
    await worker.wait()
    assert app.reference == VerseRef(58, 3, 16)
    assert not app.translation_running
    assert 'translation unavailable' in app.last_message


async def test_settings_write_failure_preserves_current_values(running_app, monkeypatch):
    app, _ = running_app
    original = app.settings

    def fail(*args, **kwargs):
        raise OSError('Explicit temporary write failure fixture')

    monkeypatch.setattr('ebible.app.save_settings', fail)
    await app.update_setting('theme', 'parchment')
    assert app.settings == original
    assert app.theme == original.theme
    assert 'Could not save' in app.last_message


async def test_smoke_isolates_and_restores_xdg_environment(tmp_path, monkeypatch):
    import os
    import runpy
    from pathlib import Path

    namespace = runpy.run_path('tools/smoke.py')
    original_config = os.environ['XDG_CONFIG_HOME']
    original_data = os.environ['XDG_DATA_HOME']
    seen = []

    async def fake_walk(out, theme, size):
        config = Path(os.environ['XDG_CONFIG_HOME'])
        data = Path(os.environ['XDG_DATA_HOME'])
        assert str(config) != original_config and str(data) != original_data
        assert 'ebible-smoke-' in str(config)
        assert 'NO_COLOR' not in os.environ
        seen.append((config, theme, size))
        return [f'{theme}-{size[0]}x{size[1]}-fixture.svg']

    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setitem(namespace['smoke'].__globals__, 'walk', fake_walk)
    await namespace['smoke'](tmp_path / 'screenshots')
    assert len(seen) == 6
    assert all(not path.exists() for path, _, _ in seen)
    assert os.environ['XDG_CONFIG_HOME'] == original_config
    assert os.environ['XDG_DATA_HOME'] == original_data
    assert os.environ['NO_COLOR'] == '1'
    assert (
        len((tmp_path / 'screenshots' / 'manifest.txt').read_text(encoding='utf-8').splitlines())
        == 6
    )
