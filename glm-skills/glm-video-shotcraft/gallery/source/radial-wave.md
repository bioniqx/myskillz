---
name: radial-wave
summary: A 17x9 dot grid lights up in rings that spread outward from the center, each dot overshooting its scale before settling into a steady glow, then a brighter pulse collapses back inward from the edges.
use: "System power-on" beat for product/brand openings; establishing shot for data grids, node maps, and network coverage narratives.
duration: ~3.8s (114f @ 30fps)
energy: Medium-High (Punchy opening burst, settling into steady low-energy ambient base post-wavefront)
---

## Intention
Transforms the static fact that "many points exist simultaneously" into the dynamic narrative that "energy expands outward from a single source to the entire system." Viewers perceive not a static grid, but an electrification event: center ignites first, radiance ripples across like water waves, settling into an illuminated state—setting the stage for subsequent content. The secondary inward wave serves as an acknowledgement pulse, signaling that the system is responsive.

## Motion Core
- Grid spans 17×9 (153 points total), with dots positioned via percentages (`left:(c+0.5)/COLS`), allowing row/column modifications without recalculating layout; each point caches normalized distance `dist = hypot(c-cx, r-cy) / maxD` (where maxD = hypot(8,4)).
- Primary wave: `seg(t, dist*0.35, dist*0.35+0.18, E.outCubic)`—start cues delay linearly with distance (outermost ring delayed by 0.35), while individual dot travel stays constant at 0.18; wavefront is formed by staggered start times rather than variable speeds.
- Dot scale goes beyond simple 0→1, employing `w1*(1+0.5*sin(w1*π))`: bulging to ~1.5 mid-flight before settling to 1; sine envelope places overshoot at the exact midpoint of travel rather than on landing.
- Secondary wave: `seg(t, 0.62+(1-dist)*0.25, +0.15)` inverts offset (outer ring initiates first), using `sin(w2*π)` as a pure transient pulse with +0.8 scale and +0.25 opacity increments, leaving zero residual state upon finish.
- Peak pulse (`pulse2 > 0.3`) cuts sharply to `#b9f2ff` with a `0 0 12px #7fd8ff` glow halo—only the secondary wave carries glow while the primary wave uses `#6c8cff` throughout, preventing the two waves from blurring visually.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Grid scale | COLS=17 / ROWS=9 (153 dots) | Dot count sets wavefront "resolution"; <8 columns steps distance too coarsely, reading like concentric stepped rings |
| Wave velocity coefficient | `dist*0.35` | 0.35 is the inverse wave speed: larger values make wave travel slower with longer tail; >0.5 delays outermost ring past halfway mark |
| Single-dot travel | 0.18 (≈21f) | Determines wavefront thickness; <0.1 creates thin scanner beam, >0.3 illuminates entire field almost at once, destroying propagation feel |
| Overshoot amplitude | `1+0.5*sin(w1*π)` → peak 1.5 | 0.5 coefficient delivers a crisp pop; omitting sine reduces to flat 0→1 fade-in, >0.8 causes dots to overlap borders |
| Secondary wave | Start `0.62+(1-dist)*0.25`, window 0.15, amplitude 0.8 | 0.62 provides breathing room between waves; advancing below 0.5 overlaps primary wave tail into messy flashing |
| Ambient baseline | `opacity = 0.25 + w1*0.5 + pulse2*0.25` | 0.25 establishes presence of unlit dots; dropping to 0 leaves void outside wavefront, hiding system scale |
| Highlight threshold | `pulse2 > 0.3` palette swap + glow | Lower threshold broadens glow duration; hard cut rather than gradient means near-zero values show harsh toggle jumps |

## Known Pitfalls
- Wave origin is hardcoded to geometric center (`cx=(COLS-1)/2, cy=(ROWS-1)/2`). To originate waves from a corner or specific node, update cx/cy and maxD simultaneously; otherwise normalized distance >1 pushes outer ring starts past t=1 where they never ignite.
- Final frame retains subtle motion: center point (dist=0) secondary wave window is 0.87→1.02; at t=1 it reaches 87% progress with `pulse2≈0.41` still glowing. For seamless loops or static endings, keep secondary wave start within 0.85.
- Dot `width:10px` and `margin:-5px` form a bound pair (centered via negative margin); changing dot diameter requires updating margin to prevent grid shifting by half a radius toward bottom-right.
- Uses two color tiers (base `#6c8cff` / peak `#b9f2ff`); re-theming requires updating both colors plus glow halo; dark background `#0a0b10` is essential for glow, as luminance pulses vanish against white backgrounds.

## Reference Implementation
demos/ui-entrance/radial-wave/
(RadialWave.tsx)
