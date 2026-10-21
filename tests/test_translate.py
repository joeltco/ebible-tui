"""Offline translation tests: real verse text and explicitly temporary DB fixtures."""

import asyncio
import importlib
import sqlite3
import subprocess
import threading
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from ebible.canon import BY_ID
from ebible.core.models import VerseRef
from ebible.core.scripture import ScriptureStore
from ebible.core.translate.base import (
    AlignmentError,
    TranslationError,
    parse_numbered_lines,
    validate_alignment,
)
from ebible.core.translate.claude import APP_ADDENDUM, MODEL, ClaudeBackend
from ebible.core.translate.google import GoogleBackend
from ebible.core.translate.service import TranslationService, select_backend


@pytest.fixture
def source(scripture):
    return {v.verse: v.text_am for v in scripture.chapter(1, 1)}


@pytest.fixture
def english(scripture):
    return {v.verse: v.english for v in scripture.chapter(1, 1)}


class FakeClient:
    def __init__(self, text, stop_reason='end_turn'):
        self.text = text
        self.stop_reason = stop_reason
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


def lines(verses):
    return '\n'.join(f'{number}. {text}' for number, text in verses.items())


def test_claude_whole_chapter_guide_model_and_fake_client(source, english):
    client = FakeClient(lines(english))
    assert ClaudeBackend(client).translate_chapter(BY_ID[1], 1, source) == english
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request['model'] == MODEL == 'claude-sonnet-5-5'
    assert (
        request['system']
        == Path('docs/translation/TRANSLATION_GUIDE.md').read_text(encoding='utf-8') + APP_ADDENDUM
    )
    assert request['max_tokens'] == 16384
    assert request['messages'] == [
        {'role': 'user', 'content': f'Genesis 1 ({BY_ID[1].name_am})\n\n' + lines(source)}
    ]
    assert not client.closed  # The injected client's lifetime belongs to its caller.


@pytest.mark.parametrize(
    'kind',
    [
        'missing',
        'extra',
        'duplicate',
        'empty',
        'commentary',
        'wrapped',
        'fenced-commentary',
        'shifted',
        'invalid',
    ],
)
def test_claude_rejects_bad_alignment(source, english, kind):
    text = lines(english)
    if kind == 'missing':
        text = lines({n: t for n, t in english.items() if n != 2})
    elif kind == 'extra':
        text += f'\n999. {english[1]}'
    elif kind == 'duplicate':
        text += f'\n1. {english[1]}'
    elif kind == 'empty':
        text = text.replace(f'2. {english[2]}', '2.   ')
    elif kind == 'commentary':
        text += '\nfixture: extra commentary'
    elif kind == 'wrapped':
        text = text.replace(' ', '\n', 1)
    elif kind == 'fenced-commentary':
        text = f'```\n{text}\n```\nfixture: commentary'
    elif kind == 'shifted':
        text = lines({n + 1: t for n, t in english.items()})
    else:
        text = ''
    with pytest.raises(AlignmentError):
        ClaudeBackend(FakeClient(text)).translate_chapter(BY_ID[1], 1, source)


@pytest.mark.parametrize('reason', ['max_tokens', 'refusal', None, 'stop_sequence'])
def test_claude_rejects_incomplete_even_if_numbers_match(source, english, reason):
    with pytest.raises(TranslationError, match='Incomplete'):
        ClaudeBackend(FakeClient(lines(english), reason)).translate_chapter(BY_ID[1], 1, source)


def test_alignment_keeps_noncontiguous_numbers(source, english):
    subset = {n: source[n] for n in (1, 3)}
    output = {n: english[n] for n in (1, 3)}
    assert parse_numbered_lines(lines(output), subset) == output
    assert parse_numbered_lines('\n' + lines(output) + '\n', subset) == output
    for bad in (
        {1: '', 3: english[3]},
        {True: english[1], 3: english[3]},
        {0: english[1], 3: english[3]},
    ):
        with pytest.raises(AlignmentError):
            validate_alignment(subset, bad)


def test_claude_lazy_sdk_and_close(monkeypatch, source, english):
    client = FakeClient(lines(english))
    options = []

    def sdk_factory(**kwargs):
        options.append(kwargs)
        return client

    original_import = importlib.import_module
    monkeypatch.setattr(
        importlib,
        'import_module',
        lambda name: (
            SimpleNamespace(Anthropic=sdk_factory) if name == 'anthropic' else original_import(name)
        ),
    )
    assert ClaudeBackend().translate_chapter(BY_ID[1], 1, source) == english
    assert options == [{'timeout': 120.0, 'max_retries': 0}]
    assert client.closed


def test_claude_sdk_missing_and_transport_error(monkeypatch, source):
    def missing(name):
        raise ImportError('fixture: SDK absent')

    monkeypatch.setattr(importlib, 'import_module', missing)
    with pytest.raises(TranslationError, match=r'ebible\[claude\]'):
        ClaudeBackend().translate_chapter(BY_ID[1], 1, source)
    client = FakeClient('')

    def fail(**kwargs):
        raise OSError('fixture: transport failed')

    client.create = fail
    with pytest.raises(TranslationError, match='request failed'):
        ClaudeBackend(client).translate_chapter(BY_ID[1], 1, source)
    assert ClaudeBackend().translate_chapter(BY_ID[1], 1, {}) == {}


def test_google_uses_stdin_no_shell_and_per_verse_timeout(monkeypatch, source, english):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout=english[len(calls)] + '\n')

    monkeypatch.setattr(subprocess, 'run', run)
    result = GoogleBackend('/fixture/trans', timeout=7).translate_chapter(BY_ID[1], 1, source)
    assert result == english
    assert len(calls) == len(source)
    for n, (command, options) in enumerate(calls, 1):
        assert command == ['/fixture/trans', '-brief', '-engine', 'google', 'am:en']
        assert options == {
            'input': source[n],
            'capture_output': True,
            'encoding': 'utf-8',
            'check': True,
            'timeout': 7,
        }


@pytest.mark.parametrize(
    'failure',
    [
        subprocess.TimeoutExpired('trans', 1),
        subprocess.CalledProcessError(1, 'trans'),
        FileNotFoundError('trans'),
    ],
)
def test_google_failure(monkeypatch, source, failure):
    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(TranslationError, match='Genesis 1:1'):
        GoogleBackend('/fixture/trans').translate_chapter(BY_ID[1], 1, source)


def test_google_missing_and_blank(monkeypatch, source):
    monkeypatch.setattr('shutil.which', lambda _: None)
    with pytest.raises(TranslationError, match='not on PATH'):
        GoogleBackend().translate_chapter(BY_ID[1], 1, source)
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(stdout=' '))
    with pytest.raises(AlignmentError):
        GoogleBackend('/fixture/trans').translate_chapter(BY_ID[1], 1, source)
    assert GoogleBackend().translate_chapter(BY_ID[1], 1, {}) == {}
    with pytest.raises(ValueError):
        GoogleBackend(timeout=0)


def test_backend_selection(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda _: None)
    assert select_backend() is None
    assert select_backend('off') is None
    monkeypatch.setattr('shutil.which', lambda _: '/fixture/trans')
    assert isinstance(select_backend(), GoogleBackend)
    assert isinstance(select_backend('google'), GoogleBackend)
    with pytest.raises(TranslationError, match='API_KEY'):
        select_backend('claude')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'fixture-key-never-sent')
    assert isinstance(select_backend(), ClaudeBackend)
    assert isinstance(select_backend('claude'), ClaudeBackend)
    assert select_backend('off') is None
    with pytest.raises(ValueError):
        select_backend('invalid')


@pytest.fixture
def partial_store(tmp_path, scripture):
    # Explicit temporary mixed-coverage fixture using real verses and translations.
    path = tmp_path / 'partial-fixture.db'
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE verse(book_id,chapter,verse,text_am,text_en)')
        for n in (1, 2, 3):
            verse = scripture.verse(VerseRef(1, 1, n))
            db.execute(
                'INSERT INTO verse VALUES(1,1,?,?,?)',
                (n, verse.text_am, verse.text_en if n == 1 else None),
            )
    return ScriptureStore(path)


class FakeBackend:
    name = 'fixture'

    def __init__(self, output):
        self.output = output
        self.calls = []

    def translate_chapter(self, book, chapter, verses_am):
        self.calls.append((book, chapter, verses_am, threading.get_ident()))
        return self.output


async def test_service_whole_chapter_fills_only_missing_in_worker(partial_store, userdata, english):
    userdata.save_translations(1, 1, {2: english[2]}, 'existing-fixture')
    backend = FakeBackend({n: english[n] for n in (1, 2, 3)})
    service = TranslationService(partial_store, userdata, backend=backend)
    result = await service.translate_chapter(1, 1)
    assert result == {3: english[3]}
    assert len(backend.calls) == 1
    book, chapter, verses, thread_id = backend.calls[0]
    assert book == BY_ID[1] and chapter == 1 and set(verses) == {1, 2, 3}
    assert thread_id != threading.get_ident()
    assert userdata.live_translation(VerseRef(1)) is None
    assert userdata.live_translation(VerseRef(1, 1, 2)).backend == 'existing-fixture'
    assert userdata.live_translation(VerseRef(1, 1, 3)).backend == 'fixture'
    assert await service.translate_chapter(1, 1) == {}
    assert len(backend.calls) == 1


async def test_service_rejects_before_any_write(partial_store, userdata, english):
    service = TranslationService(partial_store, userdata, backend=FakeBackend({2: english[2]}))
    with pytest.raises(AlignmentError):
        await service.translate_chapter(1, 1)
    assert userdata.live_chapter(1, 1) == {}


async def test_service_off_and_completed_chapter(partial_store, scripture, userdata, monkeypatch):
    assert await TranslationService(partial_store, userdata, 'off').translate_chapter(1, 1) == {}

    def unexpected(*args):
        pytest.fail('No backend should be selected for a complete chapter')

    monkeypatch.setattr('ebible.core.translate.service.select_backend', unexpected)
    assert await TranslationService(scripture, userdata).translate_chapter(1, 1) == {}
    assert userdata.live_chapter(1, 1) == {}


async def test_worker_does_not_block_event_loop(partial_store, userdata, english):
    entered, release = threading.Event(), threading.Event()

    class WaitingBackend(FakeBackend):
        def translate_chapter(self, *args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('fixture: event loop failed to release worker')
            return self.output

    service = TranslationService(
        partial_store, userdata, backend=WaitingBackend({n: english[n] for n in (1, 2, 3)})
    )
    task = asyncio.create_task(service.translate_chapter(1, 1))
    try:
        async with asyncio.timeout(3):
            while not entered.is_set():
                await asyncio.sleep(0.01)
        assert not task.done()
    finally:
        release.set()
    assert await task == {2: english[2], 3: english[3]}


@pytest.mark.parametrize('label', ['', 'text', 'plaintext'])
def test_single_fenced_translation_wrapper(source, english, label):
    assert parse_numbered_lines(f'```{label}\n{lines(english)}\n```', source) == english


@pytest.mark.parametrize(
    'wrap',
    [
        '```\n{body}\n```\nsummary',
        'summary\n```\n{body}\n```',
        '```\n```\n{body}\n```\n```',
        '```\n{body}\n```\n```\n```',
    ],
)
def test_wrapper_does_not_allow_commentary_or_multiple_blocks(source, english, wrap):
    with pytest.raises(AlignmentError):
        parse_numbered_lines(wrap.format(body=lines(english)), source)


def test_guide_unchanged_and_addendum_explicit():
    assert (
        Path('src/ebible/core/translate/TRANSLATION_GUIDE.md').read_bytes()
        == Path('docs/translation/TRANSLATION_GUIDE.md').read_bytes()
    )
    assert 'No summary, no commentary' in APP_ADDENDUM
    assert 'numbered verse lines only' in APP_ADDENDUM
