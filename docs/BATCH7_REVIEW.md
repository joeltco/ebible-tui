# Batch 7 — in-place verse morph

Batch 6 was verified and pushed by Claude before this work. This batch changes
presentation and phone key-paste handling; translation requests, alignment,
ephemeral session storage, annotations and protected scripture data retain their
existing contracts.

## Behaviour and decisions

- Saving a key strips leading/trailing Unicode whitespace, including pasted
  newlines, before validating. Internal whitespace and empty suffixes still fail;
  failures preserve the previous credential. Input remains masked and never logs
  its payload. The change applies consistently to both typed and pasted keys.
- Morphs use Unicode character indices, not bytes, words or terminal columns:
  `english[:i] + amharic[i:]`. The index spans the longer string, so both shorter
  and longer English results finish cleanly. Widgets rewrap naturally without
  rebuilding the chapter or adding a translation line.
- A full journey takes one second. Interruptions retain their exact fractional
  position and continue at the same normalized speed in the opposite direction;
  returning from halfway therefore takes half a second. The 30 fps timer is paused
  when idle. Several requested verses may animate concurrently, updating only
  their own widgets.
- The six-character English edge blends secondary toward accent; the newest
  character uses accent exactly. Remaining Amharic blends 40% toward background.
  Fetch shimmer repeats every 1.4 seconds, with a soft triangular band, at most
  55% toward accent. All colours derive from the active theme, including light
  themes and built-ins; no extra palette constants or CSS hex colours were needed.
- A dim `◇` appears beside the unchanged verse number whenever English is visible,
  including during a morph. It disappears on return to Amharic. Bookmark/note
  glyphs, source highlights, selection and per-verse touch targets remain.
- Paragraph flow stays one continuous, interactive paragraph. Unchanged verse
  fragments are cached; each tick recomputes only affected fragments and updates
  the single paragraph widget once. Reflow of the containing paragraph is needed
  when a verse changes length; unrelated widgets receive no update call.
- Timers pause while another screen is open. The monotonic timeline continues;
  returning renders the current position or completed result without replaying a
  finished animation. Chapter navigation and theme/size changes preserve state.
- Reduce motion is an immediately persisted boolean, off by default. Enabling it
  snaps to the requested endpoint and removes shimmer. Fetching instead appends a
  static dim “Translating…” hint to Amharic. Errors restore source text and keep
  the existing short actionable message. Taps during fetch still deduplicate;
  reversal begins once a translation exists.
- README, help, AGENTS.md and current architecture notes describe in-place
  replacement, motion preferences and trimmed key saves. Historical batch reviews
  remain historical records.

## Verification and artifacts

The new tests cover real Amharic with explicitly marked fake English, shorter and
longer results, exact frame strings, all six theme gradients, shimmer motion,
literal Rich markup characters, timer duration, continuous interruption/reversal,
cache re-show, widget update isolation, rewrapping, errors, pending reduce-motion
changes, persisted settings, screen return, theme switching and resize. There are
11 new morph unit cases, 14 new Pilot cases (both terminal sizes), and a recording
tool test. The key fix adds four trim cases and updates the existing masked-paste
Pilot cases; one formerly invalid trailing-whitespace case is now valid.

Four isolated mutation checks in temporary source copies failed as intended:
removing key trimming (4 failures), breaking the Amharic suffix slice (2), jumping
to zero on interruption (2), and removing the glow band (6). The real working
source was never modified by those checks. See `/tmp/b7-mutations.log`.

Smoke writes 216 SVGs: 36 states × 2 sizes × 3 themes. New snapshots freeze the
clock for mid-shimmer, half-forward, half-reverse and paragraph morph; rest, error,
actions and all existing pages remain covered. Credentials are fake and every SVG
is checked for disclosure. Output: `/tmp/ebible-smoke`; full directory listing:
`/tmp/ebible-smoke-listing.txt`.

`python tools/record_morph.py --out /tmp/ebible-morph` writes 65 SVGs and
`manifest.json`, containing ordered filenames, stages, reveal indices and 50 ms
frame timestamps. This is deterministic **animation time**, independent of SVG
export speed; play at 20 fps when assembling a GIF. The sequence lasts 3.25 seconds,
including fetching, forward, English rest, reverse and Amharic rest. It uses real
Genesis 1:1 and explicitly labelled fixture English, with temporary XDG directories
and a fake backend. No key or live network is needed. The real 30 fps timer is
exercised separately by Pilot at both sizes with a 0.95–1.4 second completion bound.

Inspected rendered phone SVGs for shimmer, forward, reverse, English rest and
paragraph morph in meskel, parchment and lalibela; wide settings/reader variants;
and nine representative recorder frames. No additional clipping or alignment
changes were needed. During development, smoke caught an overlong invalid-key test
fixture causing input horizontal scroll; it now uses a short, explicitly invalid
internal-whitespace fixture. SVG tests ignore line-wrap/selection-gutter elements
when reconstructing verse text, while frame-unit tests assert exact whitespace.

Final gate counts and protected-data checksum are recorded in AGENTS.md Status.
No physical Termux performance run or real translation request was made in this
batch. The animation and exports were exercised headlessly with fake backends;
these checks do not establish frame delivery on a particular Android terminal.
No push or publication was performed.
