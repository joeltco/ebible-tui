# eBible · መጽሐፍ ቅዱስ

A Termux-first **Amharic reader** for the 81-book Ethiopian Orthodox Tewahedo
canon. Built for a 50×30 phone terminal, with a centred reading column on desktop.

Launch opens an ornamental Bible cover. **Continue reading** opens your saved
place; **Begin** starts at Genesis 1. Books, Search, Plans and Settings are directly
tappable. Press **`c`** in the reader to return to the cover, or use Help → Title page.
Escape (or the close link) quits from the cover. Settings → **Title page on launch**
turns it off; a CLI reference always opens the reader directly.

The frame draws in and the cover opens with a page-edge wipe. Any key or tap during
an animation skips it; **Reduce motion** makes both transitions instant. The cover
fits 40×20, 50×30, 74×30 and 120×40. Its epigraph is the exact DB text of the requested
Psalm 119:105, stored at **118:105** in this source; both references are shown.

**In the reader, press Enter or tap a verse to translate it.** A bright, theme-matched band sweeps
over Amharic while fetching. English replaces it from left to right with a bold,
glowing edge, then briefly pulses before settling.
Tap again to morph back; tapping mid-animation reverses from that position.
Re-showing uses the session result and plays the morph without another request.
Translations are never saved to disk and disappear when the app closes.

## Run locally

Requires Python 3.11 or newer. Install inside the repository's venv:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ebible
ebible 'john 3:16' --theme parchment
ebible 'ዘፍ 1'
ebible --version
```

The reader resumes your last position. A CLI reference overrides resume; `--theme`
overrides the saved theme for the session. Settings changes save immediately.

## Read, translate, keep

Choose Amharic verse lines or flowing paragraphs. Book names may be Amharic,
English, or both. Translations replace their source verse in place in either flow;
text rewraps as its length changes. Full morphs take about one second.
**Settings → Reduce motion** gives instant swaps and a static fetching hint.

Below 80 columns, one-row headers leave room for reading. Six custom themes
(`meskel`, `tewahedo`, `parchment`, `lalibela`, `midnight`, `high-contrast`) appear
first in the theme picker, followed by Textual's built-ins.

Press **`a`** or tap the footer **Verse** button for bookmarks, colour highlights,
Markdown notes, and copying. `◆` marks a bookmark; `✎` marks a note. Copy Amharic
with its reference, or include a verse's translation if it was requested during
this session. There is no English-only copy action.

Browse books by section, filter English/Amharic names, and choose a chapter.
Search, saved collections, history, and generated reading plans have dedicated
screens. Deletion/restart requires confirmation; unsaved notes are protected.

| Keys | Action |
|---|---|
| `↑` / `k`, `↓` / `j` | Previous / next verse |
| `←` / `h`, `→` / `l` | Previous / next chapter |
| Enter / tap a verse | Translate / hide that verse's translation |
| `a` / footer Verse | Verse actions |
| `c` / Help → Title page | Return to the cover |
| `b`, `/`, `g` | Books, search, go to reference |
| `m`, `v`, `n`, `t` | Bookmarks, highlights, notes, history |
| `p`, `s`, `?` | Plans, settings, help |
| Tab, Enter / Space | Focus and activate controls |
| Escape | Back; reader: focus reading; title page: quit |
| `q` | Quit from the reader |

Typing in search, reference, and note fields never activates reader shortcuts.
Every primary action is tappable; no Ctrl/Alt combinations are required.

## On-demand translation

```sh
# Optional Claude backend, inside the activated venv:
pip install -e '.[claude]'
```

In **Settings → Translation & Touch**, paste your Anthropic API key into the masked
field and select **Save key** (or press Enter). Saving checks the `sk-ant-` prefix
after trimming spaces/newlines from the ends, and rejects internal whitespace.
Saving never makes a network request. After saving, only
`sk-ant-…` and the final four characters are shown. **Replace** starts a blank masked
entry; **Remove** deletes the saved key. Cancel or Escape leaves the existing key
unchanged. The source label shows whether the environment, saved key, or Google
fallback is active. An environment key continues to work after removing a saved key.

The key is stored separately at `$XDG_CONFIG_HOME/ebible/anthropic_key` (default
`~/.config/ebible/anthropic_key`), created privately with mode `0600` and replaced
atomically. It never enters `settings.json`. This is a private local file, not an
encrypted credential vault.

Automatic mode chooses Claude when `ANTHROPIC_API_KEY` is set or a saved key exists.
A nonempty environment key takes precedence over the saved key. Otherwise it uses
translate-shell's `trans` when available, otherwise off. Settings also offers
explicit Claude, Google, and Off choices. With no backend, Enter explains how to
configure one inline. Network errors, timeouts, and mismatched verse numbers also
show an inline message with a retry/configuration action.

Claude uses `claude-sonnet-5-5` and the unchanged translation guide. It receives the
whole chapter's Amharic as context, but must return **only the requested verse** as
one `N. text` line. A single surrounding code fence is tolerated; wrong, missing,
extra, duplicate, empty, incomplete, or commentary-bearing responses are rejected.
Google receives only the target verse. Requests run in workers while reading and
navigation remain responsive. A dim `◇` beside the verse number identifies
secondary-coloured machine English. Repeated taps during a request do not create duplicate requests.

## Search and source numbering

**Type Amharic or English.** Amharic searches safely as you type, using token/prefix
matching. Submit an English word with **Enter** or **Search** to translate it into
Amharic with the active backend. Nothing is sent while you type. The query line
shimmers while waiting; Reduce motion gives a static hint.

English results show the Amharic terms and original query. Tap a term to put it in
the box and refine it (keyboard: Tab to the terms, arrows to choose, Enter to use).
Select a result to open it. English submissions stay on the result page; Enter on a
typed Amharic query still opens its first result.

Translated queries match substrings, finding affixed forms such as በብርሃን and
ብርሃንም, and list results in canonical order. Google returns one Amharic form;
Claude can return up to three. All/OT/NT/current-book scopes and Show more work for
both search paths. Query translations are reused only within this session and are
never saved to disk. Errors explain how to enable a backend or retry.

Mixed Latin/Ethiopic queries are searched as typed. Start with `=` for raw FTS5,
for example `="እግዚአብሔር"`; these queries are never translated. Invalid syntax gets
an explanation. Only Amharic scripture is indexed—there is no English scripture
cache. Every result has the same one-row gap after its snippet.

Every jump validates actual source chapter and verse numbers. **Psalm 151 is filed
as Psalms 150:7-14**: use `ps 150:7-14`. No verses are invented or renumbered.

## Storage

The packaged `src/ebible/data/bible.db` contains 39,169 Amharic verses and no English
scripture, English FTS column, or translation-coverage metadata. Runtime access is
read-only. Batch 5 removed English with `tools/strip_english.py`; every original
Amharic verse tuple and book row is protected by the recorded pre-removal checksums
in `tests/fixtures/amharic_checksums.json`. The old database is recoverable from git
at `e1564db`; no old-English database copy is kept in the tree.

To reproduce the stripped database from a source database:

```sh
python tools/strip_english.py /path/to/source.db --out /tmp/amharic.db
```

The tool preserves the source values, builds Amharic-only FTS, verifies the result,
VACUUMs it, and atomically replaces its destination. The offline translation pipeline
has been removed. The translation guide and source-issues document remain intact.

Preferences use `$XDG_CONFIG_HOME/ebible` (default `~/.config/ebible`); annotations,
history, resume, and plans use `$XDG_DATA_HOME/ebible/user.db` (default
`~/.local/share/ebible/user.db`). Relative/empty XDG values use these defaults.
Existing user databases migrate forward to drop and erase the old translation cache
while preserving personal data. Removed settings keys are ignored safely.

Copy uses `termux-clipboard-set` when available, otherwise OSC 52. Optional bookmark
vibration uses `termux-vibrate -d 20`, off by default. The app never changes `~/.termux`.

## Development checks

```sh
ruff check src tests tools
ruff format --check src tests
mypy src
pytest -q
python tools/smoke.py --out /tmp/ebible-smoke
```

Smoke uses temporary XDG directories at 50×30 and 120×40 under meskel, parchment,
and lalibela. It also captures four cover states at all four sizes under all six
custom themes: **354 SVGs** total. The reader suite visits every screen/modal, including shimmer, mid-morph,
reverse, completion pulse, translated, error, actions, and Amharic/English search
states (including query shimmer, reduced motion, terms and errors). All translation responses in
smoke and tests are explicitly labelled fixtures; no real backend or network is used.

Record the cover's entrance and opening at 50×30 (52 SVGs at 50 ms steps):

```sh
python tools/record_title.py --out /tmp/ebible-title-meskel --theme meskel --gif
python tools/record_title.py --out /tmp/ebible-title-parchment --theme parchment --gif
python tools/measure_startup.py --out /tmp/ebible-startup.json
```

`--gif` uses installed `rsvg-convert` and ImageMagick `magick`; omit it for SVGs
only. The tools use temporary XDG directories and do not call translation services.

Record a deterministic 50×30 morph sequence for a GIF:

```sh
python tools/record_morph.py --out /tmp/ebible-morph --theme meskel
```

This exports 71 SVG frames at 50 ms animation-time steps (20 fps), plus
`manifest.json` with order, timing and reveal indices. It uses real Genesis 1:1
Amharic and explicitly labelled fixture English, isolated temporary XDG dirs,
and no network. The sequence includes fetching, forward, a 300 ms completion
pulse, rest and reverse. Pass `--text` with existing English text to record it
instead of the fixture; `--theme` also accepts parchment, midnight and other themes.

See [AGENTS.md](AGENTS.md) for the binding spec and current gate results and
[UI decisions](docs/UI_DECISIONS.md) for interaction choices.
