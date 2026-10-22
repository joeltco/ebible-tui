# Batch 4 polish review

Scope: B1–B3 and P1–P5 from the review. No new features, preferences, data changes,
or translation-policy changes. Batch 3 was pushed by Claude before this work;
Batch 4 remains local.

## Requested fixes and decisions

- **B1 — snippets:** Amos 7:6's source, Rich Text, and terminal cells already contained
  the space in “LORD repented”. The visible loss occurred at an SVG styled-span boundary.
  Keep every original whitespace character and put whitespace following a highlighted
  match in a separate bold, non-underlined span. The next word gets its own SVG position.
  Result references remain bold; ordinary snippet text is normal weight so matches stand
  out. Tests use the real Amos verse and check exact characters and exported SVG spacing.
- **B2 — counts:** centralize singular/plural wording. Audit collections, book chapter
  counts, reader verse counts, search passage counts, translation notifications, and
  chapter-count errors. History counts use “history entry/entries”. Existing empty-state
  messages remain. “1 / 365 days read” describes the 365-day total; “1-day streak” is
  adjectival, so both stay unchanged.
- **B3 — progress:** show “<1%” for positive fractions below one percent, retaining
  Textual's regular percentage display at zero and from one percent onward. Keep the
  existing bar geometry and gaps.
- **P1 — paragraphs:** show the whole Amharic chapter, two empty rows, then the whole
  English chapter. Use the existing secondary English colour. Bilingual verse markers
  are dim Unicode superscript digits; annotations and selection retain their styling.
  Both blocks retain verse hit targets. After tapping English, keyboard cursor movement
  follows the English block. Parallel uses two language columns and still falls back
  below 90 columns. Single-language paragraph content and numbering remain unchanged.
  Rebuilds are serialized and language blocks mount together, so resize, refresh, and
  immediate shutdown after reopening paragraph settings cannot leave a missing block.
- **P2 — themes:** use the six themes in specification order, under a disabled “eBible
  themes” heading, followed by built-ins under disabled “More themes”. Native Select
  scrolling, keyboard wrapping, touch, and live persistence remain intact. The app's
  theme enumeration and settings dropdown have the same order.
- **P3 — secondary headers:** below 80 columns, use one row containing a three-cell
  tappable ‹ and an ellipsizing title; hide the heading subtitle. Restore the previous
  roomy header at 80 columns. Tests cover library, books, chapters, search, settings,
  plans, notes, note editor, and help, plus tapping Back and live resize. Touch testing
  exposed double dispatch through inherited Back handlers; prevent repeated handling
  of that event. Search workers also check that their page is current before accessing
  its controls, including when leaving during a pending search.
- **P4 — note wording:** use exactly “Markdown supported · saved only on this device”.
  This separate hint remains one line at 50 columns, even with the compact heading.
- **P5 — help:** retain the existing groups, with a 16-cell accent key-chip column,
  a one-cell gutter, wrapping descriptions, and a row gap. Keep the existing touch
  routes and all key information. Backspace and Delete have individual rows so each
  chip fits. Long help content scrolls vertically as before.

## Verification record

The new suite has **26 cases: 8 unit cases and 18 Pilot cases**. Each requested item
has a Pilot regression at both sizes. All eight phone checks failed against an isolated
copy of the pushed Batch 3 source on the expected old behavior. An additional concurrent
rebuild test failed before the paragraph lifecycle fix; the existing settings restart
test also reproduced that defect and now exercises the fix. Existing paragraph,
theme-picker, and translation-notification tests were updated for the requested changes.
Full gate results are recorded in AGENTS.md Status.

Fresh smoke covers the same 24 states × two sizes × three themes (144 SVGs), using
temporary XDG directories. It also checks the compact secondary-header row budget.
The output directory is `/tmp/ebible-smoke`, with every SVG listed in `manifest.txt`.

Personally inspected fresh rasterizations of these phone states in **meskel, parchment,
and lalibela**: books, chapters, bookmarks, search (including Amos 7:6), plans, settings,
theme picker, note editor, help, help bindings, paragraph reader, and parallel fallback.
Also inspected the Amharic-to-English paragraph boundary in all three themes and the
wide meskel search, theme picker, and parallel paragraphs. No additional visual fixes
outside the requested list were needed. All normal smoke states still pass layout and
binding checks at 50×30 and 120×40.

No physical Termux device or real translation service was exercised. Translation and
device-service tests use fakes. The database, canon, raw source, schema, and binding
translation documentation remain unchanged. No push or publication was performed.
