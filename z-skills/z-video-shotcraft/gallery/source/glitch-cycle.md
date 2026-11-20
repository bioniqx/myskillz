---
name: glitch-cycle
summary: Status phrases cycle through one monospace slot, each dissolving into noise at both ends with RGB split and jitter, while a progress bar tracks the whole run.
use: Status reporting during load/build/deploy processes; technical intro "system self-diagnostics"; rhythmic background beds pushing time forward with a machine tone
duration: ~5.6s (168f@30fps; 38f per phrase in demo, with final phrase extending to shot end as hold)
energy: Medium-high (continuous high-frequency noise pulses, peaking at transitions)
---

## Intention
The clumsiest approach to status logs is fading in four lines of text one by one. Cycling compresses them into **a single slot**: phrases fuse into glitch at both ends and solidify in between, remaining pristine with only occasional single-character twitches in the middle — the audience reads "the system is advancing step-by-step," rather than four disconnected lines of copy. Glitch intensity is this card's grammar: dense = switching states, faint = dwelling in the current state. A bottom progress bar stitches the four beats into a cohesive timeline, while the final phrase settles probability to zero, concluding upon rest.

## Motion Core
- The slot pre-builds `MAXCH` spans sized for the longest phrase (`min-width:0.66em` fixed slot width), with shorter phrases symmetrically padded with spaces (centered row) — **characters are never added or removed, only content is swapped**, so the row never reflows.
- Time divided into equal slots: `slot = floor(frame / SLOT)`, intra-phrase progress `p = (frame - slot·SLOT)/SLOT` (demo SLOT=38f;
  the final phrase follows `KF_LAST` across the same 38f, remaining clean until shot end to leave ~28f for resolution).
- Glitch probability keyframes `KF=[1,0,0,0.1,0,0,1]` interpolated linearly against p: **1.0 full scrambled noise at start, 0 in the middle, rebounding to 0.1 around p=0.5 (occasional jitter), and returning to 1.0 at the end to fuse into the next phrase**.
- Final phrase uses `KF_LAST=[1,0,0,0.1,0,0,0]`, zeroing out probability at the end → clean frame at t=1.
- Character-level evaluation: `rand(i·31 + bucket·17 + slot·97) < g` triggers replacement with glyph-pool characters; hit characters randomly take accent highlight or dark tone (demo aurora: pink / dark purple); `bucket = floor(frame/2)`, rerolling every 2 frames.
- Row jitter and RGB split intensity both multiply by g (values in 480 design space; native 1920 in demo with 104px phrase): `jx = ±g·10`px (demo ±g·36), `jy = ±g·4`px (demo ±g·10), `text-shadow` offsets `g·3`px left/right (demo pink / ice blue each g·10, enabled only when g>0.04) — **a single noise intensity variable simultaneously drives glyph replacement, displacement, and chromatic aberration**, ensuring they never clash. When g>0.25, the same g drives a horizontal tear band (splitting line into three slices with middle slice shifted horizontally, band height rerolled every 2 frames); when g>0.45, 3 pixel block ghosts are layered.
- Demo layout: top status line (pulsing dot + RENDERING · project name · render number), thin corner brackets around slot, 1100px progress track below advancing linearly (underlying the four beats with three tick marks + glowing head) + `STEP n/4` / percentage (tabular-nums); when the final phrase settles cleanly, a soft bloom pulse triggers (awarded to the hero once), and after the progress bar fills, status switches to RENDERED, the dot turns solid, and an accent signature line rises (video-shotcraft logo + wordmark).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Phrase list | 4 phrases, longest 17 chars (demo `LOCKING BEAT GRID`) | 42f per phrase is the lower limit for readable status; with >5 phrases, sub-34f slots reduce phrases to meaningless flashes |
| Probability keyframes | `[1,0,0,0.1,0,0,1]` (6 segments) | The 0.1 middle value proves the system is "alive"; removing it makes phrases feel static; raising 0-segments to 0.3+ turns the entire shot into chaotic malfunction |
| Reroll frequency | Every 2 frames (`floor(frame/2)`) | 1-frame changes turn into a grey blur; >4 frames make scrambled characters legible as "another word" rather than noise |
| Jitter amplitude | `x ±g·10` / `y ±g·4`px (480 space; native 1920 ~3.6x) | x larger than y is crucial for horizontal tearing (equal jitter reads like an earthquake); exceeding ~2 character widths causes row to escape slot |
| RGB split | Left red / right cyan each `g·3`px, threshold g>0.04 | The hallmark of electronic glitches; without a threshold, the 0.1 mid-segment keeps text permanently frayed |
| Monospace slot | SF Mono 26px (480 space; native 1920 at 104px), slot `0.64–0.66em` | Monospace + fixed slot width are mandatory; 3px letter-spacing gives scrambled characters room to breathe, preventing clumped blocks |
| Progress bar | 150×2px (demo native 1100×4px), accent gradient fill, linear + 4-beat ticks | The sole linear element, providing a steady reference frame for the 4 noise beats; removing it obscures progression |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **Keep character counts close across phrases when replacing copy (demo uses 12–17 characters)**: Slot count is initialized for the longest phrase, with shorter phrases padded with spaces on the right — if one phrase has 4 characters and another 30, the short phrase sits isolated on the left while line width is held wide, reading as awkward drift.
- Probability keyframes map across 6 equal segments within each phrase: changing phrase count alters phrase duration, but keyframe shapes remain constant — so more phrases compress the absolute duration of the 1.0 glitch phases, weakening transitions; if exceeding 5 phrases, widen the 1.0 segments at both ends.
- The final phrase must use `KF_LAST` (ending at 0): using standard KF leaves t=1 frozen on scrambled noise, making the next cut feel like an unfinished render.
- Dark backgrounds only: dark backdrop + cool/vibrant noise form the foundation (demo uses aurora deep purple-black + pink/ice blue split); RGB split is virtually invisible on light backgrounds. Sound is also critical — the four transition points are natural rhythm points that require electronic glitch/switch SFX; see sound-design.md (use identical SFX for matching elements, alternating two samples to avoid machine-gun repetition).

## Reference Implementation
demos/typography/glitch-cycle/
(GlitchCycle.tsx)
