---
name: marker-underline-title
summary: After the headline settles, a marker stroke draws itself under the keyword — tapered, rough-edged, and slightly tilted to follow the italic.
use: Emphasizing a single keyword in a headline (new / free / AI…); brand tone with handcrafted/human warmth; editorial annotation-style emphasis
duration: Starts +4–8f after headline settles, draws in 8–12f, total 1–1.5s
energy: Low (single-stroke flourish, does not compete with headline)
---

## Intention
A hand-drawn marker stroke suddenly appears beneath printed headline typography, using textural contrast to pull a single word out of the composition — like someone circling a key point on a printed poster. Three critical rules:
**Fast** (drawn in 8–12f in a single continuous stroke; any slower reads as a progress bar), **Close** (hugging the text baseline; too far away reads as a divider line rather than emphasis), **Following letter posture** (the stroke beneath italic text must tilt slightly upward from lower-left to upper-right — drawing the tilt in reverse is the most common and immediately fake mistake; see Known Pitfalls).

## Motion Core
- SVG path drawing (strokeDashoffset or clip window), 8–12f left-to-right, with ease-out finish (fast start, slightly softer end = natural hand pressure).
- Stroke shape: variable-width path (thickest in the middle), rough edges (subtle noise displacement / rough brush texture), tapered ends representing pen touchdown and release.
- Placement: hugs the baseline (bottom offset ≈ -0.1em), with central axis slightly upward-slanted to follow italic posture.
- Timing: begins drawing +4–8f after the headline settles completely — underlining represents "emphasis applied after reading the headline"; moving simultaneously with the headline steals its focus.
- Texture (demo): The stroke passes through a deterministic dry-brush filter — low-frequency feTurbulence displacement (1.8px) creates jagged edges, while high-frequency noise thresholds stretched along the stroke axis generate delicate dry-brush streaks; ink color uses warm, near-black tone multiplied into the paper surface.
- Demo exports `MARKER_UNDERLINE_TITLE_DURATION = 75`: two staggered headline lines settle in 22f → underline draws at f32–42 → static hold for 33f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Draw duration | 10f (measured cadence from reference; 14f version was rejected as sluggish) | >14f reads as a progress bar; <6f makes stroke direction imperceptible |
| Baseline offset | ≈-0.1em (tightened from -40 to -20 @1080p to hug letter posture) | Too far reads as a divider line; colliding with descenders creates mess |
| Slant direction | Upward slant from lower-left to upper-right (matches italic) | **Drawing reversed (upper-left to lower-right) looks instantly fake** — rework precedent |
| Stroke width | Midpoint ~0.12em, ends ~0.6x | Uniform width looks like a machine vector; variation >2x reads as calligraphy |
| Roughness | Subtle edge noise | Overly rough looks like video glitch; fully smooth looks like a CSS border |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Overlaps with draw-svg-trace (deliberately split into two cards): that card covers general SVG path drawing (icons / illustrations / arbitrary line art); this card is dedicated specifically to the marker texture of **text emphasis** (variable width + roughness + matching letter posture); use that card for graphic linework.
- Slant precedent: v1 drawn with high-left and low-right was flagged in review — underline slant must strictly track italic slant, or stay horizontal with subtle organic jitter for roman upright type.
- Residual gap: In the original reference (notion-ai), the dry-brush particles at the tip were even finer; production implementations can layer finer brush grain.

## Reference Implementation
demos/typography/marker-underline-title/
(MarkerUnderlineTitle.tsx)
Original source: notion-ai.mp4
