---
name: integration-hub-map
summary: A page flips 180 degrees into an integration hub where five app icons pop in together and rainbow light tubes connect with pulses flowing through them.
use: Integration and ecosystem showcase sections (one product connecting everything); version overhaul narratives (legacy page flipping to new page); dark neon aesthetic feature climaxes.
duration: Anticipation ~0.5s + fast flip ~1.2s + simultaneous icons pop -> light tubes connect across two beats ~0.7s + pulse breathing ≥1.5s; full segment 4.5–5s
energy: Medium-High (Flip is the explosive peak, pulse flow is the lingering resonance)
tags: effects
---

## Intention
Flipping a page represents "entering a new era": the old document page rotates a full 180° to reveal the new hub page—it must be a complete flip rather than an angle tilt, executing as a **fast flip with a deceleration tail** in a single continuous movement without mid-way stalls (users interpret "uniform" as unbroken momentum rather than literal linear timing; stopping at the 90° edge was rejected). The edge profile only flashes briefly (1–3f pulse; prolonged bloom plates were rejected). Integration executes across **two beats**: five icons pop in on the exact same frame (beat one) → five light tubes draw and connect simultaneously on the same frame (beat two)—synchronicity is essential to convey "ecosystem ready at once"; staggered connections read like piecemeal negotiations (rejected in two review rounds). Once connected, bright pulses circulate along light tubes from icons toward the central hub; continuous "throughput" gives life to the final state.

## Motion Core
- Page flip: rotateY 0→180°, 35f, Easing.out(cubic) (first 41% of time completes 80% of rotation, tail provides extended deceleration landing), dual-sided card (front: legacy page / back: new page).
- Edge flash: at ~90° mark, 2f pulse bloom (0→1→0.25→0, returning to zero within 4f).
- Two-beat connection: five icons tIcon pop simultaneously (flip landing +3f); +10f five light tubes tPipe start drawing simultaneously, growing to full brightness in 9f.
- Flow pulses: light tube dash bright spots loop from icons toward hub (speed ~4.6px/f, phases staggered per pipe); central hub page breathes gently once all connections lock.
- Background: dark purple ambient texture + floating neon rectangles framing the stage.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Flip duration | 35f (previous 70f rejected as "make it 2x faster") | <24f fails to read dual faces; tail deceleration takes ~60% of time for final 20% of angle |
| Flip curve | ease-out monotonic without stalls | Mid-edge pauses or multi-stage flips rejected; strict linear starts/stops feel robotic—use fast flip with gentle landing |
| Edge flash | 2f pulse, zeroed in 4f | Extended bloom plate rejected as "just a single flash is enough" |
| Connection cadence | Two-beat: icons on same frame → +10f light tubes on same frame | Staggered connections rejected twice as "appear together, then connect together"; inter-beat interval <6f reads as single beat |
| Light tube growth | 9f simultaneous length | 18f version felt slow; light tubes vary in length but arrive on the same frame (normalized by individual len) |
| Flow pulses | ~4.6px/f loop, staggered phases | Static connection lines lack "feeling of throughput"; shared phases read as flickering |

## Known Pitfalls
- Demo calibrated on grayscale placeholder assets—parameters serve as calibration baseline, not final production specs; verify against real assets in production.
- Chronological review history on record: staggered connection ×2 rejected → synchronous pipes with staggered icons rejected → two-beat rule passed. Synchronicity is this card's rhythmic signature.
- Division with glow-flyline-moves: that card focuses on lighting drama of the arcs themselves; this card centers on the narrative architecture of flip + two-beat connection + throughput, with tubes acting merely as components.
- Division with canvas-materialize-moves: that card focuses on canvas element materialization; this card's core is the generational upgrade metaphor of "flipping old into new."
- Dual-sided card implementation: horizontal/vertical lines with bbox=0 invalidate SVG filters and gradients (causing lines to vanish); define tube gradients independently per pipe using userSpaceOnUse.

## Reference Implementation
demos/ui-entrance/integration-hub-map/
(IntegrationHubMap.tsx)
Source clip: clickup-30.mp4
