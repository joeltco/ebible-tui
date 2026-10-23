# Batch 9 — English search through query translation

Batch 8 was independently verified and pushed by Claude before this work. English
search now translates the submitted query into Amharic and searches the existing
Amharic source. It does not add English scripture, an English index or disk caching.

## Decisions and interaction

- Detection uses Unicode Latin-letter names and excludes queries containing any
  Ethiopic-named character. Leading whitespace before `=` is allowed; raw and mixed
  queries pass through untranslated. A Latin word may contain punctuation/numbers.
  Scripts without Latin letters do not trigger English translation.
- English requires explicit Enter or the new Search button. Typing, opening the
  screen, and changing scope before submission never call a translator, even when
  a translation is cached. The hint explains how to submit. Typed Amharic retains
  the original 120 ms debounce, FTS token/prefix matching, ranking and Enter jump.
- English submission remains on results so the user can inspect “Searched … · from
  …” and refine the terms. The Search button also stays on results for Amharic.
  Existing result tap/arrow/Enter navigation continues to validate references.
- All translated terms appear as literal underlined accent links above the list.
  Tapping one replaces the input and switches to normal Amharic FTS. Keyboard users
  can Tab to the term summary, choose with left/right, and press Enter. This keeps
  refinement accessible without adding several rows of buttons on a phone.
- The query stays editable while a theme-derived “Translating…” shimmer runs beside
  it. Reduce motion uses a static dim hint. Repeated submit during the same pending
  request is ignored. Scope changes during translation apply to the eventual query
  without making another request. Editing or leaving invalidates/cancels the UI
  worker; late results cannot replace a newer query or reopen the screen.
- Cancelling a worker cannot forcibly interrupt an already running Python thread;
  backend timeouts remain bounded. Discarded requests do not populate the cache.
  No query translation or network wait blocks the UI message pump.
- Successful query translations live on the app instance, keyed by backend setting
  and trimmed/case-folded query. They survive closing/reopening Search, but not app
  restart. Scope changes and Show more reuse the variants. Errors are not cached.
  No settings or user.db schema changes were needed.

## Backend and matching contracts

- Google uses exactly `trans -b en:am`, query on stdin, bounded subprocess timeout,
  and retains one usable result. Claude uses the active model/key and a short
  dedicated scripture-word-form prompt, capped at 256 output tokens. The verse
  translation guide is not sent for keyword translation. Both guide copies remain
  byte-identical; the shared Claude request lifecycle still passes keys explicitly,
  closes owned clients and sanitizes SDK errors.
- Validation strips each line's outer whitespace, keeps unique Ethiopic letters
  and combining marks, and returns at most three variants. Internal spaces,
  punctuation (including Ethiopic punctuation), numerals, numbering and Latin
  commentary are junk. Lines are discarded wholesale rather than extracting a word
  from commentary. No usable line produces an actionable error. This treats the
  requested variants as word forms, not multiword phrases.
- Substring search uses parameterized `instr(text_am, ?) > 0`, ORs the variants,
  and orders by book/chapter/verse. SQL wildcards and regex characters are literal.
  All/OT/NT/current-book scopes are the same as existing search. No database rebuild,
  index or data mutation was performed.
- Translated results are fetched in 40-row pages with real offsets and appended by
  Show more, up to the existing 1,000-result UI cap. Counts describe loaded passages,
  as before. Typed Amharic keeps its existing FTS pagination behaviour.
- Snippets start up to 48 characters before the first match and normally show at
  most 180 characters, expanding if needed to include that complete match. Longest
  variants match first when overlapping, avoiding duplicate result rows or nested
  highlights. Ellipses indicate cropping. The same control markers and literal
  Rich spans preserve the source's whitespace and prevent markup interpretation.
- All errors stay inline and include a retry/configuration hint. Unexpected backend
  errors use fixed safe text; no credential or raw SDK exception is rendered.

## Performance

Measured against the unchanged packaged database on this machine, Python 3.14.7.
Every sample includes opening/closing the read-only connection, SQL, result creation
and snippet highlighting; network latency and terminal rendering are excluded.
The filesystem cache was warm. Twenty calls per offset, 40 rows per page, first/
middle/last/beyond-last offsets for three variant sets: **240 timed calls**.

| Variants | Matches | First page median / max | Last page median / max | Worst call including empty final page |
|---|---:|---:|---:|---:|
| ብርሃን | 282 | 13.28 / 17.50 ms | 30.15 / 39.33 ms | 46.74 ms |
| እግዚአብሔር | 8,932 | 0.68 / 0.82 ms | 28.02 / 33.51 ms | 33.51 ms |
| ብርሃን, ብርሃኑ, ብርሃንንና | 314 | 29.30 / 37.85 ms | 73.63 / 99.61 ms | 99.61 ms |

All calls were below **150 ms**. Full offsets, medians, p95s and maxima are in
`/tmp/b9-search-benchmark.json`. The unit suite also enforces a 150 ms bound for
three 40-row common-word pages near the end of the canon (offset 8,800).

## Verification and artifacts

Forty new core cases cover detection, junk rejection, deduplication, response limits,
Google direction/stdin/timeout/errors, Claude's dedicated prompt, worker threading,
safe errors, no database writes, real-source scope/order/pagination/highlighting,
affixes, SQL-literal handling, FTS preservation and page latency. Twenty new Pilot
cases at 50×30 and 120×40 cover Enter and tap submission, no keystroke calls,
shimmer/static hints, deduplication, scope changes while pending, cancellation,
restart/cache boundaries, unchanged personal files, errors/retry, pointer/keyboard
refinement and translated/native result jumps. Only fake backends were used.

Smoke adds six states: English entry, query shimmer, reduced-motion waiting,
three-variant results, refined Amharic and query-translation error. It now writes
43 states × two sizes × three themes = **258 SVGs**. Actual phone SVGs for all six
new states were inspected under meskel, parchment and lalibela. No clipping or
alignment corrections were necessary. Wide views and the final disclosure scan
are also included in the final verification recorded in AGENTS.md Status.

Output: `/tmp/ebible-smoke`; listing: `/tmp/ebible-smoke-listing.txt`;
gate output: `/tmp/b9-gates.log`; preview contact sheets: `/tmp/b9-visual/`.

No live Google/Claude query request or physical Termux session was run in this
batch. Network semantic quality is not established by fake-backend tests. The
40 ms class of single-variant page timings is a host measurement, not a phone
latency promise. No push or publication was performed.
