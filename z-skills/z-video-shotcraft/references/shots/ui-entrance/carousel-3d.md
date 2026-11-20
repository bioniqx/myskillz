---
name: carousel-3d
summary: Eight cards sit on a circular ring laid out with sin and cos, spinning through exactly one full revolution while each card billboards outward with matched front and back faces so it never reads as mirrored or upside down.
use: Looping showcase for portfolios, template libraries, or integration directories; background plates or landing page heroes requiring seamless looping.
duration: ~5.6s (168f @ 30fps)
energy: Medium (Steady-state infinitely loopable motion, with stops every 45° establishing cadence)
---

## Intention
The simplest way to showcase "a set of items" is a horizontal slider, but sliders have a distinct beginning and end. A ring has neither—it loops naturally, so viewers never feel it has "finished playing" regardless of how long they watch. The core issue this card solves is the most common failure point of 3D carousels: the back faces of cards. The solution is dual-sided matched texturing, ensuring that looking from inside or outside the ring displays the exact same upright card—no frame ever displays mirrored or inverted content across a full revolution.

## Motion Core
(Demo version: Acid-lime graphite dark-theme video-shotcraft shot recipe gallery, 340×460 cards, radius 700px, native 1920×1080 coordinates)
- Ring positioning formula takes a single line: `transform: rotateY(i*360/N) translateZ(RADIUS)`—rotate to azimuth angle first, then push outward along the new Z axis by radius. This simultaneously handles layout and billboarding: card normals naturally face outward. The card directly facing forward pushes outward an extra 44px along its normal (pure translation without rotation), reading as "selected" during stops.
- Entire ring rotates via parent container: `ring.transform = rotateY(-spin)`, while individual card transforms hold only positioning components. **Cards never rotate around X or Z**, which is the fundamental guarantee of staying upright at all times.
- Rotation is not uniform velocity: `turn = 0.5·f/168 + 0.5·stepPart(f)`, where `stepPart` takes one step every 21f (8f stop + 13f smooth shift). The uniform base keeps the ring continuously moving (steady-state loop), while the stepped layer delivers a "push—rest" pulse every 45°. 8 steps × 21f = 168f completes exactly one revolution; at f=168 turn=1, enabling seamless pixel-perfect looping.
- Dual-sided matched texturing: front and back share the **exact same card surface**, with back receiving an extra `rotateY(180deg)` and both layers set to `backface-visibility:hidden`. Outside the ring sees front, inside sees back, both displaying identical orientation—single-layer approaches show mirrored text when cards rotate behind the ring.
- Forward card lighting: `hl = smooth(1 - |azimuth|/26°)`, driving fluorescent rim glow, graphical tint interpolation (graphite gray → fluorescent yellow-green), and outward extrusion; bottom captions (mono index + 72px title) scroll vertically in a clipping window in sync with stepped shifts, freezing during stops.
- Fixed camera without motion across all frames: `perspective: 2200px`, ring container `translateZ(-RADIUS) rotateX(-9deg)`—front card lands at z=0 (rasterized at native size without font blurring); all motion stems from ring rotation, creating a "gallery" rather than a "roller coaster".
- Ground plane: 2.7x radius reflective disk + 96-tick dial ring (rotating in sync) `rotateX(90deg)` flat beneath cards; plus a mirror reflection ring with ground plane `scaleY(-1)` (leaf layer 8% opacity + fade mask; opacity cannot be attached to preserve-3d container or it flattens the 3D context).
- Aerial perspective: overlays background tint onto card faces based on azimuth `(1-cos θ)/2` (rearmost card reaches 70%), making foreground-background depth instantly readable.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Card count | N=8 (azimuth spacing 45°) | 8 cards at 700px radius avoid mutual occlusion; >12 cards overlap edges, requiring larger RADIUS |
| Radius | RADIUS=700px (cards 340×460) | Radius / card width ≈2 is the density sweet spot; <1.5x back cards peek through front card gaps, cluttering frame |
| Spin composition | 50% constant + 50% stepped (21f/step, 8f rest) | Stepped ratio >70% causes ring to nearly stall during stops, feeling like stutter; <30% loses stop cadence, reverting to flat rotation |
| Revolutions | 1 full turn across sequence (8 steps) | Revolutions and steps must both be integers for clean looping; non-integers cause last-frame jumps |
| Perspective | `perspective: 2200px` | Relatively flat perspective for 700px radius; values below 1200px exaggerate foreground cards into fisheye distortion |
| Camera pitch | `rotateX(-9deg)` | Mild downward tilt just enough to reveal ground disk and tick dial; steeper than -20° squashes ring into flat ellipse |
| Highlight window | Azimuth ±26° | Too wide highlights adjacent cards simultaneously, blurring hero focus; too narrow leaves entire ring dark mid-shift |
| Reflection | 8% opacity, fading from 62% | >15% makes reflection text legible, competing with bottom captions |

## Known Pitfalls
- Steady-state looping is both this card's strength and limitation: **it has no start or end**. Stepped stops provide cadence, but as a primary hero shot it remains relatively calm—best suited for background plates, loop assets, or layered under foreground typography / camera motion.
- Every frame recalculates transforms for 8 cards (`rotateY(i*45) translateZ(RADIUS + 44·hl)`)—rotation components remain constant while only normal-axis extrusion tracks highlight. This keeps "cards do not self-rotate" explicit in code; avoid attaching extrusion to rotation.
- `backface-visibility:hidden` requires `-webkit-` prefix under certain WebKit environments (code includes both). Omitting prefix displays both faces simultaneously, turning card content into overlapping mess.
- Card faces are mock recipe cards (mono index + generative graphic + large digit + title); production requires real screenshots, and **front/back must use identical content**, otherwise dual-sided orientation assumptions break.
- When cards swing behind the ring, viewers see the back layer facing forward, keeping content legible—this also means there is no opportunity for a "flip-to-reveal" action. Flip reveals require discarding backface-hidden and implementing a different approach.
- Dark ambient backdrop + graphite card surfaces + aerial perspective darkening operate as a unified system; porting to white backgrounds requires recalibrating darkening layers and reflections (darkening mixes toward background color, reflection opacity drops to ~5%).
- Caption "active card" derives from stepped layer step index rather than raw azimuth: uniform base rotation advances the ring by ~8.6° during rest periods, so front card sitting slightly left of center is normal; when tweaking stepped ratio, ensure highlight window (±26°) still covers this drift.

## Reference Implementation
demos/ui-entrance/carousel-3d/
(Carousel3D.tsx)
