---
name: deck-deal-flyin
summary: A physical card stack opens the scene, then cards accelerate into a live grid as the camera follows the growing page.
use: Showcasing list views and card walls with high content volume and continuous incoming streams; establishing immediate impressions of information density.
duration: 150f (~5s: 0–36 deck close-up + anticipation, 36–~101 dealing, 108–150 full board hold)
energy: High (Workhorse for rhythm ramp-up sections; avoid placing as opening shot)
---

## Intention
Present suspense first (what is this stack?), then reveal the payoff (it is dozens of items flying into the page to take their places). Viewers must feel items streaming in endlessly, with each card snapping into position with urgent momentum.

## Motion Core
- First half (pile-orbit-open, optional): All cards stack into a physical deck with real height resting on a dark brushed graphite surface beside the page board. Overhead spotlight illuminates only the deck while camera orbits tightly from a low angle. As camera pulls back, the light expands from the deck via soft-edge vignette to illuminate the dark page board—the page board remains a display board resting on a dark table throughout to the final frame.
- **Anticipation (adapted from Disney Principle 2)**: Before first card launches, provide a section-level anticipation beat—the entire deck compresses slightly downward while top card pulls back opposite to deal direction, pulling viewers' eyes to the deck before dealing begins. Anticipation occurs once at section level, **never per card** (per-card anticipation destroys the hard-accelerating cadence).
- Second half (deck-deal): 26 cards deal from deck toward grid target slots in reading order, with launch intervals hard-accelerating; individual card flight carries z-arc crest, overshoot settle, and landing press-bounce (settle/press embodies Principle 5 follow-through—rapid stop paired with cushioning, removing it reads as rigid freeze).
- Camera tracks dealing toward board bottom (accelerating), simultaneously rising, tilting backward, and orbiting sideways to settle into a dramatic runway overhead view: entire board extends diagonally into the distance with all 26 cards visible and far edge shaded for depth of field; full board holds static (>0.5s with subtle 1.5% slow push), bottom-left reveals slogan + mono counter (counter increments on each landing). Settle rest phase stabilizes layers across staggered frames—card body lands first, shadow contraction lags ~3f, flight ghost fades last (drag hierarchy adapted from Principle 5; freezing all elements on the exact same frame reads robotic).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| orbit rotation | Camera keyframes expand frame-by-frame via monotonic cubic Hermite spline (continuous velocity at keyframes, zero hitching). Frames 0→30, rotX 48 / rotY −30 / rotZ 9 / zoom 1.9 orbits to rotX 42 / rotY 24 / rotZ −6 / zoom 1.8, persp 1100 | Close-up quartet is indispensable: oblique tilt + perceptible physical height + orbit + contrasting dark material |
| Stack height | STACK_STEP=3px physical thickness × 26 cards → top card z≈78px; jitter px/py uses deterministic formula `(((k*7)%9)−4)*2` ±8px, rotZ ±3° | Jitter must use deterministic pseudo-randomness (reproducible rendering rule); true randomness shakes across renders |
| Graphite tabletop | 4 layered elements: overhead radial light expanding with zoom-out + 104deg specular highlight band + deterministic feTurbulence anisotropic brushed texture tile (baseFrequency 0.0018×0.62, alpha 0.4) + 115deg cool gray gradient; plane extends 4000px outward, soft edges fading into dark void. Page board (screenshot content area x 352–1568 + extended canvas) starts covered by 0.88 dark layer, revealed 34→64f via soft spotlight centered on deck; cards landing outside lit zone are shaded by same formula | Avoid fading out metal to full-screen white paper—dark/light contrast delivers the physical texture of this shot; brushed texture contrast must stay low at 0.5x overhead view to avoid moire |
| Anticipation beat | 10f before first deal cue (26→36): entire deck compresses 48px (~60% stack height) + top card pulls back 30px against launch direction, easing easeOut, releasing instantly at first deal | **Amplitude must exceed visual threshold**: 4px/2px initial draft was imperceptible to human eye, requiring 12x amplification (48/30px) to pass review—verify without stepping frame-by-frame; frame budget taken from tail of orbit, preserving deal phase |
| Deal cadence | Card k cue = 36 + 4k − 0.0792·k(k−1), interval shrinks from 4f down to 0.2f | Uniform intervals feel robotic; linear acceleration is insufficient—requires hard-accelerating level |
| Card volume | 10 real cards + 16 extras = 26 cards; grid expands downward by 5 rows, canvas extends 2036px | Too few cards fails to convey flooding stream; extras land into real extended grid slots, never floating |
| Single card flight | Deal 8f (bezier(0.3,0,0.2,1), z-arc crest +110px sin, scale peak 1.06) + settle 4f (bezier(0.3,0,0.25,1.15) subtle overshoot) + press 0.996→1 bounce 2f | Landing bounce requires bezier with y1>1; settle+press totals 6f ≈ 30% of 8f flight—fast stop paired with ample cushioning (Principle 5 ratio); force identity transform after settling to prevent sub-pixel drift on angled boards |
| Settle drag hierarchy | Layered settling within rest phase: card body locks once press-bounce completes, landing shadow `0 32px→0 2px` contraction lags card body by 2–4f, flight ghost opacity tail drags 3–5f before fading | Adapted from Principle 5 drag hierarchy (root→primary→secondary staggered by 2–4f); 0.5s rest hold holds firm—stagger occurs at head of rest phase, while end of rest is completely locked |
| Motion blur (single card) | 5% path lag blur(6px) ghost trail during flight, opacity 0.25·(1−t) | Ghost trails are cheaper and sufficient compared to full motion blur—maintain this approach per card |
| Motion blur (camera) | Fast camera moves ≥30px/f (such as tracking scroll) wrap shot in `<CameraMotionBlur shutterAngle={180} samples={10}>` from `@remotion/motion-blur`; slice wrapping scope to fast phase via `<Sequence>`, omitting slow close-up phase (<10px/f) | At 30fps camera jumps of 50–70px per frame cause strobing; fast whip streaks are physical camera nature; larger shutterAngle yields longer streaks (>270 blurs heavily), samples adjust to render budget (+1 sample ≈ +1x render time); wrapping entire shot blurs fine 1px brushed metal textures during slow orbit—wrap only fast moves |
| Tracking + Rise | Anchor f62 front-facing board top (zoom 0.8, rotX 22) → f86 board center (zoom 0.56, rotX 38, rotZ −10) → f110 runway overhead (zoom 0.5, rotX 52, rotY −6, rotZ −26, persp 3300, screen shifted right 300px for bottom-left slogan) → f150 zoom 0.508 | Persp must scale up alongside backward tilt (1100→3300) to prevent near plane clipping camera; full board must hold static at end, allowing only subtle push |

## Audio
Anchor whoosh-big on orbit pull-back and initial deals (placed at f308 in template), anchor whoosh-fast on deal acceleration phase (f340/356). Three techniques prevent machine-gun fatigue during rapid landings: alternate two audio samples, decrease volume stepwise, and accelerate intervals alongside animation curve—as deals merge into dense cluster, fade audio into a single swoosh rather than scoring individual cards.

## Known Pitfalls
- Abstract flood animations failed multiple iterations; adopting physical "card dealing" metaphor passed in one round—ground collective motion in physical metaphors before writing code.
- Card textures must use slices from real product pages; mock cards immediately look fake. Extras reuse real card slices arranged with offsets.
- Launching all cards simultaneously reads as an explosion; staggered accelerating cascade is the soul of this shot. If cutting initial orbit, provide an alternative establishing beat for where the deck comes from.
- Anticipation and follow-through derive from Disney's 12 Principles (distilled in pixel2motion skill); anticipation amplitude must exceed visual threshold—verify without stepping frame-by-frame whether energy wind-up is visible.
- Textbook ratio (anticipation = 20–30% of main action) produces tiny pixel displacements under zoomed-out cameras—**calculate pixel displacements before ratios**; promo audiences watch panoramas, not micro close-ups.
- `<Sequence>` base frame reset + CameraMotionBlur internal Freeze causes PageCam sampling frame misalignment (horizontal blur artifacts)—pass absolute `frame` prop to PageCam for shots using absolute frame timing.

## Reference Implementation
demos/ui-entrance/deck-deal-flyin/DeckDealFlyin.tsx (formerly template/src/aifl/live/SceneFlyIn.tsx 0–113 section)
