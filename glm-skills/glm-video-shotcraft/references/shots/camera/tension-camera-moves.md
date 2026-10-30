---
name: tension-camera-moves
summary: Two emotional camera tools: a frozen orbit and an isolating pull-back.
use: Camera language for emotional beats (awe / consolidation); complements the showy acrobatics of space-camera-moves—these two moves are minimal in physical displacement but heavy in emotional gravity
duration: 5–6s per variant (150–170f); <=2 variants total per video (<=1 time each)
energy: A High / B Low resolution
---

## Intention
The space-camera-moves recipes are high-energy showcases that treat a page as a 3D physical object; these two variants take the opposite approach—physically restrained motion where all dynamic force is invested in emotional semantics: Variant A says "this moment is worth stopping time to inspect" (elements frozen in mid-motion while the camera orbits to observe); Variant B says "in the end, only this one thing remains" (surroundings extinguish layer by layer as the camera pulls back, isolating a solitary element to resolve the entire piece). Each variant occupies a distinct emotional niche, serving as direct vocabulary for the question: "what should the audience feel in this beat?"

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A bullet-time-freeze-orbit | Chart growth freezes mid-animation along with sparks erupting from bar tops (sparks suspended mid-air with trailing tails intact); camera orbits around the panel with rotateY sweeping 52 deg and returning in a true 3D scene, then time resumes to complete growth | Crowning moment for core metrics/charts; the "worth stopping the clock to behold" beat |
| B pull-back-isolation | Camera pulls back from a hero card close-up as 8 sibling cards extinguish in distance-staggered order and background sinks to black, leaving the solitary card suspended in the center of darkness | Ending resolution; the curtain-call beat saying "the entire video exists for this single number" |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Dual clocks | Content animation consumes `eff` (speed ramp integral: 8f smooth braking -> freeze 52f -> 8f recovery); camera consumes true frame f | Critical requirement: content must be visibly completely motionless during freeze while camera continues moving—two independent clocks; abrupt hard stops lack the speed-ramp elasticity of bullet time |
| A Orbit | preserve-3d scene with perspective 1800 (panel / sparks with z-depth / grid floor / distant dot-matrix wall): rotateY 0 -> -52 deg (26f smooth) -> slow drift at apex 12f -> return to 0 (22f swift), paired with rotateX lift 6 deg and 160px push-in | 50–55 deg is the lower threshold for "orbiting to side view"; >70 deg flattens the panel into paper, breaking realism; without depth references (single panel + solid color background), camera orbiting cannot be registered |
| A Frozen motion | Spark streak length and counter roll blur are calculated from content clock speed | In freeze state they maintain an "in-motion" posture—what is frozen is an instant, not a still life |
| B Pull-back | scale 2.2 -> 0.62 / 110f Easing.out(cubic), origin locked to hero card center, laid out at 2.2x CSS zoom before scaling down | Hero card fills frame for the first 20f, opening in close-up without needing an extra hold; scaling up via transform blurs close-up text (Q2) |
| B Extinguish | Sibling cards sorted by hypot distance, one every 8f starting at frame 30, taking 16f to reach opacity -> 0 (EASE.out) + brightness -> 0.3 + defocus blur 5px + sink 0.97; background crossfades from bright soft-lit ground to hue-tinted dark ground across 60–110f | Extinguishing near-to-far = "world collapsing into darkness outward"; randomized extinguishing reads as a glitch |
| B Glow | Two layers of cool white box-shadow fade in on hero card over 60–100f, illuminated top edge emerging synchronously | Glow is the visual testament of "only this remains," effective only when synchronized with background darkening |
| Resolution | Hold >=30f after motion finishes for both variants (Variant A keeps subtle breathing light; Variant B stays purely motionless 110–150f) | R1; Variant B is the film's final period, give a generous 40f+ motionless hold; can add a concluding sign-off in screen space |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Variant A shares time-manipulation semantics with speed-ramp-freeze and impact-feedback; do not stack them in the same shot (frame remaps fight each other). Variant A freeze is "stop to show you" + camera moves; speed-ramp-freeze is "freeze to annotate"—choose by semantics, not visual resemblance.
- In endings, Variant B followed immediately by outro-group-photo-launch will clash (contraction vs. expansion); choose one.

## Reference Implementation
demos/camera/tension-camera-moves/
(BulletTimeFreezeOrbit.tsx / PullBackIsolation.tsx)
