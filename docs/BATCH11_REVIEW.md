# Batch 11 review — theme colours and animation audit

The approved six base `Theme` palettes and annotation colour tables are unchanged.
This batch fixes derived contrast, implicit opacity and stale rendered colours.
It preserves Claude's `EPIGRAPH` constant and **Psalms 118:105** label, the database,
search's **“40 passages · more below”** behaviour, layouts and translation behaviour.

## Audit first

[THEME_AUDIT.md](THEME_AUDIT.md) was committed as **9d7c970**, before any application
changes, against **ac05d43**. It ranks seven finding groups with measured colours,
ratios and rendered PNG evidence. Baseline evidence is in `/tmp/ebible-theme-before/`.
The implementation is **f47b0c2**; tool/recorder refinements are **e521231**. The pressed-state follow-up was
recorded before its fix in **b3e47eb**, then fixed/tested in **a115149**.

## Repairs and measured results

1. **Cached colours:** theme changes rebuild query-term links, modal swatches,
   book/collection metadata and verse/paragraph text. Textual `Content` compares
   letters only, so swatch updates explicitly replace and invalidate `Button.label`.
   Selected items, scroll positions, query text and morph positions survive.
2. **Readable entrance:** cover lettering starts at a contrast-constrained quiet
   colour, then brightens/darkens over the existing entrance timeline. It never
   starts as invisible panel-coloured text.
3. **Framework defaults:** placeholders, Select arrows, disabled labels, footer/
   secondary text and metadata use the same explicit secondary role. Both Textual
   disabled-button opacity layers are removed. The later full-smoke review also
   identified a transient pressed-button tint: it reduced Plans labels to 4.02:1
   on parchment and 4.39:1 on midnight. That whole-widget tint is now transparent;
   the existing pressed/focused background remains. The lowest held-pressed label
   among all five variants/all six themes is now 6.91:1 (midnight). Input selection, idle outlines and
   scrollbar thumbs receive the smallest theme-derived contrast correction.
   Passing hover/focus/overlay/toast colours remain under their existing policies.
4. **Effects:** high-contrast uses a darker centre background and a readable dim
   source colour. Other themes retain the approved peak and 35% centre tint.
   Edge/source colours ease at reveal boundaries; fetching eases in and carries its
   last colours into the result over 120 ms. The completion pulse rises and falls
   smoothly over the same 300 ms; interrupting it carries the current colours into
   the reverse. Errors still stop immediately and restore Amharic. Reduce motion
   still swaps instantly, without shimmer or pulse.
5. **Static pending hints:** the existing reduced-motion search hint also inherited
   the motion-muted colour. Its baseline was **#7e786b / #f5eedc = 3.79:1** on
   parchment and **#737681 / #0c1018 = 4.20:1** on midnight. It now uses the ordinary
   secondary text role, as does the verse hint. This is the same implicit-dimming
   defect identified in the audit, confirmed in the baseline smoke SVGs.

All colour literals and contrast-derived role/effect policy remain in `ui/themes.py`.
TCSS refers only to theme variables. No palette redesign or new app feature was added.

### Before → after contrast ratios

The pairs below are from actual exported SVG fills and composited cell backgrounds,
not source palette values. [Pressed Plans after: parchment](/tmp/ebible-theme-after/parchment-pressed-plan.png),
[midnight](/tmp/ebible-theme-after/midnight-pressed-plan.png).

Input selection is distinct from the reversed cursor;
the cursor already passed. Cover entries use the minimum visible letter pair during
entrance; the baseline's exact initial panel-on-panel state was additionally 1:1.

| Theme | Placeholder | Disabled label | Input selection | Cover entrance |
|---|---:|---:|---:|---:|
| meskel | 3.47 → **7.08** | 3.19 → **6.15** | 4.38 → **4.60** | 1.02 → **3.12** |
| tewahedo | 3.39 → **7.29** | 3.18 → **6.05** | 4.46 → **4.65** | 1.02 → **3.14** |
| parchment | 2.61 → **6.37** | 2.26 → **5.56** | 6.40 → **6.40** | 1.02 → **3.12** |
| lalibela | 3.39 → **6.71** | 3.09 → **5.59** | 4.60 → **4.67** | 1.02 → **3.12** |
| midnight | 3.53 → **6.46** | 2.56 → **5.72** | 3.96 → **4.63** | 1.01 → **3.11** |
| high-contrast | 3.54 → **13.90** | 3.90 → **11.71** | 4.54 → **7.11** | 1.02 → **7.17** |

Dark→parchment swatches improve from **1.11–1.36:1 to 5.10–5.56:1**;
parchment→meskel from **1.72–1.87:1 to 7.02–8.59:1**. The stale meskel query link
was **1.56:1** on parchment; it now takes parchment's accent immediately.
High-contrast edge/shimmer centre changes from **#fff2c5 / #6f643d = 5.26:1** to
**#fff2c5 / #585035 = 7.18:1**. Its input selection changes from
**#ffffff / #767676 = 4.54:1** to **#ffffff / #585858 = 7.11:1**.

### Exact after pairs for the repaired text roles

| Theme / role | Rendered foreground | Rendered background | Contrast |
|---|---|---|---:|
| meskel / placeholder | `#b7ac94` | `#20231c` | 7.08:1 |
| meskel / disabled | `#b7ac94` | `#2b2e24` | 6.15:1 |
| meskel / input | `#e8dfcc` | `#6e6140` | 4.60:1 |
| meskel / cover | `#7d7865` | `#2b2e24` | 3.12:1 |
| tewahedo / placeholder | `#acb9a0` | `#1a2a23` | 7.29:1 |
| tewahedo / disabled | `#acb9a0` | `#26382d` | 6.05:1 |
| tewahedo / input | `#e1e6d7` | `#516a57` | 4.65:1 |
| tewahedo / cover | `#758471` | `#26382d` | 3.14:1 |
| parchment / placeholder | `#584f40` | `#eee4cd` | 6.37:1 |
| parchment / disabled | `#584f40` | `#e3d5b9` | 5.56:1 |
| parchment / input | `#302a21` | `#c1ab8c` | 6.40:1 |
| parchment / cover | `#807563` | `#e3d5b9` | 3.12:1 |
| lalibela / placeholder | `#bbae9f` | `#302724` | 6.71:1 |
| lalibela / disabled | `#bbae9f` | `#40332d` | 5.59:1 |
| lalibela / input | `#e9dfd5` | `#795b50` | 4.67:1 |
| lalibela / cover | `#8c7f73` | `#40332d` | 3.12:1 |
| midnight / placeholder | `#989bad` | `#121823` | 6.46:1 |
| midnight / disabled | `#989bad` | `#1c2331` | 5.72:1 |
| midnight / input | `#b8bbc7` | `#444a59` | 4.63:1 |
| midnight / cover | `#6a6e7f` | `#1c2331` | 3.11:1 |
| high-contrast / placeholder | `#dddddd` | `#111111` | 13.90:1 |
| high-contrast / disabled | `#dddddd` | `#222222` | 11.71:1 |
| high-contrast / input | `#ffffff` | `#585858` | 7.11:1 |
| high-contrast / cover | `#aeaeae` | `#222222` | 7.17:1 |

## Full rendered evidence

`tools/audit_themes.py` produces SVGs, a JSON measurement ledger and `pairs.csv`.
It exercises actual widgets with the production stylesheet, freezes animation clocks,
and samples at 30 fps. Every exported foreground/background pair is measured;
one representative cell is retained per role/pair (or character/pair for smoke).
The complete final ledger has **1,932 captures and 129,814 measured pair rows**:
**1,260** diagnostic/switch/timeline captures plus **672** production smoke captures.
The 1,260-capture role matrix has **zero violations** of the documented thresholds.
Raw low-contrast unavailable modal context and invisible border filler remain in
its ledger and are explicitly classified, not silently changed.

Reproduce on the host, using `.venv`:

```sh
python tools/smoke.py --out /tmp/ebible-smoke
python tools/audit_themes.py --out /tmp/ebible-theme-after --smoke /tmp/ebible-smoke --png
```

`--png` uses the existing system `rsvg-convert` and ImageMagick executables; no
runtime or global Python dependency was added. SVG/CSV/JSON generation needs neither.
Rich's synthetic terminal window decoration is excluded from colour measurements;
its traffic-light dots and dark title bar are not eBible/Termux UI colours.

### Before/after contact sheets, all six themes

Each controls sheet shows controls, Books, entrance, live-switched modal, live-switched
query terms and the completion boundary. A dark-theme sheet's two switch panels
intentionally show parchment; parchment's show meskel. The after modal includes the
session translation copy option because the probe has just exercised a translation.
This is fixture setup, not a feature change.

| Theme | Before controls | After controls | Before motion | After motion |
|---|---|---|---|---|
| meskel | [PNG](/tmp/ebible-theme-before/png/meskel-before.png) | [PNG](/tmp/ebible-theme-after/meskel-contact.png) | [PNG](/tmp/ebible-theme-before/png/meskel-motion.png) | [PNG](/tmp/ebible-theme-after/meskel-motion.png) |
| tewahedo | [PNG](/tmp/ebible-theme-before/png/tewahedo-before.png) | [PNG](/tmp/ebible-theme-after/tewahedo-contact.png) | [PNG](/tmp/ebible-theme-before/png/tewahedo-motion.png) | [PNG](/tmp/ebible-theme-after/tewahedo-motion.png) |
| parchment | [PNG](/tmp/ebible-theme-before/png/parchment-before.png) | [PNG](/tmp/ebible-theme-after/parchment-contact.png) | [PNG](/tmp/ebible-theme-before/png/parchment-motion.png) | [PNG](/tmp/ebible-theme-after/parchment-motion.png) |
| lalibela | [PNG](/tmp/ebible-theme-before/png/lalibela-before.png) | [PNG](/tmp/ebible-theme-after/lalibela-contact.png) | [PNG](/tmp/ebible-theme-before/png/lalibela-motion.png) | [PNG](/tmp/ebible-theme-after/lalibela-motion.png) |
| midnight | [PNG](/tmp/ebible-theme-before/png/midnight-before.png) | [PNG](/tmp/ebible-theme-after/midnight-contact.png) | [PNG](/tmp/ebible-theme-before/png/midnight-motion.png) | [PNG](/tmp/ebible-theme-after/midnight-motion.png) |
| high-contrast | [PNG](/tmp/ebible-theme-before/png/high-contrast-before.png) | [PNG](/tmp/ebible-theme-after/high-contrast-contact.png) | [PNG](/tmp/ebible-theme-before/png/high-contrast-motion.png) | [PNG](/tmp/ebible-theme-after/high-contrast-motion.png) |

Additional side-by-side comparison sheets are `/tmp/ebible-theme-after/<theme>-comparison.png`;
selected-input detail PNGs use `<theme>-input-selection.png`.

Motion sheets show fetch shimmer, half morph, completion pulse, half reverse,
query shimmer and half-open cover. I inspected all six before/after controls sheets
and all six after motion sheets. Frame-by-frame assertions supplement the PNG review;
PNG antialiasing itself is not used to compute WCAG ratios.

## Tests and validation

**33 new cases:** 23 unit cases and 10 Pilot cases. Unit coverage checks exported
animation colours against narrow theme-derived RGB interpolation segments (two
8-bit quantisation levels of tolerance), contrast, phase boundaries, static/instant
endpoints, generated roles, framework-theme compatibility, and a colour-literal lint
with deliberate failing examples. The lint also rejects uncontrolled Rich `dim`.

The six Pilot matrix cases export all 210 captures per theme: every requested
control state including held-pressed buttons, all five highlights, three notification severities, 30 fps samples
of every animation, light/dark switching, selected Input text and cursor separately.
They assert the motion/static contrast floors and exact rendered reduced-motion
endpoints. The cover wipe may only expose colours from its actual reader/cover
endpoints plus its theme page-edge tint. Three live-switch cases exercise Settings
mid-morph, modal, search, cover, Books and history caches. A separate Pilot checks
colour continuity on fetch completion and a pulse interrupted by reverse.

The existing recorder test now checks the smooth five-sample pulse curve
`0.25, 0.75, 1, 0.75, 0.25`, with zero at both boundaries. The recorder still saves
71 frames at 50 ms, and translation/reveal timing and text are unchanged.
The smoke matrix now covers **six themes × two sizes × 48 states**, plus
**six themes × four sizes × four cover states = 672 SVGs**. Added states include
all notification severities and live theme switches on the modal and morph.

Required gates, Python 3.14.7 / Textual 8.2.8 in `.venv`:

| Gate | Result |
|---|---|
| `ruff check src tests tools` | All checks passed |
| `ruff format --check src tests` | 71 files already formatted |
| `mypy src` | No issues in 43 source files |
| `pytest -q` | **565 passed in 754.81s** |
| `python tools/smoke.py --out /tmp/ebible-smoke` | **672 SVGs, all passed** |

Complete final output: `/tmp/b11-gates-final.log`.

Smoke directory: `/tmp/ebible-smoke/`; complete listing:
`/tmp/ebible-smoke-listing.txt`; manifest: `/tmp/ebible-smoke/manifest.txt`.
Audit directory: `/tmp/ebible-theme-after/`; all pairs and file references are in
`pairs.csv` and `measurements.json`. An independent raw/XML-text scan found **no credential disclosures in all 1,932 SVGs**; `/tmp/b11-evidence.log` records the scan and per-theme counts.

### Remaining role similarities (proposal only)

Using the same SVG-derived ΔE76 <10 criterion after the fixes gives the pairs below.
These are role-level similarities, not identical whole palettes: foreground contrast,
background, accent and semantic colours together distinguish the six themes. Shared
annotation colours are intentional. No further hue changes are implemented.

| Role | Themes | Rendered colours | ΔE76 |
|---|---|---|---:|
| Body | meskel / tewahedo | `#e8dfcc` / `#e1e6d7` | 5.79 |
| Body | meskel / lalibela | `#e8dfcc` / `#e9dfd5` | 4.67 |
| Body | tewahedo / lalibela | `#e1e6d7` / `#e9dfd5` | 6.17 |
| Secondary | meskel / tewahedo | `#b7ac94` / `#acb9a0` | 9.84 |
| Secondary | meskel / lalibela | `#b7ac94` / `#bbae9f` | 5.04 |
| Heading | meskel / tewahedo | `#dfbd73` / `#d7b665` | 4.52 |
| Background | meskel / tewahedo | `#171914` / `#111d19` | 4.86 |
| Background | meskel / lalibela | `#171914` / `#231d1b` | 5.60 |
| Background | meskel / midnight | `#171914` / `#0c1018` | 9.61 |
| Background | meskel / high-contrast | `#171914` / `#000000` | 9.18 |
| Background | tewahedo / lalibela | `#111d19` / `#231d1b` | 9.26 |
| Background | midnight / high-contrast | `#0c1018` / `#000000` | 7.13 |

## Judgement calls and limits

- **Thresholds:** static body/labels are 4.5:1; motion text and decorative strokes
  are 3:1. Terminal bold text is not assumed to be large text. High-contrast uses
  a stricter 7:1 body/effect target. Policy uses small quantisation margins
  (4.6/3.1/7.1) before checking the actual exports.
- Disabled labels are normally exempt under WCAG; they were still repaired because
  phone readability was the issue. Their secondary role distinguishes them from
  enabled foreground labels without reducing whole-widget opacity.
- Retained the approved modal veil: unavailable reader text behind it need not be
  readable. Invisible border filler is not foreground text. Active modal content
  and all visible animated text must pass. Retained passing severity blends and
  control focus/hover policies rather than replacing all Textual defaults.
- Also recorded the empty Plans track at 1.07–1.15:1 and switch background/edge
  shading at 1.02–1.18:1. I classify these as nonessential background paint: numerical
  progress/filled segments and the switch slider/position convey the information.
  Kept these quiet backgrounds; strengthening them is an optional visual proposal.
  This does not exempt slider/filled-segment colours, scrollbar thumbs or labels.
- The cover starts with readable quiet lettering instead of a fade from invisibility;
  this reconciles the original entrance with the new minimum-contrast requirement.
- Kept animation durations, band widths and hue anchors. Used a 120 ms colour handoff
  and a symmetric 300 ms pulse to remove lifecycle jumps without delaying the reveal.
  Intentional page-edge occlusion and character replacement are not colour discontinuities
  on a stationary glyph. Theme switching intentionally applies the new palette immediately.
- The two closest heading accents remain meskel/tewahedo (ΔE76 **4.52**). The audit's
  neutral-grey secondary near-duplicates now use each theme's own secondary role.
  A stronger separation of gold accents or a second light theme remains a proposal,
  **not implemented**. The shared semantic highlight colours are also preserved.
- Measurements are sRGB exported fills, not a physical phone's brightness, font
  rasterisation or colour calibration. Tested the six eBible themes; Textual's
  built-ins have a compatibility check, not a complete contrast certification.
  No live translation/API request or physical Termux session was run. All backend
  output and personal data in the tools/tests are explicit temporary fixtures.

Packaged DB unchanged: **12,521,472 bytes**, SHA-256
`46da43911496d300784fd303a69cbf5a108486a06a8e45ea2c82efa1c11e9997`.
The recorded original-data checksums still cover **39,169 Amharic tuples and 81 book
rows**. Schema, canon, raw source, source-issues documentation and both guide copies
are unchanged. No push or publication.
