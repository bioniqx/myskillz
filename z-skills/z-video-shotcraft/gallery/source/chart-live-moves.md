---
name: chart-live-moves
summary: Three data-driven motions: a live oscilloscope trace, dots regrouping into a figure, and an axis forced to rescale.
use: Data storytelling segments; respectively conveying "real-time aliveness," "every data point is a person," and "growth that cannot be contained"
duration: 165–192f each (5.5–6.4s)
energy: Medium-high (data as drama)
---

## Intention
Charts are not illustrations—they are the narrative. A shared prerequisite across all three variants (production testing precedent): **authentic chart context is mandatory**—authentic axis labels, authentic data, authentic copy; grayscale placeholder bars fail to convey data storytelling power.
Variant A Oscilloscope stream: the curve write head is pinned to the right edge oscillating up and down, while historical data streams off the left frame edge, interrupted by a sudden burst spike (amplitude 2.2x, readout jumps larger in accent color)—"real-time" needs no words, and events happen live.
Variant B Unit dot swarm regroup: 320 dots (~40 renders per dot) disperse -> cluster into three swarms (floating authentic labels: Promo, Launch film, Explainer) -> march into bar columns (authentic axis markers) -> assemble into a large dot-matrix numeral "12,847"—the exact same dots throughout, allowing viewers to trace an individual dot joining the formation.
Variant C Axis rescale shock: line climbs normally, then new values punch through the chart ceiling boundary by 226px (a thick accent line impaling the title area and crashing into top-right KPI numbers), pauses half a beat, and the y-axis dramatically rescales (old ticks fly out / new ticks slide in / grid lines densify / old line flattens into the horizon), with new values dropping into place alongside authentic value tags—enacting growth as "the axis cannot hold it."

## Variant Selection
| Variant | Core Motion | Use Case |
|---|---|---|
| A oscilloscope-stream | Sampling window translation 8px/f + Gaussian pulse spike (with precursor and aftershocks) + complete static freeze + slow post-freeze push toward spike | Monitoring / real-time products: a "living" system |
| B unit-dot-swarm-regroup | Three-act spring staggered migration (stiffness 150, damping 13, stagger 8f), sunflower spiral packing for clusters, final act assembling dot-matrix number | User count / composition storytelling: "every dot is a person" |
| C axis-rescale-shock | Punches 226px through ceiling (boundary fracture + debris) + 3-way coupled rescale (ticks swap / grid densifies / old line compresses) + 10px shake | Growth curve highlight: literal "off the charts" drama |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Authentic context | Authentic titles / axis ticks / units / readouts | **Acceptance prerequisite**: all 3 grayscale prototypes were rejected; all passed after switching to authentic context |
| Hero color | Accent color highlights key events/heroes (demo: A coral red spike, B cobalt blue Launch film cluster, C terracotta overflow segment) | Monochromatic gray fails to signal "where to look" |
| A Stream speed | 8px/f | 5.5px/f is perceptible, 8px/f is decisive; use pure mathematical functions for waveforms, no randomness |
| B Dot count / radius | 320 / 20px diameter (stretching into capsules up to +20px based on speed during transit) | Too few dots cannot form numbers, too small obscures individuals; over-stretching smears into a blur |
| C Overflow amplitude | 226px past ceiling guide | An 80px overshoot is not dramatic enough; piercing straight into the header zone creates the genuine sense of an incident |
| Resolution | All three variants require >=36f pure static hold | Data charts that drift at the tail look unfinished |

## Known Pitfalls
- The demo was calibrated on illustrative video-shotcraft rendering metrics (A deep blue oscilloscope display: render farm fps, B porcelain infographic: volume by video type, C sand Swiss poster: monthly render volume); values are illustrative—parameters are starting points, not production finals, and must be re-verified with real assets.
- Readouts, tick labels, and badges across all three variants are sized for final production (>=32px, primary readouts 120–176px); charts fill the screen rather than being constrained inside cards.
- The three variants are distinct standalone techniques, not a bundled package—if using more than one in the same film, limit each to <=1 occurrence and separate them across chapters.
- The spike in Variant A and the rescale in Variant C must occur only once; repeating them degrades their impact.
- Variant B's final number glyph must be pre-calculated (dot count = target coordinate count to ensure neatness; the reference implementation uses arc-length sampling along single-line skeletons with normal-aligned dual rows, achieving exactly 320 non-overlapping dots).
- Division of labor with dataviz-landscape-open (abstract data terrain opening): that card sets opening mood, whereas these three variants deliver concrete data arguments within chapters.
- Audio: Variant A spike gets an alert tick; Variant B gets a whoosh per migration act; Variant C gets a riser bursting through the frame and a dramatic snap on rescale.

## Reference Implementation
demos/data/chart-live-moves/
(AxisRescaleShockV2.tsx / OscilloscopeStreamV2.tsx / UnitDotSwarmRegroupV2.tsx)
