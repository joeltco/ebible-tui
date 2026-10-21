-- ebible: compiled Bible store.
--
-- The Amharic text ships as 1,466 .txt files under assets/Bible81/. Reading those
-- at runtime means a directory walk plus a file open per chapter, which is slow on
-- Termux/Android storage. This schema is the compiled form: one file, indexed,
-- with FTS5 for instant search across both languages.
--
-- Built by tools/build_db.py. Do not hand-edit the generated database.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- books

CREATE TABLE book (
    id           INTEGER PRIMARY KEY,   -- canonical order, 1..81
    slug         TEXT    NOT NULL UNIQUE,-- stable ascii id, e.g. 'genesis'
    name_am      TEXT    NOT NULL,       -- ኦሪት ዘፍጥረት
    name_en      TEXT    NOT NULL,       -- Genesis
    section      TEXT    NOT NULL,       -- see canon.Section
    chapter_count INTEGER NOT NULL,
    -- Books outside the 66-book protestant canon have no widely-available English
    -- translation. The UI marks these so an untranslated verse reads as a known
    -- gap rather than a bug.
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
    -- NULL means "not translated yet", which is distinct from '' ("translated as
    -- empty"). The UI must not conflate the two: one is a pending build step, the
    -- other would be a translation bug.
    text_en  TEXT,
    UNIQUE (book_id, chapter, verse)
);

CREATE INDEX verse_chapter_idx ON verse(book_id, chapter);

-- ---------------------------------------------------------------- search

-- External-content FTS: the index references verse rowids rather than copying the
-- text, which keeps the database roughly half the size it would otherwise be.
CREATE VIRTUAL TABLE verse_fts USING fts5(
    text_am,
    text_en,
    content = 'verse',
    content_rowid = 'id',
    tokenize = 'unicode61 remove_diacritics 0'
);

-- Keep FTS in sync with verse. The build script inserts with triggers active, so
-- the index is populated as a side effect of loading.
CREATE TRIGGER verse_ai AFTER INSERT ON verse BEGIN
    INSERT INTO verse_fts(rowid, text_am, text_en)
    VALUES (new.id, new.text_am, new.text_en);
END;

CREATE TRIGGER verse_ad AFTER DELETE ON verse BEGIN
    INSERT INTO verse_fts(verse_fts, rowid, text_am, text_en)
    VALUES ('delete', old.id, old.text_am, old.text_en);
END;

CREATE TRIGGER verse_au AFTER UPDATE ON verse BEGIN
    INSERT INTO verse_fts(verse_fts, rowid, text_am, text_en)
    VALUES ('delete', old.id, old.text_am, old.text_en);
    INSERT INTO verse_fts(rowid, text_am, text_en)
    VALUES (new.id, new.text_am, new.text_en);
END;

-- ---------------------------------------------------------------- metadata

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
