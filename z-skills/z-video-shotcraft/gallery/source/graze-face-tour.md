---
name: graze-face-tour
summary: The camera skims low across the UI surface like terrain while page text hovers above the interface and settles down as the shot advances.
use: Feature area tour (skimming UI like terrain); paired with dark stages + neon rim lights for a product "inner world" sequence; UI content appearing zone by zone
duration: Single segment 4–5s; can extend via multi-segment relays
energy: Medium-high (continuous camera advance + sequential element landings, high information density)
tags: ui-entrance
---

## Intention
Filming UI as landscape: a steep-angle close-up turns sidebar trees, navigation bars, and list rows into passing terrain, while shallow depth of field reinforces "surface skimming." The dramatic focal point is **text settling onto the page from above**: text/components do not fade in on the spot, but hover above the interface (lifted along the 3D z-axis), casting matching soft shadows onto the surface while aloft; as the camera advances, they accelerate downward and settle, with shadows converging and vanishing with height—the audience watches the interface "complete itself" as the camera glides by. The shadow is essential: without a shadow, hovering reads as a generic translation entrance; with a shadow, the spatial relationship snaps into place instantly.

## Motion Core
- Camera: CSS perspective + rotateX/rotateY at a steep angle (glancing almost edge-on), steadily advancing along a path across the interface; shallow depth of field = progressive blur into the distance.
- Floating elements: Initial hover height H ~ 120–180px (lifted along surface normal), using easeFall for accelerating descent + soft landing (no rebound or micro-rebound on contact).
- Matching soft shadows: Rendered blurred and darkened in original position, with blur/offset/opacity all scaling linearly with current hover height (high = large, soft, faint shadow; landed = shadow converges onto element and disappears).
- Staggered settling: Element landing times are distributed along the camera travel direction (elements passed first land first), assembling the interface progressively before the camera.
- Long shots can be split into relayed segments: adjacent segments blend via crossfade (precedent: non-overlapping opacity windows create black flash frames).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Hover height | 120–180px | <80px makes both shadow and displacement imperceptible; >250px lands with excessive weight |
| Shadow parameters | blur/offset/opacity converge linearly with height | Constant shadows that don't scale with height feel like stickers; landed shadow must reach zero |
| Landing stagger | Normalized 0.2 -> 0.85 along camera travel direction | Landing all on the same frame feels like a light switch; scrambled order looks like a bug; **staggered = staggered start times but overlapping parallel descents**; serial waiting (one completes before the next starts) is rejected |
| Descent curve | easeFall acceleration + soft landing | ease-out descent feels like a floating balloon; sense of gravity requires acceleration |
| Segment relay | Adjacent segments crossfade >=8f | Non-overlapping opacity windows cause black flashes (rework precedent: frame 100 pure black frame) |
| Depth of field | Progressive blur in the distance | Completely sharp reads as flat scrolling; shallow depth of field provides the physical "skimming" feel |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Keep hovering elements from being swallowed by dark vignetting: airborne elements need ~1.3x spotlighting/brightening, otherwise the hover state is imperceptible.
- Distinction from space-camera-moves / tension-camera-moves: those cards represent pure camera language; this card is a combined signature of glancing camera position **+ element landing**; if either half is missing, use a camera card instead.
- **Rhythm semantic precedent** (counterpart to neon-frame-orbit-drop): this tour shot requires staggered parallel descents; full entrance shots require all elements landing on the exact same frame (the staggered version of that card was rejected). Choosing the wrong syntax will fail review in both directions.
- The original reference (clickup-30) is a continuous upward single-take; the recreation uses a 3-segment relay with cuts hidden in crossfades—real single-take path planning is significantly more expensive in production.

## Reference Implementation
demos/camera/graze-face-tour/
(GrazeFaceTour.tsx)
Original source: clickup-30.mp4
