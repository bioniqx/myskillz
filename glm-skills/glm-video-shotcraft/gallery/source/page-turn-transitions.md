---
name: page-turn-transitions
summary: A full-page transition where the old page splits open like double doors to reveal the new one.
use: Chapter-level page transitions: "turning the page" ritual between two major narrative movements; distinct division of labor from the shot-transitions family (camera handoffs)—where that family represents "the drone moving across," this represents "the page itself being a physical slab."
duration: Single variant 150f (prior state establishment 30–40f + transition 24–40f + follow-through and settle ≥70f), approx. 5.0s.
energy: Medium-high
---

## Intention
The three shot-transitions variants and transition-travel/hidden-cut all treat the page as a "scene"—the camera moves between environments. This card treats the page as a **physical entity**: it possesses thickness, mass, and can split apart. The physical slab metaphor imparts a heavier ceremonial weight, tailored for chapter-level page transitions (concluding Feature A → introducing Feature B) rather than shot-level continuity handoffs. The double-door barn split represents "the old yielding to the new"—the outgoing page tears open down the center and slides apart, while the incoming page ascends from beneath, suggesting supersession and replacement.

## Variant Selection
| Variant | Method | Application |
|---|---|---|
| A barn-door-split | The outgoing page is split across two 960px overflow containers aligned seamlessly, which accelerate outward simultaneously via ease-in (applying horizontal motion blur proportional to velocity); the tear reveals incoming light—the 10px inner bevel edge catches illumination, the door face adjacent to the seam is warmed by light bleed, and the incoming page rises from scale 1.08 → 1 with an overexposure flare; the demo illustrates video-shotcraft version iteration: "Shotcraft 3" cool-gray legacy page → "Shotcraft 4" Ember launch page (with engraved lens emblem in header), rolling metrics from old values to new values (indicative data) | Generational succession: before/after redesigns, Option A → Option B, major version releases |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Anticipation | A hairline highlight (with bloom) draws vertically from center (20–30f); at 30–40f, the seam eases open 0 → 16px into a light slit | Splitting without anticipation leaves the audience unaware of where the fault line lies; hard toggle flash lines look like render glitches |
| Slide-out | Each translates X ∓1000px / 24f, bezier(0.42, 0, 0.8, 0.25) accelerating | Ease-out slide feels like being pushed away; ease-in conveys yielding/parting; quartic-in is too abrupt, reading as "freeze → vanish on final frame" |
| Incoming rise | scale 1.08 → 1 (snappy 36f, launching 2f after doors), overexposure flare decays across ~30f as doors recede; outgoing and incoming pages share identical grid layout | Mismatched layouts fail to convey "replacement / supersession" |
| Tear edge | 10px illuminated inner bevel (bright → accent → dark) + 620px light bleed on door face (screen mode); doors do not cast shadows onto incoming page | Omitting edge highlights reduces the split to a generic left/right wipe; casting shadows into the seam muddies the incoming light |
| Settle | Secondary actions upon landing (metric count-up / checklist tick) + hold ≥30f; camera performs an ultra-slow 1.5–2% push-in during hold | R1 |

## Known Pitfalls
- The demo was calibrated on custom pages designed for the camera—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- The single-technique-per-seam rule applies just as in shot-transitions; physical slab transitions are significantly heavier than camera handoffs, **≤2 times per full video**; using slab transitions on consecutive seams feels like flipping through a clunky slide deck.
- Both halves must be **seamlessly aligned** (right half inner layer translateX(-960px))—any visible seam during the static hold breaks the illusion; when using real screenshots, watch for odd-pixel width rounding.
- Both outgoing and incoming pages require ≥30f static holds before and after the transition—if both ends are animated, the physical slab sensation is drowned in motion.

## Reference Implementation
demos/transition/page-turn-transitions/
(BarnDoorSplit.tsx)
