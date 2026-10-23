"""Credential tests use deliberately fake keys and never contact a service."""

import importlib
import os
import stat
import traceback
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from rich.pretty import pretty_repr

from ebible.canon import BY_ID
from ebible.core.credentials import (
    CredentialError,
    active_key,
    key_path,
    read_saved_key,
    remove_key,
    save_key,
)
from ebible.core.settings import Settings, load_settings, save_settings
from ebible.core.translate.base import TranslationError
from ebible.core.translate.claude import ClaudeBackend
from ebible.core.translate.service import select_backend
from ebible.paths import settings_path

FAKE = 'sk-ant-FAKE-TEST-NOT-A-REAL-KEY-1234'
OTHER = 'sk-ant-FAKE-ENV-NOT-A-REAL-KEY-5678'


@pytest.mark.parametrize('umask', [0, 0o077])
def test_private_atomic_create_replace_and_remove(monkeypatch, umask):
    assert read_saved_key() is None and active_key() is None
    opened = []
    real_open, real_replace = os.open, os.replace

    def private_open(path, flags, mode):
        fd = real_open(path, flags, mode)
        opened.append((mode, stat.S_IMODE(os.fstat(fd).st_mode)))
        return fd

    def atomic_replace(source, target):
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        if target.exists():
            assert target.read_text(encoding='utf-8') == FAKE
        real_replace(source, target)

    def forbidden_chmod(*args):
        pytest.fail('Credentials must be private on creation, never chmod afterward')

    monkeypatch.setattr(os, 'open', private_open)
    monkeypatch.setattr(os, 'replace', atomic_replace)
    monkeypatch.setattr(os, 'chmod', forbidden_chmod)
    previous = os.umask(umask)
    try:
        save_key(FAKE)
        assert key_path().read_bytes() == FAKE.encode()
        save_key(OTHER)
    finally:
        os.umask(previous)
    assert opened == [(0o600, 0o600), (0o600, 0o600)]
    assert key_path().name == 'anthropic_key'
    assert stat.S_IMODE(key_path().stat().st_mode) == 0o600
    assert key_path().read_bytes() == OTHER.encode()
    assert list(key_path().parent.iterdir()) == [key_path()]
    remove_key()
    remove_key()
    assert not key_path().exists() and active_key() is None


@pytest.mark.parametrize(
    'bad',
    [
        '',
        'wrong-prefix',
        'sk-ant-',
        ' sk-ant- ',
        'sk-ant-FAKE\nMORE',
        'sk-ant-FAKE\tMORE',
        'sk-ant-FAKE\u00a0MORE',
    ],
)
def test_invalid_input_never_writes(bad):
    with pytest.raises(CredentialError, match='start with sk-ant-'):
        save_key(bad)
    assert not key_path().exists()
    save_key(FAKE)
    before = key_path().read_bytes()
    with pytest.raises(CredentialError):
        save_key(bad)
    assert key_path().read_bytes() == before


def test_precedence_auto_explicit_key_and_safe_reprs(monkeypatch, scripture):
    save_key(FAKE)
    saved = active_key()
    assert saved.value == FAKE and saved.source == 'saved'
    assert saved.masked == 'sk-ant-…1234'
    assert FAKE not in repr(saved) and FAKE not in pretty_repr(saved)
    assert isinstance(select_backend(), ClaudeBackend)
    monkeypatch.setenv('ANTHROPIC_API_KEY', OTHER)
    assert active_key().value == OTHER and active_key().source == 'environment'
    assert read_saved_key().value == FAKE
    requests = []
    original = importlib.import_module

    class FakeClient:
        def __init__(self, **kwargs):
            requests.append(kwargs)
            self.messages = self

        def create(self, **kwargs):
            return SimpleNamespace(
                stop_reason='end_turn',
                content=[
                    SimpleNamespace(type='text', text='1. Explicit temporary translation fixture')
                ],
            )

        def close(self):
            pass

    monkeypatch.setattr(
        importlib,
        'import_module',
        lambda name: (
            SimpleNamespace(Anthropic=FakeClient) if name == 'anthropic' else original(name)
        ),
    )
    context = {v.verse: v.text_am for v in scripture.chapter(1, 1)}
    select_backend().translate_verse(BY_ID[1], 1, context, 1)
    assert requests[-1] == {'api_key': OTHER, 'timeout': 30.0, 'max_retries': 0}
    assert os.environ['ANTHROPIC_API_KEY'] == OTHER
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    select_backend('claude').translate_verse(BY_ID[1], 1, context, 1)
    assert requests[-1]['api_key'] == FAKE
    assert 'ANTHROPIC_API_KEY' not in os.environ
    monkeypatch.setenv('ANTHROPIC_API_KEY', '')
    assert active_key().value == FAKE
    assert select_backend('off') is None
    remove_key()
    assert active_key() is None and select_backend() is None


def test_settings_json_and_repr_never_contain_key():
    save_key(FAKE)
    save_settings(Settings(theme='parchment'))
    assert FAKE not in settings_path().read_text(encoding='utf-8')
    assert FAKE not in repr(load_settings())
    assert 'api_key' not in asdict(load_settings())


def test_atomic_failure_preserves_old_key_without_exception_or_temp_leaks(monkeypatch):
    save_key(FAKE)

    def fail(*args):
        raise OSError(OTHER)

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(CredentialError) as error:
        save_key(OTHER)
    assert OTHER not in ''.join(traceback.format_exception(error.value))
    assert key_path().read_bytes() == FAKE.encode()
    assert list(key_path().parent.iterdir()) == [key_path()]


@pytest.mark.parametrize('operation', ['read', 'remove'])
def test_file_errors_do_not_echo_exception_details(monkeypatch, operation):
    from pathlib import Path

    def fail(*args, **kwargs):
        raise OSError(FAKE)

    monkeypatch.setattr(Path, 'read_text' if operation == 'read' else 'unlink', fail)
    with pytest.raises(CredentialError) as error:
        (read_saved_key if operation == 'read' else remove_key)()
    assert FAKE not in ''.join(traceback.format_exception(error.value))
    monkeypatch.setenv('ANTHROPIC_API_KEY', OTHER)
    assert active_key().value == OTHER  # An unreadable saved file cannot defeat env precedence.


@pytest.mark.parametrize('stage', ['construct', 'request', 'close', 'stop_reason'])
def test_sdk_failures_never_expose_credentials(monkeypatch, scripture, caplog, stage):
    save_key(FAKE)
    original = importlib.import_module

    class FailingClient:
        def __init__(self, **kwargs):
            if stage == 'construct':
                raise RuntimeError(FAKE)
            self.messages = self

        def create(self, **kwargs):
            if stage == 'request':
                raise RuntimeError(FAKE)
            return SimpleNamespace(
                stop_reason=FAKE if stage == 'stop_reason' else 'end_turn',
                content=[
                    SimpleNamespace(type='text', text='1. Explicit temporary translation fixture')
                ],
            )

        def close(self):
            if stage == 'close':
                raise RuntimeError(FAKE)

    monkeypatch.setattr(
        importlib,
        'import_module',
        lambda name: (
            SimpleNamespace(Anthropic=FailingClient) if name == 'anthropic' else original(name)
        ),
    )
    context = {v.verse: v.text_am for v in scripture.chapter(1, 1)}
    backend = select_backend()
    assert FAKE not in repr(backend)
    if stage == 'close':
        assert backend.translate_verse(BY_ID[1], 1, context, 1)
    else:
        with pytest.raises(TranslationError) as error:
            backend.translate_verse(BY_ID[1], 1, context, 1)
        assert FAKE not in str(error.value) and FAKE not in ''.join(
            traceback.format_exception(error.value)
        )
    assert FAKE not in caplog.text


@pytest.mark.parametrize('padding', [' ', '\n', '\r\n\t', '\u00a0'])
def test_phone_key_ends_are_trimmed_before_validation(padding):
    save_key(padding + FAKE + padding)
    assert key_path().read_bytes() == FAKE.encode()
    with pytest.raises(CredentialError):
        save_key('sk-ant-FAKE' + padding + 'INTERNAL')
    assert key_path().read_bytes() == FAKE.encode()
