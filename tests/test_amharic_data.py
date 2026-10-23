"""Golden digests recorded from the original DB before removing any English."""

import hashlib
import json
import runpy
import sqlite3
from pathlib import Path

from ebible.core.scripture import DB_PATH, open_readonly


def digest(rows):
    return hashlib.sha256(
        ''.join(
            json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in rows
        ).encode('utf-8')
    ).hexdigest()


def test_every_amharic_verse_and_book_matches_original_checksum():
    golden = json.loads(Path('tests/fixtures/amharic_checksums.json').read_text(encoding='utf-8'))
    with open_readonly() as db:
        verses = [
            tuple(r)
            for r in db.execute(
                'SELECT book_id,chapter,verse,text_am FROM verse ORDER BY book_id,chapter,verse'
            )
        ]
        books = [tuple(r) for r in db.execute('SELECT * FROM book ORDER BY id')]
    assert len(verses) == golden['verse_count'] == 39169
    assert digest(verses) == golden['verses_sha256']
    assert len(books) == golden['book_count'] == 81
    assert digest(books) == golden['books_sha256']


def test_packaged_schema_contains_no_english_scripture_or_coverage():
    with open_readonly() as db:
        assert [r[1] for r in db.execute('PRAGMA table_info(verse)')] == [
            'id',
            'book_id',
            'chapter',
            'verse',
            'text_am',
        ]
        assert [r[1] for r in db.execute('PRAGMA table_info(verse_fts)')] == ['text_am']
        assert set(r[0] for r in db.execute('SELECT key FROM meta')) == {
            'schema_version',
            'book_count',
            'chapter_count',
            'verse_count',
        }
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA freelist_count').fetchone()[0] == 0
    assert b'In the beginning the LORD' not in DB_PATH.read_bytes()


def test_strip_tool_is_deterministic_and_removes_legacy_english(tmp_path):
    strip = runpy.run_path('tools/strip_english.py')['strip_english']
    source = tmp_path / 'explicit-legacy-fixture.db'
    source.write_bytes(DB_PATH.read_bytes())
    with sqlite3.connect(source) as db:
        db.execute('ALTER TABLE verse ADD COLUMN text_en TEXT')
        db.execute("UPDATE verse SET text_en='Explicit temporary translation fixture'")
        db.execute("INSERT INTO meta VALUES ('translated_count','39169')")
    one, two = tmp_path / 'one.db', tmp_path / 'two.db'
    strip(source, one)
    strip(source, two)
    assert one.read_bytes() == two.read_bytes() == DB_PATH.read_bytes()
    strip(one, one)
    assert one.read_bytes() == two.read_bytes()


def test_offline_pipeline_removed_and_guides_preserved():
    assert not Path('tools/translation').exists()
    for name in ('RESUME.md', 'AGENT_BRIEF.md'):
        assert not Path('docs/translation', name).exists()
    assert Path('docs/translation/SOURCE_ISSUES.md').is_file()
    assert (
        Path('docs/translation/TRANSLATION_GUIDE.md').read_bytes()
        == Path('src/ebible/core/translate/TRANSLATION_GUIDE.md').read_bytes()
    )
