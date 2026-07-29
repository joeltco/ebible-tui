# ebible

Offline Amharic / English reader for the 81-book Ethiopian Orthodox Tewahedo canon,
built for the terminal and for Termux.

No network. No translation calls at runtime. The text is compiled into the package.

```
b     books        t   layout (parallel / Amharic / English)
/     search       n   next chapter        p   previous
v     verse numbers    q   quit
```

## Install

```sh
pip install -e .
ebible
```

On Termux, `tools/termux-launcher` runs it with no extra setup — there is nothing
to install beyond the package itself. (Earlier versions required `translate-shell`
and a proot bind for live translation; both are gone.)

## What ships

| | |
|---|---|
| Books | 81 (full Ethiopian canon, including Jubilees, Enoch, and 1–3 Meqabyan) |
| Chapters | 1,466 |
| Verses | 39,169 |
| Database | ~12 MB, SQLite + FTS5 |

Search covers both languages at once and is backed by FTS5, so it returns
instantly across all 39,169 verses.

## Layout

```
src/ebible/
  canon.py          the 81 books: order, names, sections
  config.py         XDG settings, reading position
  data/
    schema.sql      books / verses / FTS5 index
    store.py        read-only access (writes belong to the translation pipeline)
    models.py       Book, Verse, SearchHit, Stats
  ui/
    app.py          reader, key bindings
    theme.py        colours shared with the stylesheet
    ebible.tcss     styling
    screens/        book picker, search
    widgets/        verse pane
tools/
  build_db.py       assets/Bible81/*.txt  ->  src/ebible/data/bible.db
  termux-launcher
assets/Bible81/     the Amharic source text (1,466 .txt files)
```

`assets/` is the source of truth; `bible.db` is a build artifact. Rebuild with:

```sh
python tools/build_db.py
```

## English translation

**Not yet generated.** `verse.text_en` is `NULL` throughout, and the reader shows
`· not translated ·` rather than an empty column — a pending build step is not the
same as a translation that produced nothing, and the UI keeps those distinct.

The plan is a one-time batch translation pass writing into `text_en`. Nothing at
runtime will call out to a network.

## Known gaps

- **Psalms has 150 chapters** in this source. The Ethiopian Psalter traditionally
  includes Psalm 151; it is absent from the source text and has not been invented.
- **Versification may differ from Western Bibles** in places. The Amharic text is
  authoritative here; chapter and verse numbers follow it, not KJV.
- **15 books are outside the 66-book protestant canon** (marked `·dc` in the book
  picker). They have no widely available English translation to check against, so
  their translations will warrant closer review than the rest.

## Tests

```sh
pip install -e '.[dev]'
pytest
```

The UI tests drive the real app through Textual's `Pilot` and assert on rendered
output. Widget code can pass every unit test and still raise on screen, so the
suite renders rather than only inspecting state.
