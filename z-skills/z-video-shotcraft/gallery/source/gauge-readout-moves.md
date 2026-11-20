---
name: gauge-readout-moves
summary: Two instrument reads: a full-range needle self-test and a moving scale that races beneath a fixed pointer.
use: Dashboard opening ceremonies or performance metric reveals; Variant A for multi-dial startup feeling, Variant B for large single-metric leaps
duration: A 140f (4.7s) / B 150f (5s)
energy: Medium-high (mechanical ceremony)
---

## Intention
Turning "reporting a number" into the physical behavior of an instrument: Variant A is an automotive ignition self-test—three side-by-side dials on a card sweep their needles across the full 270 deg arc in a swift whoosh, lighting swept tick marks in sequence, then spring back to settle on authentic values in a staggered wave; values beneath each dial pop on the settle frame, presenting the full range before reporting the metric to create an opening statement of power.
Variant B uses aircraft airspeed tape syntax—the readout window and indicator needle remain pinned to the screen centerline, while a full-height scale tape scrolls from behind the window, first creeping against an old upper limit, breaking through to sprint (peaking at ~100px/f), and concluding with a spring-braked rebound: "the world moves, the needle stays," converting numeric magnitude into tangible displacement distance.

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A needle-sweep-selftest | Dial face and outer ring illuminate -> needle sweeps full arc over 12f ease-out (ticks light in sequence, falling back within 24f) -> spring rebound with ~8 deg oscillation settles on authentic value; three dials staggered by 4f; values pop with overshoot beneath dials on the settle frame as metric titles fade in; status pill switches from "Running self-test..." to "Ready to render" | Dashboard opening / system readiness ceremony |
| B tape-scroll-fixed-pointer | Full-height tape translates: slow creep against old limit line -> limit line snaps -> 5f anticipation recoil -> 22f sprint (peaking at ~100px/f, vertical motion blur) -> spring brake with overshoot oscillation settles on target, with new limit indicator docking at needle; window readout updates in sync | Massive single-metric leap (performance doubling / quota expansion) |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Sweep amplitude | Full 270 deg scale, reversing immediately at top | Sweeping only to true value lacks self-test ceremony; full sweep before return establishes "range first"; ticks swept on outbound path (including redline) illuminate in sequence |
| A Overshoot | ~8 deg oscillation on rebound (spring damping reverse-calculated from travel) | Without overshoot it reads as a digital readout; overshoot provides mechanical needle mass |
| A Stagger | 4f per dial (left -> center -> right) | Simultaneous sweep looks like copy-paste; staggered sweep forms an organic wave |
| B Sprint velocity | 5px/unit, peaking at ~100px/f (large leap segment) | Too slow reads as a uniform crawl, breaking the "world moves" effect; longer tape lengths require vertical motion blur |
| B Braking | Spring overshoot (surges past mark before rebounding to stop) | The rebound in the original spec is the physical source of the heavy thud; stopping abruptly wastes the mechanical momentum |
| Pure static hold | Fully locked for >=30f after stopping (A settles final dial at ~66f, B locks constant at 110f) | Needle instruments suffer most from lingering tail drift |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- ring-close-overfill in the same batch remains pending rework without commentary—circular progress recipes await redesign; do not rush to incorporate as a third variant.
- Variant A dials are custom-drawn SVG (arc ticks + needle); when embedding in real dashboards, prioritize close-ups of genuine in-product gauge components rather than fabricating from scratch.
- Audio: Variant A gets a whoosh on sweep + crisp tick on settle (staggered for each dial); Variant B gets low-frequency rolling rumble during sprint and a solid mechanical thud on brake.

## Reference Implementation
demos/data/gauge-readout-moves/
(NeedleSweepSelftest.tsx / TapeScrollFixedPointer.tsx)
