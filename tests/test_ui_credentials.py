"""All keys below are obvious test fixtures; no credential test uses the network."""

import os
import stat

import pytest
from rich.pretty import pretty_repr
from textual import events
from textual.widgets import Input, Static

from ebible.app import EBibleApp
from ebible.core.credentials import key_path, read_saved_key, save_key
from ebible.paths import settings_path
from ebible.ui.widgets.controls import SecretInput

FAKE = 'sk-ant-FAKE-PILOT-NOT-REAL-1234'
REPLACEMENT = 'sk-ant-FAKE-REPLACEMENT-NOT-REAL-5678'
ENV = 'sk-ant-FAKE-ENV-NOT-REAL-9012'


async def tap(app, pilot, selector):
    app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    assert await pilot.click(selector)
    await pilot.pause()


def assert_private(app, *keys):
    surfaces = [app.export_screenshot(), repr(app.settings), app.last_message]
    for widget in app.screen.walk_children():
        surfaces.extend([repr(widget), pretty_repr(widget), str(widget.render())])
        if isinstance(widget, Static):
            surfaces.append(str(widget.content))
    for key in keys:
        assert all(key not in surface for surface in surfaces)
        if settings_path().exists():
            assert key not in settings_path().read_text(encoding='utf-8')


async def test_save_replace_cancel_remove_restart_and_all_surfaces(
    terminal_size, monkeypatch, caplog
):
    def no_network(*args, **kwargs):
        pytest.fail('Saving a key must not translate or create a client')

    monkeypatch.setattr('ebible.core.translate.service.select_backend', no_network)
    for session in range(2):
        app = EBibleApp()
        async with app.run_test(size=terminal_size) as pilot:
            await app.ready.wait()
            await pilot.press('s')
            screen = app.screen
            entry = screen.query_one(SecretInput)
            assert entry.password and entry.value == ''
            if session == 0:
                assert 'No key — no backend' in str(screen.query_one('#key-source').content)
                entry.scroll_visible(animate=False)
                await pilot.pause()
                entry.focus()
                pasted = ' \n' + FAKE + '\r\n '
                paste = events.Paste(pasted)
                entry.post_message(paste)
                await pilot.pause()
                assert entry.value == pasted and paste.text == ''
                assert_private(app, FAKE)
                assert not key_path().exists()  # Typing/pasting does not save.
                await pilot.press('enter')
                await pilot.pause()
                assert key_path().read_text(encoding='utf-8') == FAKE
                assert stat.S_IMODE(key_path().stat().st_mode) == 0o600
                assert entry.value == '' and not screen.query_one('#key-editor').display
                assert screen.query_one('#key-mask').content == 'sk-ant-…1234'
                assert screen.query_one('#key-source').content == 'Using saved key'
                assert_private(app, FAKE)
                await tap(app, pilot, '#key-replace')
                assert entry.value == ''
                entry.value = REPLACEMENT
                assert_private(app, FAKE, REPLACEMENT)
                await tap(app, pilot, '#key-cancel')
                assert read_saved_key().value == FAKE and entry.value == ''
                await tap(app, pilot, '#key-replace')
                entry.value = REPLACEMENT
                await tap(app, pilot, '#key-save')
                assert read_saved_key().value == REPLACEMENT
                assert screen.query_one('#key-mask').content == 'sk-ant-…5678'
                await app.update_setting('verse_numbers', False)
                assert_private(app, FAKE, REPLACEMENT)
            else:
                assert screen.query_one('#key-mask').content == 'sk-ant-…5678'
                assert screen.query_one('#key-source').content == 'Using saved key'
                assert_private(app, FAKE, REPLACEMENT)
                await tap(app, pilot, '#key-remove')
                assert not key_path().exists()
                assert entry.value == '' and screen.query_one('#key-editor').display
                assert screen.query_one('#key-source').content == 'No key — no backend'
                entry.value = FAKE
                await pilot.press('escape')
                await pilot.pause()
                assert app.screen is app.reader and entry.value == ''
                assert not key_path().exists()
    assert all(key not in caplog.text for key in (FAKE, REPLACEMENT))
    assert 'ANTHROPIC_API_KEY' not in os.environ


async def test_environment_source_wins_and_removal_does_not_remove_environment(
    running_app, monkeypatch
):
    app, pilot = running_app
    save_key(FAKE)
    monkeypatch.setenv('ANTHROPIC_API_KEY', ENV)
    await pilot.press('s')
    assert app.screen.query_one('#key-source').content == 'Using key from environment'
    assert app.screen.query_one('#key-mask').content == 'sk-ant-…1234'
    assert_private(app, FAKE, ENV)
    await tap(app, pilot, '#key-remove')
    assert not key_path().exists()
    assert os.environ['ANTHROPIC_API_KEY'] == ENV
    assert app.screen.query_one('#key-source').content == 'Using key from environment'
    assert_private(app, FAKE, ENV)
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    monkeypatch.setattr('ebible.ui.screens.settings.shutil.which', lambda name: '/fixture/trans')
    await pilot.press('escape', 's')
    assert app.screen.query_one('#key-source').content == 'No key — using Google translate'
    app.screen.query_one('#setting-translation_backend').value = 'off'
    await pilot.pause()
    assert app.screen.query_one('#key-source').content == 'No key — no backend'


async def test_invalid_paste_and_disk_failures_are_inline_and_private(running_app, monkeypatch):
    app, pilot = running_app
    await pilot.press('s')
    entry = app.screen.query_one(SecretInput)
    for bad in ['wrong-prefix', FAKE + '\nextra', FAKE + ' internal', FAKE + '\textra']:
        entry.value = ''
        entry.post_message(events.Paste(bad))
        await pilot.pause()
        await tap(app, pilot, '#key-save')
        assert not key_path().exists()
        assert 'no whitespace' in str(app.screen.query_one('#key-error').content)
        assert_private(app, FAKE)
        assert not app.screen.query_one('#width-error').content
    entry.value = FAKE

    def fail(*args, **kwargs):
        raise OSError(FAKE)

    with monkeypatch.context() as patch:
        patch.setattr('ebible.core.credentials.os.replace', fail)
        await tap(app, pilot, '#key-save')
        assert 'Could not save key' in str(app.screen.query_one('#key-error').content)
        assert not key_path().exists()
        assert_private(app, FAKE)
    await tap(app, pilot, '#key-save')
    with monkeypatch.context() as patch:
        patch.setattr('pathlib.Path.unlink', fail)
        await tap(app, pilot, '#key-remove')
        assert 'Could not remove key' in str(app.screen.query_one('#key-error').content)
        assert key_path().exists()
        assert_private(app, FAKE)


async def test_input_event_reprs_have_no_secret(running_app, monkeypatch):
    app, pilot = running_app
    await pilot.press('s')
    entry = app.screen.query_one(SecretInput)
    entry.value = FAKE
    for kind in (Input.Changed, Input.Submitted, Input.Blurred):
        message = kind(entry, FAKE)
        # Post on an unmounted instance to inspect sanitization without triggering Save.
        other = SecretInput(id='fixture-secret')
        other.post_message(message)
        assert message.value == ''
        assert FAKE not in repr(message) and FAKE not in pretty_repr(message)
    assert_private(app, FAKE)
    # Capture Textual's event log *before* handlers run, including real app paste routing.
    from types import SimpleNamespace

    logged = []

    class EventLog:
        def verbosity(self, verbose):
            return lambda *args: logged.append(repr(args))

    monkeypatch.setattr('textual.message_pump.log', SimpleNamespace(event=EventLog()))
    entry.value = ''
    entry.focus()
    app.post_message(events.Paste(FAKE))
    await pilot.pause()
    assert entry.value == FAKE and logged
    assert any('SecretPaste' in message for message in logged)
    assert all(FAKE not in message for message in logged)
    await tap(app, pilot, '#key-save')
    assert all(FAKE not in message for message in logged)
    assert_private(app, FAKE)


async def test_saved_key_translation_worker_error_is_private(running_app, monkeypatch, caplog):
    import importlib
    from types import SimpleNamespace

    app, pilot = running_app
    save_key(FAKE)
    original = importlib.import_module
    received = []

    class FakeClient:
        def __init__(self, **kwargs):
            received.append(kwargs['api_key'])
            self.messages = self

        def create(self, **kwargs):
            raise OSError(FAKE)  # An SDK exception containing the credential must be sanitized.

        def close(self):
            pass

    monkeypatch.setattr(
        importlib,
        'import_module',
        lambda name: (
            SimpleNamespace(Anthropic=FakeClient) if name == 'anthropic' else original(name)
        ),
    )
    await pilot.press('enter')
    await app.workers.wait_for_complete()
    await pilot.pause()
    assert received == [FAKE]
    assert 'Claude request failed' in app.translation_errors[app.reference]
    assert_private(app, FAKE)
    assert FAKE not in caplog.text
