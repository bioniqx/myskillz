---
name: letterspace-materialize
summary: Every letter of a widely tracked wordmark draws itself in parallel, growing like handwriting and finishing together on the same frame.
use: Opening or closing brand wordmark reveals (wide tracking, thin skeleton wordmarks; demo uses video-shotcraft lowercase); chapter title cards; closing frames requiring serenity and premium restraint
duration: Still ~15f + draw ~50f + terminal hold >=30f; total 3–4s
energy: Low (serene ritual, completes in a single breath)
tags: typography, outro
---

## Intention
The wordmark neither fades in nor types out; rather, it "crystallizes": the strokes of all letters begin growing simultaneously, as if an invisible hand were writing every letter at once, finishing together in the exact same frame. Two critical requirements: **continuity** (strokes must be drawn continuously without segmented masking—drawing half then another half reveals the trick; every intermediate frame must look like "halfway written"); **synchronicity** (all letters begin and end in the same frame—letter-by-letter stagger carries typewriter semantics, whereas here it conveys holistic brand ritual).

## Motion Core
- Each character uses a single-line skeleton SVG path, normalized with `pathLength={1}` and drawn continuously via `strokeDashoffset` from 1->0.
- All characters share identical progress p: starting in the same frame, with normalized pathLength ensuring letters of varying stroke lengths finish in unison (no per-character delay or jitter).
- Glyph proportions: square and slightly wide (glyph aspect ratio ~1.07; vertical glyphs previously rejected for being "too tall"); thin strokes + wide tracking (letterSpacing ~0.6em). Demo wordmark is video-shotcraft (brand rules mandate all lowercase): geometric monoline lowercase with circular bowls, baseline 59 / x-height 22 / ascender 5 in 64h viewport, scaled 1.3x with stroke inversely scaled to maintain 5.5px.
- Drawing curve: overall ease-in-out, slightly accelerated in middle and gentle at terminals (mimicking handwriting cadence).
- Background: atmospheric gradient or live-action empty shot (e.g. twilight mountain landscape); wordmark is the sole motion in frame.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Drawing duration | ~50f (starts f16, resolves f68 @30fps) | <30f cannot parse drawing process; >80f drags |
| Synchronicity | All characters start and finish in same frame, zero stagger | Staggered versions previously rejected: "all letters should finish writing at the exact same time" |
| Continuity | Continuous growth via pathLength, no segmented jumps | Segmented mask versions previously rejected: "should be drawn with continuous strokes" |
| Glyph geometry | Monoline skeleton, aspect ratio ~1.07, delicate stroke | Tall glyphs (ratio <0.8) rejected; heavy strokes lose crystalline quality |
| Tracking | ~0.6em | Wide tracking defines this card's identity; <0.3em should use standard draw cards |
| Terminal hold | >=30f | Viewers must have time to read complete wordmark post-crystallization |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Division of labor with draw-svg-trace: that card handles general illustration drawing (icons/illustrations/individual elements); this card focuses on **fully synchronized** crystallization ritual for brand wordmarks.
- Division of labor with type-assembly-moves: that card handles block assembly (spatial translation); this card grows strokes from nothing with zero letter displacement.
- Skeleton glyphs require hand-crafted single-stroke paths (standard font outlines use dual-line closed contours, producing an outline-draw look); the 13 lowercase glyphs in demo (`v i d e o - s h t c r a f`) each carry custom width `w`; prioritize reusing demo glyph library in production; multi-stroke letters (dot on i, crossbars on t/f) are ordered sequentially at path end, finishing simultaneously after pathLength normalization.
- Original video (superhuman-promo) uses live-action twilight mountains with water reflections; demo uses gradient approximation; production strongly recommends live-action or AI-generated cinematic footage.

## Reference Implementation
demos/opening/letterspace-materialize/
(LetterspaceMaterialize.tsx)
Source: superhuman-promo.mp4 ~4.5–6.5s
