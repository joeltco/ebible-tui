# Batch 5 review — Amharic reading, translation on demand

Joel's direction supersedes the previous English overlay/layout contract. The
reader now starts with Amharic only. Enter or tapping a verse requests its English
translation inline; repeating the action hides/re-shows it. Results exist only in
memory for the current app session. `a` and the footer Verse button open actions.

## Data conversion and preservation

The packaged database is **12,521,472 bytes**, down from **19,423,232 bytes**.
Its SHA-256 is:

```
46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997
```

`tools/strip_english.py` creates a fresh Amharic-only database, preserving every
book row, verse ID, chapter/verse number, and Amharic value. It rebuilds FTS on
`text_am` only, keeps only schema/book/chapter/verse counts, validates rows and FTS,
VACUUMs, then replaces the destination atomically. Source and destination may be
the same path. Repeated builds are byte-identical on the tested SQLite 3.53.4.
The actual database retrieved from `e1564db` reproduced the packaged bytes exactly.

The golden checksum test passed for **all 39,169 verse tuples and all 81 book rows**.
Checksums were recorded before conversion using UTF-8 compact JSON arrays, one
row per line, ordered by book/chapter/verse (books by ID):

- Verse tuples: `baf8fb427a14db0cf61677c1c1dbf11b03a28402aca264cba0958fb69a4c7d3b`
- Book rows: `aee558fe17f3bbe04320dcb086d126768168043fd5055ce3613890d08934d127`

Read-only integrity check returned `ok`; the freelist is empty. Canon data and
code are unchanged apart from its obsolete introductory translation comment.
Raw Amharic source, SOURCE_ISSUES, and both translation-guide copies are unchanged.
The offline pipeline and its RESUME/AGENT_BRIEF documents were removed. A stale
ignored `build/` package containing the old database was also removed. No old
English database or distribution archive remains in the tree.

User schema v3 drops `live_translation`, using secure deletion, VACUUM and WAL
truncation to remove its contents. Tests upgrade a populated v2 fixture and verify
bookmarks, highlights, notes, history, resume and plan progress survive, while the
cache table/API and a sentinel translation disappear. Runtime translation has no
user-store dependency and never writes results to disk.

## Interaction and implementation decisions

- Translation is one verse. Claude receives the whole Amharic chapter as context
  and must return exactly the target `N. text` line. The original guide is followed
  by an explicit single-verse/no-summary/no-commentary addendum. Google receives
  only the selected verse. Strict alignment rejection and one optional code fence
  remain; non-final Claude responses are rejected.
- Backend priority stays Claude with a key, otherwise translate-shell, otherwise
  off. A selected backend's failure is reported inline, without silently switching
  services. Claude uses a 30-second SDK timeout and no retries; Google uses 20
  seconds; the service has a 45-second outer deadline and a 4,096-token Claude
  output budget. A timed-out thread may finish cleanup later; its result is discarded.
- Pending taps do not duplicate a request. Different verses may translate
  concurrently. Navigation does not cancel a request; completion updates that
  verse's session result and refreshes only the currently open chapter.
- Enter retries after an error. Results use the theme's secondary colour and
  “◇ Translation”; pending/errors use a readable foreground/background blend.
- Paragraph flow remains Amharic. A visible translation interrupts the paragraph
  directly beneath its source verse; hiding it restores continuous flow. Existing
  verse hit targets, numbers, selection, annotations and cursor scrolling remain.
- Copy Amharic is always available. “With translation” is available after that
  verse was translated during this session, even when currently hidden. It includes
  both source and translation, with reference and machine marker. English-only copy
  and chapter translation are gone.
- All scripture-language layouts, placeholder settings/notices, English search and
  the search-language selector are removed. Book-name language remains. Unknown
  legacy settings keys are ignored while valid preferences survive.
- Search results have one explicit bottom padding row. Reserving scrollbar space
  before measurement prevents wrapped snippets from retaining heights measured at
  a wider width. The regression checks allocated heights as well as rendered blank
  rows; merely rendering a blank row was insufficient to expose the old problem.
- Translation/resize refreshes serialize passage rebuilds. Cursor changes during
  rebuilding are applied when mounting finishes; queued scroll callbacks wait for
  widgets to exist. A deterministic Pilot test removes the widgets mid-refresh,
  then delivers cursor and scroll callbacks in both flows.

## Tests and visual review

The regression suite covers database stripping/determinism, checksums, v2 cache
removal, exact target alignment with chapter context, Google target-only input,
workers/timeouts, inline pending/results/errors, duplicate requests, navigation,
toggle/re-show, restart forgetting results, actions/copy, removed settings/search
controls, help/README, consistent search gaps, and the rebuild race. Clients,
backends, device commands and translation responses are fakes, never network calls.
Obsolete tests for removed layouts, overlay precedence and offline tools were
replaced with tests of the new contract; retained reference/annotation/plan/theme
and navigation tests still run.

Against an isolated copy of pushed Batch 4, eight checks failed: bundled-English
schema, cache migration, Enter translation, `a` actions, legacy settings removal,
help, actual allocated search-result spacing, and the single-verse Claude API.
Separately removing the new rebuild guards failed both phone-flow race tests.

Inspected rendered SVGs, not only geometry, for these 12 phone states in meskel,
parchment and lalibela: reader, translating, translated, translation error, actions,
actions with translation, settings, paragraph, search, help, help bindings and
Jubilees. The final search views were rechecked after reserving scrollbar space. Also
inspected the wide translated reader and translated paragraph geometry at both sizes.
No additional redesign was made. The fixes discovered during verification were
Rich muted-colour parsing, queued scroll callbacks during replacement, and search
height measurement after scrollbar appearance.

Smoke walks **27 states × 2 sizes × 3 themes = 162 SVGs**, with temporary XDG dirs
and explicitly labelled temporary translation fixtures. It covers every remaining
screen/modal, plus pending/result/error and both actions-menu states. The listing
is `/tmp/ebible-smoke-listing.txt`; exact generated filenames are also in
`/tmp/ebible-smoke/manifest.txt`.

## Final gates and limits

All required gates passed in the root `.venv` (Python 3.14.7, Textual 8.2.8):

- `ruff check src tests tools`: all checks passed.
- `ruff format --check src tests`: 55 files already formatted.
- `mypy src`: no issues in 39 source files.
- `pytest -q`: **348 passed in 237.71s**, including 139 UI cases (26 Batch 5 Pilot cases).
- `python tools/smoke.py --out /tmp/ebible-smoke`: **162 SVGs passed**.

The complete output is in `/tmp/b5-gates.log`; Status is also updated in AGENTS.md.
Implementation commits: `485ff44` and `f6774da`, followed by this documentation commit.
No physical Termux session, real translation API or device clipboard/vibration
was exercised. This batch was committed locally; nothing was pushed or published.
