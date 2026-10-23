# eBible v2 — agent brief

Read this whole file before touching anything. It is the spec and the rules.

## What this is

A sophisticated terminal Bible reader for the **81-book Ethiopian Orthodox Tewahedo
canon**, an Amharic reader with on-demand verse translation, built with **Textual**, designed **first for Termux on an
Android phone** (Galaxy S25, portrait, touch + Termux extra-keys row), and working
equally on a desktop terminal.

This is a ground-up rebuild on branch `rebuild/v2`. The only things carried over from
the previous attempts are DATA, not code:

| Path | What | Rule |
|---|---|---|
| `src/ebible/data/bible.db` | 39,169 Amharic verses; Amharic-only FTS5 | Runtime read-only. Authorized Batch 5 rebuild strips ALL English using `tools/strip_english.py`; thereafter preserve the new database. Never alter Amharic text, book rows, or numbering. Verify the recorded old-data checksums in `tests/fixtures/amharic_checksums.json`. |
| `src/ebible/data/schema.sql` | Amharic-only schema | Keep synchronized with the packaged database. |
| `src/ebible/canon.py` | 81 books in Ethiopian order | Preserve all data rows. |
| `source/Bible81/` | raw Amharic source | Never edit. |
| `docs/translation/TRANSLATION_GUIDE.md` | binding live translator prompt | Keep byte-identical, including the packaged copy; append an in-app single-verse output contract. |
| `docs/translation/SOURCE_ISSUES.md` | source defects | Preserve. |

The old English database is recoverable from git at `e1564db`. Do not keep a copy
in the tree. The offline pipeline and its RESUME/AGENT_BRIEF documents are removed.


All app code is new. Do not resurrect code from git history of `master` or
`rebuild/offline-reader`; design it properly here.

## Architecture

```
src/ebible/
  __main__.py        CLI: `ebible [REF] [--theme NAME] [--version]`; REF opens there ("john 3:16", "ዘፍ 1")
  app.py             EBibleApp: wiring, theme registration, global bindings, screen routing
  canon.py           books (imported data)
  paths.py           config/data dirs, resolved AT CALL TIME (honour XDG_CONFIG_HOME / XDG_DATA_HOME;
                     defaults ~/.config/ebible, ~/.local/share/ebible). Tests point these at tmp dirs.
  core/              NO textual imports anywhere under core/
    models.py        frozen dataclasses: VerseRef, Verse, Chapter, Bookmark, Highlight, Note, HistoryEntry...
    refs.py          parse/format references: English names + common abbreviations + Amharic names/prefixes,
                     "book", "book ch", "book ch:v", "book ch:v-v"; ambiguity → error, not a guess
    scripture.py     read-only store over bible.db: books, chapter(book, ch) -> Chapter, verse lookup,
                     search(query, scope) via Amharic-only FTS5 with snippet highlighting
    userdata.py      user.db (sqlite, in data dir): bookmarks, highlights (named colour), notes (markdown text,
                     created/updated), history (last N positions), reading_position (resume), plan progress. No translation storage. Schema versioned with PRAGMA user_version + forward migrations.
    settings.py      typed Settings dataclass ↔ JSON at config dir; atomic write (tmp + os.replace);
                     unknown/invalid keys fall back to defaults with no crash
    credentials.py   separate atomic 0600 anthropic_key file; safe repr/errors, env-over-saved resolution
    plans.py         reading plans GENERATED from canon chapter counts (no hand-typed schedules):
                     whole canon in a year, New Testament in 90 days, Psalms+Proverbs monthly, Gospels in 30 days.
                     day N -> list of (book, chapter); progress = days completed; "today" from plan start date
    translate/       on-demand, one verse per request; NEVER persist translations
      base.py        Backend protocol: translate_verse(book, chapter, chapter_am, target) -> {target: text}
      claude.py      lazy optional Anthropic SDK, claude-sonnet-5-5; whole chapter's Amharic as context,
                     ONLY target verse as one N. text line; exact alignment verified
      google.py      translate-shell subprocess for target verse ONLY, bounded timeout
      service.py     auto = Claude if environment or saved Anthropic key, else Google if trans on PATH, else off;
                     async thread worker with timeout; no database writes
  ui/
    themes.py        custom textual.theme.Theme objects (see Themes); registered at startup
    morph.py         clock-driven reversible character reveal, theme-derived glow and shimmer
    styles/app.tcss  ONE stylesheet; use theme variables ($primary, $accent, $surface, $panel...), never hex
    screens/         reader, books (picker), search, bookmarks, notes, history, plans, settings, help,
                     verse_actions (modal menu for the selected verse)
    widgets/         header bar, verse view, chapter grid, status/footer bar, etc.
tests/               pytest; core unit tests + Textual Pilot UI tests
tools/smoke.py       boots the app headless at 50x30 and 120x40, walks every screen, saves SVG screenshots
                     to a given out dir, exits non-zero on any exception
tools/record_morph.py headless 50x30 SVG sequence at 50 ms animation-time steps for GIF assembly
```

### Translation contract

No bundled English, persisted English cache, coverage metadata, or placeholder text.
Enter or a verse tap translates that one verse in a worker. A soft theme-derived
shimmer sweeps over Amharic while fetching. When ready, morph IN PLACE using
`english[:i] + amharic[i:]` by Unicode character, rewrapping each frame. Advance
over approximately one second at 30 fps using set_interval; refresh only the
animating verse widget (the containing flowing paragraph in paragraph mode). The
last six revealed characters grade from secondary to accent, brightest at the
edge; unrevealed Amharic is dimmed. English rests in secondary colour with a dim
◇ marker and the original verse number. No separate translation line.
Enter/tap reverses the morph back to Amharic; mid-animation toggles reverse from
the current position. Re-showing cached text morphs forward without fetching.
Reduce motion defaults off; when enabled, swaps are instant and fetching uses a
static dim “Translating…” hint with no shimmer. Errors stop motion, restore Amharic
and show an actionable inline message (configure backend/key, check network, retry).
Results exist only in process memory and disappear on restart. Never write them to disk.
Existing user databases migrate forward by dropping `live_translation` and erasing its
freed contents; bookmarks, highlights, notes, history, resume, and plans survive.

### Anthropic key contract

Settings provides a password-masked API key field with explicit Save/Enter, Replace,
and Remove. After saving, display only `sk-ant-…` plus the last four characters;
never prefill the key. Never expose full keys in UI, logs, errors, SVGs, or Settings
repr. Keep credentials out of settings.json. Store only the key in
`<config dir>/anthropic_key`, created with `os.open(..., 0o600)` before writing;
replace atomically and never chmod afterward. Missing files are normal; removal
unlinks the file. Strip leading/trailing Unicode whitespace before validating.
Reject keys without the `sk-ant-` prefix, an empty suffix, or internal whitespace; errors are inline and leave the old file unchanged. Saving never calls
a service. Nonempty ANTHROPIC_API_KEY wins over the saved key; auto treats either
as Claude credentials. Pass the resolved key explicitly as `api_key=...`; never
mutate the process environment. Show the active source or Google/no-backend fallback.

## Features

- **Reader:** Amharic verse lines or flowing paragraphs. No English-only, interleaved,
  parallel, or language layout setting. Translations morph in place within the
  continuous paragraph as well as verse lines. Verse cursor up/down/j/k;
  chapter left/right/h/l and tappable ‹ ›; dim numbers, selection, annotation glyphs,
  theme-aware highlights. Book names may be Amharic, English, or both.
- **Translate:** Enter or tap a verse toggles its session translation. Repeated taps
  during a request do not issue duplicates. Navigation stays responsive.
- **Verse actions:** `a` or the footer Verse button opens bookmark/highlight/note/copy.
  No chapter translation action. Copy Amharic always; copy both languages only after
  that verse was translated this session. Never offer English-only copy. Use
  termux-clipboard-set when available, otherwise OSC 52.
- **Books:** section headings in canon order, filter names, chapter grid; `g` reference
  prompt. Validate every jump against source counts, including Psalm 151 guidance.
- **Search:** `/`, Amharic only, no language selector; all/OT/NT/current-book scopes.
  Safe plain typing, explicit `=` raw FTS with friendly syntax errors, styled snippets,
  consistent spacing between all results, Enter/tap jumps.
- **Collections:** bookmarks, highlights, Markdown notes with confirmation before
  deleting/discarding; recent history and resume; generated plans with mark-read,
  progress and streak. Positive progress below one percent displays `<1%`.
- **Settings:** theme, flow, numbers, spacing, book-name language, maximum reading
  width, Reduce motion (default off), translation backend, an Anthropic API key field, optional haptics. Persist immediately; removed/unknown
  legacy JSON keys are ignored. Six custom themes grouped first, built-ins after.
- **Help:** every binding including Enter = translate, a = actions; accent key chips.
- Below 80 columns, reader and secondary page headers occupy one row. Keep roomy
  wide headers, visible one-cell themed scrollbars, and a centred reading column.

## Themes

Several custom themes with Ethiopian character, each a full `Theme` (primary, secondary, accent,
foreground, background, surface, panel, success, warning, error, dark flag). At least:
`meskel` (warm gold on deep night), `tewahedo` (green / gold / red accents on dark),
`parchment` (light sepia, ink text), `lalibela` (rock-hewn stone + terracotta), `midnight`
(low-light, very dim, for reading in bed), `high-contrast`. Also allow Textual's built-ins.
Highlight colours are theme-aware (readable on every theme).

## Termux-first laws

- Design for **50 columns × ~30 rows** first; must also look good at 120×40. Nothing may clip or
  require horizontal scroll at 50 cols. Test both sizes.
- **Touch**: every primary action reachable by tap (Textual mouse events work in Termux). Generous
  tap targets (buttons ≥ 3 cells wide, 1 row tall min, spaced).
- **Keys**: single keys and arrows/Esc/Enter/Tab only (the Termux extra-keys row). No binding may
  need Ctrl/Alt combos. `escape` = back everywhere. `q` quits from the reader only.
- No heavy dependencies: `textual`, `rich` only (+ optional `anthropic`). Python ≥ 3.11.
  Startup < 1 s: lazy-import translate backends and anything optional.
- Never block the UI thread on IO > a few ms: translation and search run in Textual workers.
- Ge'ez/Ethiopic glyphs are 1 cell wide in Rich (verified); don't special-case widths.
- Runtime persistence stays inside the config/data dirs. Conversion and test/smoke
  tools may write their explicitly requested output paths and temporary fixtures.
  Never touch `~/.termux`.

## Code laws

- `core/` is pure Python with full type hints, testable without Textual.
- Text files opened with `encoding='utf-8'` always.
- Never `def _render` on a Widget/Screen (collides with Textual internals). Escape user/scripture
  text before putting it in Rich markup (`rich.markup.escape`) — square brackets occur in the text.
- No invented content: no fake verses, fake notes, sample data or made-up translations anywhere,
  including tests (tests use real verses from bible.db or explicit tmp fixtures marked as fixtures).
- Every behaviour has a test that would fail if the behaviour were reverted.
- Gates, all must pass before you report done:
  `ruff check src tests tools && ruff format --check src tests && mypy src && pytest -q && python tools/smoke.py --out /tmp/ebible-smoke`

## Process

- `.git` is writable for you: commit each coherent step on `rebuild/v2` with a clear message.
  Do NOT push, do NOT publish to PyPI, do NOT install anything globally (use `pip install -e .`
  inside a venv at `.venv/` if you need one).
- When done, report: what you built, the gate output (real numbers), anything you could not do,
  and every judgement call you made that the spec didn't settle.

## Status

- 2026-10-23: **Batch 7 complete** on `rebuild/v2`, package `ebible` 2.0.0.dev0.
  Phone key saves now trim leading/trailing Unicode whitespace and pasted newlines
  before validating; internal whitespace remains invalid. Masking, private atomic
  storage, environment precedence and safe errors remain unchanged.
- English replaces Amharic **in place** using `english[:i] + amharic[i:]`, with
  natural rewrapping, a six-character theme-derived glowing edge, dim remaining
  Amharic, and a repeating soft fetch shimmer. Full morphs take one second at
  30 fps. Enter/tap reverses from the current position; cached re-show morphs
  without fetching. English rests in secondary colour with a dim ◇ marker.
- Only animating verse widgets update. Paragraph flow caches unchanged verse
  fragments and updates its containing paragraph once per tick. Idle/hidden-screen
  timers pause; returning reconciles elapsed time. Reduce motion defaults off,
  persists immediately, uses instant swaps and a static fetch hint. Errors stop
  shimmer and restore Amharic with the existing actionable inline message.
- Required gates passed in `.venv` (Python 3.14.7, Textual 8.2.8):
  `ruff check src tests tools` — **all checks passed**;
  `ruff format --check src tests` — **62 files already formatted**;
  `mypy src` — **no issues in 41 source files**;
  `pytest -q` — **406 passed in 290.45s**, including **163 UI cases**;
  `python tools/smoke.py --out /tmp/ebible-smoke` — **216 SVGs passed**,
  36 states × 50×30 and 120×40 × meskel, parchment, lalibela.
  Gate output: `/tmp/b7-gates.log`.
- New coverage includes 11 morph unit cases, 14 Pilot cases at both sizes,
  one recording-tool test, and four key-trim cases (one formerly invalid padding
  case is now valid). Four isolated mutation checks fail on broken trimming,
  frame slicing, interruption continuity and glow. No network calls in tests.
- Smoke includes mid-shimmer, half-forward, half-reverse, English rest and paragraph
  morph states. Every SVG is checked for full fake keys before saving; an independent
  raw/XML-text scan of all 216 SVGs also passed. Output has 216 SVGs + manifest.txt;
  complete listing: `/tmp/ebible-smoke-listing.txt`.
- `tools/record_morph.py --out /tmp/ebible-morph` produced **65 SVG frames** at
  50 ms animation-time steps (20 fps), plus manifest.json with order/timestamps,
  stages and reveal indices. Real Genesis 1:1 Amharic and explicitly labelled
  fake English; isolated temporary XDG directories, no live service. Listing:
  `/tmp/ebible-morph-listing.txt`.
- Inspected shimmer/forward/reverse/rest/paragraph phone SVGs in all three smoke
  themes, wide reader/settings views, and nine representative recording frames.
  See [Batch 7 review](docs/BATCH7_REVIEW.md) for every implementation decision,
  test coverage, inspection and limits. README, help and current architecture
  notes match the new presentation and key-paste contracts.
- Packaged database unchanged: **12,521,472 bytes**, SHA-256
  `46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997`.
  Original-data checksums still match all **39,169 Amharic verse tuples and 81 book
  rows**; integrity tests pass. Schema, canon, raw source, source-issues documentation
  and both translation-guide copies are unchanged. No translation persistence.
- Batch 6 was independently verified and pushed by Claude before this work.
  Batch 7 used fake backends only; no physical Termux animation/performance run or
  real translation request was made. Headless real-timer Pilot cases pass a
  0.95–1.4 second completion bound at both terminal sizes.
- Implementation commits: `c3c7169` (key paste), `6e2f32e` (morph), `72b9e88`
  (smoke/recorder), followed by the documentation/status commit.
  **No Batch 7 push or publication was performed.**
