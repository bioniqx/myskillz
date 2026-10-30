---
name: quad-split-parallel-scenes
summary: The frame hard-cuts into a 2×2 grid where four micro-scenes run in parallel — typing, a whip zoom, word pops, and a cursor interaction chain — with every beat offset by a few frames.
use: Montage beats in rhythmic sections conveying "many features running concurrently"; peak density moments in trailer midsections
duration: 90f (3s @ 30fps: 0–62f parallel bombardment + 28f final hold, zero transitions throughout)
energy: High (four parallel threads + staggered beat impacts, textbook BGM chorus placement)
---

## Intention
Substitute parallel density for sequential showcases: four events unfold simultaneously before the viewer's eyes. Audiences cannot read every detail line-by-line, but because one quadrant "acts" every 3–6 frames, the scanning rhythm is gripped tight. This is a methodology card: all in-panel content is replaceable—the staggered beat choreography is the true recipe.

## Motion Core
- Four independent quadrant scenes (sample content: four parallel moments during a video-shotcraft launch video production): TL browser tabs pop in with overshoot + address bar types out + page loads large title sliding up at 44f + continuous inQuad slow push 1->1.1; TR terminal command typing + two output lines + final line triggers whip zoom 1->1.85 (sine envelope blur 5px, old lines fade to 8%); BL three 132px headline words slam down with overshoot; BR review card slides in -> bezier cursor flies to Approve click -> button turns Approved -> secondary flight to Publish click -> deployment notification pops up and tallies.
- **Staggered timing is the soul**: TL tabs 6/11/16/21, page 44; TR output 27/33, whip zoom 37; BL words 14/30/49; BR click 25, recolor 27, click 52, notification 56—intervals between adjacent heavy events are always >=3 frames; something is always moving, but never in lockstep unison.
- Cursor blink cycles across the two typing scenes are intentionally offset (16f vs 14f + 5 phase) to prevent synchronous flashing.
- Four quadrants alternate in checkerboard luminance (ember palette: cream #f7eee4 / warm black #160d09 / solid orange / latte #e9d7c4), separated by 8px warm black seams + 20px rounded corners; inner text scaled for 1080p (auxiliary >=32px, hero words 132px).
- After frame 62, all four quadrants freeze in their final states (Launch film. / promo.mp4 ready / Prompt. Render. Ship. / Live · 3,214 views), composing a cohesive poster held for 28f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Stagger interval | 3–6 frames between adjacent major events | <2 frames reads as simultaneous (unison motion = mechanical rigidity); >8 frames dilutes density, destroying bombardment feel |
| TL Slow push | inQuad 1->1.1, origin 50% 90% | Accelerating "ambient floor motion" keeping static quadrants alive; excessive scale clips corner badges |
| TR Whip zoom | 37–47f, scale 1.85 + blur peak 5px, old lines fade to 8% | The heaviest punch in the shot, locking to BGM accent beats; blur envelope must be sine (symmetric entry/exit) |
| Typing speed | TL 20 chars / 0–40f, TR 19 chars / 0–24f | Maintain similar character counts when editing copy to prevent typing cadence from drifting out of sync with other quadrants |
| BR Interaction chain | Slide-in 4 -> travel 14 -> click 25 -> recolor 27 -> secondary travel 38 -> click 52 -> notify 56 | Interlocked sequence; altering any step requires offsetting subsequent steps; notification overshoot pop provides chain finale accent |
| Background tones | Checkerboard alternating light / dark / accent / light | Maintain >=15% lightness delta between adjacent quadrants when updating theme colors, or grid line separation dissolves |
| Finale | All quadrants hold final state for 28f after 62f | After parallel bombardment, viewers must receive a resting beat to absorb all four quadrants together |

## Known Pitfalls
- Methodology card: all quadrant content is modular and replaceable (product screenshots / screen recordings / other motion cards), but **the staggered timing schedule must be recomposed**—key moments in new content must map to the master timing chart, otherwise quadrants degrade into four disconnected video clips.
- ~2.1s of bombardment represents the upper limit of cognitive density; extending longer requires introducing a second wave of events to each quadrant to avoid empty stagnation; ending hold is budgeted separately.
- Cursor blinks calculate from frame numbers (periods 16f / 14f+5); verify phase offset when altering timelines.
- Simultaneous typing or simultaneous pop-ins across quadrants are the most common regression errors—audit frame-by-frame: no single frame should exhibit "heavy events" in two quadrants simultaneously.

## Reference Implementation
demos/rhythm/quad-split-parallel-scenes/
(QuadSplitParallelScenes.tsx)
