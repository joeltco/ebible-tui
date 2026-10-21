# eBible v2 — agent brief

Read this whole file before touching anything. It is the spec and the rules.

## What this is

A sophisticated terminal Bible reader for the **81-book Ethiopian Orthodox Tewahedo
canon**, Amharic with English, built with **Textual**, designed **first for Termux on an
Android phone** (Galaxy S25, portrait, touch + Termux extra-keys row), and working
equally on a desktop terminal.

This is a ground-up rebuild on branch `rebuild/v2`. The only things carried over from
the previous attempts are DATA, not code:

| Path | What | Rule |
|---|---|---|
| `src/ebible/data/bible.db` | compiled scripture: 39,169 verses, `text_am` all, `text_en` for 20,443 (52%), FTS5 index `verse_fts` | ⛔ **never modify, rebuild or reformat it.** Open it read-only (`file:...?mode=ro`, `uri=True`). |
| `src/ebible/data/schema.sql` | that db's schema | reference only |
| `src/ebible/canon.py` | the 81 books, Ethiopian order, sections, deuterocanonical flag | keep the data rows exactly; you may tidy the module API |
| `source/Bible81/` | raw Amharic source text the db was built from | never edit |
| `docs/translation/*.md` | the binding translation guide, source defects, pipeline notes | `TRANSLATION_GUIDE.md` is the live translator's instructions |
| `tools/translation/*.py` | the offline translation pipeline | fix import/paths only (they moved: `assets/Bible81` → `source/Bible81`, `tools/` → `tools/translation/`) |

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
                     search(query, scope, lang) via FTS5 with snippet highlighting; English overlay (below)
    userdata.py      user.db (sqlite, in data dir): bookmarks, highlights (named colour), notes (markdown text,
                     created/updated), history (last N positions), reading_position (resume), plan progress,
                     live translations. Schema versioned with PRAGMA user_version + forward migrations.
    settings.py      typed Settings dataclass ↔ JSON at config dir; atomic write (tmp + os.replace);
                     unknown/invalid keys fall back to defaults with no crash
    plans.py         reading plans GENERATED from canon chapter counts (no hand-typed schedules):
                     whole canon in a year, New Testament in 90 days, Psalms+Proverbs monthly, Gospels in 30 days.
                     day N -> list of (book, chapter); progress = days completed; "today" from plan start date
    translate/       live fill for verses whose text_en is NULL:
      base.py        Backend protocol: translate_chapter(book, chapter, verses_am) -> {verse: text}
      claude.py      Anthropic SDK (optional extra `ebible[claude]`, imported lazily); model claude-sonnet-5-5;
                     system prompt = packaged TRANSLATION_GUIDE.md; whole chapter per request; verse-number
                     alignment VERIFIED (missing/extra numbers = reject, never shift)
      google.py      `trans` (translate-shell) subprocess fallback, per verse, timeout
      service.py     picks backend (setting: auto|claude|google|off; auto = claude if ANTHROPIC_API_KEY else
                     google if `trans` on PATH else off), runs in a worker, writes to userdata live table
  ui/
    themes.py        custom textual.theme.Theme objects (see Themes); registered at startup
    styles/app.tcss  ONE stylesheet; use theme variables ($primary, $accent, $surface, $panel...), never hex
    screens/         reader, books (picker), search, bookmarks, notes, history, plans, settings, help,
                     verse_actions (modal menu for the selected verse)
    widgets/         header bar, verse view, chapter grid, status/footer bar, etc.
tests/               pytest; core unit tests + Textual Pilot UI tests
tools/smoke.py       boots the app headless at 50x30 and 120x40, walks every screen, saves SVG screenshots
                     to a given out dir, exits non-zero on any exception
```

### English overlay
Display English = bundled `text_en`, else live translation from user.db, else an honest
"not yet translated" placeholder (styled, never blank). Live text is visibly marked (e.g.
a dim `◇` or "machine" tag) so it is never mistaken for the reviewed bundled text.
Deuterocanonical books have no bundled English in some cases; the placeholder says so.

## Features (all v1)

- **Reader**: verse-per-line or paragraph flow; layouts `amharic`, `english`, `interleaved`
  (Amharic then English per verse), `parallel` (side by side; auto-falls back to interleaved
  when width < 90). Verse cursor (up/down/j/k), chapter prev/next (left/right/h/l and
  clickable ‹ › buttons), smooth scroll, selected-verse highlight, highlights rendered in their colour,
  bookmark/note glyphs in the gutter. Header shows book (Amharic · English per setting) and chapter.
- **Book picker**: grouped by section with Ethiopian order, filter-as-you-type, then a tappable
  chapter grid. `g` = go-to-reference prompt using refs.py.
- **Verse actions** (Enter or tap a verse): bookmark, highlight (colour swatches), add/edit note,
  copy (Amharic / English / both, with reference), translate now (live fill this chapter).
  Copy: `termux-clipboard-set` if on PATH, else Textual's OSC 52 `copy_to_clipboard`.
- **Search** (`/`): FTS over Amharic and English, scope (all / OT / NT / current book), results list
  with highlighted snippet; Enter jumps and selects the verse.
- **Bookmarks / highlights / notes** screens: list, jump, delete (with confirm), notes editable in a TextArea.
- **History + resume**: app reopens at last position; history screen of recent positions.
- **Reading plans**: choose a plan, see today's chapters, mark read, streak/progress bar.
- **Settings** screen (persisted immediately): theme (live preview), layout, verse numbers, verse
  spacing (compact/comfortable), book-name language (am/en/both), text max-width, translation backend,
  show-untranslated-placeholder, haptic feedback (`termux-vibrate -d 20` on bookmark, off by default).
- **Help** (`?`): every binding.

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
- Never write outside the config/data dirs. Never touch `~/.termux`.

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

- 2026-10-21: **Batch 1 complete** on `rebuild/v2`: package `ebible` 2.0.0.dev0,
  typed core, references, read-only scripture/FTS/English overlay, versioned personal
  data, atomic settings, generated plans, validated live translation workers,
  relocated offline-tool imports/paths, and a minimal bootable CLI/placeholder.
- Required gates passed in `.venv` (Python 3.14.7, Textual 8.2.8):
  `ruff check src tests tools` — all checks passed;
  `ruff format --check src tests` — 25 files already formatted;
  `mypy src` — no issues in 17 source files;
  `pytest -q` — **200 passed in 2.88s**;
  `python tools/smoke.py --out /tmp/ebible-smoke` — **50×30 and 120×40 passed**,
  SVGs saved as `ebible-50x30.svg` and `ebible-120x40.svg` in that directory.
- Additional validation: **100% core statement coverage (580 statements)**;
  built wheel contains byte-identical DB/schema/stylesheet/translation guide;
  packaged headless boot including imports/data checks took **0.319s** on this host.
  `ebible --version` reports `ebible 2.0.0.dev0`; offline `translate.py status`
  reports **20,443 / 39,169 (52.2%), 35 / 81 books complete**.
- Protected database unchanged: SHA-256
  `167e4b3d97977e74ea77eebeb9609e8b0ef2fdd68798a6aa2a05cc1cf7d7e6cb`.
  Canon rows, raw source, schema, and binding translation documentation unchanged.
  All translation tests use fake clients/subprocesses; no translation network calls.
- **Batch 2 not started.** Reader screens, custom themes, persisted UI preferences/resume,
  live-text styling, and device integration remain for that batch. Physical Termux
  and real translation services were not exercised. See
  [foundation decisions](docs/FOUNDATION.md) for every implementation judgement,
  API convention, and the inherited offline writers' restrictions. Three implementation
  commits: `ac4b501`, `1b51833`, `4662c99`; nothing pushed or published.
