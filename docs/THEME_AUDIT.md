# Theme audit — Batch 11, before changes

Baseline: **ac05d43**. This audit was written and committed before changing application
code. It preserves Claude's epigraph label, **Psalms 118:105**, and the shared
`EPIGRAPH` constant. Findings below describe the baseline, not the eventual fixes.

## Method and evidence

Measurements come from **actual Textual/Rich exported SVGs**, not assumed palette
pairs. The extractor resolves each SVG text class's fill, maps each character to
its terminal cell and the background rectangle beneath it, then applies WCAG
sRGB linearisation and relative-luminance contrast `(Lmax + .05)/(Lmin + .05)`.
Rich's terminal-window decoration outside the clipped terminal is excluded.
Spaces and invisible border filler are retained in raw evidence but are not
readable text. Text remains at the terminal's normal size even when bold: **4.5:1**
for static body/labels, **3:1** for decorative strokes and motion text. For the
advertised high-contrast theme, a **7:1 body/effect target** is used in addition.

The diagnostic control screen uses the actual app stylesheet and Textual widgets,
with explicitly labelled temporary fixture text. It exercises normal, hover,
focus, disabled and severity buttons; cursor/placeholder Inputs; Select and its
overlay; OptionList; muted text, headings and key chips. Actual reader/search/
modal/cover screens and all 43 existing smoke states supplement it in **all six
themes**. Five highlights are captured on ordinary and selected verses and on
modal swatch panels. Real notification severities are captured with Pilot
notifications explicitly enabled (the normal smoke default suppresses them).

The frame sweep samples at 30 fps: 28 fetching frames, 40 forward/flourish frames,
31 reverse frames, 28 query shimmer frames, 25 entrance frames and 18 opening
frames per theme. Additional controlled query captures avoid the initial empty
search worker cancelling a diagnostic pending state. Live-switch captures cover
reader motion, search shimmer/terms, cover and modal swatches. All data is isolated
under temporary XDG directories and all translations are explicit test fixtures.

Artifacts: `/tmp/ebible-theme-before/` contains SVGs, JSON measurements, `pairs.csv`
(**144,229** measured character/pair rows with coordinates, states and ratios), and `png/`.
Each visual finding has rendered PNG evidence below; six before contact sheets
are in `png/<theme>-before.png`. No remote translator was called.

## Ranked findings

### 1. High — live theme switching leaves cached Rich colours behind

Modal swatches retain the previous light/dark palette. Switching from any dark
theme to parchment produces **1.11–1.36:1** dots on the light panel. The reverse
leaves dark swatches at **1.72–1.87:1** on meskel. These are actionable controls.
For example, a meskel query link switched to parchment remains `#dfbd73` on
`#f5eedc`, **1.56:1**. Query refinement links also cache a literal accent; changing the CSS theme does
not rebuild that Rich Text until focus/selection happens. The colour-keyed LRU
helpers themselves are safe: keys include colour values. Reader settings refresh
and the cover's render-time palette resolve the new theme correctly.

| Swatch after dark → parchment | Rendered foreground / background | Ratio |
|---|---|---:|
| Gold | `#e4c56e` / `#e3d5b9` | 1.16 |
| Green | `#a5d9a3` / `#e3d5b9` | 1.11 |
| Red | `#f1a69a` / `#e3d5b9` | 1.36 |
| Blue | `#a6c8ef` / `#e3d5b9` | 1.19 |
| Purple | `#d6b1eb` / `#e3d5b9` | 1.28 |

Evidence: [swatches](/tmp/ebible-theme-before/png/meskel-switch-modal-after.png),
[reverse direction](/tmp/ebible-theme-before/png/parchment-switch-modal-after.png),
[query links](/tmp/ebible-theme-before/png/meskel-switch-terms-after.png).
Small fix: subscribe cached Rich producers to Textual's completed theme-change
signal, rebuild visible colours without resetting the query, selection or animation.

### 2. High — cover fade makes every label unreadable during entrance

The title, epigraph, reference and actions start at the panel colour itself (**1:1**).
At the first visibly different sample, text is still only about **1.01–1.03:1**.
This includes high-contrast, and violates the requested 3:1 motion floor. The
parchment fade has the correct darkening polarity; it is simply too faint early.

| Theme | Rendered foreground / background · contrast |
|---|---|
| meskel | `#2d2f25` / `#2b2e24` · **1.02:1** |
| tewahedo | `#28392e` / `#26382d` · **1.02:1** |
| parchment | `#e1d3b7` / `#e3d5b9` · **1.02:1** |
| lalibela | `#41342e` / `#40332d` · **1.02:1** |
| midnight | `#1d2432` / `#1c2331` · **1.01:1** |
| high-contrast | `#242424` / `#222222` · **1.02:1** |

Evidence: [meskel fade](/tmp/ebible-theme-before/png/meskel-cover-entrance-012.png),
[parchment fade](/tmp/ebible-theme-before/png/parchment-cover-entrance-012.png).
Small fix: begin at a readable theme-derived muted colour, then brighten/darken
through the same accent family. Preserve geometry and the existing 0.8 s timing.

### 3. High — input hints and disabled labels fall below the body threshold

Placeholders use Textual's default disabled-text opacity rather than a readable
secondary role. These are instructions needed to use search/settings on a phone.

| Theme | Rendered foreground / background · contrast |
|---|---|
| meskel | `#747672` / `#20231c` · **3.47:1** |
| tewahedo | `#717a76` / `#1a2a23` · **3.39:1** |
| parchment | `#938d7f` / `#eee4cd` · **2.61:1** |
| lalibela | `#7e7977` / `#302724` · **3.39:1** |
| midnight | `#6c6f76` / `#121823` · **3.53:1** |
| high-contrast | `#6b6b6b` / `#111111` · **3.54:1** |

Disabled labels are WCAG-exempt in isolation, but several are so faint that the
available-but-disabled action is difficult to identify; fix their contrast while
retaining a secondary colour to distinguish them from enabled text.

| Theme | Rendered foreground / background · contrast |
|---|---|
| meskel | `#726f63` / `#20221b` · **3.19:1** |
| tewahedo | `#6c756c` / `#1a2922` · **3.18:1** |
| parchment | `#9e9685` / `#ebe1ca` · **2.26:1** |
| lalibela | `#7b726c` / `#312723` · **3.09:1** |
| midnight | `#565a65` / `#131923` · **2.56:1** |
| high-contrast | `#717171` / `#101010` · **3.90:1** |

Evidence: `png/<theme>-controls.png` for every theme. Focused book-filter placeholder
is even lower in parchment: **#8d8779 / #e4dac4 = 2.57:1**.
Small fix: explicit theme secondary role, no inherited text opacity or terminal dim.

### 4. Medium — input selection and list-detail contrast/role inconsistencies

The focused Input's selected text is below 4.5 in meskel, tewahedo and midnight.
The cursor itself uses reversed foreground/background and passes; the low pair
belongs to the selection behind it (focus selects the fixture text).

| Theme | Rendered foreground / background · contrast |
|---|---|
| meskel | `#e8dfcc` / `#726442` · **4.38:1** |
| tewahedo | `#e1e6d7` / `#536d59` · **4.46:1** |
| parchment | `#302a21` / `#c1ab8c` · **6.40:1** |
| lalibela | `#e9dfd5` / `#7a5c51` · **4.60:1** |
| midnight | `#b8bbc7` / `#4e5463` · **3.96:1** |
| high-contrast | `#ffffff` / `#767676` · **4.54:1** |

Rich `dim` details in highlighted book/history rows are **4.03:1** on parchment
(`#6c6456` / `#e1d5bf`) and **4.33:1** on midnight (`#848792` / `#20242e`).
Muted page hints/footer use generated neutral grey while reader buttons use the
warm/cool secondary palette. For example, meskel page hints are **#a2a3a1**,
reader secondary is **#b5aa92**, and book details vary again with terminal dim.
These are three implementations of the same semantic secondary-text role.

Evidence: `png/<theme>-input-cursor.png`, `png/<theme>-books.png`.
Small fix: assign explicit selection and secondary roles in themes.py and replace
uncontrolled Rich dim; preserve existing backgrounds wherever they already pass.

### 5. Medium — subtle borders/scrollbar thumbs fall below 3:1

Meskel normal Input outline is **#2b2e24 / #20231c = 1.15:1** and its idle scrollbar
thumb is **#74643c / #20231c = 2.75:1**. Similar low outline/thumb contrast occurs
across the family. These indicate control bounds and scroll position, not body text.
They should reach 3:1 with the smallest adjustment toward the existing accent.
Selected verse gutters and ordinary cover frames already have strong contrast.

Evidence: `png/<theme>-controls.png`, `png/<theme>-reader.png`. The complete raw
pair table includes stroke/fill inversion used by Textual's half-block glyphs.

### 6. Medium — effect boundaries jump, and high-contrast loses its target

The forward-completion pulse starts at full strength in a single frame. Maximum
same-letter channel steps at that boundary are **61, 67, 39, 56, 71, 34** (sRGB units)
for meskel, tewahedo, parchment, lalibela, midnight and high-contrast respectively.
Reverse completion similarly snaps the dim source to full ink. Fetch-start applies
its waiting dim immediately. These are colour discontinuities, not text replacement.

The high-contrast edge/shimmer centre uses **#fff2c5 / #6f643d = 5.26:1**, below its
7:1 target, although above the general 3:1 motion floor. High-contrast moving source
on the selected verse is **#999999 / #161616 = 6.35:1**. Other verse effects retain
at least 3:1 in the sampled baseline; parchment peaks correctly darken toward ink.
No default blue/ANSI or pure-white parchment peak was observed in the verse effects.

Evidence: `png/<theme>-forward-029.png` beside `png/<theme>-forward-030.png`;
[high-contrast effect](/tmp/ebible-theme-before/png/high-contrast-forward-015.png).
Small fix: continuous colour envelopes at phase boundaries and a constrained tint
for high-contrast. Keep the one-second reveal, band widths and overall hue choices.

## Measured passing roles and intentional exceptions

Static body, headings, regular links, normal/hover/focus button labels, normal
Select values/overlay selection, search match underline, bookmark/note markers,
and normal highlight colours pass their applicable thresholds, except where noted
above. All three notification severities pass: e.g. meskel error title is
**#e7b7ae / #3b3e34 = 6.12:1**; parchment error title **#6a231d / #f8eacd = 9.43:1**.
Toast sidebars remain >=3:1. Notification colours are severity-derived theme
mixtures, not a blue/ANSI leak; no wholesale toast redesign is warranted.

Inactive reader content visible behind the 75% modal backdrop is intentionally
subdued (roughly 1.2–1.8:1). It is unavailable context, not an actionable/readable
foreground, and is recorded but not treated as a contrast repair target. Blank
border filler also has 1:1 contrast by construction. Neither exception applies
to text in the active modal or to cover/verse animation text.

The completed forward/rest and reverse/rest states have the same content and
colours as instant/reduced-motion endpoints. The cover's final canvas likewise
matches its reduced-motion state. A looping search/fetch shimmer has no terminal
frame until the operation finishes; the appropriate endpoint is its completed
result/reader, with the pending label removed. Regression tests will compare these
endpoints, separately from the transient boundary jumps above.

## Source and framework-default audit

No hard-coded hex/RGB/named Rich colour occurs in application source outside
`ui/themes.py`; the stylesheet has no literal hex values. The relevant leaks are
**implicit policy**: `$text-muted`, `$text-disabled`, Input cursor variables, Select
arrow opacity, default button disabled opacity, and `style='dim'` in Books and
Collections. Textual generates palette lighten/darken and severity blends; their
mere presence is not a failure when the rendered pair is in-family and passes.
A lint regression should reject new literal colours and uncontrolled Rich dim,
while allowing colour names as stored annotation data and transparent layout fills.

## Distinctiveness and proposals (not implementation scope)

The six backgrounds and text roles remain distinct. Shared gold accents and
near-white glow peaks intentionally bring meskel/tewahedo/lalibela closer together.
The following near-duplicate roles are measured from SVG colours (CIELAB ΔE76 <10).
This is a design observation, not permission to redesign Joel's palettes.

| Role | Themes | Rendered colours | ΔE76 |
|---|---|---|---:|
| Heading | meskel / tewahedo | `#dfbd73` / `#d7b665` | 4.52 |
| Muted hint | meskel / tewahedo | `#a2a3a1` / `#9fa4a3` | 1.60 |
| Muted hint | meskel / lalibela | `#a2a3a1` / `#a7a4a3` | 1.78 |
| Muted hint | meskel / midnight | `#a2a3a1` / `#9d9fa2` | 3.14 |
| Muted hint | meskel / high-contrast | `#a2a3a1` / `#999999` | 3.82 |
| Muted hint | tewahedo / lalibela | `#9fa4a3` / `#a7a4a3` | 3.10 |
| Muted hint | tewahedo / midnight | `#9fa4a3` / `#9d9fa2` | 2.94 |
| Muted hint | tewahedo / high-contrast | `#9fa4a3` / `#999999` | 4.22 |
| Muted hint | lalibela / midnight | `#a7a4a3` / `#9d9fa2` | 3.62 |
| Muted hint | lalibela / high-contrast | `#a7a4a3` / `#999999` | 4.54 |
| Muted hint | midnight / high-contrast | `#9d9fa2` / `#999999` | 2.85 |

A future palette revision could separate the shared gold accents more strongly or
add a second light theme. Neither is implemented here. This batch should correct
contrast, theme refresh and motion continuity without replacing the approved hues.

## Scope limits

This is a deterministic headless render audit on the host, not a physical Termux
font/display calibration. WCAG ratios measure sRGB colour pairs, not Ethiopic font
stroke thickness. The audit captures all declared states and 30 fps timeline samples;
it does not claim every possible input string or an uncountable continuous timeline.
Raw data remains available for independent review. Part B will record before/after
pairs and regression coverage in `docs/BATCH11_REVIEW.md`.
