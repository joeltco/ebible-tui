import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from ebible.canon import BOOKS
from ebible.core.models import VerseRef
from ebible.core.refs import ReferenceError
from ebible.core.scripture import DB_PATH, SearchError, open_readonly


def test_real_store_and_readonly(scripture):
    before = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert scripture.books() == BOOKS
    assert scripture.book_by_slug('john').id == 58
    assert scripture.stats().verses == 39169
    counts = scripture.chapter_counts()
    assert len(counts) == 81
    chapter = scripture.chapter(1, 1)
    assert len(chapter) == 31
    assert chapter.book.id == 1 and chapter.number == 1
    assert chapter.verses[0].text_am
    with open_readonly() as db:
        assert db.execute('PRAGMA query_only').fetchone()[0] == 0  # mode=ro enforces it
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            db.execute('DELETE FROM verse')
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == before
    scripture.close()


@pytest.mark.parametrize(('book', 'chapter'), [(0, 1), (1, 0), (1, 999)])
def test_missing_chapter(scripture, book, chapter):
    with pytest.raises(ReferenceError):
        scripture.chapter(book, chapter)


def test_missing_verse(scripture):
    with pytest.raises(ReferenceError):
        scripture.verse(VerseRef(1, 1, 999))


@pytest.mark.parametrize(
    'kwargs',
    [
        {'scope': 'bad'},
        {'scope': 'book'},
        {'limit': 0},
        {'limit': 1001},
        {'offset': -1},
    ],
)
def test_invalid_search_options(scripture, kwargs):
    with pytest.raises(SearchError):
        scripture.search('LORD', **kwargs)


def test_worker_safe_connections(scripture):
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _: scripture.chapter(1, 1), range(8)))
    assert all(r == results[0] for r in results)


@pytest.mark.parametrize(
    'query', ["john's", 'God AND', '(', '"', ':', '[God]', 'ሰላም OR', '***', '—']
)
def test_plain_typing_never_uses_fts_syntax(scripture, query):
    assert isinstance(scripture.search(query), tuple)


def test_plain_tokens_and_explicit_advanced_search(scripture):
    assert scripture.search('God AND') == scripture.search('="God" AND "AND"*')
    assert scripture.search("john's") == scripture.search('="john" AND "s"*')
    assert scripture.search('እግዚአብ')
    assert scripture.search('="እግዚአብሔር"')
    with pytest.raises(SearchError, match='remove ='):
        scripture.search('=God AND')


def test_amharic_only_search_scopes_and_pagination(scripture):
    query = 'እግዚአብሔር'
    hits = scripture.search(query, limit=10)
    assert len(hits) == 10
    assert all('\x01' in h.snippet and '\x02' in h.snippet for h in hits)
    assert scripture.search(query, limit=5, offset=5) == hits[5:]
    assert all(h.ref.book_id < 55 for h in scripture.search(query, 'ot'))
    assert all(h.ref.book_id >= 55 for h in scripture.search(query, 'nt'))
    scoped = scripture.search(query, 'book', book_id=58)
    assert scoped and all(h.ref.book_id == 58 for h in scoped)
    assert scripture.search('LORD') == ()
    assert scripture.search('  ') == ()
    with pytest.raises(SearchError):
        scripture.search('="')
