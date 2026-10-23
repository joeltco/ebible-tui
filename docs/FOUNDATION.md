# Foundation decisions (updated for Batch 6)

These choices resolve details not fixed by AGENTS.md. Batch 2 now supplies the
reader, themes, device integration, and persisted UI wiring; see UI_DECISIONS.md.
The reference, search, and translation contracts below include the review fixes.

## Scripture and references

- `ScriptureStore` opens a `mode=ro` connection per operation and closes it before
  returning. `UserDataStore` similarly owns short-lived connections, so workers
  never share a SQLite connection. Core imports no Textual or Rich code.
- Names and aliases are case-insensitive. Exact names and conventional aliases
  take precedence over prefixes; multiple prefix matches raise `ReferenceError`.
  Full Amharic names and prefixes of their distinctive names work. Numbered
  English books accept Arabic digits and I/II/III. Chapter/verse input uses Arabic
  digits. A bare book or chapter selects verse 1. No cross-chapter ranges.
- Parsing validates actual chapter and range endpoints by default. Pass
  `validate=store.validate_reference` to use a specific store. UI parsing runs off
  the UI thread. Psalm 151 errors identify its location at Psalms 150:7-14.
  Interior source gaps are not filled or renumbered.
- Search quotes plain word tokens, with a prefix on the final token. Raw FTS5 is
  opt-in with a leading `=`. It ranks results and supports offset pagination
  (default 100 results, maximum 1,000). It searches Amharic only. Session
  translations are never indexed. Snippets carry control
  characters U+0001/U+0002 around matches, not Rich markup. UI code must render
  literal Text spans safely; the UI invokes search in a Textual worker.
- Verse values contain only their reference and Amharic text. The packaged database
  has no English column, English FTS terms, or translation coverage metadata.
  `tools/strip_english.py` creates a fresh deterministic database from the source,
  verifies every source row, then VACUUMs and atomically replaces the destination.
  Golden digests cover every original verse tuple and every book row; these were
  recorded before stripping English. The old database remains in git, not the tree.

## Personal data and settings

- Migration v1 creates annotations, history/resume, and plans; v2 adds live
  translation historically; v3 drops that cache with secure deletion, VACUUM, and
  WAL truncation. Migrations run in one transaction with a write lock. Newer schema
  versions are rejected unchanged; failures roll back schema and version.
- Annotations attach to individual verses; range annotations are rejected. There
  is one bookmark, highlight, and Markdown note per verse. Highlight names are
  gold, green, red, blue, purple; their rendering adapts to light/dark themes.
  Empty notes are preserved until explicitly deleted.
- History defaults to the last 200 positions. Consecutive identical positions
  update their timestamp without adding duplicates. Recording a position updates
  resume and history atomically. Deleting history does not delete resume.
- Settings are immutable values. Unknown fields are ignored; invalid fields
  individually fall back to defaults. Max text width is 20–240 (default 100).
  The additional `verse_flow` setting is `lines` or `paragraph`. Theme names are
  nonempty strings of at most 100 characters; registration/availability is a UI
  concern. Unknown saved theme names fall back to meskel; the UI supports six
  custom themes and Textual built-ins.
- Atomic JSON writes use a unique temporary file in the destination directory,
  flush/fsync, then `os.replace`; failures clean up the temporary file.

## Credentials

- API keys are not Settings fields. `core/credentials.py` resolves the XDG config
  path at call time and stores only the key in `anthropic_key`. Unique temporary
  files use exclusive `os.open` with `0o600`, UTF-8, flush/fsync, then atomic replace.
  No chmod and no newline. Missing-file reads/removals are harmless; failed writes
  preserve the old file and clean up their temporary file. Errors contain no OS
  exception details. This is a private plaintext credential file, not encryption.
- Save strips leading/trailing Unicode whitespace (including phone paste newlines),
  then requires `sk-ant-`, a nonempty suffix, and no internal whitespace. The draft
  remains password-masked; the stored file contains only the trimmed key.
- A nonempty environment key wins without reading the saved file. An empty variable
  behaves as unset. The resolved secret has a redacted dataclass repr; the settings
  UI receives only a masked saved-key hint and source label. No network check on save.
- Claude receives the resolved key explicitly as `api_key=...`. No environment
  mutation. SDK construction/request exceptions are replaced by fixed actionable
  errors with the original exception chain suppressed; close errors are suppressed.

## Plans

- Chapter counts come from the bundled DB: 1,466 chapters in Ethiopian order.
  Plans divide contiguous chapter lists into groups whose sizes differ by at
  most one. Longer groups come first. No hand-authored reading schedules.
- Whole canon: 365 days; NT: 90 days (Matthew through Revelation, including Acts);
  Psalms plus Proverbs: fixed 30-day cycle; Gospels: 30 days. The monthly plan is
  not tied to the length of a calendar month. Restart it explicitly for a new cycle.
- Days are one-based. Today is computed from the local calendar date and returns
  no day before the start or after the schedule ends. Restarting a plan clears
  only that plan's previous progress. Repeated completion is idempotent.
- Progress is completed schedule days / total days. Streak is consecutive actual
  completion dates, counting back from today or yesterday. Multiple completions
  on one date count as one streak day; backfilled schedule days do not fabricate
  earlier activity. Completion before the plan start is rejected.

## Translation

- The async service offloads scripture reads, backend selection, and translation
  through `asyncio.to_thread`. The UI awaits it in a Textual worker. Results are
  returned to memory only; neither the service nor backend writes personal data.
- The translation unit is exactly one verse. Claude receives its whole chapter's
  Amharic as context and returns only the requested numbered verse. Missing, extra,
  duplicate, wrong numbers, blank output, or commentary reject the result. A single
  surrounding code fence is accepted. Truncated/non-final responses are rejected.
- Claude is lazy-imported and preferred when an environment or saved API key exists. A missing optional
  SDK or backend error is reported, not silently retried through Google. Requests
  use a 30-second SDK timeout, no retries, and a 4,096-token output budget. The guide
  is byte-identical, with an appended single-verse/no-commentary output contract.
- Google receives only the selected verse over stdin without shell interpolation,
  using translate-shell's Google engine and a 20-second subprocess timeout.
- The service has a 45-second outer deadline. Errors are actionable and results
  that fail alignment never enter session memory. A timed-out thread may finish
  cleanup later; its result is discarded and cannot write a cache.
- There is no offline translation pipeline. Tests use fake clients/backends only.
  The packaged guide is a byte-for-byte copy of the binding documentation.

## API references consulted

The reader and smoke runner use Textual's documented
[headless testing API](https://textual.textualize.io/guide/testing/) and
[screenshot API](https://textual.textualize.io/api/app/). Claude request construction
follows the [Messages API](https://platform.claude.com/docs/en/api/messages/create),
with the model name fixed by AGENTS.md. Remote service availability is not tested.


## English search (Batch 9)

- Query translation is separate from verse translation: no chapter context or
  translator guide is sent for keywords. Claude receives a short scripture-word-form
  prompt; Google receives English on stdin with `trans -b en:am`. Both use the
  existing key/backend selection, lazy clients, bounded workers and safe errors.
- Validation keeps up to three unique lines of Ethiopic letters/combining marks;
  whitespace at the ends is stripped. Internal spaces, punctuation, digits and
  Latin commentary are rejected, not extracted. Google retains one result.
- `search_substrings` uses parameterized `instr(text_am, ?) > 0`, ORs variants and
  orders by canonical book/chapter/verse. It has the same scopes and page bounds as
  FTS; substring snippets use the same control markers and literal Rich rendering.
- The UI owns session query-cache entries keyed by backend setting and trimmed,
  case-folded query. Core services remain stateless and no schema migration is needed.
  Typed Amharic, mixed-script and explicit raw queries retain the original FTS path.
