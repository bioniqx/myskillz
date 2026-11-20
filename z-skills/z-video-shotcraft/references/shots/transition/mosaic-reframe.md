---
name: mosaic-reframe
summary: Twelve tiles morph continuously between a regular grid, a feature mosaic with one hero slot, and a rotated diagonal cascade, each tile interpolating position and size independently with a slight stagger.
use: Display transition demonstrating "multiple ways of viewing the same content": showcase of layout versatility for portfolio, template library, or photo gallery products.
duration: Approx. 7.1s (214f@30fps; emerge 0–22f · hold A · A→B 56–92f · hold B · B→C 132–176f · hold C through 214f).
energy: Medium (continuously flowing rearrangement, no jarring burst, composed and confident demeanor).
---

## Intention
Let the audience witness "layout itself thinking": the exact same twelve pieces of content transform from an orderly archival state (regular grid) into an editorial hierarchy (feature mosaic), and finally into a dynamic, expressive composition (diagonal cascade).

## Motion Core
- Three layout states are hardcoded into coordinate tables based on 1920×1080 native pixels (content bounds: x 96–1824, y 212–984):
  - State A = 4×3 regular grid (gap 24px);
  - State B = 6×4 cell mosaic (first tile occupies a 3×2 hero slot, gap 16px);
  - State C = vertical photo cards 300×372 fanned out diagonally along (850, 214) → (1724, 930), with incrementally increasing rotation rot = −15° + i·3°.
- Each tile **interpolates center x/y, w/h, and rot independently**, rather than applying a global container transform scale—true geometric width and height changes preserve border-radius and shadow dimensions without optical distortion; position converges first, w/h converges 2f later, and rotation converges 4f later, with the B→C rotation carrying a subtle overshoot (`cubic-bezier(0.45, 0, 0.3, 1.22)`).
- Relocation curve uses `cubic-bezier(0.75, 0, 0.15, 1)` (slow start → rapid transit → soft landing with long tail); 26f per tile for A→B, 30f per tile for B→C; mid-flight elevation follows a sine envelope (scaling up +3.5% with deeper, softer shadows), snapping back down upon touchdown.
- Causal drive: the top-right segmented control (Grid / Mosaic / Cascade) slides its accent capsule to the next tier first (snappy 12f, horizontally stretching mid-flight); tiles begin rearranging 4f later (parent acts first, children follow).
- Stagger: A→B sweeps through tile indices with accelerating density (10f total span); B→C deals out tiles like playing cards at uniform intervals (14f total span); starting at B→C, stacking order switches to "later cards layered on top" (State B has zero overlap, making the z-index swap invisible).
- Three states convey three tones: State B's hero card overlays a large serif photo caption (Featured shot / Golden Hour / Shot 01 · Crash zoom · 4.5s rising word by word); State C's tiles sprout a 14px white photo border, while the bottom-left negative space reveals a prominent serif headline + subline, concluding on a complete editorial poster (demo features video-shotcraft's 12-shot storyboard: header emblem + wordmark + Storyboard, closing on "Every shot, in sequence." + brand tagline).
- Opening: 12 photos rise with diagonal stagger (16f snappy), while the camera maintains an ultra-slow push-in from 1 → 1.025 throughout.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Segment duration / hold | A→B 26f, B→C 30f; hold A 30f, B 36f, C 34f | Hold durations provide breathing room to read layouts; compressing below 20f blurs the three states into a chaotic mess |
| Control-to-tile lag | 4f | 0f loses causal connection; >8f makes controls feel unresponsive |
| Stagger span | A→B 10f, B→C 14f | 0f produces mechanical simultaneous shifts; >24f makes the wave motion overpower the layout itself |
| Cascade parameters | Photo cards 300×372, center spacing ~(79, 65)px, rot −15° + 3°/tile | Incremental rotation is the soul of the cascade; uniform rotation degenerates into a tilted grid |
| Mosaic hero slot | First tile spans 3×2 grid cells | Reconfiguring the slots table adjusts visual weight; ensure at least one anchor slot is ≥2×2 |
| Lift envelope | scale +3.5%, shadow elevation 6 → 40 | Too high resembles floating modal popups; 0 reads as flat sliding tiles |
| Tile content | Procedural SVG artwork (viewBox + slice ≈ cover, warm 35mm film aesthetic) | When swapping to real photography, preserve overflow: hidden rounded containers + object-fit: cover |

## Known Pitfalls
- Independent center/dimension interpolation means you **cannot** substitute transform: scale—animating width/height triggers child layout passes, requiring child images to use object-fit: cover.
- In Segment C, the final tile intentionally exceeds the bottom viewport boundary; frame cropping is part of the composition; State C's diagonal axis must avoid the top-left wordmark and top-right control, preserving bottom-left space for the headline.
- Vertical photo cards crop landscape imagery into a central vertical slice: keep photographic focal points near the horizontal center; in the hero image, position the sun slightly to the right to leave room for the bottom-left caption.
- Stacking order (zIndex) can only be safely swapped during non-overlapping states (the launch frame of B→C); swapping zIndex mid-overlap produces jarring layer pop.
- Compounding segment windows, stagger spans, and control lag means the final tile in B→C settles around 176f; if adding further segments, compress earlier segments rather than pushing outward (ensuring all tiles settle before t=1).

## Reference Implementation
demos/transition/mosaic-reframe/
(MosaicReframe.tsx)
