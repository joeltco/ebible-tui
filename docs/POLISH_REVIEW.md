# Batch 3 polish review

The scope is presentation polish. No data, translation policy, navigation feature,
or saved preference schema was changed. Batch 2 was already pushed by the maintainer;
Batch 3 commits remain local.

## Requested fixes and decisions

- **P1:** Below 80 columns, hide the brand and use one row for the book name,
  chapter/count, and two three-cell tappable arrows. Remove vertical viewport padding.
  Keep both action rows and the status row, leaving **26 scripture viewport rows at
  50×30**. Restore the full header at 80 columns, including during resize. Preserve the
  chapter/count suffix when ellipsizing a long book name. Tests use the real Meqabyan
  and 2 Chronicles names and a constrained title width to exercise the ellipsis.
- **P2:** Determine chapter availability after applying the existing English overlay.
  If every verse is untranslated, show one notice above Amharic-only verses in all
  four layouts and both flows. Mention deuterocanonical status only when applicable,
  the verse-menu translation action, and backend availability. This does not change
  the saved layout. In partial chapters, show “Not yet translated”, or “Untranslated”
  with detailed messages disabled, in dim italic text. The chapter notice remains
  visible regardless of that preference. Keep ◇ exclusively for machine English;
  remove it from the unmarked Bookmark button too. First-verse navigation shows the
  notice, and paragraph cursor scrolling accounts for the notice's height.
- **P3:** Give the plan bar the remaining column width after reserving a four-cell
  percentage label, a one-cell gap before the label, and one-cell right padding.
  This keeps the label inside the column even at 100%, without touching the scrollbar.
- **P4:** Set both scrollbar dimensions to one cell throughout the app, including
  dropdowns and note editors. Keep theme-based thumb, hover, active, and track colours.
  Existing overflow behavior controls when a scrollbar is needed.

## Additional defect found and fixed

The **theme dropdown clipped its options to one visible row** and its overlay was
shifted sideways. The generic `OptionList` margin/height/border rule also applied to
Textual's `SelectOverlay`. Scope that layout rule to `PassageList`, preserving each
Select overlay's automatic height and alignment. The Pilot regression checks multiple
visible rows, aligned edges, a one-cell scrollbar, and tapping a different theme.
The fix applies to the other dropdowns as well. No other clipping, collision, or
misalignment was found in the phone review.

## Visual inspection record

Each state below was personally inspected from a rasterization of the actual fresh
50×30 SVG in **all three themes: meskel, parchment, and lalibela** (72 views).
Dropdowns were rechecked after their clipping fix. The final smoke run also generates
all 24 states at 120×40, for 144 SVGs total.

| State | Meskel | Parchment | Lalibela |
|---|---|---|---|
| reader | checked | checked | checked |
| books | checked | checked | checked |
| chapters | checked | checked | checked |
| goto | checked | checked | checked |
| goto-error | checked | checked | checked |
| verse-actions | checked | checked | checked |
| note-editor | checked | checked | checked |
| note-discard | checked | checked | checked |
| bookmarks | checked | checked | checked |
| confirm-delete | checked | checked | checked |
| highlights | checked | checked | checked |
| notes | checked | checked | checked |
| history | checked | checked | checked |
| search | checked | checked | checked |
| search-error | checked | checked | checked |
| plans | checked | checked | checked |
| confirm-restart | checked | checked | checked |
| settings | checked | checked | checked |
| theme-picker | checked | checked | checked |
| help | checked | checked | checked |
| help-bindings | checked | checked | checked |
| reader-parallel | checked | checked | checked |
| reader-paragraph | checked | checked | checked |
| reader-untranslated | checked | checked | checked |

Smoke output: `/tmp/ebible-smoke`; its `manifest.txt` lists every SVG. Smoke now also
asserts the phone viewport budget, one-cell scrollbars, and dropdown list height.
The phone regressions for P1, P2 (both flows), P3, P4, and the dropdown were run against
an isolated copy of the pushed Batch 2 source in `.venv`: all six failed on the expected
old behavior. The full current gate results are recorded in AGENTS.md Status.

No physical Termux session or real translation service was used for this batch.
The maintainer reported successful Batch 2 tmux testing at 50×30 and approval of its
appearance. That does not substitute for device testing of these new changes.
