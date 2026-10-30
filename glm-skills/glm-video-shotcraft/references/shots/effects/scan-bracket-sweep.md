---
name: scan-bracket-sweep
summary: A skeleton document pops to center, black L-shaped framing brackets drop into its corners, and a thin line with a gradient trail sweeps up and down across it five times.
use: Process shots depicting "analyzing / verifying this document"; capability demos for document products; mid-funnel sequences in upload-to-analysis pipelines
duration: ~5.0s (150f @ 30fps)
energy: Medium-low (mechanical, restrained, rhythm carried entirely by the breathing of reciprocating passes)
---

## Intention
Help viewers comprehend that "this asset is being inspected line by line by a machine." Framing brackets box the target first (declaring the object of inspection), and a scanning light band traverses the full layout back and forth (declaring the inspection process). The key requirement is that **the document itself remains completely motionless**: if the document also moves, viewers cannot distinguish whether it is "being analyzed" or "loading."

## Motion Core
- Document pops from scale 0.86 to 1 via `seg(0->0.11, outCubic)`, opacity reaching full brightness early via `dp * 3`; landing precedes scale stabilization—first "present," then "settled."
- 34px L-brackets at the four corners land sequentially with `i * 0.022` stagger, completing in 0.055 each, pulling inward diagonally with 8px travel from outside (overshoot easing, ~8% gentle rebound before settling).
- Scanning window `t 0.17->0.95` strictly linear, divided into 5 passes; within each pass, `inOutSine` eases ends slow and middle fast, leaving 12% full pause at stroke ends (`local = (raw - pi) / 0.88`).
- Scanning band = 1.2px indigo core + 10px symmetric soft glow + trailing tail; tail max length 82px, `SCAN .2->0` multiply blend, length expanding and contracting with scan velocity (collapsing to 0 at end-of-pass pauses to prevent reversal jumps); orientation flips with `dir`: trails above on downward passes, below on upward passes, gradient reversing synchronously.
- Table rows traversed by the light core illuminate subtly (row background SCAN 9%, gaussian decay)—light reads while document stays motionless.
- Entire light band is clipped within an `overflow: hidden` layer sharing the document's 10px corner radius, fading in `0.16->0.20` and fading out `0.93->0.99`.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Document pop-in | scale 0.86->1, t 0->0.11 outCubic | Starting below 0.8 feels like "flying in from afar"; pop-in should stay subtle to resemble real UI |
| Framing brackets | Arm length 34px, round stroke 1.6px, outer inset −7px; stagger 0.022 / duration 0.055 each | Simultaneous corner arrival reads like a static border; 0.022 stagger suffices to communicate sequential landing |
| Pass count | PASSES = 5, window t 0.17->0.95 linear | 3 passes feels insufficient to communicate "back and forth"; >7 passes in 5s feels frantic |
| Intra-pass easing | inOutSine + 12% pause at stroke ends | Pauses provide breathing space to "see the pass clearly"; omitting pauses feels like a constant metronome |
| Scanning band | 1.2px core + soft glow + <=82px tail SCAN .2->0 (multiply) | Lines >4px read like mask edges rather than light; dark gray tails read like dirt streaks |
| Trail direction | Downward: top: −tail / Upward: top: 0, gradient reversing; tail scales with velocity | Reversing only one causes trails to lead ahead of motion, reading like "light sucking inward"; fixed-length trails jump abruptly upon direction flips |
| Clipping layer | overflow:hidden matching document's 10px corner radius | Leaking beyond document boundaries turns "scanning a document" into "scanning the whole canvas" |

## Known Pitfalls
- Scanning band must be strictly clipped inside the document bbox with identical corner radii—any leak destroys the semantic clarity of "scanning this specific document."
- Trail `top` and gradient direction are configured separately; both must be updated synchronously when changing scan directions, or the tail will appear in front of the line, creating an unphysical aesthetic.
- Bracket 34px arm length and −7px offset are tuned for 300x178 document dimensions; recalculate for real screenshots—arm lengths exceeding 1/4 of the shorter edge will crowd content.
- Two core color variables: INK (brackets + body text) and SCAN (light core + soft glow + trail + row highlights); reskinning requires updating only these two variables.

## Reference Implementation
demos/effects/scan-bracket-sweep/
(ScanBracketSweep.tsx)
