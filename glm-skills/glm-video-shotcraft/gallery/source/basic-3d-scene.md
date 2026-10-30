---
name: basic-3d-scene
summary: Impress-style spatial slides: cards sit at scattered 3D poses and the camera flies to align with each one by inverting its transform, ending on a pulled-back overview where every card lights up.
use: Spatial storytelling for concepts, roadmaps, or a 3-step framework; replaces flat 2D slides with a "different spatial perspective for every step"
duration: ~7.5s (225f@30fps; four stops, three flight segments 28/32/32f, hold >=30f per stop)
energy: Medium (spatial surprise on each transition, quiet card reading during hold)
---

## Intention
Turn "page flipping" into "traveling through an idea space": each card has not only a position but also a 3D pose (the second stop tilts the world left by 38°, the third stop lays the frame on its side by 90°), and as the camera aligns to each card, the viewer's world rotates with it—the spatial transformation itself creates a sense of ceremony for entering each new chapter.

## Motion Core
- One-line core recipe: **camera = stepTransform.inverse()**. Each stop only defines the card's own pose (x/y/z/rx/ry/rz/s). The camera transform takes the exact inverse in strictly reverse order: `scale(1/s) rotateZ(-rz) rotateY(-ry) rotateX(-rx) translate3d(-x,-y,-z)`.
- The demo uses a graphite dark background (near-monochrome with champagne gold accents) for video-shotcraft's three chapter cards: Frame / Craft / Ship (a brand punchline split into three chapters, with the logo mark + wordmark pinned at the top-right of each card): cards use **native 1:1 typesetting** at 1240x700 (matching screen pixels when aligned, no upscaling from design coordinates, keeping text crisp), with a 156px headline + 44px description + 560px light-weight chapter numeral cropped by the card border.
- Four stops, each with its own dramatic note: STEP01 front-facing at the origin -> STEP02 (1690, -260, -650) + ry -38° -> STEP03 (2590, 830, -850) + rz 90° (frame on its side, camera rotates to right it) -> OVERVIEW s=2.7 (camera pulls back by 1/2.7); the overview position is reverse-calculated so the three cards land in the upper right, leaving the lower left for the end lockup.
- Chained flight interpolation: three flight segments at frames 36–64 / 96–128 / 158–190, using an asymmetric ease bezier(0.62, 0, 0.16, 1); the camera pulls back an extra 30% mid-flight (hop, sine envelope) to reveal surrounding cards in the space; flight segments use time-sampled motion blur (shutter 0.5f, adaptive 1–8 subframes based on camera velocity).
- Holds remain alive: after settling, the camera executes an ultra-slow 1.5% push-in (reverted along the same curve upon takeoff for the next segment), while a golden progress line at the card base fills across the current segment; headlines rise word-by-word from beneath the line 8f before landing, revealing each card only once.
- Spatial reference: 70 true 3D dust particles suspended in world coordinates (each with its own z), with all parallax driven by camera motion; enter/exit focus applies `opacity 0.22–1 + blur 0–7px` based on distance `d = |af - i|`, with all cards returning to 0.85 opacity in the overview stage.
- The OVERVIEW lockup is anchored to the overview pose (typeset at 2.7x scale, viewed by the camera at 1/2.7 = 1:1 on screen): eyebrow title with video-shotcraft logo + wordmark, "Craft the shot." 150px serif title rising word-by-word, ending with a 1.5% push-in hold.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Stop poses | At least one new transform dimension per stop | Moving only x/y is just a 2D slide pan; an rz stop (frame roll) creates a visual memory anchor—use once per video |
| Flight duration | 28–32f | Don't go shorter than 28f for segments with rotation; viewers need time to register "the world is turning" |
| Hold duration | >=30f | Reading window; when a card has heavy text, prioritize lengthening the hold rather than shortening flight |
| Hop pull-back | 30% | 0 = flat panning across card surface with no spatial depth; >50% makes every transition feel like an overview |
| OVERVIEW scale | s=2.7 | Higher values mean higher altitude overview; lock in the overview poster composition first, then reverse-engineer world coordinates for each stop |
| Focus falloff | Opacity 0.22 floor + blur 7px peak | Keep the floor above 0.2—out-of-focus cards must remain present, pure black destroys the sense of space |
| Perspective | 2600px | Ratio to maximum |z| (850) is ~3:1; deeper z requires larger perspective to prevent distortion |

## Known Pitfalls
- The reverse rotation order (Z -> Y -> X inverting forward X -> Y -> Z) cannot be swapped; misordering won't show on single-axis rotation, but multi-axis compound stops will skew out of place.
- Card poses are consumed in two places: the card's own transform and the camera formula; to add stops, only edit the POSES table and leave both transform strings intact.
- Text inside the rz 90° card lies sideways and only becomes readable once the camera rights it—this is by design (the "aha, I get it" moment upon righting), but keep copy short for this stop.
- When the final lockup lives in the 3D world, it appears tilted during the final flight segment: fade it in late (after mid-flight), and delay the word-by-word reveal until 6f before settling.
- There is no return flight after OVERVIEW; it serves as a section finale. To loop back to STEP01, add a fly-back segment at the end (cam lerps back to POSES[0]).

## Reference Implementation
demos/camera/basic-3d-scene/
(Basic3DScene.tsx)
