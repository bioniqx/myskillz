---
name: terminal-3d
summary: Three terminal windows float at different poses in 3D space; the camera flies between them with a sine pull-back, and at each stop a command types out and its results slide in line by line.
use: CLI / workflow demos for developer products: turning a "3-step command" into a 3-stop spatial journey
duration: ~8.2s (246f@30fps; ~2–3s hold at each of the 3 stops + two 30f flight segments)
energy: Medium (flight provides motion, typing provides cadence, overall steady technical narrative; concluding on a luminous READY beacon)
---

## Intention
Terminal output is inherently anti-cinematic flat scrolling; this card translates it into spatial storytelling: each command occupies a physical window in 3D space, with the camera visiting each window like walking through a server room. Mid-flight pull-backs give the audience glimpses of surrounding windows—imparting a holistic sense of workflow structure.

## Motion Core
- Three windows each hold an individual pose (x/y/z/ry in world px), with the camera executing the **inverse transform**: `translateZ(-pull) rotateX(tilt) rotateY(view - ry) translate3d(-x, -y, -z)`—defining the window pose table directly produces the camera flight path; each stop maintains an 8–10 deg glancing perspective (VIEW table) so the landed window is never completely flat, ensuring clear legibility while retaining 3D volume.
- Windows are laid out at native screen resolution (1180x620, command 52px / output 38px monospace), rasterized 1:1 when the camera settles—no outer container scaling, avoiding blurred text (Q2).
- Two flight segments of 30f each (swift asymmetric in-out), with a `sin(pi * u^0.85) * 1250px` pull-back bulge mid-flight—at peak elevation the scene scales to ~0.6 with all three windows framed simultaneously, providing an architectural overview; lateral directional blur scales with camera screen velocity (active only during flight segments).
- Depth of field: each window computes focus based on distance to the current stop -> `blur 0–3px + brightness 0.62–1 + opacity 0.72–1`; during pull-back, overall depth of field deepens (defocus narrows with pull distance), keeping all three windows recognizable as terminals in the wide shot.
- Spatial anchors: the floor is an SVG perspective grid drawn line-by-line using projection math isomorphic to the world coordinates (constant stroke width without flickering); a backlight pool shines behind the focused window and an accent reflection pools beneath it (both projected to screen space from window center); each window is backed by a 560px outlined step numeral, creating parallax against the window during flight.
- Typewriter trinity: commands type out character by character (deterministic 0.75–1.65f per character jitter, +0.6f on spaces), block cursor stays glued to the text tail (solid during typing, blinking on an 8f half-cycle when idle), pausing 2f after typing before pressing enter; output uses terminal-style rapid printing (each line fades in snappily over 6f + retracts left by 10px, line spacing 4f), with status indicators spinning a braille spinner for ~6f before settling into a checkmark.
- Typing trigger TYPE_AT `[8, 94, 184]` occurs exclusively after arrival at each station—no typing during flight to keep viewer attention undivided; the only bloom effect in the entire shot is reserved for the final READY output line (Q4).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Pull-back bulge | sin(pi * u^0.85) * 1250px | Omitting it turns flight into a flat slide without takeoff/landing feel; <800px reveals only two windows mid-flight, losing the overview sensation |
| Flight / hold | Flight 30f, in-station ~60–90f | Holds must accommodate ~20f typing + ~20f output + >=14f reading window |
| Glancing angle | 8–10 deg (VIEW table) | 0 deg degenerates into a flat screenshot; >18 deg squashes monospace text under perspective distortion (Q6) |
| Depth of field | blur <=3px, scaled by (1 - 0.45) during pull-back | Excessive defocus blurs the entire flight sequence, destroying spatial relationships |
| Typing cadence | 0.75–1.65f/char + 0.6f on spaces | Constant per-char speed feels like robotic playback; >2.5f/char makes viewers impatient |
| Output printing | 6f snappy, line spacing 4f | Terminals spit output out rapidly; slow slide-ins (>12f) look like slideshow bullets |
| Window poses | x spacing ~1500px, z -220 to +260, ry +/-14–28 deg | Angular variance and front-back stagger create spatial distribution; facing all windows forward degenerates into a flat carousel |

## Known Pitfalls
- The camera is driven by inverse transform: **window transform, world transform, and the floor/backlight project() function must remain strictly isomorphic**—to update poses, only modify POSES / VIEW data; changing the camera chain requires updating all three in tandem, otherwise the floor grid and windows will slide relative to each other.
- The command and output text illustrate video-shotcraft's production pipeline (shotcraft init / render / export: storyboard -> render -> audio mix and export); when adapting to other products, preserve the "short command, 3–5 output lines" information architecture.
- Cursor blinking uses frame modulo (8f half-cycle) and is independent of shot duration; preserve the contrast between "solid while typing, slow blink on idle."
- The third window's READY line pops at ~220f; leave at least ~24f hold afterward to ensure the final frame settles properly.
- The cursor must hug already typed characters: do not use opacity 0 placeholders for untyped characters, which would push the cursor into empty space at the line end.
- The SpeedBlur stack is a full-screen SVG filter enabled only when flight velocity > 0; it incurs zero overhead during static holds and should never be left enabled permanently.

## Reference Implementation
demos/camera/terminal-3d/
(Terminal3D.tsx)
