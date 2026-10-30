---
name: line-carry-transition
summary: A progress line exits scene A, guides the camera sideways, then turns corners to become the frame of scene B.
use: Transitions between two scenes with graphical kinship (progress bar → card frame, underline → chart axis); marquee transition position in a promo video, evoking the graphic relay of the Catch Me If You Can title sequence.
duration: ~6.3s / 190f (progress bar fills 36f + breakout 10f + lateral pan 56f + frame wrap 24f + in-frame poster 30f + static hold 24f).
energy: Medium
tags: camera
---

## Intention
The three major families in the transition library (travel / hidden cut / block push) all answer the question of "how to swap scenes." This card's answer is: **do not swap at all—let a single line guide you across**. Once a progress bar fills to 100%, its leading tip extends past the card edge and punches out of the frame. The camera tracks the line laterally across 1920px into a new world. In transit, the line turns right angles to construct the card frame of Scene B. The frame closes, content fades in, and from start to finish the viewer's eyes never leave the line. Graphic continuity *is* the transition. Contrast with a match cut: a match cut aligns shapes across an edit point—it is still an edit; this is continuous drawing—**there is no cut**. The line's identity must possess narrative logic (the progress bar has "completed," so it extends outward); a line without motivation is merely arbitrary decoration.

## Motion Core
- A 3840px-wide world container uses `translateX` as the camera, translating 1920px across 56–112f with smooth in-out easing (`cubic-bezier(0.65, 0, 0.35, 1)`).
- A single continuous polyline path (648px progress bar + breakout segment + right angles + 720×480 rectangular frame, total length 4944px) evolves its `dasharray` throughout, driving drawn length in staged segments.
- **The Crux: During lateral pan, drawn = 1144 + cam, synchronizing line growth with camera velocity**—the pen head remains pinned around x ≈ 1480 on the right side of the screen, never exiting the viewport and never falling behind; if velocity desyncs and the viewer loses track of the line, the transition falls apart.
- **Velocity Continuity at Handoffs**: Progress bar eases out to zero velocity → holds full for 6f (state flips to completed, checkmark pops up) → breakout segment starts and ends at zero velocity (swift) → camera starts from zero velocity with in-out easing → frame wrap catches the camera's deceleration at zero velocity.
- The pen head serves as the only accent color focal point in the sequence (terracotta r=14 + halo); after the frame seals (136–142f), it dissolves and is conditionally unmounted (following the mask removal precedent).
- During the lateral pan, world content (cards, dot matrix, exhibit captions) undergoes horizontal motion blur proportional to camera speed (`SpeedBlur`, ≤16px), while the line and pen head remain razor-sharp outside the blur layer; drafting ticks bloom beneath the line after it passes, providing a spatial velocity reference for the eye when only the line occupies the frame mid-pan.
- Scene B's exhibit caption title sits outside the frame and can rise before or as the camera arrives; content inside the frame must strictly wait until the frame seals (from 136f onward) before blooming into view.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Line stroke | 8px solid ink line, square cap + sharp miter joins | Too thin gets lost during fast pans; dashed lines read as an unfinished drafting state |
| Pan ratio | 1920px / 56f (average speed 34px/f) | For longer pan distances, scale duration proportionally without increasing speed—peak velocity >80px/f causes the eye to lose the pen head |
| Pen head anchor | Screen x ≈ 1480 (~77% toward the right) | Centering reads as "line chasing the camera"; anchoring too close to the edge risks clipping out of frame on minor jitter |
| Corners | Sharp right angles, no border rounding | Rounded fillets destroy the technical drafting aesthetic, stripping away the Saul Bass design character |
| Frame closure | Interior content enters only on/after the closure frame | Spawning content before the frame seals ruins the suspense built by the line |
| Outro settle | ≥24f true static hold after poster finishes drawing | The pen head ink dot must be conditionally unmounted; visual debris ruins the static hold |

## Known Pitfalls
- The demo is a handcrafted video-shotcraft rendering sequence (cream paper + ink + terracotta accent; Scene A render promo progress card → Scene B final poster of the video)—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- Relationship with draw-svg-trace: that card performs element-level vector tracing (the line belongs to the element); this card performs scene-level graphic relay (the line belongs to the camera)—both can coexist in the same film, but the line's visual language must remain cohesive: either both are 8px geometric ink strokes, or both share a hand-drawn texture; mixing styles reads as disparate art directions.
- Use ≤1 time across an entire video—this is a signature hero transition, not an everyday utility wipe; repeating it dispels the magic.
- The line origin must be a natural continuation of an existing visual component (a filled progress bar, a completed underline); spawning a line from nowhere reads like an idle screensaver.
- Audio cues: continuous pen friction sound as the line draws, followed by a crisp click/tap when the frame seals (sound-design §4.5).

## Reference Implementation
demos/transition/line-carry-transition/
(LineCarryTransition.tsx)
