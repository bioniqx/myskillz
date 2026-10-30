---
name: fracture
summary: Twenty-five 3D tiles fly in from scattered space and lock into a poster in a center-out ripple, hold for a beat, then accelerate outward off-screen in all directions.
use: Opening establishing shot for brand/poster reveals "from chaos to formation"; reversing or isolating the second half functions as a hard transition
duration: ~5.2s (156f@30fps; assembly 0–2.6s · hold 1s · dispersion 1.5s)
energy: High (high energy at both ends, calm in the middle; ideal for locking to BGM accent beats)
---

## Intention
Framing "product formation" as a physical event: fragments carry individual rotations out of 3D space and fly into position, letting viewers watch a coherent visual emerge from disorder; after holding to read copy, the entire assembly detonates off-screen, cleanly handing attention to the next shot. Symmetrical entry and exit allows the asset to run forward or reversed.

## Motion Core
- 25 tiles each hold deterministic pseudorandom initial poses: displacement +-450/+-300/+-490px (x/y/z) + three-axis +-180 deg rotation, generated via `rand(seed)` for reproducible rendering.
- Entrance staggered via Manhattan distance ripple: `delay = (|r-2|+|c-2|) * 0.045`, center settling first and corners last, each tile traveling over 0.34 duration along `bezier(0.42,0,0.3,1)` (extended deceleration before landing); landing followed by ~10f damped rotateX oscillation <=2.5 deg = tactile "click" into place.
- 25 tiles slice from **the exact same poster** (each tile offsets according to its grid slot), revealing complete artwork only upon alignment; tiles shaded by orientation (darker when angled away from lens).
- Opacity rises rapidly to 1 via `tin * 2.5`—tiles appear solid even from afar, avoiding fade-in softness that dilutes physical weight.
- Poster carries eyebrow INTRODUCING + video-shotcraft wordmark (logo + lowercase wordmark) sliced with tiles, lighting up across t=0.42–0.52 to command focus during hold; exit does not fade text independently; typography and logo tear away with fragments; whole poster slowly pushes in 3% during hold.
- Exit avoids fading: each tile accelerates along vector away from screen center (`atan2` calculation + +-0.8 jitter), flying 620–880px off-screen with additional +-150 deg rotation via `inCubic` acceleration as solid physical entities.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Grid | 5x5, 380x230px, perspective 900px | Denser tiles yield smoother ripples but diminish individual tile presence; persp <700 distorts perspective excessively |
| Initial scatter | dx+-450 / dy+-300 / dz -210~+490 | Wider scatter heightens initial chaos, but longer assembly paths require wider delay windows |
| Ripple interval | 0.045/ring (Manhattan distance) | >0.07 turns ripple into sequential roll call; <0.03 arrives nearly simultaneously, losing ripple effect |
| Entrance duration | 0.34 per tile (inOutCubic) | Shorter snaps into place faster; pair with ripple interval to ensure final tile lands by <=0.6 |
| Exit window | Departs at 0.70 + delay*0.5, duration 0.18 (inCubic) | **Window must complete before t~0.97**: previously 0.72+delay*0.7/0.26 caused corner tiles to linger on frame boundary for a full second |
| Exit distance | 620–880px (away from center + random jitter) | Insufficient distance leaves fragments stuck at frame edge; center tile direction is random (lacks "away from center" vector) |
| Poster palette | `ACCENT_HUE=218` derives entire poster (cool deep stage + top-left soft light + bottom glowing horizon arc) | Change a single hue constant to recolor entire poster; tile gap 0.5 design px—wider cuts missing strokes in text |

## Known Pitfalls
- Exit must clear screen via translation rather than opacity fading—fading reads as "disappearing" rather than "flying away," ruining physical realism; preserve `opacity = min(1, tin*2.5)` without exit modifier when adjusting parameters.
- All random values must use deterministic `rand(seed)` (equivalent to Remotion `random()`); true randomness causes frame-to-frame render jitter.
- Hold segment (t~0.6–0.7) is the sole reading window; extending copy requires expanding the gap between label fade-out and initial tile departure, otherwise tiles scatter before text is read.
- Do not let logos straddle tile seams: seams cut thin gaps or residual edges into logos, appearing broken. The demo centers the wordmark on row 3 center and sets font size to 22 so it sits entirely within column 2; recalculate when modifying logo dimensions or grid layout.
- When used as a transition, isolate t=0.7–1 dispersion segment running half reversed and half forward; mapping incoming and outgoing assets to tile faces requires custom texture mapping.

## Reference Implementation
demos/opening/fracture/
(Fracture.tsx)
