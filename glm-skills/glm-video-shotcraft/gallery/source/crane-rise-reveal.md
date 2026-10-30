---
name: crane-rise-reveal
summary: The camera starts tight on one data row, rises and pulls back, then reveals a full dashboard filling the frame.
use: Establishing shot transitioning "from detail to global view"; inverse counterpart to drone-dive-landing (global -> single point dive)
duration: 5.5s (165f: close-up hold 24f + crane lift 102f + settle/aftermath/hold 39f)
energy: Medium-High (continuous unidirectional motion, no impact beat)
tags: camera, data
---

## Intention
The library already contains drone-dive-landing for opening establishing shots—slamming into a hero close-up from a bird's-eye perspective ("global -> focus"). This card is its exact mirror: "focus -> global"—first zooming tight onto a single row of real data so viewers parse "what this is," then rising and pulling back like a crane arm as row after row floods into view, until the full product dashboard covers the screen—"the row you just saw is merely one cell in this entire wall." Suited for openings spotlighting product scale and content richness; choose only one direction per film.

## Motion Core
- transform-origin fixed top-left, linked via formula `translate = screenCenter - focusPoint*scale`; focus point moves along (tracked row left segment) -> (page center) sharing **the exact same asymmetric easing bezier(0.2,0,0.25,1) progress** with scale 3.0->1.0—one p = one camera maneuver.
- Deceleration curve (fast start, slow end) delivers "crane arm" sensation: punchy start, gentle stop at apex; zero initial velocity, peaking at 19% (~2.3x average speed), avoiding instantaneous jump to top speed from hold; during hold, camera first "inhales" and pushes in 1.5% as anticipation.
- Focus: During close-up hold, only the tracked row is solid (cobalt blue base + pulsing tracking dot at start), with remaining rows crushed to 38%, recovering fully ~26f after lift begins—first let viewers parse "this single shot," then see everything.
- Row-by-row light wash: When visible camera upper bound `visTop = fy - 540/s` first crosses a row's top edge, an accent wash sweeps from row start to end (starts at 3f, peaks after 6f, settles over 18f, with 1px accent border)—the primary source of legibility for "surging in"; triggered frame-by-frame in strict sync with camera move.
- Sense of scale: Header KPI (frames rendered today) counts from 0 to 48,210 synchronously with lift (expo-out, settling on same frame as camera); window shadow elevates from surface to floating height as camera widens; stage dot matrix drifts slowly at 0.35 parallax—window ultimately reads as a physical object on stage.
- Aftermath: After settling, tracked row status capsule flips from "Rendering" to "Rendered" (spring damping 16 + checkmark draw + progress bar filling), providing the sole micro-event within hold segment.
- "Brightening" is invisible on white backgrounds; **darkening or coloring is required for perceptibility** (benchmark: brightness increase on white cards is imperceptible).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Initial close-up | scale 3.0, aimed at left segment of tracked row (shot number / transition 63px large type; lower framing rests above window bottom edge without exposing outside) | Hold >=20f so "this is a row of data" is readable before launch |
| Crane lift | 102f bezier(0.2,0,0.25,1), scale 3.0->1.0 | Faster than 80f causes row wash to lag behind; slower than 130f drags in middle |
| Focus | Non-tracked rows 38% -> 100%, 26f post-lift | Without dimming, all rows have equal weight in close-up, leaving viewers unsure where to look |
| Row wash | Triggered upon boundary crossing, accent sweeps from row start + hairline border, ~24f | Wash falling behind camera (fixed interval trigger) immediately ruins illusion |
| Settle | Do not add secondary push after reaching full frame; rely on status flip to keep hold alive, static hold >=30f | Full frame serves as canonical composition |

## Known Pitfalls
- Demo calibrated on custom product window with fictional data (video-shotcraft render queue)—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Starting close-up = inspecting a single row of content magnified 3.2x; real assets must first satisfy high-resolution rasterization guidelines, otherwise low-res screenshots blur immediately on opening.
- Fast lift segment can wrap CameraMotionBlur, but only for the first half's rapid section—wrapping the final slow section blurs and softens typography; do not place translucent light wash overlays inside CameraMotionBlur (multi-sampling creates vertical streak artifacts); keep on separate layer sharing same camera.
- Do not combine with drone-dive-landing in the same film (one ascending and one descending are mirrors, reading as the same trick); tilt-reveal, which is semantically closest to crane, is not in the library—do not conflate them.

## Reference Implementation
demos/opening/crane-rise-reveal/
(CraneRiseReveal.tsx)
