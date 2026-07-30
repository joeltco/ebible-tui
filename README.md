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
  translate.py      pull / push chapters, with verse-alignment enforcement
  plan_batches.py   partition remaining work by verse count
  check_consistency.py  terminology drift between independently-translated batches
  fix_term.py       scoped single-term normalisation
  audit_source.py   regenerates SOURCE_ISSUES.md from the data
  repair_artifacts.py   in-place source fixes that preserve translations
  termux-launcher
assets/Bible81/     the Amharic source text (1,466 .txt files)
TRANSLATION_GUIDE.md  binding conventions for translators
SOURCE_ISSUES.md      generated defect inventory
```

`assets/` holds the Amharic source of truth. `bible.db` is **tracked in git** — it
was a pure build artifact until it began carrying the English translation, which
cannot be regenerated from the Amharic. Rebuild the Amharic side with:

```sh
python tools/build_db.py    # WARNING: recreates the db, dropping every translation
```

Use `tools/repair_artifacts.py` instead for in-place source fixes that must
preserve translated text.

## English translation — in progress

**13,217 of 39,169 verses (34%).** Untranslated verses hold `NULL`, and the
reader shows `· not translated ·` rather than an empty column — a pending verse
is not the same as a translation that produced nothing.

| | |
|---|---|
| **Complete** | Genesis, Exodus, Leviticus, Numbers, Deuteronomy, Joshua, Judges, Ruth, Matthew, Mark, Luke, John |
| **Partial** | Acts 96%, 1 Samuel 69%, Enoch 25%, Psalms 12% |
| **Not started** | 65 books |

Translation is done by agents working from **`TRANSLATION_GUIDE.md`**, which is
binding. Its prime directive: the Amharic is the source of truth, and no
harmonising toward the KJV or any remembered English Bible. That is why this
text reads Adullam where English Bibles read Eglon, Asaph where they read Asa,
and "Jonathan son of Gershom, son of **Moses**" at Judges 18:30 where the
Masoretic softens it to Manasseh.

### Pipeline

```sh
python tools/plan_batches.py --target 600     # partition remaining work
python tools/translate.py pull genesis 1      # emit a chapter as numbered lines
python tools/translate.py push genesis 1 < en.txt   # write English back
python tools/translate.py status              # progress
python tools/check_consistency.py             # terminology drift across batches
python tools/fix_term.py --from X --to Y      # scoped single-term normalisation
python tools/audit_source.py > SOURCE_ISSUES.md
```

`push` rejects any payload whose verse numbers do not match the source exactly.
A shifted verse would silently attach the wrong English to the wrong Amharic and
nothing downstream would notice, so that guard is not optional.

## What has NOT been verified

**No one has audited these translations for accuracy.** What has been verified is
mechanical: divine names consistent at 99–100%, no `God God`, no translator notes
leaked into verse text, no drift on watched terminology. That is consistency
checking, not correctness checking.

Agent self-reports flag hundreds of verses as genuinely uncertain, which is the
system working. The risk that remains is *silent* fluent error — a confidently
wrong rendering reports itself as confident. Establishing quality would need a
verification pass: independent re-translation of sampled chapters, compared
against what is stored, with divergences surfaced. That has not been done.

## Known gaps

- **70 verses are defective in the source** — see `SOURCE_ISSUES.md`, generated
  from the data. Most seriously, **33 verses are absent**: the scrape dropped a
  verse and left the following verse's number stranded inline. They are recorded,
  not reconstructed.
- **Leviticus 27:31 is not scripture** — a lexicographer's note on coinage that
  occupies a verse slot and shifts the chapter. Left in place; removing it would
  renumber the chapter the translation is aligned to.
- **Psalms has 150 chapters** here. The Ethiopian Psalter traditionally includes
  Psalm 151; it is absent from the source and has not been invented.
- **Enoch's astronomical chapters contradict their own arithmetic** in at least
  four places (21:21, 21:41, 26:4, 26:15) — a doorway its own day-ratios forbid,
  a day that both doubles and halves, two broken sequences. Translated as
  written. Emending a number would be indistinguishable from translating one.
- **Enoch 16–18 are Noah speaking, not Enoch** — the text says "my grandfather
  Enoch" throughout and names Noah at 18:1. Not an error.
- **Versification differs from Western Bibles** throughout. The Amharic is
  authoritative; chapter and verse numbers follow it, not the KJV.
- **15 books sit outside the 66-book canon** (marked `·dc` in the picker). They
  have no widely available English to check against, so they warrant the closest
  review — which is exactly why their agents were asked for verse-level
  confidence reports rather than clean summaries.

## Tests

```sh
pip install -e '.[dev]'
pytest
```

The UI tests drive the real app through Textual's `Pilot` and assert on rendered
output. Widget code can pass every unit test and still raise on screen, so the
suite renders rather than only inspecting state.
