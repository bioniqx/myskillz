---
name: card-flip-reveal
summary: Feature cards rotate 180 degrees around the Y axis, flash at the edge, and reveal a large result on the back.
use: Paired "feature → outcome" narratives: a row of feature cards flipping one by one to reveal their respective metrics/conclusions; element-level transition card.
duration: Total 150f (~5s, including hold); per card: 4f prep + 16f flip + ~10f spring settle; 12f stagger across three cards.
energy: Medium-high
tags: data
---

## Intention
The library's "flip" family already includes the wipe-transitions blinds-slice (vanes flipping sequentially to execute a page turn). This card represents a **semantic flip**: the front and back of a card form a cause-and-effect pair—the front displays the feature UI, while the back reveals the quantitative conclusion it produces. The flip gesture itself serves as the answer to "So what?", a staple visual grammar of Apple bento segments. Staggered by 10f–12f across a row, three cards unveiling three figures deliver the distinct rhythm of a "rapid-fire impact report."

## Motion Core
- `perspective: 1600px` + `transformStyle: preserve-3d`; both faces set `backfaceVisibility: hidden`, with the back face pre-rotated via `rotateY(180deg)`.
- Three flip phases: 4f preparation (anticipatory backward lean of −10°, ease-out) → 16f `cubic-bezier(0.55, 0, 0.3, 1)` accelerating flip to 194° (14° overshoot) → physical spring (`damping: 15`) settling back to 180°; during the flip, `translateZ` lifts by 60px on a sine envelope.
- **Lighting / Sheen**: Card surfaces darken based on angular deviation from facing the camera (`(1 − |cos θ|)` dimming, 0.55 on the dark side / 0.4 on the light side); across the 56° → 124° side-edge window, a narrow specular sheen band sweeps from left to right across the card, peaking in a triangular envelope at 90° (the thinnest knife-edge instant)—linking specular intensity to rotational angle ensures it reads as "light grazing a turning surface", providing physical illumination rather than an artificial glint overlay.
- **Front-to-Back Contrast Inversion**: In the demo, the front is a dark feature card (graphite dark stage), while the back is a porcelain-white conclusion card—flipping transitions from dark to light. Once all three cards flip, the screen transforms from a row of dark cards into a row of bright white numeric posters; the 158px back-face number snaps in from 1.08 → 1 upon landing, the outcome label rises 4f later, and the top "Before / After" comparison bar contracts upon settling.
- **Spatial Staging**: Cards stand on a dark specular floor; each card features a vertically mirrored reflection that flips in sync (mask fade at 26%, `opacity: 0.22`), with floor contact shadow width scaling dynamically with projected profile `|cos θ|`.
- Stagger delay is 12f per card; true static hold ≥40f after all cards finish settling (demo holds for 78f after 72f); camera maintains an ultra-slow push-in from 1 → 1.03 throughout.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Flip duration | 4f prep + 16f flip + ~10f spring | <14f loses the knife-edge profile glance; >28f feels like a lazy rotation; cutting prep reads as being flicked away rather than intentionally flipped |
| Overshoot | 194° → 180° (14°), spring damping 15 | Settling with zero overshoot reads as an abrupt mechanical stop; damping <12 creates a double bounce resembling jelly |
| Surface lighting | Face dimming ≤0.55 + side-edge narrow band peaking at 90° | Peaking offset from 90° reads as a texture mapping error; sheen sweep without surface dimming looks like an overlaid white strip |
| Stagger | 12f/card, ≤4 cards | Simultaneous flipping reads as a solid wall turning, eliminating the sequential rhythm of a rapid-fire outcome report |
| Back content | Large-scale number (150–170px range) + single-line label + at most one comparison bar | Packing a full UI on the back is unreadable—the viewer only grants a single beat of attention post-flip; wide text like "−41%" above 160px may overflow card boundaries |
| Outro settle | True static hold ≥40f after final card settles | R1 |

## Known Pitfalls
- The demo was calibrated and passed on grayscale/placeholder assets—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- The front and back faces must form a semantic pair (interface → its outcome); flipping to unrelated content reduces the motion to a gimmicky image swap.
- When using actual screenshots on the front face, beware of backface rendering overhead; split into separate Sequences if using more than three cards.
- Audio candidate cue: a subtle, crisp "snap/click" on each card's settle frame (sound-design §4.5); a triple snap multiplies rhythmic impact.

## Reference Implementation
demos/transition/card-flip-reveal/
(CardFlipReveal.tsx)
