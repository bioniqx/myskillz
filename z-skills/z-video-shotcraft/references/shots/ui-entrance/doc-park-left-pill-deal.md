---
name: doc-park-left-pill-deal
summary: The source document slides left until only a sliver remains and keeps scrolling slowly, while three outlined pills are dealt one at a time, each followed by a caption that darkens word by word.
use: Voiceover-driven sections presenting analytical conclusions one by one; core explanatory shot for document understanding, recommendation reasoning, or review critique products.
duration: ~5.8s (174f @ 30fps)
energy: Low (Deliberate dealing cadence without peaks; maintains visual vitality via continuous background auto-scroll)
---

## Intention
Conclusions must be delivered one by one for audiences to absorb them. But fading out the source document leaves conclusions floating in a vacuum—viewers lose track of where the findings originate. This card's solution is **keeping the source document in frame**: it parks against the left edge with only a sliver exposed, scrolling slowly (signaling it is actively being parsed), while each conclusion pill on the right branches directly from this source. The dealing cadence is deliberately measured to provide ample time for the voiceover to complete each sentence.

## Motion Core
- Parking (not fading): `seg(t, 0.06, 0.24, E.inOutCubic)` drives `translateX(0→-55%) scale(1→0.92)`, with `transform-origin: 0% 50%` anchoring scale to the left edge so document shrinking never leaves the left screen margin—ultimately exposing ~35% width.
- Continuous auto-scroll: `translateY(-t * 120)` runs at constant velocity (≈0.7px/f), with content extending >140px beyond container. Legacy modulo approach `-(t*3 % 1) * 40` caused noticeable 40px snap-backs every 1/3 of shot duration on non-periodic content, and is deprecated.
- Slow dealing: three pill cards anchor launch cues hardcoded at `T0 = [0.26, 0.48, 0.70]`—spacing 0.22 (≈38f / 1.27s), matching the spoken length of a short voiceover sentence rather than a rapid UI stagger.
- Dual parallel curves per pill: `o = seg(t, f, f+0.035, E.outQuad)` controls opacity (snappy, ~6f), `b = seg(t, f, f+0.062, E.outBack)` governs `translateY(14→0) scale(0.94→1)` (deliberate, ~11f with overshoot)—seeing the element first before it settles delivers a tangible "caught and placed" feel compared to single-curve fades.
- Four-phase caption choreography: start `cs = f+0.05` (~3 frames after pill settles), `show` rapidly reveals over a 0.02 window, `inn` darkens word by word across `(ce-cs)*0.7`, `ce` marks next pill start minus 0.03 (final pill ce=0.98), `out` fades over `ce-0.05→ce`—each caption clears before the next pill arrives, keeping exactly one active sentence on screen.
- Pills finalize into a static vertical list (`top = 54 + k*48`), remaining permanently in view once settled to establish the completed list of conclusions.
- Source linkage: once each pill settles, corresponding source text in the document highlights left-to-right (f+0.06→0.13), with an accent connector line drawing from line end to pill left edge (f+0.04→0.11 draw-on), fading out as caption exits.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Deal cue points | `T0 = [0.26, 0.48, 0.70]`, interval 0.22 (≈38f) | Interval matches voiceover phrase length; below 0.12 word-by-word darkening cannot finish, reading as a flash before disappearing |
| Parking window | 0.06→0.24 (inOutCubic) | Must settle before first pill (0.26); overlap creates visual confusion of document sliding while pills are already dealing |
| Parking extent | `translateX -55%` + `scale 0.92`, exposing ~35% | Exposing too little (<25%) reduces document to decoration, losing source semantics; exposing too much crowds out 172px wide pills |
| Pill opacity window | 0.035 (≈6f, outQuad) | Intentionally shorter than position window—solidifies before settling; equal durations read as generic fade-ins |
| Pill position window | 0.062 (≈11f, outBack), y 14→0, scale 0.94→1 | outBack overshoot provides physical landing bounce; switching to outCubic feels floaty |
| Caption delay | `cs = f + 0.05` (≈9f) | Caption starts only after pill settles (0.062); starting early causes text to precede conclusion |
| Caption darkening span | `(ce-cs)*0.7` | Accounts for 70% of phrase visibility, leaving remaining 30% for static reading; 1.0 fades caption immediately upon finish |
| Auto-scroll | `-t × 120px` continuous constant | Over 5.8s ≈ 0.7px/f, subtly signaling active reading; >3px/f steals focus as a content tour |

## Known Pitfalls
- Auto-scroll uses continuous displacement rather than modulo looping (modulo only works without jumps on strictly periodic content); when adjusting duration or distance, ensure document length exceeds container by full travel distance to avoid empty space.
- Final caption `ce = 0.98` fades over 0.93→0.98, leaving three pills without captions on the final frame. To hold final caption until end, set `ce` > 1 and remove `out`.
- Pill layout is hardcoded to `left:214px, top:54+k*48` at 172px width, matched with ~87px exposed parked document on a 480px canvas. Tweaking parking displacement requires recalculating PX positions to prevent overlap.
- Pill copy (demo references video-shotcraft promo recommendations: Crash Zoom / Deck Deal / Logo Sting) and captions are schematic; text length directly influences reading speed of word darkening—recalibrate `inn` span when applying production copy.
- Pill count is fixed at 3 (length of `T0`). Expanding to 4 exceeds timing budget: final pill start exceeds 0.9, leaving insufficient time for caption; for >3 items, shorten phrases rather than cramming cards.
- Caption `ce` depends on `T0[k+1]`; shifting any card's cue alters preceding caption display duration—this tight coupling is intentional (captions fill up to next card), but must be considered during tuning.

## Reference Implementation
demos/ui-entrance/doc-park-left-pill-deal/
(DocParkLeftPillDeal.tsx)
