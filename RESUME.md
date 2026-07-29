# Resuming this work

Written at 13,217 / 39,169 verses (34%), with the project on hold. A session with
no memory of the previous work should be able to pick up from this file.

---

## Read first

1. **`TRANSLATION_GUIDE.md`** — binding. Every convention, and the reasoning. Do
   not re-derive these; they were each settled after an agent hit the gap.
2. **`SOURCE_ISSUES.md`** — the 70 defective source verses. Regenerate with
   `python tools/audit_source.py > SOURCE_ISSUES.md`.
3. **`README.md`** § *What has NOT been verified* — the honest limits of what is
   known about quality.

## State

```sh
python tools/translate.py status      # overall
python tools/translate.py next --count 20   # what needs doing, canonical order
python tools/check_consistency.py     # drift across batches
```

Complete: Genesis, Exodus, Leviticus, Numbers, Deuteronomy, Joshua, Judges, Ruth,
Matthew, Mark, Luke, John.

Partial, with resume points:

| Book | Resume at |
|---|---|
| Acts | ch. 28 only |
| 1 Samuel | ch. 21 |
| Psalms | ch. 23 |
| Enoch | ch. 10 |

Five agents were lost mid-run to server-side API 500s. Nothing was corrupted:
`translate.py push` writes per chapter, so completed chapters survived and only
in-flight ones were lost.

## Dispatching translation agents

```sh
python tools/plan_batches.py --target 600
```

Then give each agent one batch. A prompt that works:

- Read `TRANSLATION_GUIDE.md` in full; it is binding.
- Name the book slug and exact chapter range.
- Quote the conventions already settled for the *neighbouring* books, so the
  agent matches rather than choosing afresh.
- Give the sanctioned read command so it can inspect existing English:
  `python3 -c "import sqlite3;d=sqlite3.connect('file:src/ebible/data/bible.db?mode=ro',uri=True);[print(r[0]) for r in d.execute(\"SELECT text_en FROM verse v JOIN book b ON b.id=v.book_id WHERE b.slug='genesis' AND chapter=1\")]"`
- List that book's stray-digit references from `SOURCE_ISSUES.md`.
- Require `pull` → translate → `push` per chapter, pushing each before the next.
- Ask for **verse-level confidence**, not a clean summary. A report claiming full
  confidence across a hard book is not believable.

**Lessons paid for the hard way:**

- Every consistency failure so far came from the guide lagging the work, never
  from an agent disobeying it. Write a newly-settled term into the guide
  immediately, not after the next collision.
- Agents cannot see each other. Two working the same book will diverge unless
  both are handed the same conventions up front.
- An agent reading `translate.py next` may conclude a book is finished because
  `LIMIT` truncated the list. Verify completion against the database, not a
  report. (This is how Mark 15–16 were nearly missed.)
- Verify factual claims in agent reports. Several were stale or wrong — one
  warned that Numbers still used old transliterations when a fix had just landed.

## Outstanding work

| # | Task | Notes |
|---|---|---|
| 1 | ~26,000 verses remain | 65 books not started |
| 2 | James/Judas pass over the NT | Referent-by-referent, not `fix_term.py`. Acts 1–15 is the reference implementation. Defer until the NT is complete so it is done once. |
| 3 | Re-run Exodus 22–40 + Leviticus 1–19 | They were translated with contradictory cult vocabulary; §3b is the reconciliation. ~1,162 verses. Leviticus 17:4 still reads "dwelling place of the LORD". |
| 4 | `repair_artifacts.py` | Strips the 19 footnote digits from `text_am` in place. **Must not run while agents hold the database** — `store.py` opens it `immutable=1`, and writing under that promise is undefined behaviour. |
| 6 | `መጻተኛ` → foreigner back-fix | ~17 verses. **Do not script past Genesis 23:4 or Deuteronomy 14:21** — both contain two outsider words where each English term is correct. |
| — | Verification pass | Not yet a task. The real gap: nothing has checked accuracy, only consistency. Independent re-translation of sampled chapters, compared against what is stored. |

## Things that look like bugs but are not

- Verse counts differing from familiar English Bibles — the source's own
  versification, followed deliberately.
- Adullam where English has Eglon; Asaph where it has Asa; "son of Moses" at
  Judges 18:30; the Lord's Prayer petitions inverted; Ruth 4:17 reading "father
  of David, the father of Jesse". All verified against the Amharic.
- Numbers 31:37–43 not summing to its own stated total — the source's arithmetic.
- Numbers 7:18–29 duplicating an offering word for word — in the source.
- `· not translated ·` in the reader — `NULL`, meaning pending, deliberately
  distinguished from an empty string.
