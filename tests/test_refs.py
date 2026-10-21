from dataclasses import FrozenInstanceError

import pytest

from ebible.canon import BOOKS
from ebible.core.models import VerseRef
from ebible.core.refs import ReferenceError, format_reference, parse_reference, resolve_book


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('john', VerseRef(58)),
        ('JOHN 3:16', VerseRef(58, 3, 16)),
        (' Jn. 3 : 16 – 18 ', VerseRef(58, 3, 16, 18)),
        ('ዘፍ 1', VerseRef(1)),
        ('ኦሪት ዘፍጥረት 2:3', VerseRef(1, 2, 3)),
        ('መጽሐፈ ሄኖክ 1', VerseRef(16)),
        ('ማቴ 5:3', VerseRef(55, 5, 3)),
        ('1 cor 13:4-7', VerseRef(61, 13, 4, 7)),
        ('II Timothy 2', VerseRef(70, 2)),
        ('3Jn 1:2', VerseRef(78, 1, 2)),
        ('1ኛ ዮሐንስ 2:3', VerseRef(76, 2, 3)),
        ('ezra', VerseRef(17)),
        ('wisdom', VerseRef(31)),
    ],
)
def test_parse(text, expected, scripture):
    assert parse_reference(text, validate=scripture.validate_reference) == expected


@pytest.mark.parametrize('book', BOOKS, ids=lambda b: b.slug)
def test_all_names_roundtrip(book):
    for name in (book.slug, book.name_am, book.name_en):
        assert resolve_book(name) == book
    for language in ('am', 'en'):
        ref = VerseRef(book.id, 1, 1, 2)
        assert parse_reference(format_reference(ref, language)) == ref


@pytest.mark.parametrize(
    'text',
    [
        '',
        'j',
        'ዮሐንስ',
        'ኦሪት',
        '1',
        'not a book',
        'john 0',
        'john 3:0',
        'john 3:18-16',
        'john -1',
        'john 3:16-',
        'john 3:1:2',
        'john 3:1-4:2',
        'john 3.16',
        'john 1 2',
    ],
)
def test_invalid_and_ambiguous(text):
    with pytest.raises(ReferenceError):
        parse_reference(text)


def test_database_bounds_and_source_gap(scripture, tmp_path):
    with pytest.raises(ReferenceError):
        parse_reference('john 999', validate=scripture.validate_reference)
    with pytest.raises(ReferenceError):
        parse_reference('john 3:999', validate=scripture.validate_reference)
    with pytest.raises(ReferenceError):
        parse_reference('john 3:16-999', validate=scripture.validate_reference)
    import sqlite3

    from ebible.core.scripture import ScriptureStore

    # Explicit temporary gap fixture, populated only with real source verses.
    path = tmp_path / 'gap-fixture.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE verse(book_id,chapter,verse,text_am,text_en)')
        for number in (1, 3):
            verse = scripture.verse(VerseRef(1, 1, number))
            db.execute(
                'INSERT INTO verse VALUES(1,1,?,?,?)', (number, verse.text_am, verse.text_en)
            )
    with pytest.raises(ReferenceError):
        ScriptureStore(path).validate_reference(VerseRef(1, 1, 2))


def test_model_immutable_and_validated():
    with pytest.raises(FrozenInstanceError):
        VerseRef(1).verse = 2
    for args in ((82,), (0,), (1, 0), (1, 1, 0), (1, 1, 3, 2)):
        with pytest.raises(ValueError):
            VerseRef(*args)
    assert '·' in format_reference(VerseRef(1), 'both')
