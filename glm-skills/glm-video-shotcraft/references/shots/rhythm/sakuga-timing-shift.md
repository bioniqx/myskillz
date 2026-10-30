---
name: sakuga-timing-shift
summary: Movement begins in stepped, held drawings and suddenly switches to frame-by-frame acceleration at the climax.
use: Emphatic displacement of single elements (card entries, metrics crossing finish lines); sequences requiring contrast between "handcrafted stutter" and "explosive climax"
duration: 150f (5s)
energy: Medium-high
tags: ui-entrance
---

## Intention
The library's timeline manipulation already includes speed-ramp-freeze's freeze-unfreeze and hit-counter's local hit-stops. This card represents a different axis—**altering frame rate rather than velocity**:
The stuttered phase uses quantized driving frames `q = floor(f/3) * 3`, moving only once every 3 frames (10fps flipbook animation); at the transition frame, it switches instantly to raw frame `f` continuous motion for a silky sprint. The blunt cadence of shooting on 3s cuts against the fluidity of shooting on 1s on the same screen, channeling the timing direction of Japanese sakuga animation. The stuttered phase does not convey poor quality but handcrafted craft, and the switch point marks the climax.

## Motion Core
- Stuttered phase: `q = Math.floor(f / 3) * 3` acts as driving frame, linearly translating X 140->1180 across 16 key poses, ≈69px per step; pose freezes with `q`: `sin(q)` rotation ±5 deg + alternating squash/stretch (0.97/1.035) + alternating high/low hops (−18/−2px), varying each step.
- Frame 48 switch: two "impact frames" (screen inverted to dark ink + focus lines converging on the card) act as climax markers, switching immediately to continuous raw `f` driving with `Easing.out(poly(4))` high-initial-velocity sprint snapping to center + 40px overshoot + 6f rebound, landing with scaleX 0.92 / scaleY 1.07 compression.
- Sprint motion stretch is driven by velocity differentials (peak scaleX ≈ 1.3 / scaleY 0.9), trailing 9 horizontal tapered ink speed lines whose lengths scale proportionally with velocity; **conditionally mounted**—unmounted as velocity drops.
- Timing shift callouts sync across three points: corner badge toggles "ON 3s / shooting on 3s" -> "ON 1s / shooting on 1s" (pops 1.25x, hand-drawn boiling underline redraws every 4 frames, freezing at f=108); bottom dope sheet marks drawing numbers only every 3 cells during shooting on 3s with vertical continuation lines, while shooting on 1s numbers every single frame—making the frame rate visible to the audience.
- Canvas: paper-look animation paper (peg holes, pale blue pencil safety frame and crosshairs), hero element is a video-shotcraft product card drawn with 5px ink lines + hard-edged cel shading ("30fps · every frame, crafted"); rests on 2% subtle push-in hold after f74.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Timing | Stuttered phase floor(f/3) (shooting on 3s) | /2 lacks stutter character; /4+ reads like video player stutter |
| Step displacement | ≈69px (1040 total travel / 15 steps) | <30px reads as dropped frames rather than intentional stutter—critical core |
| Inter-step pose | sin(q) rotate ±5 deg + squash/stretch + high/low hops | Pure displacement stutter without pose changes looks like a bug rather than a flipbook |
| Switch frame | f48 (stutter:sprint ratio ≈ 3:2) | Switch must execute in a single frame; any tweening destroys the "timing shift" perception |
| Sprint easing | Easing.out(poly(4)) + 40px overshoot + 6f rebound | Initial velocity must be fierce to maximize contrast with the stuttered phase |
| Finale | 70f hold after settling (preserving 2% subtle push), badge boiling freezes at f108 | Lingering boil ruins true resting rest (akin to feTurbulence unmasking precedent) |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Impact frames represent full-canvas visual hits (R4 tally); allocate strictly once per shot at the transition point, capped at 2f.
- Single timeline manipulator precedent: mutually exclusive with speed-ramp-freeze / hit-counter hit stops; only one manipulator may alter the timeline in a single shot.
- Stuttered steps must displace >=30px per step to read as intentional—micro-stutters look like render drops; if travel distance is insufficient, shorten total duration to widen step displacements.
- The shift point must feature annotations (badge "ON 3s" -> "ON 1s", dope sheet cells, or an audio hit per sound-design §4.5)—without cues, viewers merely feel it "got faster" rather than recognizing a shift in timing.

## Reference Implementation
demos/rhythm/sakuga-timing-shift/
(SakugaTimingShift.tsx)
