---
name: transition-travel
summary: A passage transition that pushes through the counter of a giant letterform into the next scene.
use: Seams between two shots sharing an "element/container" spatial relationship (technique card: selected complementarily with the three shot-transitions variants).
duration: n/a (technique card; demo 150f, main push action segment 52f, preceding/trailing holds budgeted separately, frames deducted from adjacent shot budgets).
energy: n/a (technique card, does not consume an energy slot).
tags: camera
---

## Intention
The three shot-transitions recipes are "handoff" types—the outgoing shot wraps up, the incoming shot enters, and the seam relies on a white flash, motion blur, or an opening window to disguise the cut. This card is a **"travel"** type—the incoming background pre-exists as a genuine physical element within the foreground frame (a hole in a letterform), and the camera dives through via a single continuous spatial trajectory. The viewer follows the same physical entity from start to finish, with no handoff beat. Selection criteria: if the incoming scene can "pre-exist" inside the foreground → travel; if the two scenes simply share sequential order without spatial nesting → handoff. The semantic concept of letterform travel is **"the title is the doorway"** (unifying the chapter title card and the transition into a single action).

## Variant Selection Table
| Variant | Method | Applicable Seams |
|---|---|---|
| A Letterform Zoom | A giant title letterform (cut via SVG mask) reveals the incoming page; camera pushes exponentially through the aperture, taking over the frame the instant the opening fills the screen while residual letter strokes whip off-camera | Chapter title → body content; a high-energy alternative replacing the paper-title-card chapter title card |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Aperture push | Cover SVG mask (white base + black text weight 900) hollows out an aperture; transform-origin aligns with the geometric center of the letter stroke (hole)—anchoring inside the letter stroke ensures the hole expands to fill the screen rather than the cover (demo: center of the vertical stem of "I" in 560px "EDITS" at (973, 515); vertical stem 107px × 30 > screen width; pick words so the "I" stem lands near the screen centerline, ensuring the aperture blooms from center); scale = 30^u, with u driven across 52f via bezier(0.6, 0, 0.85, 0.5) (slow start, steep acceleration); 26–34f prior to push performs a 2% pull-back anticipation | ZOOM_MAX scales to ensure "the hole fully consumes the frame"; thinner strokes require larger multipliers; the slow-start phase grants viewers time to see that "something lives inside the hole" |
| A Content visible in aperture | Dark cover, bright hole: warm-black cover vs. molten-gold gradient video-shotcraft launch page; cards visible through the hole also feature bright surfaces (milky white frosted glass); letter edges carry a blurred orange stroke drawn exclusively on the cover layer (simulating light leaking from the hole) + a 1.5px warm-white cut bevel | Dark patches inside the hole make letters read as solid characters, destroying the suspense of traveling through an aperture |
| A Light without text inside hole | During the title-card hold phase, text and card layers of the incoming page are completely hidden; only warm gradients + soft luminous silhouettes shine through (a soft white glow at card position, a dark red smudge at title position); mid-push across 64–90f, content layers fade in and snap into focus from 18px blur (EASE.out), becoming razor-sharp at takeover | If full page headlines are legible inside the hole, the two typographic layers clash, reading as visual clutter rather than a pristine aperture |
| A Departure & Streak blur | At scale ∈ [14, 26], cover opacity ramps 1 → 0; starting at u > 0.35, expected blur ramps 0 → 20px (divided by scale before applying to blur) + 4 layers of ghosted cover silhouettes from 0.8–3.2 frames earlier blend into a radial zoom motion trail; at the takeover instant, page brightness flashes +12% before settling | Failing to divide blur by scale results in an over-magnified blurry wall; using only two ghost layers reads as stepped translucent slabs—four layers create a continuous optical streak |
| A Background parallax | Incoming page pushes only 1 → 1.08 (driven by 0.7·u during main push, completed with quint-out post-takeover, maintaining velocity continuity across the boundary) + drifts 28px left across 0–100f; post-takeover, shot counter on the render card ticks 0 → 12, duration bar fills with stagger, and DONE badge pops up | A completely stationary background looks like a dead flat image inside the hole; zooming the background too fast matches cover velocity, collapsing spatial depth |

## Known Pitfalls
- The push anchor point must be calibrated on actual rendered frames (the vertical stem coordinates in the demo were measured from a static frame); changing fonts, words, or layout engines alters tracking and shifts the anchor—inspect test renders: if the aperture does not expand from center, nudge the origin rather than blindly trusting calculated em values; if the anchor stroke is too far from screen center (e.g., the "I" in "FILM" at x ≈ 726), the hole expands lopsidedly, leaving the opposing cover lingering on screen; choose words that place the vertical stem centrally.
- When the incoming page pushes to 1.08, ~4% of its perimeter is cropped: calculate safe layout margins based on the post-push state (demo preserves margins: left/right 200/230px, top 122px).
- Never stack letterform travel with the three handoff variants on the same seam—one technique per seam; travel transitions already carry high kinetic energy, wrapping them with additional white flashes or screen shakes reads as an amateur visual error (consistent with shot-transitions rules).

## Reference Implementation
demos/transition/transition-travel/
(LetterformZoom.tsx)
