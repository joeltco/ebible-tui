# Batch 1 foundation decisions

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
  (default 100 results, maximum 1,000). It searches bundled text only; live user
  translations are not part of the protected FTS index. Snippets carry control
  characters U+0001/U+0002 around matches, not Rich markup. UI code must render
  literal Text spans safely; the UI invokes search in a Textual worker.
- Verse values retain raw `text_en` separately from display `english` and
  `english_source`. NULL means untranslated; an existing empty bundled string is
  not silently replaced. The UI styles placeholders and labels live English ◇ Machine.

## Personal data and settings

- Migration v1 creates annotations, history/resume, and plans; v2 adds live
  translation. Migrations run in one transaction with a write lock. Newer schema
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

- The async service offloads scripture reads, backend selection, translation, and
  writes with `asyncio.to_thread`. The UI awaits it inside a Textual worker.
- Whole-chapter source text is sent even when only some verses lack English.
  Exact verse-number alignment is required for every backend. Persist only verses
  missing both bundled and live English; existing reviewed/live text is preserved.
  There is no automatic refresh or overwrite mode in this batch.
- Claude is lazy-imported and selected first when an API key exists. A missing
  optional SDK or a backend error is reported, not silently retried through Google.
  Claude gets one request per chapter, a 120-second timeout, no automatic retries,
  and 16,384 output tokens. Non-final/truncated responses are rejected even if
  their verse numbers happen to match. Missing/extra/duplicate numbers, wrapped
  lines, commentary, and blank output reject the batch before writes. A single
  surrounding code fence is accepted. The guide remains unchanged; an appended
  in-app system-prompt addendum explicitly forbids summaries and commentary.
- translate-shell receives Amharic over stdin (no shell interpolation), uses
  Google explicitly, translates per verse, and has a 20-second per-verse timeout.
  Its output is machine translation; it cannot enforce the Claude translation
  guide. All live text carries provenance and is visibly marked in the reader and copies.
- The packaged guide is a byte-for-byte copy of the binding documentation. A test
  catches drift. No network translations or invented scripture were used in tests.
- Offline pipeline changes are import/path fixes only. `translate.py`'s historical
  writable helper name points to `open_readonly`; this lets status/pull/next work
  without reintroducing any bundled-DB writer in the application core. Historical
  push cannot write. Other inherited maintenance scripts remain archival tooling.

## API references consulted

The reader and smoke runner use Textual's documented
[headless testing API](https://textual.textualize.io/guide/testing/) and
[screenshot API](https://textual.textualize.io/api/app/). Claude request construction
follows the [Messages API](https://platform.claude.com/docs/en/api/messages/create),
with the model name fixed by AGENTS.md. Remote service availability is not tested.
