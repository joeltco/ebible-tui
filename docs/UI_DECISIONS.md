# UI interaction and visual decisions

These are the implementation choices left open by the specification. The core
conventions in FOUNDATION.md still apply, with the reviewed search/reference/
translation contracts updated there.

## Reading and navigation

- Meskel is the default. All six custom palettes define every required Theme field;
  Textual built-ins remain available. Theme previews and every other preference save
  immediately. A CLI theme overrides the saved theme for the session; a subsequent
  preference edit saves the current session preferences together.
- The reading column is centred and bounded by the configured width, with two cells
  of outer margin on a phone. Below 80 columns, the book/chapter header is one row,
  the brand is hidden, and the viewport has no vertical padding. Two one-row action
  bars and the dim status line remain: scripture gets 26 of 30 rows. At 80 columns
  and wider the brand and full chapter header remain. Long compact titles ellipsize
  the book name while preserving the chapter/count suffix and tappable arrows.
- Selected verses have a narrow theme-coloured rule and a 9% tint. English uses the
  secondary colour, numbers are dim, and bookmarks/notes retain their gutter glyphs.
  Highlights use distinct light/dark foreground palettes. No CSS colour literals.
- Paragraph flow joins verses continuously, retaining per-verse hit targets, numbers
  (if enabled), and annotation glyphs. Selection is bold/underlined in paragraph flow.
  Interleaved paragraphs separate each verse's languages with a slash. Parallel
  paragraphs have separate language columns; the cursor scroll follows the first.
- Parallel becomes interleaved whenever terminal width is below 90, including live
  resizing. Verse cursor movement scrolls smoothly; initial/resumed positions and
  re-layout jump directly to the selected verse.
- A range opens at its first verse after both endpoints are validated. Previous/next
  chapter crosses book boundaries in Ethiopian order; the canon's endpoints disable
  the corresponding buttons. Moving beyond a chapter's verse endpoints stays put.
- All jumps (CLI, go-to, book/chapter, search, collections, resume, plans) use source
  validation. Invalid saved positions show a message and resume at Genesis 1:1.
- Book groups preserve the exact canon order, so the History heading appears again
  for Acts after the Gospels. Filtering matches English names, Amharic names, or slugs.
- Reader shortcuts live on the reader, not globally. `q` cannot quit another screen
  or interrupt typing. Tab cycles controls; Enter/Space activates the focused control.
  With no control focused, Enter opens verse actions. Returning to the reader clears
  control focus. Escape at the reader returns focus to reading without quitting.
- Desktop modifier bindings are removed from screens, inputs, text areas, scroll
  containers, passage lists, and Select overlays. Note Undo/Redo are tappable buttons.
  Help includes all bindings and touch routes, including a Quit button.

## Search and collections

- Plain search tokenizes Unicode word runs, quotes them individually, ANDs them, and
  prefixes the last token. Punctuation-only input returns no results. Leading `=`
  enables advanced syntax; invalid advanced input gets an inline explanation.
- Search waits 120 ms after input and runs in an exclusive Textual worker with a
  request-generation check. Enter in the search input opens the first result;
  results are also directly tappable or selectable with arrows and Enter.
- The result page starts at 40 passages; Show more adds 40, up to the core's 1,000 cap.
  Language and scope selectors apply immediately. Snippets use literal Rich Text
  spans with bold/underlined matches, so source brackets cannot become markup.
- Collection screens share tabs for bookmarks, highlights, notes, and history.
  References and note previews are literal text. Deletion requires confirmation.
- Notes use a soft-wrapped TextArea and explicit Save. Escape/Back asks before
  discarding changed text; unchanged notes close immediately. Markdown remains plain
  editable source. Empty notes may be saved, matching the existing core contract.
- Vertical scrolling is allowed in long screens and sheets. Primary touch controls
  are at least three cells wide; reader action bars use one-row targets, while
  menus/grid controls generally use three rows. No horizontal scrolling is required.

## Plans, translation, and device services

- Plan selection does not start a plan automatically. Start today records the local
  date; Mark day read toggles a day, and day arrows allow browsing/backfilling.
  Today is disabled outside a plan's schedule. Restart requires confirmation.
  The screen shows completed-day count, progress bar, and actual-calendar-day streak.
- Live translation is explicit, via the verse menu. Only one request runs at a time.
  Navigation remains available; completion refreshes the reader only if that chapter
  is still open. Failure is a notification and never replaces reviewed text.
- Live text and copied live English both include a machine marker. Only live English
  uses ◇; an unmarked Bookmark button has no diamond. A wholly untranslated chapter
  has one calm notice and Amharic-only verses, in every layout/flow. The notice names
  deuterocanonical status when applicable and explains the verse menu's translation
  action and backend requirement. This is a display fallback; the layout preference
  stays unchanged. Partial chapters use short dim per-verse placeholders without ◇.
  Disabling detailed placeholders shortens those to “Untranslated”; the chapter
  notice is always shown. No source or overlay data changes.
- Copy includes the English reference followed by the requested language(s). It uses
  termux-clipboard-set if present, otherwise OSC 52. Termux copy has a five-second
  timeout; optional vibration has a two-second timeout and does not undo a successful
  bookmark if unavailable/failing. Both subprocess paths are tested with fakes.
- Settings/annotations/position reads and writes run with asyncio.to_thread. Search
  and translation additionally have Textual worker lifecycles. Saved-position writes
  complete before the next reader input event is handled.

## Verification and limits

- Pilot tests exercise both sizes, every screen's Escape route, real list rendering,
  settings and annotations across restart, source-invalid jumps, keyboard focus,
  paragraph hit targets, resize fallback, and the complete mounted binding tables.
- Smoke creates fresh temporary XDG config/data for each size/theme combination,
  restores the invoking environment, and removes its temporary personal data. Its
  note is explicitly labelled a temporary fixture and quotes real bundled text.
- Smoke writes 24 views for each of 3 themes × 2 sizes: 144 SVGs and manifest.txt.
  Extra states include error messages, deletion/discard/restart confirmations,
  Select's theme overlay, parallel/paragraph readers, and an untranslated chapter.
  Colour is enabled explicitly for screenshots even if the invoking CI shell has
  NO_COLOR set; the real app otherwise respects the user's NO_COLOR setting.
- Visuals were inspected from the actual SVGs, not only widget geometry. The app is
  tested headlessly on this host. Physical Android touch/clipboard/vibration and
  remote translation services still require device/service verification.
- Batch 3 inspected every one of the 24 phone views under all three smoke themes.
  Scrollbars are one cell throughout, with theme-derived colours. Plan percentages
  have one-cell gaps from the bar and scrollbar. Passage-list layout rules exclude
  Select overlays, so dropdowns retain their full list height and aligned borders.
  See [polish review](POLISH_REVIEW.md) for the complete inspection record and limits.
