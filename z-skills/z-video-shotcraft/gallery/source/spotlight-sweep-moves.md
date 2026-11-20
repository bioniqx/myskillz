---
name: spotlight-sweep-moves
summary: Three dark-scene spotlight moves: a wake-sleep sweep, an edge-glow pan with purple bleed, and a radial reveal expanding from a corner.
use: Introducing UI panels and feature areas sequentially in dark brand videos; bringing an interface on-screen by "lighting it up" from a black void; lighting transitions between chapters
duration: 3.5–4.5s per variant; A and B can link into a continuous tour sequence
energy: Medium-low (restrained, mysterious; peak impact at the instant of illumination)
tags: ui-entrance, transition
---

## Intention
In a black void, viewers only see what light reveals—spotlights serve simultaneously as illumination, camera movement, and editing cut: wherever the beam travels, that section debuts; when the beam departs, it takes its bow. All three variants share the signature motif of a "rim-hugging purple glow ray" (a light ray hugging UI borders, logos, and top edges; the glow must be bright and soft, acting as light "caressing" the interface rather than a mechanical stroke animation). The vital rule is **constant velocity**: beam translation and expansion must be strictly linear—easing gives light perceived "intent," whereas constant velocity conveys the mechanical sweep of a searchlight (Variant C precedent: linear velocity with an excessive final radius saturates in the first 1/4, failing to read as constant).

## Motion Core
- **A Wake-Sleep Sweep** (glow-wake-sleep-panel): A radial reveal mask tracks the spotlight head from left to right at constant velocity, outside of which all is pitch black. A top-edge purple ray with 3-tier glow (blur26 wide soft + blur9 mid + bright core + pink offset) travels synchronously with the sweep, casting a box-shadow glow when crossing the logo and leaving a vertical residual gleam on the right edge. In the tail phase, the light leaves and the panel sinks back into darkness—waking, then sleeping.
- **B Edge-Glow Pan** (slide-spotlight-pan): Light ray anchors to panel edges (tracing the vertical left corner edge, turning, and gliding along the top edge), bleeding violet glow into the inner top UI. The spotlight head pans right at constant speed while the panel glides left at constant speed, creating the sensation of a camera panning right.
- **C Corner Reveal** (corner-spotlight-reveal): A radial spotlight in the top-left corner expands with strictly linear radius growth, illuminating covered regions while unreached areas remain in deep black, eventually achieving full illumination (light as transition).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Spotlight move / expand | Strictly linear throughout, zero easing | **Constant velocity is mandatory**—zero easing across the entire shot; adding easing makes light feel consciously driven |
| Variant C final radius | Covers full frame exactly at shot end (1300 @ 1080p / 100f) | Excessive final radius = early saturation and false linearity; luminance samples must climb smoothly throughout (measured: 8/46/101/…/238) |
| Rim ray glow | 3–4 layers (blur26 + blur9 + bright core + pink offset) | Too few layers read as thin line strokes; glow must be sufficiently bright and diffused to read as "light" |
| Ray anchoring | Strictly hugs UI borders, top edge, and logo | Detaching rays from edges destroys the "caressing the interface" semantics (Variant A rework precedent: lost positioning caused purple ray to drift to bottom edge) |
| Reveal mask | Radial gradient with slightly softened edge (feather ~15%) | Excessively hard edges look like circular cookie cutters; overly soft edges blur the boundary between lit and unlit |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Division of labor with `light-play-moves`: that card handles sheen and highlight play on elements and text (sheen sweeps and breathing glows); this card treats light as **camera movement and editing** (reveals, curtain calls, transitions), where light dictates viewer focus.
- Three-variant rework precedent: spotlight sweeps must travel with edge-hugging rays (v1 had only a reveal mask and was rejected—a bare spotlight lacks identity, whereas the edge-hugging purple ray is the signature of this technique).
- In the original reference (clickup-30), light rays display an instant of rainbow chromatic dispersion at corners, omitted in the demo; in production, consider adding a 1–2f dispersion layer at corners to enhance tactile fidelity.

## Reference Implementation
demos/effects/spotlight-sweep-moves/
(CornerSpotlightReveal.tsx / GlowWakeSleepPanel.tsx / SlideSpotlightPan.tsx)
Original source: clickup-30.mp4
