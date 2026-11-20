---
name: spotlight-hero-card
summary: A spotlight selects one card, the camera pushes diagonally, the card lifts for two outline passes, then returns to the page.
use: Single-hero product openings; establishing an atomic unit (card, item, module) as the central protagonist of the video
duration: 172f (~5.7s; lock f34 -> touchdown f142 -> 30f true static hold)
energy: Medium (highest texture and polish, slow and deliberate rhythm)
tags: effects, camera
---

## Intention
Telling a focused opening story: this single card is the atomic unit of the product. The spotlight guides viewer attention, elevation provides volume and weight, the contour beam acts as a scanning metaphor, and reseating confirms it belongs to the page layout.

## Motion Core
- **Lights down**: Real screenshot multiplied down to ~6–14% luminance (warm black `rgba(14,12,10)` preserving hue), with only the light pool displaying natural page colors; turning lights on mimics a switch: f1–6 bright -> flickers to 62% -> stabilizes.
- **Light pool**: Multi-stop near-Gaussian decay (center transparent -> perimeter dark, avoiding hard edges) + low-intensity tungsten warm-white soft light; roams across 3 stops (2–3f pause between stops, smooth in-out) before locking to card center, tightening with a 6% pulse upon lock; post-lock (f38–58, during push-in), screen-space circular pool cross-fades into **page-space card-shaped light**: full-page dark mask under identical camera (translateZ 1px, 0.94 warm black) cuts a soft card-shaped aperture (tight aperture sigma 22 + 15% wide spill sigma 60); card sits above dark mask on z-axis, maintaining edge-to-edge native contrast while decay occurs strictly outside card; soft-light fades synchronously; warm-white rim light + subtle spill ensures silhouette reads cleanly on dark page; dark mask breathes gently +-1.2% during hold.
- **Volumetric beam**: Light source placed far off-screen top-right, casting trapezoidal beam onto pool (outer blur 28px, inner clip-path, soft edges), with deterministic floating dust particles; beam dims by 45% post-push-in.
- Camera pushes from orthogonal full-page overview to oblique close-up (left-side camera dominant), shifting focus left so card lands slightly right of center, reserving left space for annotations; locks completely post-push-in.
- Card rises (with overshoot) -> hovering sine bob -> reseat (slight landing compression + champagne ground light); shadow casts toward bottom-left (light source from top-right).
- SVG rounded-rect contour beam completes two laps: lap 1 fast and bright, lap 2 slow and subdued (champagne gold + white core).
- Card elevation leaves page background patch + champagne outline in original slot, brightening and vanishing on touchdown.
- 3D hovering annotations: White bold two-line video-shotcraft tagline "Your product, / in motion." on card left (34px page space, ~100px post-push-in), with 12f champagne marker block growing behind keywords (inverting text to ink), backed by dark scrim; annotation layer renders above lighting layer sharing identical camera math (camAt)—self-illuminated typography immune to stage darkening; reseats flush with page plane on touchdown (translateZ 92->4), concluding as a complete poster.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Card selection | cards[3], center x exactly at 960 (page center) | Select hero card based on post-push-in composition rather than arbitrary choice |
| Camera | Static full-page zoom 0.8 (0–40f) -> 18f push-in zoom 2.6; rotY 34 deg dominant + rotX 8 deg, persp 1200; focus point offsets card center left 105px, up 10px; locked completely to end | Lateral angle reads better than top-down perspective ("filming from left rather than below"); avoid terminal drifting zooms like 2.6->2.58; delegate breathing to light rather than camera |
| Lights down | Multiply 0.90->0.94 outside light pool (~6–10% luminance) | <0.8 reads as a "dimmed page" rather than theater; >0.96 loses context of surrounding cards |
| Spotlight | 3 waypoints (4->28f), pool radius 400->300, lock +6% pulse; soft-light warm white 0.24; swaps to card-shaped light post-lock | Circular pool leaves card corners dark and center blown out; card-shaped soft aperture lights card evenly; waypoints make roaming credible |
| Volumetric beam | Source (pool.x+420, -720), beam width 0.6x pool; screen 0.34->0.06 vertical gradient | Source too close reads like flashlight; beam too wide blurs with pool |
| Motion arc | rise 10f (bezier(0.2,1.25,0.3,1) overshoot) -> hover 58f (sine bob amp 4px cycle 40f, z=110px*lift) -> reseat 18f, touchdown press 0.997 | Lock to touchdown ~108f (~3.6s)—prestige shots must slow down to 3s+; initial drafts are almost always too fast |
| Contour beam | lap1 68->82f (double layer strokeWidth 5+2.5), lap2 88->108f (3.5+1.75, opacity 0.62); strokeDasharray "0.16 1" via dashoffset | Distinct speeds across two laps convey continuous scanning; single lap feels like a blink; award beam only to hero |
| Dual-layer shadow | Offset bottom-left `-10*lift, 10*lift ..., -36*lift 48*lift 90*lift` growing with altitude | Shadow failing to scale with altitude breaks hovering illusion; direction must align with light source |

## Audio
Lights on pins low light-clunk (f2), elevation pins whoosh-big (demo f56, template f127), beam scan pins sparkle (f68), reseat pins transition-snap (f142)—distinct audio signatures for elevation, light effects, and landing.

## Known Pitfalls
- Multi-card ensemble openings fail to establish strong initial impression—opening was rebuilt multiple times before converging on single hero card; start drafts with single protagonist and complete motion arc.
- Text blurs under close-up zoom due to rasterization resolution rather than DoF—apply high-resolution rasterization techniques.
- Per-card glint flashes rejected twice ("no need for every card to sparkle"); restrict lighting strictly to hero.
- Card-shaped light mask must reside in page space (inside PageCam, translateZ between page and card); screen-space masks fail to track perspective and lift; card translateZ must be >= +2px to avoid co-planar z-fighting with mask post-reseat.
- Right edge of annotation dark scrim must terminate before card left edge to prevent dark wedge over card surface.
- Annotations rendered inside PageCam below lighting layer get dimmed into grey text by multiply blend; render annotation layer above lighting layer using identical camera.

## Reference Implementation
demos/opening/spotlight-hero-card/SpotlightHeroCard.tsx (adapted from template/src/aifl/live/SceneOpen.tsx 82–220, revised to dark theater version)
