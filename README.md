# eBible · መጽሐፍ ቅዱስ

A Termux-first **Amharic reader** for the 81-book Ethiopian Orthodox Tewahedo
canon. Built for a 50×30 phone terminal, with a centred reading column on desktop.

**Press Enter or tap a verse to translate it.** English appears beneath that verse;
press Enter or tap it again to hide it. Re-showing is instant within the same session.
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
English, or both. Opening a translation in paragraph flow places it beneath its
source verse; hiding it restores the continuous paragraph.

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
| `b`, `/`, `g` | Books, search, go to reference |
| `m`, `v`, `n`, `t` | Bookmarks, highlights, notes, history |
| `p`, `s`, `?` | Plans, settings, help |
| Tab, Enter / Space | Focus and activate controls |
| Escape | Back; in the reader, return focus to reading |
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
and rejects whitespace, without making a network request. After saving, only
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
navigation remain responsive. `◇ Translation` identifies the secondary-coloured
English. Repeated taps during a request do not create duplicate requests.

## Search and source numbering

Search indexes **Amharic only**. Plain words and punctuation are safe as you type;
the last token is a prefix. Start with `=` for raw FTS5, for example
`="እግዚአብሔር"`. Invalid syntax gets an explanation. All/OT/NT/current-book scopes
are available, and every result has the same one-row gap after its snippet.

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
and lalibela. It visits every screen/modal, including translating, translated,
translation-error, actions, and Amharic search states. All translation responses in
smoke and tests are explicitly labelled fixtures; no real backend or network is used.

See [AGENTS.md](AGENTS.md) for the binding spec and current gate results and
[UI decisions](docs/UI_DECISIONS.md) for interaction choices.
