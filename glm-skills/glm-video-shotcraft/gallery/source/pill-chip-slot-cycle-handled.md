---
name: pill-chip-slot-cycle-handled
summary: A dark chip inside the sentence rolls through feature words, its width easing to each word so the surrounding text is pushed apart while grey ghost items show above and below.
use: "We handle your ___" value proposition copy; concluding punchlines for SaaS capability enumerations; primary hero moments in light-background brand videos
duration: ~5.0s (150f@30fps: static hold → 3 transitions (0.25/0.47/0.69) → ending static hold)
energy: Medium (steady 3-beat rhythm, width expansion/contraction is the sole continuous motion)
---

## Intention
Word slot cycling divides into two schools: insulating the sentence from change (fixed-width reels), or forcing the sentence to **accept** change (capsule expands, pushing adjacent words outward). This card chooses the latter: the cost is requiring precise width calculations, but the reward is a living sentence — "Your" and "Handled" get physically pushed aside, making the audience feel the tangible weight of words within the chip. Grey ghost items revealed above and below serve as a secondary signature: explicitly indicating "this is a scrollable list," setting viewer expectations for subsequent terms.

## Motion Core
- Width pre-measurement: During setup, a hidden `<span>` measures each word's `offsetWidth`, adding 74px padding to store into `widths[]` (with `o.w.length·13` fallback to prevent zero-measure crashes before DOM mount).
- Positional progress `pos` accumulates across 3 window segments: transition points `[0.25, 0.47, 0.69]`, each lasting 0.12 (~18f), eased via `E.inOutCubic` — **smooth deceleration at both ends**, representing reel start and stop.
- Inner column `colIn` translates vertically `-pos·48`px (line height 48 = capsule height); capsule width interpolates via `lerp(frac, widths[ci], widths[ci+1])`, calculating **intra-frame interpolation** so expansion is continuous, with surrounding `flex:none` text naturally pushed apart by the flex layout.
- Ghost items sit outside the capsule (inside chipWrap) at top -38px / bottom +58px, sampling adjacent neighbor texts around `near = round(pos)` and shifting slightly with scrolling via `(pos-near)·48·0.5` (**half-speed parallax**, moving at half the speed of internal words to suggest an "outer ring").
- Ghost item opacity `0.13 · (0.4 + settle·0.6)`, where `settle = 1 - min(1, |pos-near|·3)` — dimmer during scroll transit, crispest upon settling.
- Each row contains an emoji + word two-part structure (18px emoji, 22px / 700 weight white text); capsule uses `#1a1c24` background + `0 8px 24px rgba(20,22,40,.22)` shadow + `overflow:hidden`.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Vocabulary | 4 words + emoji (Shots / Camera / Sound / Renders — the features handled by video-shotcraft), 3 transitions | Length variance governs the feel of outward displacement: demo ranges from shortest 5 letters to longest 7 letters; variation >2x causes jerky capsule jumps, swaying sentence balance |
| Transition cues | `[0.25, 0.47, 0.69]`, window 0.12 (~18f) | Inter-segment pauses ~0.10 (~15f) for reading; opening pause before 0.25 lets viewers absorb the sentence structure first |
| Easing | `E.inOutCubic` | Decelerating at both ends simulates mechanical wheel physics; outCubic (decelerating only at end) feels flung up with abrupt width snapping |
| Capsule | Height 48px, radius 99, `#1a1c24`, width = text width + 74 | +74 accounts for left/right padding + emoji slot; <50 crowds borders, >100 bloats capsule into a generic button |
| Ghost items | Top -38px / bottom +58px, base opacity 0.13 | 0.13 is the sweet spot for "visible without distracting"; >0.25 reads as three competing lines of text; removing destroys list cues |
| Ghost parallax | `(pos-near)·48·0.5` (half-speed) | Half-speed produces the depth of an outer drum; full speed makes all three lines slide as a flat card, negating ghost utility |
| Typography hierarchy | Outer sentence 30px/800, capsule text 22px/700 | Capsule text smaller than outer sentence establishes proper hierarchy (badge attached to sentence); equal or larger size feels like two conflicting headlines |
| Palette | Canvas `#fbfbfd`, sentence `#15171d`, capsule white text | Light canvas + single dark block is this card's identity; dark backgrounds cause the capsule to disappear, requiring a full redesign |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **Width relies on `offsetWidth` measurements during setup**: Measuring before webfonts load yields fallback font dimensions, causing incorrect capsule widths — ensure webfonts are ready before measuring, or use offscreen canvas `measureText`; the `length·13` fallback only prevents crashes, not inaccuracy.
- Constrain word length variance within 2x: adaptive width is both the primary appeal and risk; jumping from 5 to 8 letters (`Sales` → `Workflow`) is the upper tolerance limit — larger deltas cause disorienting swings in surrounding text.
- Surrounding text must be set to `flex:none`: otherwise flex will compress them instead of shifting them, squashing text instead of pushing it aside.
- Ghost items sample text around `round(pos)`, triggering a **text swap at exact midpoints (pos=x.5)** — masked by `settle` at maximum dimness so it is imperceptible; raising opacity to 0.25+ will expose this snap.
- System emoji glyph widths vary across platforms (especially `⚙️` with variation selectors), shifting measured width by several pixels; use custom monochrome SVG icons in production instead of system emojis.
- Division of labor with vertical-word-roll-blur-cycle: that card uses fixed widths, bare words, and cylindrical blur (words as sentence components); this card uses adaptive widths, dark capsules, and ghost items (words as badges) — use only one per video. Audio: 3 landing points require lightweight switch/capsule latch clicks, alternating two samples; see sound-design.md.

## Reference Implementation
demos/typography/pill-chip-slot-cycle-handled/
(PillChipSlotCycleHandled.tsx)
