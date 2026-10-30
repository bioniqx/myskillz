---
name: bezier-source-converge-merge
summary: Four source nodes each draw a thin bezier curve toward one convergence point, then slide along their own curve and shrink as if swallowed, while accent data packets glide the paths and the curves erase backward.
use: Core mechanism shot for "multi-source integration / unified access / data convergence"; explanatory section for integration, aggregation, and single-entry products.
duration: ~5.6s (168f @ 30fps)
energy: Medium (Slow long-take push, maintaining vitality via gliding packets; swallow moment is the only subtle peak)
---

## Intention
"We unified four sources" is an abstract claim. This motion turns it into a visible physical process: first establish four independent channels (draw-on means "connected"), then have the four sources slide along their respective curves into the exact same point and get swallowed (shrinking to 0 means "absorbed"), and finally erase the paths leaving only the brand logo ("now there is only one"). Each of the three narrative stages has clear start and end points, letting viewers grasp the cause and effect without voiceover.

## Motion Core
- Path geometry: each `d = "M -22,y L 74,y C 186,y 214,120 332,120"`—start point sits outside the frame at -22, 74 is the resting position of the source node, followed by a cubic bezier curving toward the convergence point (332, 120). The four lines differ only in starting y (36/92/148/204), so their curvatures and entry angles differ naturally.
- Draw-on uses `stroke-dasharray = len` + `dashoffset = len*(1-draw)`, `seg(t, 0.04+i*0.045, +0.17, E.outQuad)`—stagger of 0.045 makes the four lines appear connected sequentially rather than lighting up together.
- Node positioning uses `getPointAtLength`: x=74 is precisely the straight segment end, calibrating path ratio `f0 = 96/len` directly (previous 40-step scan lacked precision, causing nodes to misalign), runtime `frac = f0 + (1-f0)*conv`, `conv = seg(t, 0.34, 0.74, E.inOutCubic)`—nodes traverse **along the real curve**, not via two-point interpolation.
- Three-stage shrinkage: when `conv < 0.75` 44→15px (gradual slimming), when `conv ≥ 0.75` 15→0px (collapses completely in final 1/4 of journey)—final rate of size change is over 4x faster, delivering the acceleration of "being swallowed"; font size scales synchronously via `size*0.26`, keeping labels anchored.
- Data packets: `pkCycle = (seg(t, 0.1, 0.74, E.linear)*2) % 1` runs two integer cycles with `i*0.13` phase offset per lane; opacity uses `1 - |cycle-0.5|*0.6` so packets are brightest mid-path and dim at the ends—preventing packets from abruptly popping in at the start.
- Path erasure: `erase = seg(t, 0.78, 0.9, E.outQuad)` pushes dashoffset negative (`-erase*len`), causing dashes to retract from the **starting point** opposite to draw-on direction, reading as "path retraction".
- Brand emblem: `seg(t, 0.16, 0.26)` fades in and scales from 0.7 to 1; at swallow moment (0.7→0.78 outBack +12%, 0.78→0.86 outQuad settles back) it pulses once upon intake; trailing `endCap` caption fades in after 0.84.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Source count | 4 paths (y=36/92/148/204, spacing 56) | 4 paths is the sweet spot for curvature contrast without knotting; >6 paths middle beziers nearly overlap and entry angles blur together |
| draw-on | Start `0.04+i*0.045`, window 0.17, outQuad | Stagger of 0.045 is ~7f; zeroing reads as four lines flushing simultaneously, losing "sequential connection" semantics |
| Convergence window | 0.34→0.74 (inOutCubic) | Spans 40% of duration as main movement; inOut ease-in starts motion and ease-out settles it, replacing with linear becomes a conveyor belt |
| Three-stage shrinkage | 44→15px (first 75%) → 0 (last 25%) | Pushing 0.75 inflection later makes swallow more abrupt; moving to 0.5 turns into gradual shrinking, losing the swallow impact |
| Packet cycle | 2 integer cycles (0.1→0.74 linear) | Must be integer cycles, otherwise packets freeze mid-path on final frame; increasing to 4 cycles feels rushed and collides with nodes |
| Packet phase offset | `i*0.13` | Staggers packets across four lanes to avoid parallel arrival; 0 makes four packets advance in lockstep like a convoy |
| Erasure | 0.78→0.9, negative dashoffset | 12f completion; erasure must occur after nodes vanish completely (conv=0.74 ends, nodes fade before 0.92), otherwise lines disappear with nodes stranded in mid-air |
| Emblem pulse | outBack +12% (0.7→0.78) → settle (0.78→0.86) | 12% represents "intake received"; >25% hijacks focus from convergence itself |

## Known Pitfalls
- `getTotalLength` / `getPointAtLength` are valid only after SVG mounts to DOM and layout completes; code uses `ready` flag in initial frame `prime()`—porting to Remotion might fail to retrieve length on frame 0 (fallback writes `|| 380`). Safe approach calculates after `useEffect`/layout or precalculates constant table, preventing frame-0 misalignment jumps.
- `f0` calibrates directly against 96px straight segment (`96/len`). Legacy 40-step linear scan had 1/40 precision, causing resting node position to drift from 74 and misaligning four nodes—altering path requires updating this calibration.
- Node opacity begins fading only after `conv > 0.92`, while conv reaches 1 at t=0.74, so nodes vanish via size collapsing to 0 rather than fading out. This is intentional (swallowing should not fade), but delaying three-stage inflection causes nodes to vanish while still visible.
- Nodes use porcelain placeholder disks with grayscale outline icons (demo: screenshot, shot card, code, audio; grayscale layering solely distinguishes four channels); in production replace with real source logos. Reserve accent color strictly for packets and ripples, never coloring nodes to avoid distracting from convergence hub. Hub emblem must rest on an opaque circular disk—curve endpoints and packets converge at center, so open-contour icons (like viewfinder brackets) without backing will expose raw wire ends.
- Convergence point (332, 120) and SVG viewport 440×240 with `overflow:visible` form a bound coordinate set. Changing canvas aspect ratio requires full recalibration; starting point -22 relies on `overflow:visible` to extend past frame edge.
- Caption "From screenshot to showreel" (video-shotcraft tagline) appears after 0.84—if paired with voiceover, align entry with spoken cadence rather than animation keyframe.

## Reference Implementation
demos/ui-entrance/bezier-source-converge-merge/
(BezierSourceConvergeMerge.tsx)
