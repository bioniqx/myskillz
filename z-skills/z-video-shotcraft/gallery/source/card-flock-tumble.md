---
name: card-flock-tumble
summary: Three UI cards tumble in 3D from edge-on to a stepped formation, keep slowly rotating, then collapse inward and burst into a smoke ring under a giant word.
use: Climax energy segments (explosive transition from feature UI cluster to brand slogan); neon/aurora dark-stage aesthetics; segments summarizing "multi-page capabilities" into a singular thesis.
duration: Tumble ~1.5s + slow rotation showcase ~0.3s + inward collapse 0.3s + smoke ring + giant word ~2s; entire sequence 4.5s.
energy: Extremely high (reserved for full-video energy peaks)
---

## Intention
Three UI cards tumble and align in 3D space like dealt playing cards, holding a brief hero pose before instantly collapsing into the center, bursting into an expanding smoke ring as a massive brand title punches through the ring—"capability showcase → energy collapse → slogan explosion" in one continuous, breathless breath. Three non-negotiables define execution: **silkiness** (edge-on → tumble → stepped formation driven by a single continuous Catmull-Rom spline, as piecewise linear interpolation produces jarring velocity steps), **no stopping** (maintaining low-angular-velocity slow rotation upon landing until inward collapse; static holds were explicitly rejected in review: "do not stop, keep rotating"—climax sequences allow no frozen frames), and **tack-sharp clarity throughout** (motion blur and depth-of-field blur completely removed; rejected in review: "do not add blur effects").

## Motion Core
- **Tumble**: Each of the three cards follows a Catmull-Rom spline through k0 (near 90° razor edge-on) → k1 (mid-flight tumble) → k2 (stepped formation landing), driven by `Easing.out(cubic)` across ~44f.
- **Stepped Slow Rotation**: Idle drift with ry +0.34°/f, rx -0.1°/f, rz +0.05°/f (with a 14f quadratic ease-in to prevent velocity kinks at spline handoff), persisting without pause until the moment of collapse.
- **Inward Collapse**: 10f `Easing.in(quad)` directly accelerates inward from the rotating posture, shrinking into the center while keeping opacity at 100% for the first 60% of travel (the "implosion" motion must remain clearly legible).
- **Flash Core**: On the exact frame of collapse convergence (70f), a white-hot central core detonates with a 12% full-screen micro-exposure flash, decaying exponentially over 6f. The ring blooms directly out of the flash core—filling the potential energy vacuum between collapse and title slam; uses pure radial light only, without stroked geometric rings or particles (both explicitly struck down in review precedents).
- **Smoke Ring**: A **single** ring (multiple concentric rings rejected), driven by three `feTurbulence` displacement maps (feathery edges / bright patches / dark clumps) + a top-to-bottom peach → pink → purple gradient (aurora spectrum) with screen blend mode—ragged wisps, organic light-dark mottling, decelerating radial expansion with prolonged persistence, zero surface water sheen at center, and zero particle debris.
- **Giant Word Slam**: Slams in just 4f after collapse (74f)—a 14f snappy entry scaling down from 1.22 to 1 with letter-spacing contracting from +0.06em to −0.025em, followed by an ultra-slow, continuous gentle expansion; solid white-hot core → soft purple vertical gradient fill + dual-layer pink/purple glow (flashing brighter on touchdown before easing back); 282px italic bold spanning ~80% of screen width; inside the ring center, an eyebrow lockup above (demo: video-shotcraft stroked logo + lowercase wordmark) and a 44px slogan below (concise brand tagline) rise with staggered timing, concluding on a launch-poster lockup frame.
- **Background**: Two rows of 300px monochromatic soft-purple outlined typographic walls slowly drifting in opposing directions + an aurora hero back-glow cradling the card cluster; during collapse, the text walls scale inward and fade out in unison with the implosion. The card cluster, collapse focal point, ring center, and giant word share a unified anchor (screen center offset downward by 30px).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| 3-card spacing / size | Substantial overlap in a stepped cascade, scale 1.6–1.74 | Escalated across two review rounds: "closer together, even larger"—the cascade must read as a cohesive unit, not three loose cards |
| Settle slow rotation | ry ~0.34°/f continuous | **Static holds forbidden** (review ruling); >1°/f reads as still settling |
| Collapse duration | 10f ease-in | 22f version rejected as sluggish; early opacity fade makes implosion illegible (rework precedent) |
| Smoke ring | Single ring, turbulent feathery wisps, ultra-slow decay | Multiple rings rejected; smooth neon hoops or particle versions rejected—calibrated frame-by-frame against dense reference footage for turbulent texture |
| Blur | Zero blur throughout | Blur during tumble or collapse was rejected |
| Spline | Single unified Catmull-Rom | Piecewise lerp introduces velocity discontinuities; "silky smooth" was the explicit review mandate |
| Giant word entrance | 4f after collapse, 14f snappy 1.22 → 1 + letter-spacing pinch | Original waited 14f to spawn text, leaving an empty dark screen with just the small ring, draining climax momentum; slow zoom (0.7 → 1 / 34f) reads as a gentle fade rather than a heavy slam |
| Flash core | Radial white-hot core + 12% full-screen micro-exposure, 6f decay | Without it, the ring seems to appear out of thin air; adding stroked neon borders immediately looks cheap (same precedent as smoke ring) |

## Known Pitfalls
- The demo was calibrated and passed on grayscale/placeholder assets—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- Smoke ring texture precedent: clean geometric rings (stroked circles / concentric shockwaves) failed three review rounds; the final feTurbulence turbulent wisp version was tuned frame-by-frame against source footage ("must look identical"); the remaining delta is that the noise field itself is static (rotating and scaling as a whole) rather than rolling with per-frame turbulence, yielding slightly less fluid churning upon close inspection.
- The smoke ring is the shockwave residue of energy collapse, not a celebratory confetti pop—never add particle fireworks.

## Reference Implementation
demos/transition/card-flock-tumble/
(CardFlockTumble.tsx)
Original source: clickup-30.mp4
