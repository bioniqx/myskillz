---
name: hashtag-to-pill-materialize
summary: A typed "#word" hard-cuts into a wide pill tag, holds, shrinks into its slot on the page, then hard-cuts again to reveal the finished view.
use: Demonstration segments for tagging, categorization, and keyword features (tagging in note apps, topic aggregation); three-stage narrative of "input -> transform into UI entity -> settle into final product"
duration: 120f (4s) — typing ~40f + hard-cut pill hold ~18f + shrink-move ~14f + post-reveal rest ~1.2s (original video 18–21.5s)
energy: Medium (crisp and decisive; derives punch from hard cuts rather than bouncy springs)
tags: typography
---

## Intention
The conventional technique for turning text into entities is gradient/morph/expand. Frame-by-frame breakdown of the original video proves Bear does the opposite: **materialization is a 1-frame hard cut**—one frame text + cursor, the very next frame a complete pill, with zero expansion, zero cross-fade, zero rebound. A hard cut delivers the certainty of "snap, done"; any gradient softens an "entity" into a "special effect." The backbone of the entire shot is **one slide sandwiched between two hard cuts**: hard cut materialization -> smooth shrink-move settling -> hard cut reveal of finished page. The sole continuous motion (shrink-move) is framed between two hard cuts, rendering it fast yet grounded. This rhythmic backbone is essential; altering the character of any of the three stages (replacing hard cuts with fades, or slide with cuts) collapses the shot.

## Motion Core
- Typing stage: Geometric sans-serif (Futura aesthetic) centered typing "#word", **solid red cursor steadily illuminated without blinking** (verified in original video, do not add blink); human cadence 4–6f/char with deterministic jitter.
- **Materialization = 1-frame hard cut**: Text + cursor layer vanishes completely; in the exact same frame, borderless light grey pill + icon + word appears (identical font size, 1:1 scale in place, # replaced by icon); only a 3f 1.03->1 subtle settle allowed to prevent stiffness.
- Pill hold ~0.6s -> Bezier easeInOut shrink-and-slide (~0.55x, ~14f) into page tag slot, position and scale sharing identical curve and start/end points without mid-flight staging.
- Settle followed by **another 1-frame hard cut** revealing finished page: background, title, body, and pill color palette change simultaneously in a single frame, concluding with true static hold.
- Implementation note: Pill drawn at large font size and scaled via outer transform; transformOrigin must be set to `0 0` with translate executed first, otherwise landing center drifts.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Typing cadence | 4–6f/char (original video ~6 char/s), mulberry32 jitter | Uniform intervals read like machine typing; cursor must stay solid (**verified in original video** without blinking) |
| Materialization | **1-frame hard cut** (verified frame-by-frame with zero transition) + 3f 1.03->1 micro-settle | Adding fade-in/expansion immediately downgrades it to a standard morph; micro-settle >4f reads as bouncy |
| Pill geometry | 740x236 @1920 (**verified from original** 493x157 @720p x1.5), no border | Pill must be "excessively wide" to convey physical entity presence; adding borders reads like a button |
| Hold | ~18f (0.6s, **verified in original**) | <12f leaves viewers no time to parse pill appearance before it flies away |
| Shrink-move | ~0.55x (**verified in original** 273/493), 14f, bezier(0.5,0,0.25,1) | Scale and displacement must share identical curve; tuning separately reads as two disjointed animations |
| Reveal | Landing +3f then 1-frame hard cut to full page | Using transitions for reveal destroys the second hard cut, collapsing half the backbone |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Overlaps with typewriter-moves (typing presentation) and ui-to-brand-morph (gradient morphing formation): this card's essence is **hard-cut materialization, not gradient morphing**—if you want to add transitions, use those two cards instead.
- Earlier versions invented a segment where "pill flies in and note card slides up from below"; debunked and removed via original video comparison; do not resurrect flight segments.
- Default transformOrigin `50% 50%` causes landing center to drift by `(1-s)*half-width`; must use `origin 0 0` + translate to target center before scaling (annotated in demo).
- Residual variance with original: Futura fallback font weight, ~10px body text spacing discrepancy on reveal frame; rhythm and hard-cut timing are tightly aligned. Demo content adapted to video-shotcraft context (original "#music" + note icon -> "#shots" + clapperboard icon, finished page "My favorite shots"); topic keyword matches original length, preserving pill geometry.

## Reference Implementation
demos/interaction/hashtag-to-pill-materialize/
(HashtagToPillMaterialize.tsx)
Source: bear-app.mp4 18–21.5s
