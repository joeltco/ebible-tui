# Batch 8 — brighter theme-matched effects

This batch changes effect intensity only. Verse fetches, character slicing,
one-second reveal, interruption/reversal, selection, session-only translations,
error handling, settings and Reduce motion retain their existing contracts.
Batch 7 was independently verified and pushed by Claude before this work.

## Colour and timing decisions

- The glow covers twelve revealed characters. Each character has its own linear
  colour step from the normal secondary colour toward the peak. The leading
  three are bold, with a feathered background ramp (one third, two thirds, full
  strength). Full strength is accent blended 35% over panel.
- `effect_colours(Theme)` in themes.py derives the peak from accent blended 60%
  toward white on dark themes and toward the theme's foreground ink on light
  themes. White was chosen for dark themes so midnight's dim foreground does not
  constrain its transient glow. Resting colours remain unchanged. Minimal built-in
  themes fall back to their primary/surface/background and light/dark polarity.
- Visibility uses **CIELAB Delta E 1976 ≥18** between the rendered edge-centre and
  resting secondary colour, computed from sRGB with a D65 white point. This is
  deliberately well above a just-noticeable difference and captures hue as well
  as lightness (especially useful for high-contrast's already pale English).
  It is a colour-difference regression bound, not a WCAG accessibility claim.
  Tests separately require the twelve steps, bold centre and background ramp.

| Theme | Edge-centre tint | ΔE76 from resting English |
|---|---|---:|
| meskel | #F2E4C7 | 21.18 |
| tewahedo | #EFE1C1 | 19.57 |
| parchment | #5A3626 | 19.51 |
| lalibela | #F3DFD3 | 18.56 |
| midnight | #DBD9E3 | 24.62 |
| high-contrast | #FFF2C5 | 24.61 |

- Fetch shimmer has a fixed eight-character band, clipping naturally as it enters
  and exits the verse. One sweep takes 0.9 seconds. Four symmetric foreground
  levels reach the accent tint in the centre; four central characters have a
  two-level soft background tint and bold weight. The waiting text outside the
  band blends 18% toward background, slightly dimmer than normal Amharic.
- The forward completion flourish starts at the same accent tint and fades
  linearly to secondary over 300 ms (about nine frames at 30 fps). It colours the
  whole English verse, without flashing the whole background or changing text.
  The character reveal still takes one second; the fade follows it. Reverse
  finishes without a flourish. Interrupting cancels that completion; reconciliation
  cannot replay an expired pulse. Reduce motion bypasses all effects, including
  the pulse; switching it on during the pulse snaps to rest.
- Timers remain active only while a fetch, morph or completion pulse needs frames.
  Only affected verse widgets update; paragraph mode updates its containing widget
  once per tick. No new controls, layouts, requests or persistence were added.

## Tests, recordings and inspection

Fourteen new unit cases cover all six themes' edge/background/contrast and shimmer
visibility/period, the exact flourish timeline, and minimal built-in Theme values.
Six new Pilot cases (both sizes, including both flows) verify pulse rendering,
per-widget updates, idle stop, quiet reverse and Reduce motion cancellation.
The real-timer Pilot cases still bound reveal completion to 0.95–1.4 seconds and
now also observe pulsing frames and rest by 1.3–1.7 seconds. A CLI test covers
supplied text, literal markup and theme selection. All backends are fake.

Four isolated mutations fail the tests: reverting to six characters (six failed
cases), removing the bright tint (six), restoring the old shimmer period (six),
and removing the flourish (one). Temporary source copies were used; the working
source was never mutated. Log: `/tmp/b8-mutations.log`.

The recorder accepts `--text` with existing English and `--theme`; its default
remains explicitly labelled fixture English. It records 71 SVGs at 50 ms
animation-time steps (20 fps), including the 300 ms fade before English rest.
`manifest.json` includes the theme, whether the default fixture was used, frame
order/timestamps, stage, reveal index and flourish strength. Text is rendered
literally. The tool makes no network request and uses isolated temporary XDG dirs.

Requested recordings, using the default fixture rather than a live request:

- `/tmp/ebible-morph-b8/meskel/`
- `/tmp/ebible-morph-b8/parchment/`
- `/tmp/ebible-morph-b8/midnight/`

Each contains 71 SVGs plus manifest.json: 213 frames and three manifests in total.
Complete listing: `/tmp/ebible-morph-b8-listing.txt`. Additional inspection-only
recordings for tewahedo, lalibela and high-contrast are in `/tmp/b8-inspection/`.

Inspected rendered shimmer, halfway morph, peak flourish, halfway flourish and
rest frames at 50×30 in **all six themes**. The bolder tinted centres are visible
on both parchment and midnight; the high-contrast glow retains a warm accent tint.
Wide completion-pulse views were also inspected in all three smoke themes.
No clipping or layout corrections were required. Contact sheets: `/tmp/b8-visual/`.
Smoke adds a separate completion-pulse snapshot: 37 states × two sizes × three
themes = 222 SVGs. Final results, disclosure scan and database checks are recorded
in AGENTS.md Status; gate log `/tmp/b8-gates.log`.

No physical Termux session or real translation request was made in this batch.
The recordings use the default fixture; `--text` permits re-recording the same
sequence with Joel's existing Google translation. No push or publication was made.
