import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from ebible.canon import BOOKS
from ebible.core.models import VerseRef
from ebible.core.refs import ReferenceError
from ebible.core.scripture import DB_PATH, ScriptureStore, SearchError, open_readonly


def test_real_store_and_readonly(scripture):
    before = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert scripture.books() == BOOKS
    assert scripture.book_by_slug('john').id == 58
    assert scripture.stats().verses == 39169
    assert scripture.stats().translated == 20443
    assert 52 < scripture.stats().translated_pct < 53
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


def test_overlay_precedence(scripture, userdata):
    bundled = scripture.verse(VerseRef(1))
    assert bundled.text_en and bundled.english == bundled.text_en
    # Real text is reused to exercise storage/precedence, never invented scripture.
    userdata.save_translations(1, 1, {1: bundled.text_en}, 'fixture')
    overlay = ScriptureStore(live_lookup=userdata.live_chapter)
    assert overlay.verse(VerseRef(1)).english_source == 'bundled'
    with open_readonly() as db:
        row = db.execute(
            'SELECT book_id,chapter,verse FROM verse WHERE text_en IS NULL LIMIT 1'
        ).fetchone()
    ref = VerseRef(*row)
    assert overlay.verse(ref).english_source == 'placeholder'
    userdata.save_translations(ref.book_id, ref.chapter, {ref.verse: bundled.text_en}, 'fixture')
    live = overlay.verse(ref)
    assert live.english == bundled.text_en and live.english_source == 'live'
    assert live.text_en is None
    with open_readonly() as db:
        row = db.execute(
            'SELECT v.book_id,v.chapter,v.verse FROM verse v JOIN book b ON b.id=v.book_id WHERE v.text_en IS NULL AND b.deuterocanonical=1 LIMIT 1'
        ).fetchone()
    placeholder = scripture.verse(VerseRef(*row))
    assert 'deuterocanonical' in placeholder.english
    assert 'Not yet translated' in placeholder.english


def test_null_distinct_from_empty(tmp_path):
    # Explicit temporary DB fixture for a state that should not occur in production.
    path = tmp_path / 'fixture.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE verse(book_id,chapter,verse,text_am,text_en)')
        real = ScriptureStore().verse(VerseRef(1))
        db.execute('INSERT INTO verse VALUES(1,1,1,?,?)', (real.text_am, ''))
    store = ScriptureStore(path, lambda b, c: {1: real.english})
    assert store.verse(VerseRef(1)).english_source == 'bundled'
    assert store.verse(VerseRef(1)).english == ''


@pytest.mark.parametrize(('book', 'chapter'), [(0, 1), (1, 0), (1, 999)])
def test_missing_chapter(scripture, book, chapter):
    with pytest.raises(ReferenceError):
        scripture.chapter(book, chapter)


def test_missing_verse(scripture):
    with pytest.raises(ReferenceError):
        scripture.verse(VerseRef(1, 1, 999))


def test_search_languages_scopes_and_pagination(scripture):
    for query, lang in [('LORD', 'en'), ('እግዚአብሔር', 'am')]:
        hits = scripture.search(query, lang=lang, limit=10)
        assert len(hits) == 10
        assert all(h.language == lang and '\x01' in h.snippet and '\x02' in h.snippet for h in hits)
        assert scripture.search(query, lang=lang, limit=5, offset=5) == hits[5:]
        assert all(h.ref.book_id < 55 for h in scripture.search(query, 'ot', lang))
        assert all(h.ref.book_id >= 55 for h in scripture.search(query, 'nt', lang))
        scoped = scripture.search(query, 'book', lang, book_id=58)
        assert scoped and all(h.ref.book_id == 58 for h in scoped)
    assert scripture.search('LORD')
    assert scripture.search('እግዚአብሔር')[0].language == 'am'
    assert scripture.search('  ') == ()
    assert scripture.search('"LORD God"', lang='en')
    assert scripture.search('zzzzzzzzzzzzzzzzzz') == ()
    with pytest.raises(SearchError):
        scripture.search('"')


@pytest.mark.parametrize(
    'kwargs',
    [
        {'scope': 'bad'},
        {'lang': 'bad'},
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
