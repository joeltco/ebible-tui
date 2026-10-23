"""All personal data and synthetic edge cases live in explicit temporary fixtures."""

import pytest

from ebible.core.scripture import ScriptureStore
from ebible.core.userdata import UserDataStore


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch, request):
    import shutil

    which = shutil.which
    monkeypatch.setattr(shutil, 'which', lambda name: None if name == 'trans' else which(name))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.delenv('NO_COLOR', raising=False)
    if request.module.__name__.startswith('test_ui_'):
        from ebible.core.settings import Settings, save_settings

        save_settings(Settings(title_page_on_launch=False))


@pytest.fixture
def scripture():
    return ScriptureStore()


@pytest.fixture
def userdata():
    return UserDataStore()


@pytest.fixture(params=[(50, 30), (120, 40)], ids=['phone', 'desktop'])
def terminal_size(request):
    return request.param


@pytest.fixture
async def running_app(terminal_size):
    import asyncio

    from ebible.app import EBibleApp

    app = EBibleApp()
    async with app.run_test(size=terminal_size) as pilot:
        await asyncio.wait_for(app.ready.wait(), 5)
        await pilot.pause()
        yield app, pilot
