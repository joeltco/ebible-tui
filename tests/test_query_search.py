"""English queries use explicit fake responses; substring checks use packaged scripture."""

import subprocess
import threading
from time import perf_counter
from types import SimpleNamespace

import pytest

from ebible.core.models import VerseRef
from ebible.core.scripture import SearchError, open_readonly
from ebible.core.translate.base import TranslationError
from ebible.core.translate.claude import ClaudeBackend
from ebible.core.translate.google import GoogleBackend
from ebible.core.translate.query import QUERY_PROMPT, needs_query_translation, parse_query_variants
from ebible.core.translate.service import TranslationService


@pytest.mark.parametrize(
    ('query', 'wanted'),
    [
        ('light', True),
        ("God's light", True),
        (' Église ', True),
        ('123 light?!', True),
        ('ብርሃን', False),
        ('light ብርሃን', False),
        ('light።', False),
        ('=light', False),
        ('  =God AND', False),
        ('123 ?', False),
        ('', False),
        ('φως', False),
    ],
)
def test_language_detection(query, wanted):
    assert needs_query_translation(query) is wanted


def test_variants_ignore_junk_dedupe_and_limit():
    # Real Amharic forms; surrounding garbage is an explicit parser fixture.
    reply = 'summary\n1. ብርሃን\nብርሃን\nብርሃን\nብርሃን light\nብርሃን ሆነ\n[ብርሃን]\n፩\n።\nብርሃኑ\nብርሃንንና\nጨለማን'
    assert parse_query_variants(reply) == ('ብርሃን', 'ብርሃኑ', 'ብርሃንንና')
    assert parse_query_variants(reply, limit=1) == ('ብርሃን',)


@pytest.mark.parametrize(
    'reply', ['', 'light', '1. ብርሃን', 'ብርሃን።', 'ብርሃን light', 'ብርሃን ሆነ', '፩\n።\n```']
)
def test_unusable_variants_actionable(reply):
    with pytest.raises(TranslationError, match='No usable.*Settings'):
        parse_query_variants(reply)


def test_google_query_stdin_direction_timeout_and_one_result(monkeypatch):
    calls = []

    def fake(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout='junk\nብርሃን\nብርሃኑ\n')

    monkeypatch.setattr(subprocess, 'run', fake)
    assert GoogleBackend('/fixture/trans', timeout=7).translate_query('light') == ('ብርሃን',)
    assert calls == [
        (
            ['/fixture/trans', '-b', 'en:am'],
            dict(input='light', capture_output=True, encoding='utf-8', check=True, timeout=7),
        )
    ]


@pytest.mark.parametrize(
    'error',
    [
        OSError('fixture'),
        subprocess.TimeoutExpired('trans', 1),
        subprocess.CalledProcessError(1, 'trans'),
    ],
)
def test_google_query_errors_safe(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(TranslationError, match='connection.*translate-shell') as caught:
        GoogleBackend('/fixture/trans').translate_query('light')
    assert caught.value.__suppress_context__


def test_google_query_missing_and_junk(monkeypatch):
    with pytest.raises(TranslationError, match='Install translate-shell'):
        GoogleBackend().translate_query('light')
    monkeypatch.setattr(
        subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='Explicit junk fixture')
    )
    with pytest.raises(TranslationError, match='No usable'):
        GoogleBackend('/fixture/trans').translate_query('light')


def test_claude_query_short_prompt_and_validation():
    class Fake:
        def __init__(self):
            self.messages = self
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                stop_reason='end_turn',
                content=[SimpleNamespace(type='text', text='junk\nብርሃን\nብርሃኑ')],
            )

    client = Fake()
    assert ClaudeBackend(client).translate_query('light') == ('ብርሃን', 'ብርሃኑ')
    (request,) = client.calls
    assert request['system'] == QUERY_PROMPT and len(request['system']) < 500
    assert 'Ethiopian Orthodox' in request['system'] and 'up to 3' in request['system']
    assert request['max_tokens'] == 256
    assert request['messages'] == [{'role': 'user', 'content': 'light'}]


async def test_query_service_worker_validation_and_no_disk(scripture, userdata):
    before = userdata.path.read_bytes()
    calls = []

    class Fake:
        name = 'fixture'

        def translate_query(self, query):
            calls.append((query, threading.get_ident()))
            return ('junk', 'ብርሃን', 'ብርሃን')

    service = TranslationService(scripture, backend=Fake())
    assert await service.translate_query('light') == ('ብርሃን',)
    assert calls[0][0] == 'light' and calls[0][1] != threading.get_ident()
    assert userdata.path.read_bytes() == before
    with pytest.raises(TranslationError, match='backend.*Settings'):
        await TranslationService(scripture, 'off').translate_query('light')


async def test_query_timeout_and_unexpected_error_are_safe(scripture):
    release = threading.Event()

    class Waiting:
        name = 'fixture'

        def translate_query(self, query):
            release.wait(2)
            return ('ብርሃን',)

    try:
        with pytest.raises(TranslationError, match='timed out.*Settings'):
            await TranslationService(scripture, backend=Waiting(), timeout=0.02).translate_query(
                'light'
            )
    finally:
        release.set()

    class Broken:
        name = 'fixture'

        def translate_query(self, query):
            raise RuntimeError('sk-ant-FAKE-NEVER-DISCLOSE-1234')

    with pytest.raises(TranslationError, match='Settings') as caught:
        await TranslationService(scripture, backend=Broken()).translate_query('light')
    assert 'sk-ant-' not in str(caught.value) and caught.value.__suppress_context__


@pytest.mark.parametrize(
    'scope,book_id', [('all', None), ('ot', None), ('nt', None), ('book', 1), ('book', 58)]
)
def test_substring_scope_order_pagination_union_and_highlighting(scripture, scope, book_id):
    variants = ('ብርሃን', 'ብርሃኑ')
    with open_readonly() as db:
        expected = [
            VerseRef(r['book_id'], r['chapter'], r['verse'])
            for r in db.execute('SELECT * FROM verse ORDER BY book_id,chapter,verse')
            if any(v in r['text_am'] for v in variants)
            and (
                scope == 'all'
                or scope == 'ot'
                and r['book_id'] < 55
                or scope == 'nt'
                and r['book_id'] >= 55
                or scope == 'book'
                and r['book_id'] == book_id
            )
        ]
    for offset in (0, 17, max(0, len(expected) - 9), len(expected)):
        page = scripture.search_substrings(
            variants, scope, book_id=book_id, limit=17, offset=offset
        )
        assert [r.ref for r in page] == expected[offset : offset + 17]
        for result in page:
            assert '\x01' in result.snippet and '\x02' in result.snippet
            plain = result.snippet.replace('\x01', '').replace('\x02', '').strip('…')
            assert plain in scripture.verse(result.ref).text_am
    assert len(expected) == len(set(expected))


def test_substrings_find_affixes_and_leave_fts_unchanged(scripture):
    rows = scripture.search_substrings(('ብርሃን',), limit=1000)
    first = rows[0]
    assert first.ref == VerseRef(1, 1, 3)
    assert first.snippet.count('\x01ብርሃን\x02') == 2
    assert '\x01ብርሃን\x02ም' in first.snippet
    fts = scripture.search('ብርሃን', limit=1000)
    extra = {r.ref for r in rows} - {r.ref for r in fts}
    assert extra and any('በብርሃን' in scripture.verse(ref).text_am for ref in extra)
    assert scripture.search('light') == ()
    assert scripture.search_substrings(("%' OR 1=1 --",)) == ()
    assert scripture.search_substrings(()) == ()


@pytest.mark.parametrize(
    'options',
    [dict(scope='bad'), dict(scope='book'), dict(limit=0), dict(limit=1001), dict(offset=-1)],
)
def test_substring_invalid_options(scripture, options):
    with pytest.raises(SearchError):
        scripture.search_substrings(('ብርሃን',), **options)


def test_substring_common_word_last_page_under_150ms(scripture):
    # Include connection setup and snippet creation; near the end of the canon.
    times = []
    for _ in range(3):
        start = perf_counter()
        assert scripture.search_substrings(('እግዚአብሔር',), limit=40, offset=8800)
        times.append(perf_counter() - start)
    assert max(times) < 0.150, times
