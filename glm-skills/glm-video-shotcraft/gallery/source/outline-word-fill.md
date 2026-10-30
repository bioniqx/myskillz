---
name: outline-word-fill
summary: An outlined word snaps down from triple size while a dashed circle and horizontal guides close in, then the stroke flips to solid white in a single frame with one brief glow.
use: Heavyweight hammer beats for single-word value propositions / slogans; anchor shots aligned with rhythm drops; emphasis frames in dark-field brand videos
duration: ~3.0s (90f@30fps, snappy single-beat + 36f landing hold)
energy: High (3.2x contraction + instantaneous ignition, brief high impact)
---

## Intention
Driving a word home like a hammered nail does not rely on a slow fade-in, but on **two successive landings**: first, an enormous hollow outlined word rapidly contracts into place (the landing of size); second, the thin stroke snaps into solid white within a single frame (the landing of texture). The intervening 1.5s of contracting dashed circles and extending horizontal guides represents an "aiming" sequence — technical drafting vocabulary that frames the ignition beat as a decisive "confirmation." Fill **must be instantaneous**: a slow wipe fill degrades an impactful hammer blow into a leisurely cosmetic animation.

## Motion Core
(Demo calibrated at native 1920×1080 coordinates and frame indices; look = ember warm black / orange)
- Rapid outline contraction: `scale = mix(3.2, 1, ramp(f, 2, 11, EASE.snappy))`, fading in across 2–8f —
  **contraction window lasts only 11f**, moving fast enough to read as an impact shock; instantaneous defocus proportional to scale velocity is applied (zero when settled).
- Dual-layer text: `outline` (`color:transparent` + `-webkit-text-stroke:2px` warm grey) layered with `solid` (white-hot `#fff5ee`, initial opacity 0), 220px / **500 weight** Helvetica Neue (medium weight, not 800 display bold — overly thick outlines blob together).
- Dashed outer circle (r=410, `dasharray 22 18`) + inner 72-division scale ring (long tick every 30°, slowly rotating in reverse) + four registration reticles: fades in at 8–18f, `scale 2.8 → 1` contracting slowly across 8–52f (EASE.out, **44f, the slowest curve in the entire shot**); main circle rotates at 0.22°/f, braking to an abrupt stop the instant fill ignites ("locked"), while inner ring continues rotating slowly so the hold section continues to breathe.
- Left and right horizontal dashed lines (`dasharray 14 12`): extend inward from screen edges to 28px outside the circle edge across 28–46f, with reticle dots at tips; monospace telemetry above lines reads "BEFORE 1 week" / "AFTER 4 hrs" — translating "faster" into concrete before/after metrics (hand-crafting a week vs. video-shotcraft delivering in an afternoon).
- Stroke preheating: warm grey warms to bright orange-white with subtle outer glow across 44–53f, providing an energy-charging prelude before the hard cut.
- **Instantaneous fill**: At frame 54, `lit = frame >= 54 ? 1 : 0`, hard-switching solid and outline opacities with zero intermediate states; in the same frame, circle and horizontal lines lock into solid orange, and right telemetry turns orange.
- Fleeting flash: `flash = lit · (1 - ramp(f, 54, 8))`, with white 14px + orange 60px dual-layer text-shadow decaying over 8f, leaving only a faint orange halo; an impact shockwave expands 160px past the circle border, dissipating over 14f (firing only once); stage key light pulses synchronously.
- Landing: Eyebrow inside circle (small video-shotcraft logo + lowercase monospace wordmark) / subtitle (40px, "One prompt to a finished promo.") rises across 56–70f, holding static from 70 to 90f, with full scene executing an ultra-slow push-in 1→1.015.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Contraction | `scale 3.2 → 1`, 11f window, snappy | 3.2x represents "backing away from your face"; <2x reads as standard scaling; window >20f becomes a slow zoom, losing impact |
| Font size & weight | 220px / **500 weight**, spanning ~1/3 screen width | 700+ weight causes thin strokes to enclose huge blank cavities, looking like balloon fonts; 500 is the sweet spot for outlined type |
| Stroke | 2px warm grey (138,118,104), preheated to bright orange-white before fill | Fine stroke embodies drafting vocabulary; >4px turns into graffiti; removing preheating makes the snap cut feel unmotivated |
| Dashed circle | r=410, `dash 22 18`, scale 2.8→1 (44f), 0.22°/f rotation, brakes upon fill | 44f slow contraction provides the scene's "breathing," contrasting against the 11f text contraction; compressing window to 20f collides them |
| Horizontal dashed lines | `dash 14 12`, 28–46f extending to 28px outside circle | Inward travel must terminate outside circle border (not entering it); spanning full width creates a sniper crosshair, which is excessive |
| Instantaneous fill | Frame 54 hard cut (frame-exact conditional, no normalized time windows) | **This moment is the sole purpose of the card**: any gradual wipe (>3f) downgrades the hammer blow into a cosmetic decoration |
| Bloom glow | White 14px + orange 60px, decaying over 8f; shock ring 14f | Must vanish quickly to read as a flash; sustained glow looks like cheap neon text |
| Duration | 90f (3.0s): 36f hold after fill | Hold <20f after fill cuts away before viewers can read the subtitle and telemetry |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **Suitable strictly for a single short word (demo uses `Faster`, 6 letters)**: Font size 220 and circle radius r=410 form fixed coordinates; longer words punch through the circle and collide with horizontal lines — changing to two words or longer phrases requires synchronously updating `SIZE`, `R`, and line terminal points.
- `-webkit-text-stroke` is a vendor-prefixed property supported in Chromium/WebKit; in Firefox, the outline layer renders fully transparent (text pops in only at ignition). Remotion renders via Chromium with zero issues.
- Instantaneous fill must be a frame-exact hard cut (demo: `frame >= POP`). Earlier versions using normalized windows like `seg(0.742, 0.762)` turned into multi-frame visible gradients when stretching duration — adjust duration solely by shifting the `POP` frame index.
- Dark backgrounds only: warm black backdrop + fine strokes + bloom constitute the entire aesthetic; outlined type is virtually invisible on white backdrops, requiring full restyling.
- Audio dependency: The ignition frame requires a crisp, heavy impact sound (metal / switch / low-end transient), providing half the card's tactile weight (see sound-design.md). Division of labor with word-relay-geometry: that card handles three-word relays (this card is an independent, upgraded realization of its first segment); do not juxtapose both in the same video.

## Reference Implementation
demos/typography/outline-word-fill/
(OutlineWordFill.tsx)
