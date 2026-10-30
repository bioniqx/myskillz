---
name: scroll-brake-moves
summary: Two fast-scroll stops: a long page decelerating precisely onto a target, and the same stop paired with a locking reticle.
use: Changelog, release history, or long list sections: "we ship continuously, and today's entry is the biggest"; use Variant B when the stop requires higher impact
duration: A 4–5s / B 5s
energy: High start, medium resolution (speed-contrast profile)
tags: rhythm
---

## Intention
Linear changelog video grammar: an entire year's release log rushes past as a long ribbon at high speed (smearing into a colored band), then exponentially decelerates with razor precision onto the current release entry, which lifts off the page surface, highlights, and dims surrounding items—density says "we never stop shipping," while the abrupt brake says "today's release is the monumental one."
Variant B is a compound mutation: on the **exact same frame** the scroll brakes, four L-brackets fly in from offscreen and clamp onto the target entry—the thud of the brake and the click of the clamp resonate on the exact same frame (composite requirement: bracket takeoff frame must match the list's initial halt frame; offsetting them degrades it into two uncoordinated effects).

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A changelog-scroll-brake | translateY sweeps ~2400px (cubic-bezier(.45, 0, .06, 1): full speed reached in ~5f followed by an extended exponential decay, 50f total); vertical directional blur driven by frame displacement differential (x0.32, capped at 30px, zeroing automatically when stopped); target row lifts with scale 1.03 + shadow + 2px accent border, other rows dim to opacity 0.38 | Baseline recipe for changelog segments |
| B brake-reticle-lock | Three-stage scroll: sin-in acceleration -> cubic-out aggressive deceleration overshooting +30px -> rebound to rest; vertical directional blur = v * 0.15 capped at 32px; brackets fly in from +/-620 / +/-320 offscreen via Easing.back(2.4) to clamp; highlight completes in 6f, badge pops with back(2.6) | High-impact highlight moments requiring heavier punch at landing |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Deceleration curve | A fast launch + long-tail deceleration (bezier .45, 0, .06, 1); B adds "+30px overshoot rebound" | Uniform scrolling feels like a stock ticker; Variant B overshoot rebound is the source of the physical thud |
| Blur driver | Inter-frame displacement differential `|p(f) - p(f-1)|` * factor | Hand-keying blur frames inevitably desyncs from speed; differential method is frame-deterministic (pattern formalized in assets/lib/helpers/motion.ts velocityAt) |
| Row height cadence | Staggered 72 / 94 / 116px tiers | Uniform row heights smear into a monotonous ribbon at high speed |
| Stop position | Target row centers vertically in frame | Landing off-center looks like an error |
| B Resonance frame | Bracket takeoff frame = list initial halt frame (strictly same frame) | Composite requirement; splitting by >=2f dissolves the cohesion |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Division of labor with timeline-travel: this card is a vertical list braking on "the latest"; that card is a horizontal timeline journey reviewing "history"—if using both in one video, space them apart and limit each to <=1 occurrence.
- Entries during the high-speed transit phase do not need readable copy—they blur into ribbons anyway, so grayscale placeholders suffice; the target entry at rest must contain publication-grade real content (Q10).
- Dimming non-target rows to 0.38 after landing is a compositional move: do not drop to 0, which destroys the surrounding context.
- Audio: low-frequency riser swells during high-speed transit, braking on a heavy impact; Variant B layers a mechanical click on the clamping frame (same frame, distinct audio voice).

## Reference Implementation
demos/data/scroll-brake-moves/
(BrakeReticleLock.tsx / ChangelogScrollBrake.tsx)
