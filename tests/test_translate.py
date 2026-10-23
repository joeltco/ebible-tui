"""Fake-client translation tests. All English output below is an explicit fixture."""

import asyncio
import importlib
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from ebible.canon import BY_ID
from ebible.core.models import VerseRef
from ebible.core.translate.base import (
    AlignmentError,
    TranslationError,
    parse_numbered_lines,
    validate_alignment,
)
from ebible.core.translate.claude import APP_ADDENDUM, MODEL, ClaudeBackend
from ebible.core.translate.google import GoogleBackend
from ebible.core.translate.service import TranslationService, select_backend

FIXTURE = 'Explicit temporary translation fixture [literal brackets].'


@pytest.fixture
def source(scripture):
    return {v.verse: v.text_am for v in scripture.chapter(1, 1)}


class FakeClient:
    def __init__(self, text, stop_reason='end_turn'):
        self.text, self.stop_reason = text, stop_reason
        self.messages = self
        self.calls = []
        self.closed = False

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type='text', text=self.text)], stop_reason=self.stop_reason
        )

    def close(self):
        self.closed = True


def test_claude_context_whole_chapter_output_only_target(source):
    client = FakeClient('16. ' + FIXTURE)
    assert ClaudeBackend(client).translate_verse(BY_ID[1], 1, source, 16) == {16: FIXTURE}
    (request,) = client.calls
    assert request['model'] == MODEL == 'claude-sonnet-5-5'
    assert (
        request['system']
        == Path('docs/translation/TRANSLATION_GUIDE.md').read_text(encoding='utf-8') + APP_ADDENDUM
    )
    assert 'exactly one numbered line' in APP_ADDENDUM
    assert 'No summary, no commentary' in APP_ADDENDUM
    assert 'Translate ONLY verse 16' in request['messages'][0]['content']
    for n, text in source.items():
        assert f'{n}. {text}' in request['messages'][0]['content']
    assert not client.closed


@pytest.mark.parametrize(
    'text',
    [
        '',
        '15. ' + FIXTURE,
        '17. ' + FIXTURE,
        '16. ',
        '16. ' + FIXTURE + '\n17. ' + FIXTURE,
        '16. ' + FIXTURE + '\n16. ' + FIXTURE,
        '16. ' + FIXTURE + '\nsummary',
        'summary\n16. ' + FIXTURE,
        '```\n16. ' + FIXTURE + '\n```\nsummary',
    ],
)
def test_claude_rejects_anything_except_exact_target(source, text):
    with pytest.raises(AlignmentError):
        ClaudeBackend(FakeClient(text)).translate_verse(BY_ID[1], 1, source, 16)


@pytest.mark.parametrize('reason', ['max_tokens', 'refusal', None, 'stop_sequence'])
def test_claude_rejects_incomplete(source, reason):
    with pytest.raises(TranslationError, match='Incomplete'):
        ClaudeBackend(FakeClient('16. ' + FIXTURE, reason)).translate_verse(BY_ID[1], 1, source, 16)


@pytest.mark.parametrize('label', ['', 'text', 'plaintext'])
def test_one_fence_wrapper(source, label):
    assert parse_numbered_lines(f'```{label}\n16. {FIXTURE}\n```', {16: source[16]}) == {
        16: FIXTURE
    }


def test_alignment_strict_numbers(source):
    for bad in ({True: FIXTURE}, {0: FIXTURE}, {1: ''}, {1: None}):
        with pytest.raises(AlignmentError):
            validate_alignment({1: source[1]}, bad)
    assert parse_numbered_lines(
        '1. ' + FIXTURE + '\n3. ' + FIXTURE, {1: source[1], 3: source[3]}
    ) == {1: FIXTURE, 3: FIXTURE}


def test_lazy_sdk_close_timeout_and_missing_sdk(monkeypatch, source):
    client = FakeClient('1. ' + FIXTURE)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-FAKE-SDK-TEST-1234')
    options = []

    def factory(**kwargs):
        options.append(kwargs)
        return client

    original = importlib.import_module
    monkeypatch.setattr(
        importlib,
        'import_module',
        lambda name: SimpleNamespace(Anthropic=factory) if name == 'anthropic' else original(name),
    )
    assert ClaudeBackend().translate_verse(BY_ID[1], 1, source, 1) == {1: FIXTURE}
    assert (
        options == [{'api_key': 'sk-ant-FAKE-SDK-TEST-1234', 'timeout': 30.0, 'max_retries': 0}]
        and client.closed
    )

    def missing(name):
        raise ImportError('Explicit missing-SDK fixture')

    monkeypatch.setattr(importlib, 'import_module', missing)
    with pytest.raises(TranslationError, match=r'ebible\[claude\]'):
        ClaudeBackend().translate_verse(BY_ID[1], 1, source, 1)


def test_claude_transport_error_and_bad_target(source):
    client = FakeClient('')

    def fail(**kwargs):
        raise OSError('Explicit transport failure fixture')

    client.create = fail
    with pytest.raises(TranslationError, match='Check your connection'):
        ClaudeBackend(client).translate_verse(BY_ID[1], 1, source, 1)
    with pytest.raises(TranslationError, match='Target verse'):
        ClaudeBackend(client).translate_verse(BY_ID[1], 1, source, 999)


def test_google_sends_target_only_stdin_timeout(monkeypatch, source):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=FIXTURE + '\n')

    monkeypatch.setattr(subprocess, 'run', run)
    assert GoogleBackend('/fixture/trans', timeout=7).translate_verse(BY_ID[1], 1, source, 16) == {
        16: FIXTURE
    }
    assert calls == [
        (
            ['/fixture/trans', '-brief', '-engine', 'google', 'am:en'],
            {
                'input': source[16],
                'capture_output': True,
                'encoding': 'utf-8',
                'check': True,
                'timeout': 7,
            },
        )
    ]


@pytest.mark.parametrize(
    'failure',
    [
        subprocess.TimeoutExpired('trans', 1),
        subprocess.CalledProcessError(1, 'trans'),
        FileNotFoundError('trans'),
    ],
)
def test_google_errors_actionable(monkeypatch, source, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(TranslationError, match='retry'):
        GoogleBackend('/fixture/trans').translate_verse(BY_ID[1], 1, source, 16)


def test_google_absent_empty_and_invalid_target(monkeypatch, source):
    monkeypatch.setattr('shutil.which', lambda _: None)
    with pytest.raises(TranslationError, match='Install translate-shell'):
        GoogleBackend().translate_verse(BY_ID[1], 1, source, 1)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=' '))
    with pytest.raises(AlignmentError):
        GoogleBackend('/fixture/trans').translate_verse(BY_ID[1], 1, source, 1)
    with pytest.raises(TranslationError):
        GoogleBackend().translate_verse(BY_ID[1], 1, source, 999)
    with pytest.raises(ValueError):
        GoogleBackend(timeout=0)


def test_backend_selection(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda _: None)
    assert select_backend() is None and select_backend('off') is None
    monkeypatch.setattr('shutil.which', lambda _: '/fixture/trans')
    assert isinstance(select_backend(), GoogleBackend)
    with pytest.raises(TranslationError, match='API_KEY'):
        select_backend('claude')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-never-sent')
    assert isinstance(select_backend(), ClaudeBackend)
    assert select_backend('off') is None
    with pytest.raises(ValueError):
        select_backend('invalid')


async def test_service_thread_alignment_and_no_disk_write(scripture, userdata):
    before = userdata.path.read_bytes()
    calls = []

    class Fake:
        name = 'fixture'

        def translate_verse(self, book, chapter, context, target):
            calls.append((context, target, threading.get_ident()))
            return {target: FIXTURE}

    service = TranslationService(scripture, backend=Fake())
    assert await service.translate_verse(VerseRef(1, 1, 16)) == FIXTURE
    context, target, thread = calls[0]
    assert len(context) == 31 and target == 16 and thread != threading.get_ident()
    assert userdata.path.read_bytes() == before
    assert not hasattr(service, 'userdata')

    class Bad(Fake):
        def translate_verse(self, *args):
            return {17: FIXTURE}

    with pytest.raises(AlignmentError):
        await TranslationService(scripture, backend=Bad()).translate_verse(VerseRef(1, 1, 16))
    with pytest.raises(TranslationError, match='API_KEY'):
        await TranslationService(scripture, 'off').translate_verse(VerseRef(1))


async def test_worker_responsive_and_timeout(scripture):
    entered, release = threading.Event(), threading.Event()

    class Waiting:
        name = 'fixture'

        def translate_verse(self, book, chapter, context, target):
            entered.set()
            release.wait(3)
            return {target: FIXTURE}

    service = TranslationService(scripture, backend=Waiting(), timeout=0.1)
    task = asyncio.create_task(service.translate_verse(VerseRef(1)))
    try:
        async with asyncio.timeout(2):
            while not entered.is_set():
                await asyncio.sleep(0.001)
        assert not task.done()
        with pytest.raises(TranslationError, match='timed out.*retry'):
            await task
    finally:
        release.set()


async def test_cache_returns_saved_verse_per_backend_and_source(scripture, tmp_path):
    from ebible.core.translate.cache import TranslationCache
    from ebible.paths import translation_cache_path

    calls = []

    def fake(label):
        class Fake:
            name = label

            def translate_verse(self, book, chapter, context, target):
                calls.append(label)
                return {target: f'{label} {FIXTURE}'}

        return Fake()

    ref = VerseRef(1, 1, 16)
    cache = TranslationCache()
    first = TranslationService(scripture, backend=fake('one'), cache=cache)
    assert await first.translate_verse(ref) == f'one {FIXTURE}'
    assert translation_cache_path().is_file()
    again = TranslationService(scripture, backend=fake('one'), cache=TranslationCache())
    assert await again.translate_verse(ref) == f'one {FIXTURE}' and calls == ['one']
    other = TranslationService(scripture, backend=fake('two'), cache=cache)
    assert await other.translate_verse(ref) == f'two {FIXTURE}' and calls == ['one', 'two']
    source = scripture.verse(ref).text_am
    assert cache.get('one', ref, source + ' changed') is None
    translation_cache_path().write_bytes(b'not a database')
    assert cache.get('one', ref, source) is None
    assert await first.translate_verse(ref) == f'one {FIXTURE}'
