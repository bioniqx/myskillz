---
name: fui-hud-moves
summary: A reticle that assembles itself around a target and locks on.
use: Calling attention to any target element (replacing red arrows and circles without freezing the frame)
duration: 2–3s (demo 90f)
energy: Medium-high (lock-on frame serves as impact beat)
tags: ui-entrance
---

## Intention
A versatile motif borrowed from sci-fi fictional UI (Jarvis / Territory): in-motion target acquisition. Four L-shaped corner brackets rush in from off-screen, overshoot and rebound, then snap firmly into place around the target element accompanied by a popping label—division of labor with freeze-annotate: that card freezes the screen for annotations, whereas this card singles out targets mid-flow.

## Variants
| Variant | Method | Use Case |
|---------|--------|----------|
| A reticle-lock-on | Four L-brackets = four mirrored instances of the same rectangle pair; fly-in (10f out-cubic) decoupled from convergence (2.2x -> 0.94x -> 1x overshoot rebound); lock-on frame triggers slight target flash + label back-pop | Target highlight; landing on heavy audio beats |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Fly-in travel | Rush in from off-screen >=1000px | Short travel reads as "brackets appearing" rather than "swooping in" |
| Overshoot | Compress past target to 0.94x before rebounding to 1x | Without overshoot there is no crisp mechanical snap |
| Lock-on frame | Target white overlay flash 0.55 -> resting 0.28 + label pops on same frame | Misaligning the highlight flash and label breaks cohesion |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Use <=2 times per video: consecutive uses read like generic sci-fi templates; lock-on targets must differ each time.
- Audio: crisp mechanical click on the lock-on frame (mechanical tactile click rather than arcade game UI blip, staying within S1 boundaries).

## Reference Implementation
demos/effects/fui-hud-moves/
(ReticleLockOn.tsx)
