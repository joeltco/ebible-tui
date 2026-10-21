"""All personal data and synthetic edge cases live in explicit temporary fixtures."""

import pytest

from ebible.core.scripture import ScriptureStore
from ebible.core.userdata import UserDataStore


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


@pytest.fixture
def scripture():
    return ScriptureStore()


@pytest.fixture
def userdata():
    return UserDataStore()
