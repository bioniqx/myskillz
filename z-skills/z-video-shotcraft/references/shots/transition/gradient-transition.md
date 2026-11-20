---
name: gradient-transition
summary: The background morphs smoothly through linear, radial, and conic CSS gradients — angle, color stops, center, and radius each interpolated per-parameter with narrow cross-fades between types.
use: Continuous variation for atmospheric backdrops or chapter background colors; provides a "living" background layer for static typographic segments.
duration: Approx. 6.7s (200f@30fps; linear 0–2.3s · radial 1.9–4.4s · conic 3.9–6.7s).
energy: Low (pure background motion, yielding to foreground content).
---

## Intention
Gradients are not static textures, but animateable parameter sets: within the same gradient type, every parameter can be interpolated to create fluid, continuous movement, while transitions across different types are seamlessly bridged using short cross-fades. Designed as a background layer, this card infuses segments that lack hero foreground action with a steady, low-velocity hum of ambient energy.

## Motion Core
- Three distinct layers each host one gradient type; only one layer dominates at any given moment, and cross-fade windows are kept narrow (12–14f) with both layers remaining in active motion throughout the blend.
- **Linear segment (0–68f)**: Angle sweeps from 18° → 198° (swift in-out); three luminance color stops (64 → 40 → 7) interpolate independently across HSL channels (`mixH` lerps h/s/l separately, avoiding the muddiness of RGB interpolation)—maximizing luminance contrast ensures the sweep angle remains clearly discernible as a shifting band of light.
- **Radial segment (56–132f)**: Center migrates diagonally from (24%, 72%) → (68%, 38%) while the radius expands from 48% → 80%; outer boundaries remain near-black, giving the impression of an ambient spotlight drifting and refocusing within the frame.
- **Conic segment (118–200f)**: A three-color wheel (purple / magenta / ice blue, wrapping back to purple) rotates its `from` angle from 0° → 250°, decelerating gracefully with a slow ease-out tail; center is anchored behind the subject at (64%, 54%), with edges and text areas further suppressed with vignette shadows.
- **Render on Small Canvas**: All three gradient layers are drawn on a 480×270 canvas and expanded to fill the frame via `transform: scale(4)`—upscaling during compositing provides natural optical softening; applying `blur(9px)` on the miniature canvas equates to ~36px at full resolution, slashing per-frame rendering cost to 1/16th of full-screen real-time blurring; a subtle noise grain overlay is composited on top to eliminate color banding.
- **Demo Foreground**: Each segment features a large 180px headline using a verb that reflects that segment's underlying parametric motion ("Bend light." / "Focus it." / video-shotcraft wordmark + brand tagline), changing in lockstep with gradient transitions; a bottom monospace annotation readout displays real-time values of the active interpolating parameters.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Segment overlap | Next segment begins 12f before prior segment ends | Overlap guarantees both layers are in motion during cross-fade; zero overlap causes a visible freeze at handoff |
| Cross-fade | 56–68f / 118–132f (smooth in-out) | Widening the window exposes clashing geometric structures; narrow cross-fades combined with active motion achieve type changes without breaking flow |
| HSL interpolation | Independent lerp across h/s/l channels | When hue delta exceeds 180°, standard lerp takes the long way around (e.g., 340° → 160°); add +360° to the start angle when a short path is required |
| Color stop luminance delta | Linear stops: light 64 / mid 40 / dark 7 | If luminance delta is <20, the sweeping angle becomes invisible, leaving only a flat color wash |
| Radial migration | Diagonal center travel + radius 48% → 80% | Expanding radius with a static center reads as "pulsing" rather than "meandering" |
| Conic rotation | from 0° → 250° (sub-360°, long ease-out tail) | A full 360° loop matches start and end frames for looping; for one-shot transitions, stopping short avoids an undesirable sense of resetting to zero |
| Palette groupings | Unified purple / magenta / ice blue trio across all segments | When adapting to project colors, maintain paired light/dark values; radial outer perimeter must remain dark to preserve spotlight contrast |

## Known Pitfalls
- This is a background card: when placing typography or UI in the foreground, overlay a dark scrim on the text side (demo uses left linear dimming + outer vignette), otherwise high-luminance tones in the conic segment will destroy foreground legibility.
- The `R` parameter in `radial-gradient(circle R ...)` accepts only absolute lengths: writing `circle 45%` invalidates the entire gradient rule and renders the segment pitch-black—either convert percentage radii to pixels (demo uses miniature canvas width 480px as 100%), or switch syntax to `ellipse X% Y%`.
- Rewriting CSS gradient strings on every frame forces browser repaints rather than GPU composite passes—benchmark performance on low-end target hardware; Remotion server-side rendering is unaffected.
- The conic segment uses a three-color cycle (A → B → C → A); seven-color rainbow spectrums read as juvenile "tech-demo" effects and should be avoided in branded commercial contexts.
- The three segments are fully modular: extracting just the linear segment (renormalized across 0–68f) yields a clean, minimalist "angled light sweep" backdrop.

## Reference Implementation
demos/transition/gradient-transition/
(GradientTransition.tsx)
