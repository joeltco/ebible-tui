# Batch 10 — a Bible cover and frontispiece

Batch 9 and Claude's search-count correction (`48fba9d`) were already pushed.
The correction remains: a loaded page says “40 passages · more below” when there
are more results. No search or translation behaviour was changed in this batch.

## Design and decisions

- The cover is a centred double-rule panel, at most 66 cells wide and 32 rows high.
  All four requested sizes have a dedicated geometry check: 40×20, 50×30, 74×30,
  120×40. The 40×20 variant reduces vertical gaps, keeping every action and the
  complete epigraph visible. A thin right-hand line suggests the page edge.
- `╔╗╚╝═║✦❖✣│─` are all exactly one cell according to `rich.cells.cell_len`.
  The title is **መጽሐፍ ቅዱስ**, as already used by this package, with **The Holy Bible**
  below. The database's metadata contains only schema/book/chapter/verse counts;
  no edition, publisher, translator or date was added.
- **Source-numbering decision:** the requested “lamp to my feet” verse is stored
  at **Psalms 118:105**. Source chapter 119 has only seven verses. We read 118:105
  directly from the read-only store and show “Psalm 119:105 · source 118:105”. The
  entire Amharic string, including its source stanza prefix, is retained. Reference
  parsing and source numbering are unchanged; no verse text is hard-coded.
- The primary Continue/Begin action uses two centred lines so the saved English
  reference has room on a phone. Books, Search, Plans and Settings share a smaller
  row, with a tappable close link below the frame. Tab/arrows cycle the six targets;
  Enter/Space activates. Direct keyboard shortcuts match the reader. `c` was free
  and now returns to the title page; Help lists it and includes a touch route.
- Links push ordinary pages over the cover: Escape returns there. Selecting a
  chapter, search result or plan reading still uses the existing validated jump
  into the reader. Escape/close on the cover quits; `q` remains reader-only.
- The default-on setting is an ordinary validated, atomically persisted boolean.
  Switching it off opens the reader directly next time. Explicit CLI `REF` values
  (`requested_reference`) bypass the cover regardless of that preference.

## Motion and implementation

- Entrance lasts **0.8 seconds**. All four sides extend from their corners first;
  the title, ornament and other lettering brighten during the latter phase. Effects
  reuse `ui.morph.palette` and `themes.effect_colours`, including the light-theme
  ink polarity. There are no new CSS colour literals.
- Opening is a **0.6-second** left-to-right wipe with a two-cell highlighted edge.
  The opaque cover widget narrows and shifts right over a transparent modal screen,
  exposing the real, already prepared reader. Its remaining content is cropped
  from the original canvas, so it does not squeeze or rewrap sideways.
- Both animations use one 30 fps `set_interval` timer. It pauses at rest and while
  another screen is current; returning adjusts the clock origin so hidden time
  does not advance motion. Resize uses the current terminal dimensions.
- Any key/tap during entrance finishes entrance only. During opening it finishes
  opening only, including taps in the already exposed reader region. Inputs are
  consumed and cannot accidentally translate a verse, navigate, or activate a link.
  Consequently the first Escape during an animation skips it; another quits.
- Reduce motion renders the final cover immediately and opens the reader without
  a wipe. Changing the theme or motion preference on a linked Settings page applies
  when returning to the cover.
- Frame construction is literal Rich `Text`, with explicit cell coordinates and
  independent hit rectangles. Verse brackets cannot become Rich markup. The same
  drawing functions power the live display, tests and recordings.

## Startup measurement

`tools/measure_startup.py` observes the first meaningful compositor frame in a
fresh process with new temporary config/data directories, at 50×30. It includes
Python imports and app initialization, excluding interpreter process creation,
terminal transport and physical screen latency. A transient empty loading screen
is not counted; the baseline must have chapter data, and the new app must have its
cover. The source filesystem cache was warm; no competing test/recording job was
running during the reported measurement.

The same probe ran 12 times against an exported `48fba9d` source tree and 12 times
against the new implementation:

| Version | Median first frame | Slowest sample |
|---|---:|---:|
| Before (`48fba9d`) | 708.70 ms | 807.21 ms |
| With cover | 596.50 ms | 662.18 ms |

Median improved by **112.20 ms (15.8%)**; every new sample is below one second.
The epigraph is read in the same background call as settings, counts and resume.
The cover is mounted before chapter rendering finishes, so the reader can prepare
behind it. This is time to first content, not time until the 0.8-second entrance
animation finishes. Timing JSON: `/tmp/b10-startup-before.json` and
`/tmp/b10-startup-after.json`. The earlier exploratory warm-import probe was
replaced by this reproducible fresh-process measurement.

## Verification and artifacts

The new coverage comprises **42 cover cases** (40 Pilot cases and two pure drawing/
settings cases), plus a recorder test that drives the real app. These exercise the
launch preference and CLI bypass, saved position, all links by tap and keyboard,
Escape/close, source epigraph and background loading, setting persistence, Help,
Reduce motion, skip-input consumption on both halves of the wipe, off-screen pause,
entrance colour/geometry progression, exact opening widths, timings, all themes,
all four sizes, literal brackets and deterministic recordings. Existing reader UI
fixtures explicitly opt out of launch covers so their original scope is preserved.
The existing Help row count now includes `c`; the smoke-isolation test checks all
30 independent temporary configurations, including the new cover matrix.

Smoke passed **354 SVGs**: the existing 43 views × 3 themes × 2 sizes (258), plus
entrance, finished cover, half-open and reduced-motion cover × 6 themes × 4 sizes
(96). All 96 cover views were visually inspected through raster contact sheets at
`/tmp/b10-visual/`. The 40×20 epigraph wraps to two lines without colliding with the
reference or actions; the frame and all links fit. Wide covers stay centred.
The opening edge clips the departing cover deliberately and reveals the reader;
no unwanted clipping, wrapped borders or collisions remained.

Visual correction during development: replacing segments in the drawn canvas had
removed their paper background, leaving darker/light rectangles behind the title,
ornament and primary action. Each replacement now preserves the panel background.
Final recordings and SVGs include the fix. No other screen redesign was required.

The manifest matches all 354 smoke filenames. An independent scan of raw SVG and
joined XML text covered **458 SVGs** (354 smoke + 104 recording frames), with **no
full fake credential strings**. Full listing: `/tmp/ebible-smoke-listing.txt`;
artifact checks: `/tmp/b10-artifact-checks.txt`; smoke log: `/tmp/b10-smoke.log`.
All required gates passed in the root `.venv` (Python 3.14.7, Textual 8.2.8):

| Gate | Result |
|---|---|
| `ruff check src tests tools` | All checks passed |
| `ruff format --check src tests` | 69 files already formatted |
| `mypy src` | No issues in 43 source files |
| `pytest -q` | **532 passed in 445.77s** |
| `python tools/smoke.py --out /tmp/ebible-smoke` | **354 SVGs passed** |

Combined output: `/tmp/b10-gates.log`. An earlier full run found only outdated Help
row-count and smoke-isolation expectations; those were updated and the full suite
rerun successfully. AGENTS.md Status records the same final results.

The packaged DB remains **12,521,472 bytes**, SHA-256
`46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997`.
No schema, canon, raw source, source-issues document or translation-guide bytes
were changed.

Recordings: `/tmp/ebible-title-meskel/title.gif` and
`/tmp/ebible-title-parchment/title.gif`. Each directory contains 52 SVG frames plus
`manifest.json` with 50 ms timing, stage, reveal progress and wipe position.
The sequence includes entrance, a finished-cover hold, opening and a reader hold.
`tools/record_title.py --gif` uses installed librsvg and ImageMagick; these are
optional development tools, not app dependencies. No network or translation backend
is involved. All recorder and smoke personal data uses temporary XDG directories.

No push, package publication, live service call or physical Termux session was
performed. Glyph widths are verified in Rich and rasterized SVGs, not on Joel's
actual terminal font. GIF and startup measurements are host review artifacts.

Implementation commits: `75694d4` (cover and behaviour), `6a0bd2e` (tools and smoke
matrix), `17638f1` (existing regression expectations), followed by the documentation
and Status commit. Nothing was pushed.
