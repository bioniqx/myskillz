---
name: steep-tilt-glide
summary: A page stands at a steep 60-degree perspective and glides across a fixed camera with speed ghosting while text settles onto the surface mid-flight.
use: Showpiece tour for long pages or multi-section UIs (content gliding across a locked camera position); dark stage neon aesthetic; complementary "lateral glancing" setup to graze-face-tour
duration: 4s (120f) single shot; can extend for wider pages
energy: Medium-high (steep perspective showcase + continuous motion, but steady pacing)
tags: ui-entrance
---

## Intention
Standing the page upright like an angled wall: the camera remains completely stationary, locked in a steep 60-degree perspective that puts the right edge right in the viewer's face while the left edge recedes into the vanishing point, while the page itself glides sideways across its own plane—content streaming past like subway cars. The core principle is **moving object, locked camera**: perspective, origin, and rotY remain constant throughout; the only variable in motion is the page's local translateX. If the camera moves, it turns into camera acrobatics; here, the focus is "the page presenting itself." The angle converged over three rounds to an exact 60 degrees (-45 deg "wrong" -> -53 deg "steeper" -> -60 deg selected).

## Motion Core
- Camera constants: perspective 1100, origin 30% 58%, rotateY(-60 deg) + rotateZ(-2 deg), transformOrigin left top, constant values throughout the entire duration.
- Page: ultra-wide panel (6200x2400 @ content coordinates) gliding along local X axis from +60 to -4100 using bezier(0.3, 0.12, 0.72, 0.9)—soft start leading into near-constant speed, with a non-zero tail slope (avoiding an abrupt dead freeze).
- Speed ghosting: trailing streak layers reprojection from prior time offsets (f-1.6 / -3.2 / -4.8, 3 layers with descending weights); opacity proportional to gliding speed (denser ghosting during fast transit).
- Floating element settle: page elements wrapped in FloatWrap hover 230–280px aloft with matching soft shadows, settling down in staggered sequence as the glide advances (tour syntax).
- Brightness reveal: panel begins dimmed to 0.7 brightness, revealing to full brightness over ~1.4s; an extra gradient shadow on the left edge recedes in tandem.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Tilt angle | rotateY **-60 deg** (exact calibrated value) | -45 deg rejected as "wrong angle", -53 deg "make it steeper"; >-70 deg makes content unreadable |
| Motion model | Locked camera, self-moving page | **Critical rule**—camera-panning version was rejected: "camera is locked; the page itself moves sideways along its own 3D plane" |
| Glide curve | Bezier with non-zero tail slope | Mid-flight freeze caught in review (v4 rework); pure linear lacks breathing room at takeoff |
| Ghosting | Opacity proportional to speed, 3 layers at f-1.6 / -3.2 / -4.8 | Constant ghosting reads like a double-exposure glitch |
| Page width | >=3 screens of content | Too narrow finishes gliding in 2s and cannot carry a full shot |
| Element landing | Staggered (tour syntax) + shadow scaling with height | Semantic precedent documented across graze-face-tour and orbit-drop card family |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Perspective angle precedent: the steep angle is this shot's identity; production adjustments should stay within 55–65 deg, outside of which it becomes a different technique entirely.
- Division of labor with graze-face-tour: that card moves the camera (skimming across) while the page is static; this card locks the camera while the page moves. Choose one per sequence.
- Hand-drawing ultra-wide pages is labor-intensive; real long screenshots can be substituted in production (glide logic remains identical).

## Reference Implementation
demos/camera/steep-tilt-glide/
(SteepTiltGlide.tsx)
Original source: clickup-30.mp4
