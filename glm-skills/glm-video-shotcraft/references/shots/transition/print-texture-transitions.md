---
name: print-texture-transitions
summary: A print-based reveal: ink bleeding outward from a drop point to consume the old scene.
use: Paper-and-ink aesthetic choices for scene change seams; the third family alongside camera handoffs and travel moves—"medium development" transitions.
duration: 4–4.5s (bleed phase 55–80f + static settle ≥30f).
energy: Medium (gradual manifestation, no jarring impact beat).
---

## Intention
Existing transition grammar already includes camera handoffs (the three shot-transitions variants) and spatial travel (transition-travel), both rooted in spatial/optical metaphors. This technique introduces a third family: **medium metaphors**—the new visual is not "arriving" through motion, but is being "printed and dyed" into reality. It taps directly into the physical imagination of the library's paper-and-ink aesthetic: an ink drop landing on rice paper, bleeding outward with feathery tendrils to consume the prior scene in an organic, writerly fashion. For films with an inherent paper/ink sensibility, this serves as an organic alternative to light-leak-burn (accent-color light leaks) within the "medium-based" seam category.

## Variant Selection
| Variant | Method | Application |
|---|---|---|
| A ink-bleed-reveal | The incoming page bleeds outward from an initial ink drop point through an organic circular mask with feathery tendrils, consuming the outgoing scene at an uneven, natural pace | Outgoing → incoming scene replacement; writerly, narrative brand tones |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Feathery edge | SVG mask white circle with `feTurbulence(fractalNoise, baseFrequency 0.02, octaves 3, fixed seed)` + `feDisplacementMap scale 60 → 160 ramping per frame` | The filter distorts only the mask geometry while interior content remains sharp; seed must be hardcoded for deterministic renders |
| Bleed expansion | Radius [20, 98f] → [0, 1450px] `Easing.out(quad)`, multiplied by `1 + 0.08·sin(0.32f)·env` non-uniform speed perturbation (envelope decays to 0 over final 20f) | A constant-speed circular expansion reads like a generic iris wipe—the rhythmic perturbation embodies the organic temperament of ink |
| Ink edge | Dual mask circles leading the incoming scene by 20–42px: outer edge 0.42 opacity + 3.2px blur, inner core 0.86 + 1px blur, plus an outer +110px heavy-blur wet halo (0.12); a small initial ink drop lands at 14–22f | Omitting the ink rim reads as a standard circular wipe; an overly wide or opaque rim resembles burning paper holes |
| Development | Incoming scene scales from 1.035 → 1 within the mask (20–100f ease-out), returning precisely to 1 before mask removal | Failing to settle at 1 causes a visible snap on the unmasking frame |
| Unmask settle | Once fully bled (frame ~100), strip the SVG mask entirely and display the raw incoming scene | feTurbulence carries subpixel jitter; failing to strip the mask prevents a true static hold at the tail (production render ruling) |
| Settle | True static hold ≥30f once the incoming scene is seated | R1 |

## Known Pitfalls
- The demo was calibrated and passed on grayscale/placeholder assets—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- The single-technique-per-seam rule applies just as in shot-transitions: medium transitions must not be layered with white flashes or screen shakes; medium-style transitions (this card and light-leak-burn) should total **≤2 times per full video**—any more makes the video feel like a commercial for a print shop.
- Mid-bleed, fragments of the outgoing scene briefly show through noise gaps—this reads as organic ink texture and is acceptable, but if the outgoing scene contains high-salience elements like human faces or primary brand logos, it reads as a visual glitch; avoid using over such subjects.
- Slow transition (55–80f action window); never use during high-tempo, rapid-fire montages—use shot-transitions Variant B (whip pan) instead for high tempo.

## Reference Implementation
demos/transition/print-texture-transitions/
(InkBleedReveal.tsx)
