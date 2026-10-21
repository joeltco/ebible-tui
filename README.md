# eBible · መጽሐፍ ቅዱስ

A Termux-first terminal reader for the **81-book Ethiopian Orthodox Tewahedo
canon**, in Amharic and English. Built for a 50×30 phone terminal, with a centred
reading column and parallel languages on wider terminals.

## Run locally

Requires Python 3.11 or newer. Everything installs inside the repository's venv:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ebible
# Open a passage or choose a theme for this session:
ebible 'john 3:16' --theme parchment
ebible 'ዘፍ 1'
ebible --version
```

The reader resumes your last position. An explicit CLI reference overrides resume;
`--theme` overrides the saved theme for the session. Settings changes save immediately.

## Read, keep, return

- Amharic, English, interleaved, or parallel languages. Parallel falls back to
  interleaved below 90 terminal columns. Choose verse lines or continuous paragraphs.
- Six custom themes: `meskel`, `tewahedo`, `parchment` (light), `lalibela`, `midnight`,
  and `high-contrast`, plus Textual's built-ins.
- Tap a verse or press Enter for bookmarks, colour highlights, Markdown notes,
  copying, or live chapter translation. `◆` marks a bookmark; `✎` marks a note.
- Browse the canon by section, filter English/Amharic book names, or use the chapter grid.
- Search, saved collections, history, and generated reading plans each have dedicated
  screens. Delete and restart actions ask for confirmation; unsaved notes are protected.

All primary actions are tappable. From the reader:

| Keys | Action |
|---|---|
| `↑` / `k`, `↓` / `j` | Previous / next verse |
| `←` / `h`, `→` / `l` | Previous / next chapter |
| Enter | Selected verse's actions |
| `b`, `/`, `g` | Books, search, go to reference |
| `m`, `v`, `n`, `t` | Bookmarks, highlights, notes, history |
| `p`, `s`, `?` | Plans, settings, help / more destinations |
| Tab, Enter / Space | Focus and activate controls |
| Escape | Back; at the reader, return focus to reading |
| `q` | Quit from the reader |

Typing in a search, reference, or note field never activates reader shortcuts.
The Help screen includes touch routes to every destination and a Quit button.

## Search and source numbering

Search treats ordinary words and punctuation as plain text, including `john's`
and `God AND`. The last word is a prefix for search-as-you-type. Start a query
with `=` for raw FTS5, for example `="LORD God"`. Invalid advanced syntax shows
an explanation without closing the search screen. Search covers bundled English
and Amharic; it does not index live translations.

Every jump validates the actual stored chapter and verse numbers. **Psalm 151
is filed as Psalms 150:7-14** in this source: use `ps 150:7-14`. A request for
`ps 151` explains this placement. No text is invented, renumbered, or rebuilt.

## Data and live translation

The protected `src/ebible/data/bible.db` contains 39,169 Amharic verses and reviewed
English for 20,443. It is opened read-only. Never rebuild or modify it. The raw
Amharic source, canon rows, schema, and binding translation documentation are preserved.

Settings use `$XDG_CONFIG_HOME/ebible` (default `~/.config/ebible`). Personal data
uses `$XDG_DATA_HOME/ebible` (default `~/.local/share/ebible`). Relative or empty
XDG variables use the defaults. The app never changes `~/.termux`.

Live English is stored separately in `user.db`, with backend and timestamp
provenance, and displayed with **◇ Machine**. Bundled English always wins.
Missing English always shows an honest marker; Settings can shorten its explanation.

```sh
# Optional Claude backend, installed inside the activated venv:
pip install -e '.[claude]'
```

With `ANTHROPIC_API_KEY` set, automatic mode selects Claude; otherwise it uses
translate-shell's `trans` if available, otherwise off. Explicit backend choices
are also available. Translation runs only when you tap **Translate this chapter**.
Claude uses `claude-sonnet-5-5`, the byte-identical packaged translation guide, and
an in-app addendum requiring numbered lines without summaries. A single code fence
is tolerated; missing, extra, duplicate, blank, or incomplete verses are rejected
before any translations are saved. Google fallback translates per verse.

Copy uses `termux-clipboard-set` when available, otherwise OSC 52. Optional bookmark
vibration uses `termux-vibrate -d 20` and is off by default. Termux commands run in
workers with timeouts; tests simulate them without invoking device services.

The relocated offline pipeline's read commands work:

```sh
python tools/translation/translate.py status
python tools/translation/translate.py pull john 3
python tools/translation/translate.py next --count 5
```

Only import/path repairs were made to the inherited pipeline. Its `translate.py`
legacy writable-helper name aliases the read-only helper, so `push` cannot modify
the protected database. Other inherited maintenance scripts retain their write
logic and must not be run against it.

## Development checks

```sh
ruff check src tests tools
ruff format --check src tests
mypy src
pytest -q
python tools/smoke.py --out /tmp/ebible-smoke
```

Smoke uses temporary XDG directories and visits every screen and modal at 50×30
and 120×40 under meskel, parchment, and lalibela. It writes 144 SVGs plus a
`manifest.txt`, including reference/search errors, confirmation sheets, the theme
picker, paragraph/parallel layouts, and untranslated passages. It never touches
real preferences or personal data.

See [AGENTS.md](AGENTS.md) for the binding spec and current gate results,
[foundation decisions](docs/FOUNDATION.md) for core conventions, and
[UI decisions](docs/UI_DECISIONS.md) for interaction and visual choices.
