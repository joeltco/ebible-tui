# Translator operating procedure

You are translating part of the Amharic Bible into English. Read
**`TRANSLATION_GUIDE.md` in full before your first chapter.** It is binding and
it is not negotiable; every rule in it was settled after a previous translator
hit the gap and got it wrong.

Work from `/home/joeltco/projects/ebible-tui`. Prefix commands with
`cd /home/joeltco/projects/ebible-tui &&`.

## The loop, once per chapter

```sh
python tools/translate.py pull  <slug> <n>  > /tmp/ch.txt     # Amharic, numbered
# translate
python tools/translate.py push  <slug> <n>  < /tmp/ch-en.txt  # English back
```

Push each chapter before starting the next. Do not batch up ten chapters and
push at the end — if you die mid-run, everything unpushed is lost. Chapters
already pushed survive.

`push` requires the verse numbers to match the source **exactly**: same set, no
gaps, no extras, no merges, no splits. It will reject the payload otherwise, and
that rejection is the point — a shifted verse silently attaches the wrong English
to the wrong Amharic and nothing downstream would ever notice. If the Amharic
verse has content you cannot construe, translate what you can rather than
dropping the line.

Format for `push` input: one line per verse, `N. text`. Lines starting with `#`
are ignored.

## Matching the voice of what is already there

You cannot see the other translators. Before your first chapter, read English
already stored for your book, or for the nearest completed book, and match it:

```sh
python3 -c "
import sqlite3
d=sqlite3.connect('file:src/ebible/data/bible.db?mode=ro',uri=True)
for r in d.execute(\"SELECT verse,text_en FROM verse v JOIN book b ON b.id=v.book_id WHERE b.slug='genesis' AND chapter=1\"): print(*r)
"
```

Use `mode=ro`, as above — not `immutable=1`. Other translators are writing to
this file while you read it, and `immutable=1` tells SQLite that locking is
unnecessary, which is false here.

If your book has no stored English yet, read a completed neighbour in the same
register: Genesis or Judges for narrative, Psalms for poetry, Matthew or Luke for
gospel, Leviticus for cultic law.

## Reporting

Report **verse-level confidence**, not a clean summary. Name the references you
are unsure of and say why. A report claiming full confidence across a hard book
is not believable and will be treated as a failure to look.

Specifically, list:

- verses whose Amharic you could not construe, and what you did
- terminology you had to decide that the guide does not cover — these get
  written into the guide, so they matter more than anything else you report
- places where the Amharic plainly disagrees with familiar English Bibles.
  These are expected and valuable; the source is authoritative. Report them,
  do not "correct" them.

Never claim a book or range is complete without checking the database. Do not
infer completeness from `translate.py next`, which truncates its output with a
`LIMIT` — a book absent from that list may simply have been cut off.

```sh
python3 -c "
import sqlite3
d=sqlite3.connect('file:src/ebible/data/bible.db?mode=ro',uri=True)
print(*d.execute(\"SELECT count(*),count(text_en) FROM verse v JOIN book b ON b.id=v.book_id WHERE b.slug='<slug>'\").fetchone())
"
```

## Source defects

`SOURCE_ISSUES.md` inventories 70 damaged verses. Check it for your book before
you start. Two classes will affect you:

- **Lost verses** — the scrape dropped a verse and left the *next* verse's
  number stranded inline at the start of the text. Translate the text that is
  there under the number it is filed under. Do not renumber and do not invent
  the missing verse.
- **Footnote digits** welded into words. Already stripped at build time, so you
  should not see them; if you do, ignore the digit.

Never invent scripture to fill a hole. A flagged gap is a good outcome; a
plausible fabrication is the worst possible one.
