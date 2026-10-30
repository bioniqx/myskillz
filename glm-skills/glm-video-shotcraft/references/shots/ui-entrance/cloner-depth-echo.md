---
name: cloner-depth-echo
summary: A card duplicates into a diagonal depth trail, holds briefly, then accelerates back into one springy original.
use: Value props of "multiple replicas / multi-tenancy / scale / batch processing"; one-shot demonstration of "one = many."
duration: 138f (~4.6s)
energy: Medium (Display-and-collapse cadence)
---

## Intention
A UI translation of the Spline/C4D Cloner vocabulary: a hero card instantly duplicates 7 translucent clones stepping backward along the Z axis (250px spacing, opacity decaying from 100% to 28%, distant clones reducing to wire outlines), popping out in a staggered column; holds for ~32f allowing viewers to register "there are many"; then all clones ease-in rapidly back into the hero card, collapsing into one with a 1.06x impact bounce. The demo ties "one = many" to a concrete feature: 1 video-shotcraft render card (launch-film) × 8 shot variations; upon collapse, 8 shot indicator dots at card base illuminate simultaneously as headline lands: "One prompt. / Eight shots." Distinct from parallax in depth-layer-moves (which layers different content): this is an equidistant echo array of the **exact same content**, conveying scale rather than spatial navigation.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Depth layout | True 3D perspective 1500, vanishing point placed top-left (360, 120); clone translateZ = −250·idx, layered with dx=−58·idx / dy=−6·idx | **Critical**: pure translateZ with vanishing point centered hides all clones directly behind hero; offsetting vanishing point to a screen corner lets depth travel naturally fan out toward that corner |
| Clone count / spacing | 7 clones / 250px | Fewer than 5 fails to read as a "formation", more than 9 turns tail into a muddy blob |
| Decay | Opacity 100%→28% linear; fill fades leaving accent border; distant clones add 0→1.6px depth of field blur | Fainter and more wireframe at distance provides evidence of depth; clones keep only top bar + line chart + shot number, omitting giant metric readouts to prevent overlapping visual clutter |
| Fan-out / Snap-back | Spring stagger 2.2f/card (damping 15, slight single overshoot); snap-back strong ease-in 10f synchronized across all clones, with velocity motion blur | Fan-out must be staggered (printing feel), snap-back must be synchronized (cohesive snap)—asymmetric rhythm is intentional |
| Hold | 32f, camera drifts in 2% with subtle parallax drift across column | Too short prevents viewers from counting "many", completely frozen becomes a dead frame |
| Collapse impact | Hero card single sine pulse 1.06x + accent border sheen (14f decay); shot slots ignite simultaneously on landing frame with counter bounce | Snap-back without bounce reads as a fade; bounce provides physical proof of mass |
| Counter | Bottom-left 260px "×N", rolls one notch per clone popped (5f, outgoing digit slides up and fades with vertical motion blur) | Counter translates "visual scale" into hard numbers; avoid overflow hidden clipping that crops glow effects into rectangles |

## Known Pitfalls
- Demo calibrated using mock video-shotcraft render card (lime dark palette)—parameters serve as calibration baseline, not final production specs; verify against real assets in production.
- Clones must render back-to-front to ensure correct z-sorting; conditionally unmount when opacity ≤ 0.005.
- Among three 3D channel explorations (thick turntable dropped, corridor kept for refinement)—pure showcase 3D camera moves face readability challenges; this card succeeds through the narrative motion of "fan-out and snap-back", avoid regressing into a static 3D array showcase.
- Audio: rapid string of subtle pops on fan-out, rising whoosh on snap-back, solid thud on collapse.

## Reference Implementation
demos/ui-entrance/cloner-depth-echo/
(ClonerDepthEcho.tsx)
