-- Amharic-only packaged scripture. Runtime access is read-only.
-- Reproduced by tools/strip_english.py; preserve every source row and number.
PRAGMA foreign_keys = ON;

CREATE TABLE book (
    id           INTEGER PRIMARY KEY,   -- canonical order, 1..81
    slug         TEXT    NOT NULL UNIQUE,-- stable ascii id, e.g. 'genesis'
    name_am      TEXT    NOT NULL,       -- ኦሪት ዘፍጥረት
    name_en      TEXT    NOT NULL,       -- Genesis
    section      TEXT    NOT NULL,       -- see canon.Section
    chapter_count INTEGER NOT NULL,
    deuterocanonical INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX book_section_idx ON book(section);

-- ---------------------------------------------------------------- verses

CREATE TABLE verse (
    id       INTEGER PRIMARY KEY,
    book_id  INTEGER NOT NULL REFERENCES book(id),
    chapter  INTEGER NOT NULL,
    verse    INTEGER NOT NULL,
    text_am  TEXT    NOT NULL,
    UNIQUE (book_id, chapter, verse)
);

CREATE INDEX verse_chapter_idx ON verse(book_id, chapter);

-- ---------------------------------------------------------------- search

-- External-content FTS: the index references verse rowids rather than copying the
-- text, which keeps the database roughly half the size it would otherwise be.
CREATE VIRTUAL TABLE verse_fts USING fts5(
    text_am,
    content = 'verse',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 0'
);

-- Keep FTS in sync with verse. The build script inserts with triggers active, so
-- the index is populated as a side effect of loading.
CREATE TRIGGER verse_ai AFTER INSERT ON verse BEGIN
    INSERT INTO verse_fts(rowid, text_am)
    VALUES (new.id, new.text_am);
END;

CREATE TRIGGER verse_ad AFTER DELETE ON verse BEGIN
    INSERT INTO verse_fts(verse_fts, rowid, text_am)
    VALUES ('delete', old.id, old.text_am);
END;

CREATE TRIGGER verse_au AFTER UPDATE ON verse BEGIN
    INSERT INTO verse_fts(verse_fts, rowid, text_am)
    VALUES ('delete', old.id, old.text_am);
    INSERT INTO verse_fts(rowid, text_am)
    VALUES (new.id, new.text_am);
END;

-- ---------------------------------------------------------------- metadata

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
