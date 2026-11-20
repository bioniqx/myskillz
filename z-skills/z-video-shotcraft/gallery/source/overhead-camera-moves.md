---
name: overhead-camera-moves
summary: Two overhead reveals: a tilted scene leveling into view, and a tabletop layout dropping sharply into place.
use: Opening or transition storytelling via pitch angles: use Variant A for single-page establishing shots, and Variant B for multi-page inspections diving into a chosen page
duration: A 120f (4s) / B 140f (4.7s)
energy: A Medium / B Medium-high
tags: opening, transition
---

## Intention
Overhead perspective has been a gap in the shot library: crane-rise is a "pan + zoom" elevation with a fixed tilt angle, while space-camera Variant C (drone-dive) is a one-way dive landing. These two recipes let the **pitch angle itself tell the story**: Variant A is a reveal—the entire page lies flat under rotateX; at opening, only a luminous perspective sliver at the far top edge is visible (like first light on the horizon), then the camera tilts up to level the page as content pours into view like unrolling architectural plans on a table; Variant B is a selection—three page cards lie flat in a tabletop layout, the overhead camera slides horizontally across them (Wes Anderson tabletop style), then dives steeply into the chosen page, leveling it to full screen: "inspect the field, pick this one." Selection guide: use A for single-page openings; use B for multi-page transitions or openings.

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A tilt-reveal | Full page lies face-up with rotateX 86 deg hinged on bottom edge, tilts up to level over 40f (overshooting to -2.2 deg before softening back); angle, scale, hinge position, perspective, and viewpoint height share a single progress driver | Opening establishing shot; single subject |
| B overhead-tabletop-drop | Card array lies flat with rotateX 62 deg; pan phase only moves translateX horizontally, drop phase synchronizes angle, scale, and translation to dive into final lockup | Inspecting multiple pages then picking one; opening or transition |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Pitch angle | rotateX 86 deg (f0–20 ultra-slow creep to 83 deg) -> -2.2 deg (f60, velocity zeroes) -> 0 deg (f70); main segment uses EASE.swift asymmetric in-out, smooth overshoot recovery, transformOrigin 50% 100% (bottom edge hinge) | Initial version at -55 deg was too weak: half the page was visible at f0 without the "narrow sliver" suspense (render precedent); if the viewpoint is below page plane, the backside is exposed (text in the sliver appears inverted) — viewpoint must stay above the page plane; per-segment out-cubic curves cause velocity jumps at seams |
| A Coupled motion | perspective 700 -> 1500; viewpoint y shifts from 300px above hinge to screen center; scale 2.5 -> 0.84 (leaving borders to expose the stage); hinge y 600 -> 935; background light pool and dust drift shift downward 150px in counter-parallax | If perspective is not coupled, the opening angle fails to show "just a sliver"; without background parallax, it looks like the page is rotating rather than the camera tilting up |
| A Resolution | Camera settles at f70; 38–82 area chart polyline draws on; 80f endpoint beacon ignites; 70–120 ultra-slow push-in 1 -> 1.018 | Overshoot amplitude <=3 deg, anything larger feels like a spring instead of a camera mount; 69f of pure static hold is too dead (>1s dead frame); holds need an ultra-slow push-in |
| B Pan phase | 0–50f only modifies translateX +760 -> -360 (smooth), pitch angle locked; 50–58 holds 8f on selection (target board lifts 16px off table, its top spotlight lights up, other two dim to 35%) | Changing angle during pan blurs stage roles (precedent: pan inspects, drop commits); without a distinct selection beat, the dive feels random |
| B Drop phase | 58–86f runs three channels concurrently: rotateX 62 -> -1.6 -> 0.5 -> 0 (zero-velocity takeoff asymmetric curve + smooth overshoot recovery), scale 1 -> 2.04 -> 2.0 (anticipatory ~5% recoil at start), translateX -360 -> 0 | All three channels must run simultaneously; sequential motion reads as two separate actions; jumping directly with out-cubic after pan halt creates velocity discontinuities |
| B Card array | Cards at 996x560 (precise 16:9 ratio), final lockup scale 2.0 perfectly fills screen frontally; transform order translateX -> rotateX -> scale | Incorrect transform order causes curved pan trajectories |
| B Floor plane | Dark graphite tabletop + hairline grid + top spotlight pool / volumetric beam for each card + print-style labels below cards (01 SHOTS...) | Without floor reference, horizontal sliding fails to convey "camera is moving"; contrast between dark desk and white artboards creates visual depth |
| B Resolution | Camera locks onto board at f94; 98–118 golden shot block slides into storyboard empty slot (single overshoot); 94–140 ultra-slow push-in 1 -> 1.012 | 47f of total stillness after landing is too lifeless; give the inner page a subtle concluding action |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- At steep perspective angles, cards must include backfaceVisibility: hidden + translateZ(4px) fallback, otherwise certain frames expose backface or depth glitches.
- Choose between Variant A and crane-rise-reveal within the same video: both are opening reveals, and having two "reveal openings" nullifies the impact.
- Locking angle during Variant B's pan phase is critical (separation of responsibilities precedent): panning is for inspection, dropping is for commitment; mixing them leaves the audience confused about camera intent.
- Both variants represent major camera maneuvers and conflict with space-camera / crane-rise in the same segment; a sequence can only have one camera operator at a time.

## Reference Implementation
demos/camera/overhead-camera-moves/
(OverheadTabletopDrop.tsx / TiltReveal.tsx)
