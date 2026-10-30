---
name: autolayout-gap-dial
summary: A gap value dial pushes a row of blocks apart in real time while badge digits tick, then everything springs back into place.
use: Feature showcase shots for design tools/low-code products highlighting "change a number, UI reacts in real time"; category language packaging using design tool semantics
duration: ~5s (150f: marquee box-select entrance + prep pull-back 10f + expansion 34f + breath hold 20f + spring rebound + settle hold)
energy: Medium (tool rationality style; satisfaction lies in locked synchronization between numbers and displacement)
---

## Intention
"Parameters change, UI responds" is the core promise of design tools, but it is typically filmed as a before-and-after cut: "click panel -> switch result," discarding causality. This shot captures causality as a continuous take: the gap badge digits tick step-by-step, the linked blocks are pushed apart in the **same frame**, and measurement lines stretch in real time—the numbers are the reins, the layout is the horse. The marquee outline + 8 handles + gap annotations speak the native language of design tools, allowing viewers to immediately recognize "adjusting parameters inside a tool." The return journey deliberately uses an underdamped spring overshoot (compressing tighter than the starting point before restabilizing), turning "return to position" into an elastic resolution. Division of labor with type-and-filter: that card handles retrieval causality ("input content -> list converges"), while this card handles parameter causality ("dial value -> geometric rearrangement").

## Motion Core
- **One gap parameter controls everything**: Block positions are recalculated from gap (the entire row stays centered), measurement line width = gap, badge pinned to gap center, and top large readout + dial scale ruler—all elements derive from the same numerical value. Locked synchronization is the entire persuasive power of this shot.
- Parameter curve: Preparation pull-back 12->6 (10f swift, "pull back before lunging forward"); outbound 6->104 over 34f swift (asymmetric in-out: slightly fast start, very soft landing); breath hold 20f; return spring(damping 9, stiffness 80, mass 1.1) deliberately overshoots below the starting point before restabilizing (overshoot segment compressed by x0.45: 104->~7 then back to 12, gap never goes negative).
- Readout as the hero: Top 196px thin tabular digits + px unit + 760px dial scale ruler (ticks roll horizontally across center gold needle with gap); readout transitions from white to measurement gold during dial movement (with ~6f warm residual), fading back to white after stabilizing; numerical values step by 2; stepping scale pulse 1+0.06*|sin| * speed threshold.
- Navigation blocks apply horizontal motion blur based on individual speed (block speed = (i-2)*dgap/dt, outermost blocks have the longest trail), zero when static.
- Marquee outline springs inwards from 26px outer margin, 8 handles pop out staggered at 1.2f, real-time total row dimensions displayed alongside layer name; gap annotations = dashed extension lines x2 + measurement line with end barbs + follower badge, rising staggered.
- Demo art direction: Graphite dark stage, dual-color semantics of selection white + measurement gold (only the manipulated numbers carry color in the frame); camera slowly pushes in 2.5% across the entire shot.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| gap amplitude | 12->104px (original video 20->24, expanded per demo adjudication) | Original amplitude almost imperceptible to the naked eye—perceptibility benchmark: if subtle, amplify into extreme version; in production use at least 4-5x travel |
| Anticipation | 12->6, 10f swift | Pull back before release builds momentum for main action; pull-back >30% reads as value jitter |
| Outbound duration | 34f swift | Faster reads as twitching; slower than 60f loosens binding between digit ticking and displacement |
| Breath hold | 20f | Lets viewers clearly read the "loosest" frame; <12f peak cannot be registered |
| Return spring | damping 9 -> overshoots below start then settles (overshoot x0.45, tightest ~7px) | Overshoot is the tactile source of "release rebound"; damping >=13 landing directly is a missed opportunity |
| Digit stepping | Step 2 + stepping scale pulse 0.06 * speed threshold | Stepping by 1 is too granular, reading like a millisecond stopwatch; stepping gives tactile "dial click" granularity |
| Motion blur | Horizontal stdDeviation = min(9, |block speed|*0.5) | Only appears during dial phase; persistent blur makes block text unreadable |
| Annotation geometry | Extension line 58px, measurement line pinned to block bottom +74px, badge pinned to gap center | Annotations must recalculate in real time with gap—any lag breaks the illusion |
| Block width | Unequal widths (252/206/278/268/220, height 120) | Equal widths read like a schematic diagram; unequal widths feel like real navigation |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Numbers and displacement must share the same source and frame: badge values and block coordinates derive from the exact same gap; even a 1f desync breaks trust in "parameter-driven."
- In demo, top large readout + dial scale ruler share the same source/frame as the layout; in production, if a real tool inspector panel exists on screen, omit the large readout to avoid redundant reporting.
- Family expansion: gap is just one dimension; radius/padding/rotation can swap parameters with identical syntax—but only tweak one parameter per shot; tweaking two or more reads as chaotic tampering.
- Marquee outline + handles borrow "design tool semantics" (native to Figma/Framer); use with caution for audiences outside design tools—viewers who don't understand selection boxes will only see blocks shifting around.
- Audio: very light tick on each badge step (dial click), pop on rebound settle; tick density matches stepping cadence.

## Reference Implementation
demos/interaction/autolayout-gap-dial/
(AutolayoutGapDial.tsx)
Source: framer-ai 4.5–5.5s
