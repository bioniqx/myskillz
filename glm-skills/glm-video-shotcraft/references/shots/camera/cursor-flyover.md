---
name: cursor-flyover
summary: After an overview fade-in the camera flies to each of four screen corners in turn while an SVG cursor arrives with it, pointing and leaving a click ripple at every stop.
use: Feature tour of a single-page product: takes the audience through four feature areas in one continuous shot, using the cursor as a "tour guide finger"
duration: ~8.0s (240f@30fps; overview 22f, four stops 44f each (flight 20f + hold 24f), pull-back 24f, hold 18f)
energy: Medium (equidistant cruise, rhythmic clicks and ripples setting the cadence)
---

## Intention
A shot-saving alternative to "four separate cuts for four features": one continuous camera threads four corners into a single visitor route, with the cursor acting as the viewer's attention proxy—wherever it moves and clicks, the viewer looks. Spatial continuity naturally helps the audience remember the spatial relationships between features.

## Motion Core
- The demo uses a bright porcelain aesthetic (cool white + cobalt blue) for the video-shotcraft workbench overview (top bar logo mark + wordmark) rendered at native 1:1 on a 2400x1500 world canvas: overview at s=0.66 shows full context, close-up at s=1.3 (world 32px text -> screen 42px, comfortably legible).
- The camera steps through a lookup table: CAMS[0] overview -> four module centers (top-left Frames rendered -> top-right Shot previews -> bottom-right Release flags -> bottom-left Top shots), interpolating `x/y/s` via an asymmetric ease (bezier 0.55, 0, 0.18, 1: crisp takeoff, very soft landing); between stops, s pulls back an extra ~8% then pushes back in (hop), with directional motion blur scaled by screen speed (SpeedBlur amount 0.09, capped at 8px).
- Transform formula: `translate(960 - x*s, 540 - y*s) scale(s)`—x/y represents the "camera focus point" in world px; modifying the table instantly updates the tour route.
- **The cursor is the hand, the camera is the eye**: the cursor departs first (swift 16f, a slight arc perpendicular to displacement with zero start/end curvature), while the camera starts 2f later and settles at 20f; the cursor "aims" at the target for one beat before pressing (clickAt = start + 22f), shrinks to 0.84 over 3f, then overshoots on rebound; the cursor is drawn in screen space and stays constant at 40px on screen.
- Each of the four stops targets a real control, triggering immediate UI feedback on click: segmented control 30D -> 90D (thumb translation + old large number slides up as new number rises from below + 12 bars spring to new staggered heights) / data point tooltip pop-up with overshoot + guide line drop / toggle spring slide + grayscale progress bar 0 -> 25% / table row highlight + accent bar + checkmark draw-in.
- Each click spawns an 80px ring ripple (18f, scale 0.3 -> 1.5 fade out).
- After stop 4, the camera smoothly pulls back to overview over 24f, bringing all four updated states into one frame ("tour complete" ensemble poster), ending with an ultra-slow 1% push-in.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Close-up zoom | s=1.3 (overview 0.66) | Native world typesetting; reverse-calculate zoom so legible text >=40px on screen; >1.6 pushes modules out of frame |
| Stepping rhythm | Flight 20f / hold 24f | Hold is the feature reading window; shorter than 15f turns a "tour" into a "glance" |
| Cursor lead | Starts 2f earlier, arrives 6f earlier | 0 = cursor dragged by camera (feels like a screen recording); >10f makes viewers look at cursor before finding content |
| Click ripple | 18f, scale 0.3 -> 1.5 | Ripples act as a metronome with 4 equidistant clicks (every 44f)—pairs with SFX 4x click |
| Tour order | Top-left -> top-right -> bottom-right -> bottom-left | Change CAMS / TARGETS table to alter route; keep adjacent visits between neighbors to avoid disorienting diagonal jumps |
| Ending pull-back | Smooth 24f back to overview | Without pull-back it stops on the last module; pull-back frames all four states into a hero poster |

## Known Pitfalls
- When using real product screenshots, re-calibrate TARGETS coordinates to the centers of controls in the screenshot; screenshots must have native resolution >=1.3x close-up zoom (Q2).
- The camera table's x/y are world pixel coordinates; if the canvas aspect ratio changes (e.g. portrait video), the entire table must be re-calibrated.
- The cursor and camera are decoupled (separate tables), but start/arrival frame offsets must be adjusted in pairs; otherwise the camera may still be moving on click, blurring out UI feedback.
- Don't overdo motion blur: on bright UI during high-speed hop exits, amount > 0.12 looks like "out of focus" rather than "motion".

## Reference Implementation
demos/camera/cursor-flyover/
(CursorFlyover.tsx)
