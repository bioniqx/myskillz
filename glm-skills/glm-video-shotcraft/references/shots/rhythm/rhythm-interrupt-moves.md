---
name: rhythm-interrupt-moves
summary: Stepped punch-in jump cuts that break cadence on the same frame.
use: Using "broken continuity" itself as a rhythm engine: stuttered punch-ins (A); complementary to beat-cut-moves (cut placement)
duration: A 135f ≈ 4.5s
energy: A Medium
---

## Intention
Rhythm cards in the library typically govern "how to cut, and how densely to cut"; this card governs **how to break cadence**—viewers anticipate continuity, and breaking that expectation becomes the expression: Variant A breaks space—three zero-tween magnification jumps within the same framing (1x -> 1.6x -> 2.6x), channeling the staccato cadence of Godard jump cuts to deliver the commanding instruction of "look here, closer, that's it" far more forcefully than a continuous camera push. Ideal for forcing attention onto critical metrics.

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A jump-cut-punch-in | transform-origin anchored to target center, three-step scale magnification (zero tweening), 2f darkening pulse on each jump acting as tick | Progressively zeroing in on key metrics; documentary-style scrutiny |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Step jumps | 1.0->1.6->2.6, holding >=35f per step | Step deltas <1.5x read like frame jitter |
| A tick | 2f brightness 0.92 canvas pulse starting on jump frame | Jump cuts without tick pulses look like dropped frames |
| Finale | Final step holds static for >=45f | Cadence-breaking techniques demand generous post-event holds |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Manipulates the "timeline" alongside speed-ramp-freeze; only one timeline manipulator may exist within a single shot.
- All three framing steps must share the exact same `transform-origin` (anchored dead-center on the target)—reframing between steps creates three separate shots rather than jump cuts.
- Strong audio dependency: audible tick on each jump cut (sound-design §4.5).

## Reference Implementation
demos/rhythm/rhythm-interrupt-moves/
(JumpCutPunchIn.tsx)
