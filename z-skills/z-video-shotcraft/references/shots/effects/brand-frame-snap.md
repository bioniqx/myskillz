---
name: brand-frame-snap
summary: A thick brand-color frame grows around the screen before content arrives, then hard-flips its color on the same frame the inner layout switches.
use: Global packaging layer for dual-mode or dual-chapter product videos (blue = Mode A, green = Mode B color coding); branded wrapping for live screen recordings
duration: Single color flip ~4.7s (140f); the frame itself can persist across the full video
energy: Medium (high at the flip moment, quiet packaging layer otherwise)
tags: transition
---

## Intention
Raw screen recordings filling the entire canvas lack brand presence, while logo watermarks feel cheap. This card frames screen recordings with a thick brand-color border: the frame **appears before content** (establishing the frame before hanging the picture creates ceremony), after which the frame color becomes the semantic code for the entire video—in the demo, cobalt blue = Design, orange-red = Dev Mode (original reference was blue/green; the key is complementary hue clash + lightness contrast). During chapter switches, the full frame snaps color within a single frame with zero gradient; this hard cut visually equals a mechanical gear-shift sound effect. Simultaneously, the inner window layout switches A->B and corner badges/wordmarks update synchronously, locking in the "mode switch" through 3-point harmonic resonance. Division of labor with theme-switch-moves: that card alters the UI body theme (with sweeping wipe boundaries), whereas this card switches the outer "framing layer" (single-frame boundaryless cut) to signal mode/chapter switches rather than UI skinning.

## Motion Core
- The frame consists of 4 solid color bands (not CSS border properties), snapping 0->60px over 19f snappy growth (visible frame from frame 2); inner aperture features 22px rounded corners (corner filler blocks) with a subtle glaze gradient (bright top, dark bottom); color flip = instant background swap on the exact same frame.
- Product window (1560x864, native pixel layout) drops into the frame via `spring(damping: 15, stiffness: 115)` from y: 660px + 18 deg -> 0 forward tilt + scale 0.88->1 (starting at frame 10, mid-way through frame growth), with vertical motion blur scaled to velocity and shadow tightening from 70->22px based on elevation.
- Motivation: cursor glides in an arc from 56–80f toward the title bar Design | Dev switch, clicks at 80, releases at 84 = flip frame.
- Four events lock to the exact flip frame: frame color swap + inner window layout A->B hard cut (right light inspector -> dark CSS panel, left layers -> tokens, blue selection -> orange callouts) + frame corner badge label swap (DESIGN -> DEV MODE, top-right video-shotcraft wordmark remains, monochrome white logo on color band) + switch button toggle state.
- Flip moment layers a 3f radial white flash (stepped decay from 0.6, brightest at frame bands) + frame thickness damped bounce (`exp(-0.24t) * cos(0.95t) * 12px`) + ~1% content hitch to deliver physical gear-shift impact; aftershocks: dimension callout lines draw on staggered by 3f, value pills pop out with overshoot.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Frame thickness | 60px (1080p), corner badge 30px bold all-caps | Too thin reads as an outline with insufficient room for readable badges; >64px encroaches on content area |
| Frame growth | 19f snappy, leads window by 10f | Frame must establish first—content arriving before frame packaging reads as an afterthought |
| Window landing | spring(damping: 15, stiffness: 115), y 660->0 + rotateX 18 deg -> 0 + scale 0.88->1 | Landing "inside the frame" is the semantic anchor; landing position must sit fully within the frame band |
| Flip timing | Demo 84f (cursor release frame); hold steady (>=30f after window settles) before flipping | Flipping before the window settles prevents viewers from establishing the "blue = current mode" mental anchor |
| White flash pulse | 3f, 0.6->0.2 stepped decay, radial (brightest at frame bands) | Helps the eye register "this frame changed"; >4f reads as canvas strobe and steals focus from the color flip |
| Thickness bounce | Damped cosine decay, 12px initial amplitude | Pure hard cuts feel dry; bounce provides mechanical feedback of "locking into gear" |

## Known Pitfalls
- Demo calibrated using a custom design tool window (frame corner badge is video-shotcraft logo + wordmark, canvas displays a video-shotcraft promo card)—parameters serve as a tuning baseline, verify against real assets in production.
- Flip must be strictly frame-accurate: if frame, inner layout, and badge copy drift apart by even 2f, the "gear shift" scatters into three disconnected micro-animations.
- Color coding must remain consistent across the video: avoid dominant green UI elements during blue-frame sections; diluting the code degrades the flip into a superficial color swap.
- The frame is packaging, not the hero: flip <=2 times per video; excessive flips read like neon signage (P4 restraint principle).
- Brand color contrast between modes must be strong (demo: cobalt blue #2F55FF vs orange-red #FF5B1F, complementary hue clash + lightness delta); adjacent hues with identical lightness produce negligible perceived change.
- Keep inner UI neutral ink tones, reserving accent color strictly for active mode cues (selection state is blue in blue sections, callouts are orange in orange sections), preventing UI noise from diluting the code.
- Audio: punch a crisp mechanical click / gear shift on the flip frame, locked synchronously with the white flash; frame growth phase can remain silent.

## Reference Implementation
demos/effects/brand-frame-snap/
(BrandFrameSnap.tsx)
Original source: figma-devmode 0:28–0:32 + 0:43–0:47
