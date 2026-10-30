---
name: grain-dissolve
summary: A clean line of text boils into displaced grain noise inside a hatched selection frame, then the particle cloud condenses into a larger glowing wordmark that locks sharp.
use: Concluding "XX. Now Live" launch announcements; energy-concentrating beats condensing sentence-level information into a brand shortmark
duration: ~2.0s (60f@30fps; grain burst 0.26–0.56s, condensation 1.2–1.42s, solidifying settle resolution)
energy: Medium-high (short, singular energy pulse; natural outro synchronization beat)
---

## Intention
Filming "distilling a sentence into a single word" as a physical event: the sentence destabilizes and boils into particles (dissolution of information), the selection bounding box implies "actively selecting and extracting," and then all particle energy collapses inward into a larger, brighter short wordmark—the audience registers that "all of this culminates in this."

## Motion Core
- Filter chain is the sole engine: `feTurbulence` (fractalNoise, baseFrequency 0.9 -> 1.3) + `feDisplacementMap` (scale 0 -> 52) + `feGaussianBlur` (0 -> 1.1px), all three driven by the same `burst` curve (t=0.13–0.28, outCubic).
- Grain "boiling" relies on frame-by-frame seed switching via `seed = floor(t*46)`—a new noise texture every frame ensures particles are never static.
- t=0.60–0.71 crossfade: the full sentence (26px) fades out while the short wordmark (44px bold) fades in, both sharing the identical filter—the switch occurs at peak boiling intensity so the font swap is invisible to viewers.
- t=0.68–0.90 `lock` curve brings displacement scale and blur back to 0, "freezing" particles into crisp typography.
- Three-stage white bloom: 0.3 subtle glow during grain burst -> surge to 0.7 at condensation peak -> settling back to 0.45 after t=0.88; dual tight and wide cool-white bloom layers inside the filter chain (feGaussianBlur -> feColorMatrix -> feMerge, radius ~4–33px) breathe synchronously; SVG is rasterized at native 1920x1080 to maintain ultra-fine particle fidelity.
- Hatched selection frame (45 deg diagonal rule array + 4 corner pixel-checkerboard handles) emerges with burst and withdraws at t=0.55–0.64—exiting prior to condensation so as not to upstage the subject.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| displacement scale | Peak 52 | <30 is merely "rough edges"; >80 scatters particles beyond legibility; "faintly discernible" is the aesthetic baseline |
| baseFrequency | 0.9 -> +0.4 | Higher frequency yields finer grain; below 0.5 creates chunky warping rather than sand grain |
| seed frame rate | floor(t*46), 46 swaps in 2s | Lower rates reveal repeating noise patterns; maintain >=20 frame updates/sec |
| Grain burst window | 0.13–0.28 (outCubic) | The initial 0.13s clean text hold establishes normal stability; cutting it destroys the contrast |
| Condensation crossfade | 0.60–0.71 (inOutCubic) | Must complete the text swap within the peak boiling window; premature crossfades expose overlapping ghost text |
| Glow envelope | burst * 0.3 + cond * 0.7 - settle * 0.45 | Condensation surge is the musical accent point hitting the BGM downbeat; do not settle to 0, leave warm residual ambient glow |

## Known Pitfalls
- The demo copy is `{ video-shotcraft. Now Live }` -> condensing into the `video-shotcraft` wordmark (all-lowercase); when swapping project names, update both `<text>` lines: the sentence `{ XX. Now Live }` and the wordmark XX must reference the exact same entity to avoid narrative disconnect.
- If the shortmark is longer (>6 characters), proportionally reduce font size or widen selection frame bw; otherwise condensation extends beyond frame boundaries, unbalancing the visual center—the demo's 15-character brand name reduced sentence font from 33px to 26px and shortmark from 54px to 44px, widening loose particle settle targets accordingly.
- `feDisplacementMap` exhibits lower performance in Safari; acceptable for a 2s short take, but longer takes require framerate profiling.
- Selection frame withdrawal (0.55–0.64) must precede completion of condensation (0.71)—leaving the frame up after condensation reads as "selection still in progress," reversing the intended semantics.

## Reference Implementation
demos/outro/grain-dissolve/
(GrainDissolve.tsx)
