---
name: space-camera-moves
summary: Three spatial camera moves: exploded assembly, subject-locked rotation, and a drone-like dive to the landing point.
use: Hero sequences treating a 2D page as a physical 3D object; both variants are "major maneuvers," use <=2 times total per video
duration: A 170f (5.7s, full sequence of explode-hover-recombine-ending title); C 105f (3.5s, dive 69f + settled hold 36f) one-way dive
energy: High
---

## Intention
The depth-layer card adds depth to panning—layers move, but the page remains a page. These two recipes go further: the entire page is treated as a 3D physical object, with the camera (or world) executing live-action-grade maneuvers around it. The two variants serve distinct narrative roles: Variant A says "look at what it is made of" (deconstructed exhibition, Apple keynote visual language); Variant C says "slam from global overhead straight into the hero" (god's-eye perspective plunging into a hero close-up, wide -> focal point).

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A exploded-view | Full page rests flat in 3/4 axonometric perspective, components explode staggered along page normal and hover (with numbered callouts), then recombine in reverse order with a solid drop-hammer lock | Architecture / composition display: "what is inside this product"; module overview section |
| C drone-dive-landing | Near-vertical overhead hover -> steep plunge dive -> air-cushion deceleration settling into hero card close-up | Opening establishing shot -> entering topic; chapter kickoff diving from macro map into a single point |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Spatial base | perspective 2400 + `translate * scale * rotateX(54 deg) * rotateZ(-34 deg)` axonometric + preserve-3d; camera pulls back 0.56 -> 0.47 and shifts down during explosion to frame layer stack; rotateZ +10 deg orbit and pitch tightens 4 deg during hover | Slight front tilt (18 deg / -12 deg) merely reads as "lifting"; flat axonometric is needed for an exploded diagram feel; hover orbit reveals inter-layer depth via parallax |
| A Explosion | 5 layers translateZ 150/270/400/520/640, spring (damping 15, stiffness 120) staggered by 5f | Layers further toward the back/top must rise higher, otherwise lower layers occlude upper ones; uniform depth reads as entire page floating |
| A Recombination | Callouts withdraw first (ease-in 8f), layers reverse ease-in over 14f staggered by 3f; on landing frame, whole assembly drops 8px with damped rebound + base contact shadow snaps tight, followed by a light sheen sweeping the page | The drop-hammer beat is mandatory—without it, recombination feels like a mushy fade-in; no screen shake needed (Q3), drop rebound + tightening shadow provide the crisp snap |
| A Depth anchors | Drop shadow on base plate shifts down, softens, and fades with height + thickness edge on back of each layer + dashed component slot outlines on base plate | Omitting any of these three cues blurs inter-layer spatial relationships |
| A Callouts | Anchor = 3D projection of outer edge midpoint (calculated manually with same matrix as CSS), left/right rails, horizontal leader lines dog-legging to rails; 44px title + 30px description, line draw 8f + rise 12f, staggered 6f | Leader lines drawn from layer center will intersect other layers; callout text <32px is unreadable |
| C Flight path | Single progress p drives rotateX 72 deg -> 0 + scale 0.42 -> 1.35 + translation convergence; origin pinned to hero card center (e.g. 518, 335); page laid out at end scale 1.35 + CSS zoom rasterization before scaling down, keeping close-up text crisp | Single p = one camera, one maneuver; separate drivers fight like three conflicting animations |
| C Velocity curve | 0–24f god's-eye establish + upward anticipation (recoil 2.5% of path) -> main dive 25f Easing.in(cubic) covering 82% of distance -> air cushion 20f Easing.out(poly(5)) covering remaining 18% -> settled hold 36f | Sudden velocity drop at handoff frame creates the physical air cushion feel; 82/18 distance ratio matters more than frame counts |
| C Atmosphere | Scene wrapped in CameraMotionBlur (shutterAngle 220, samples 12), with background and grain kept outside blur; page hovers above dot-matrix ground in the same 3D world (initial lift 150), dot matrix rushes toward camera during dive; ground contact shadow tightens and sharpens during descent, fading to 0 right before touchdown; subtle vignette darkens around hero after landing to focus gaze | Soft shadow sells altitude; blur sells speed; missing either dimension breaks realism; multi-sampling large gradients causes color banding, so keep backgrounds outside blur wrapper |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Both variants require real screenshot slicing / high-resolution textures: Variant A requires the page sliced into independent component assets (top bar, sidebar, cards each rendered separately; a single full-page image cannot explode); Variant C ends in a tight close-up, requiring preparation with Q2 high-resolution rasterization first.
- Variant C common bug: Remotion has no `Easing.quint`; write `Easing.poly(5)` instead (encountered during this production run).
- Variant A component layout must use absolute positioning replicating the original page grid (the demo has 5 layers: sidebar, chart, assistant, metric, command bar); flex/flow layout cannot support per-component translateZ.

## Reference Implementation
demos/camera/space-camera-moves/
(DroneDiveLanding.tsx / ExplodedView.tsx)
