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
Enter or a verse tap translates that one verse in a worker. A visible eight-character
theme-derived shimmer sweeps over slightly dimmed Amharic every 0.9 seconds while fetching;
its centre is bold with a soft background tint. When ready, morph IN PLACE using
`english[:i] + amharic[i:]` by Unicode character, rewrapping each frame. Advance
over approximately one second at 30 fps using set_interval; refresh only the
animating verse widget (the containing flowing paragraph in paragraph mode). The
last twelve revealed characters grade from secondary to a strong accent tint,
brightest at the edge. Theme effects derive in themes.py: accent blended 60%
toward white on dark themes or foreground ink on light themes. The leading three
characters are bold with an accent background tint (35% over panel, feathered).
Unrevealed Amharic is dimmed. At forward completion, the whole English verse
pulses once from accent tint to rest over 300 ms; reverse ends quietly. English
rests in secondary colour with a dim ◇ marker and the original verse number. No separate translation line.
Enter/tap reverses the morph back to Amharic; mid-animation toggles reverse from
the current position. Re-showing cached text morphs forward without fetching.
Reduce motion defaults off; when enabled, swaps are instant without a completion
pulse, and fetching uses a static dim “Translating…” hint with no shimmer. Errors stop motion, restore Amharic
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

- 2026-10-23: **Batch 8 complete** on `rebuild/v2`, package `ebible` 2.0.0.dev0.
  Effect intensity only: twelve-character glow with a bold leading three and
  feathered accent background; eight-character fetch shimmer every 0.9 seconds;
  one 300 ms whole-English colour fade after forward completion. Reverse ends
  quietly. One-second reveal, reversal, cache behaviour and Reduce motion remain.
- Effect colours derive from each Theme in themes.py: accent blended 60% toward
  white on dark themes or foreground ink on light themes; peak background tint is
  accent at 35% over panel. The waiting source dims 18% toward background.
  Edge-centre versus resting-English **CIELAB ΔE76 ≥18** on all six custom themes
  (measured range **18.56–24.62**), with separate bold/background/gradient tests.
- Required gates passed in `.venv` (Python 3.14.7, Textual 8.2.8):
  `ruff check src tests tools` — **all checks passed**;
  `ruff format --check src tests` — **63 files already formatted**;
  `mypy src` — **no issues in 41 source files**;
  `pytest -q` — **427 passed in 305.63s**, including **169 UI cases**;
  `python tools/smoke.py --out /tmp/ebible-smoke` — **222 SVGs passed**,
  37 states × 50×30 and 120×40 × meskel, parchment, lalibela.
  Gate output: `/tmp/b8-gates.log`.
- Added 14 unit cases for palette visibility, shimmer and flourish timing, six
  Pilot cases for the pulse, update isolation, quiet reverse and Reduce motion,
  plus a CLI text/theme recording test. Updated existing animation and recorder
  checks for the new effects. Four isolated mutation checks fail on old width,
  missing peak tint, old shimmer period and missing flourish (`/tmp/b8-mutations.log`).
- Smoke now captures the completion pulse separately from settled English.
  Every SVG is checked for fake-key disclosure before saving; an independent
  raw/XML-text scan of all 222 SVGs also passed. Output: 222 SVGs + manifest.txt;
  complete listing `/tmp/ebible-smoke-listing.txt`.
- `tools/record_morph.py` accepts **--text** (default labelled fixture) and **--theme**.
  Recorded meskel, parchment and midnight at 50×30 into
  `/tmp/ebible-morph-b8/{meskel,parchment,midnight}/`: **71 SVG frames each**, at
  50 ms animation-time steps (20 fps), plus manifests with timing, reveal indices
  and flourish strength. Total: **213 SVGs + three manifests**. Complete listing:
  `/tmp/ebible-morph-b8-listing.txt`. These recordings use the default fixture.
- Inspected rendered shimmer, mid-morph, peak/fading flourish and rest at 50×30
  in all six themes, plus 120×40 flourish views in all three smoke themes. No
  clipping or layout corrections were needed. See [Batch 8 review](docs/BATCH8_REVIEW.md)
  for every colour/timing decision, per-theme measurements, test and artifact details.
  README and current architecture/spec notes match the brighter effects.
- Packaged database unchanged: **12,521,472 bytes**, SHA-256
  `46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997`.
  Original-data checksum tests match all **39,169 Amharic verse tuples and 81 book
  rows**; integrity tests pass. Schema, canon, raw source, source-issues documentation
  and both translation-guide copies remain unchanged. No translation persistence.
- Batch 7 was independently verified and pushed by Claude before this work; Claude
  also recorded a real Google Genesis 1:1 translation for Joel. Batch 8 used fake
  backends only; no physical Termux performance run or live service request was
  made. `--text` can record an existing real translation without a network call.
- Implementation commits: `fa973b9` (effects/tests), `2d3b9f4` (recorder/smoke),
  followed by the documentation/status commit. **No Batch 8 push or publication.**
