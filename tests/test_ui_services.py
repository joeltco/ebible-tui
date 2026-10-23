import subprocess

from ebible.core.models import VerseRef


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
    await app.copy_verse(VerseRef(1), 'am')
    assert 'Could not copy' in app.last_message


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
    monkeypatch.setitem(namespace['smoke'].__globals__, 'cover_walk', fake_walk)
    await namespace['smoke'](tmp_path / 'screenshots')
    assert len(seen) == 30
    assert len({path for path, _, _ in seen}) == 30
    assert {size for _, _, size in seen} == {(40, 20), (50, 30), (74, 30), (120, 40)}
    assert all(not path.exists() for path, _, _ in seen)
    assert os.environ['XDG_CONFIG_HOME'] == original_config
    assert os.environ['XDG_DATA_HOME'] == original_data
    assert os.environ['NO_COLOR'] == '1'
    assert (
        len((tmp_path / 'screenshots' / 'manifest.txt').read_text(encoding='utf-8').splitlines())
        == 30
    )
