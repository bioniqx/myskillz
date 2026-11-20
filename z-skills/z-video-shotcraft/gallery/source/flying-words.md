---
name: flying-words
summary: Keywords spawn deep in a perspective tunnel and rush past the camera along the z axis, fading in and out on a lifecycle curve across two seamless loops.
use: Dynamic background for keyword clouds / capability catalogs; high-information bottom layer for openers and closers; transitions requiring depth-travel sensation
duration: ~6.0s (180f@30fps, 2 full cycles, seamlessly loopable)
energy: High (continuous full-screen 3D translation, never static)
---

## Intention
The crudest way to list keywords is piling them into a static word cloud. The word tunnel spreads those same terms **across the time axis**: spawning in the distance, scaling up, and sweeping past the lens to vanish. The audience only actively reads three to five words at any moment, yet the subjective impression is "an enormous wealth of concepts." It serves as a background layer, not the hero — with the camera stationary and elements moving, layering a headline or UI foreground on top causes zero visual conflict. Replacing the word list with project-specific keywords requires zero changes to the underlying motion logic.

## Motion Core
- Perspective (in 480 design space): `perspective: 1100px`, with words advancing linearly along z from **-1750 → 800px** — positive values pass behind the camera plane, creating the "fly-by" brush. In native 1920 space (demo), all values scale by 4x: P=4400, z from -7000 to +3200, with manual perspective projection `s = P / (P - z)` (strictly equivalent point-by-point to CSS perspective).
- Spawning uses the golden angle: `a = i·2.39996 + rand(i·7+1)·0.8`, radius `r = 82 + rand·165` (native 4x: 330 + rand·660), with y-radius compressed by 0.6x into a flat ellipse — clearing screen center and preventing near-field words from clustering into a dense knot.
- Lifecycle curve `OP=[0,1,0.5,0.2,0]` at `OT=[0,0.25,0.6,0.85,1]`: **surges to full opacity in the first 1/4, dims to half-opacity in the middle, and trails off to zero at the tail** — far more nuanced than a basic fade-in/out, keeping the middle muted so foreground elements remain unobstructed.
- Outward drift `drift = 0.5 + u·1.35`: tightly clustered at center in the distance, flinging outward toward screen edges as words draw near, combining with z-axis travel for authentic perspective depth.
- Near-field defocus: when `u > 0.86`, linear blur is applied via `(u - 0.86)` — words expanding uncontrollably right before the lens are masked by this blur; true speed sensation is delivered via velocity-aligned directional motion trails (demo: 6-layer fading text-shadow ghosts along -v, far cheaper than full-screen SVG filters on every word); the initial 22% of travel in the distance adds atmospheric fog blur.
- The demo adds two additional reference layers sharing tunnel motion: 10 flat elliptical hairline rings (tunnel walls, thickening and fading in near field) + 56 dust motes rendered as radially stretched streaks (streak length = screen travel across ~2.6 frames); the full tunnel executes an ultra-slow roll of `±2.5°·sin(2πt)` (periodic function, seamless start-to-end).
- Foreground: The demo centers a static wordmark group (monospace eyebrow + 112px headline + radial dark veil); words flying into the elliptical wordmark zone are suppressed to 20% opacity — demonstrating how the background layer leaves foreground titles uncompromised; the wordmark stays stationary while the loop remains seamless.
- `CYCLES = 2` specifies integer revolutions, evaluated as `t = frame / DURATION` (frame after final frame = frame 0) for seamless looping; each word's phase `ph = i/N` distributes evenly with fully deterministic spawning; a center electric-blue halo breathes twice (`opacity = 0.82 + sin(t·4π)·0.14`), anchoring the "tunnel terminus" as a visual focal point.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Vocabulary | 22 words, font size `20 + rand·16`px (20–36; native 64–120), 700 weight + 6 serif italic words | Word count binds to phase `i/N`: <12 feels sparse, >30 clusters into a near-field blur; randomized sizes generate depth, whereas uniform sizes look like flat textures |
| Depth travel | z -1750 → +800px, perspective 1100 (native 4x) | Starting farther (-2500+) makes words too small to recognize; ending ≤0 gives "stops in your face" rather than "flies through" |
| Drift factor | `drift = 0.5 + u·1.35` | Factor <1 shoots words straight from center like an explosion; >2 flings them offscreen too early, turning a tunnel into a fountain |
| Lifecycle curve | `[0,1,0.5,0.2,0]` at `[0,0.25,0.6,0.85,1]` | The 0.5 mid-value yields to foreground elements; staying at 1.0 steals focus, while dropping to 0 early hollows out the tunnel |
| Cycle count | `CYCLES = 2` (must be an integer) | Non-integers break continuity between t=1 and t=0, causing a jarring pop at loop boundary; higher cycle counts accelerate fly-by speeds |
| Near blur | Linear blur when `u > 0.86` + velocity directional trails | Raising threshold to 0.95 makes huge hard-edged words jarring; factor >40 creates color blotches at the tail |
| Color palette | Demo (midnight): cold white 3-step `#f2f5ff/#c3cbe2/#8a95b5` + 4 electric-blue accent words `#86a8ff` (only accent words glow), electric-blue center halo | Dark background with glowing light text is essential; applying this card to white backgrounds fails completely — light palettes require full redesign |
| Center halo | ~1040×720 radial gradient, breathing 2 cycles/shot | Removing it eliminates the focal anchor at tunnel's end, making words look like random scatter; breathing cadence must sync with CYCLES |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Replacing the word list requires **maintaining comparable word counts and character lengths** (demo uses 22 words, 4–9 letters each): phase is evenly distributed by `i/N`, so altering word count scales density across the board; CJK characters are twice as wide as Latin characters, requiring smaller font sizes to avoid crowding near-field frames.
- `CYCLES` must be an integer, otherwise start and end frames will not match — this is the sole prerequisite for seamless looping; adjust flight speed via integer increments/decrements, never fractions.
- Use strictly as a background layer: the 0.5 dip in the lifecycle curve is explicitly tuned to yield to foreground text; boosting it to full brightness makes the scene read as visual clutter.
- Dark backgrounds only: `text-shadow` glows and radial vignettes constitute half the effect; on light backgrounds words degrade into muddy smudges. All 22 word elements remain mounted in the DOM throughout (transform/opacity animated without remounting) — preserve this structure in Remotion without dynamically adding/removing nodes per frame.

## Reference Implementation
demos/typography/flying-words/
(FlyingWords.tsx)
