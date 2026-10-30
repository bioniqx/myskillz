---
name: countdown-arc-scatter
summary: Numbers arranged tangentially along a large arc sweep past and brake to a stop, the winning digit sliding out of the dial to become the first character of the headline.
use: Countdown/time-commitment copy ("5 min to install"); data reveal moments; short light-background shots requiring an "instrument dial" vocabulary
duration: ~3.3s (100f@30fps: dial sweep ~30f + landing 20f + headline assembly + hold 22f; can be compressed to 33f single-shot minimum)
energy: High (large 96° sweep compressed into ~20 frames, pure impact)
---

## Intention
Writing "installs in 5 minutes" as a static title card carries zero credibility. Sweeping an instrument dial places this number into a **scale**: 45, 35, 28, 22, 17, 10 sweep past and brake hard at 5 — the audience sees a decline "from a lot down to very little," where the number proves its own claim. After stopping, "5" does not vanish; instead, it **translates directly to become the first character of the headline**. Having a single element transition seamlessly from gauge to copy is the highest-value technique in this card.

## Motion Core
- Arc layout: 9 digits placed around a shared center (native 1920×1080 canvas: center (960,1150), R=700, arc apex y=450),
  `ang = (i-6)·24`°, position `x = cx + sin·R`, `y = cy - cos·R`, rotated by its own position angle (`rotate(position angle)`) — **tangential layout**,
  tilting digits along the arc as if engraved on the dial; digits are 112px Helvetica bold tabular, identical size and weight.
- Full dial sweep: 5f reverse anticipation (+3°), followed by a physical spring 99°→0° (damping 12 / stiffness 60,
  overshooting 0° by ~2° at ~24f, settling at ~34f) — "decelerating hard stop + single pointer rebound" delivers all the landing force.
- Arc ends fade in/out: `op = clamp((70 - |pa|)/22)`, dropping to zero when position angle exceeds ±70°, gradually appearing within ±48° —
  **opacity calculated from angle instead of masks**, making digits appear to rotate naturally into view.
- Digit "5" at `i=6` is configured at angle 0 (resting dead center at arc apex upon sweep completion), launching 2f before rebound settles: 20f asymmetric in-out (EASE.swift)
  translates into the headline's first character slot, with the same curve driving 112→150px scaling and rotation leveling out. The first headline slot is a fixed-width 0.6em empty box,
  and the flying "5" uses a matching centered box, aligning landing position with slot center without swapping elements.
- The remaining 8 digits fade and defocus in place from 28 to 44f (`blur(out·6)`, **no displacement**, as movement would clash with the translation of "5"), clearing out 4f before "5" takes flight; directional motion blur along tangential velocity is applied during the sweep phase (dropping to zero when stopped).
- Dial visual hierarchy: a ring of fine tick marks rotates at dial speed inside the numbers (one tick every 4°, extended at digit locations); an accent-colored needle rotates at `rot·0.35`
  — a **0.35x differential speed**, creating layered depth between the dial face and pointer; outside sits a static hairline arc + top accent reading mark,
  retained at 35% opacity on the poster after the dial scatters (making the headline appear read directly from the instrument).
- Three headline words enter sequentially with `blur((1-p)·10)` + fade-in + 0.12em rise, across windows 42–56 / 46–60 / 50–66f (overlapping = one sentence);
  the final word interpolates from ink color to accent color (vermilion in demo) across 64–76f — the only color transition event in the shot; below sits a 34px monospace command line providing product proof (in demo: the real video-shotcraft install command `npx skills add Vincentwei1021/video-shotcraft`; upper right features the video-shotcraft wordmark).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Number sequence | `[45,35,28,22,17,10,5,4,3]`, 24° spacing | Unequal descending intervals (45→35→28…) feel like an authentic scale, whereas arithmetic progressions look like a ruler; "5" must sit at index i=6 (6 sweep past, 2 follow as padding) |
| Arc radius | R=700px, center below screen (arc apex y≈450) | Radius determines arc curvature: <R/3 bunches digits into a small circle, while near-flat arcs destroy dial feel; visible arc should span 60–70% of screen width |
| Sweep motion | +3° anticipation (5f) → spring 99°→0° (damping 12 / stiffness 60, ~2° overshoot) | Overshoot >4° feels like a spring toy; zero-overshoot in-out lacks instrument snap |
| Visible window | `(70-|pa|)/22` (fully transparent outside ±70°) | 22 is gradient width (~one slot); increasing to 40 makes digits enter semitransparent and blurry; setting to 0 hard-cuts them |
| "5" landing | 32→52f (20f, EASE.swift), 112→150px, simultaneous rotation leveling | Landing begins immediately upon sweep stop with zero pause — pausing splits the motion into two disconnected actions; landing target must be headline slot 1 (fixed slot width guarantees alignment) |
| Remaining digits fade | 28→44f + `blur(out·6)` | Fade begins **before** "5" launches to clear visual noise; blur ensures dissolution feels like defocusing rather than vanishing |
| Tick differential | Needle `rot·0.35`; headline word stagger overlaps ~10f, `blur (1-p)·10`px | Differential speed creates dial vs. pointer depth, whereas 1.0x reads as a flat spinning texture; overlapping word windows create a cohesive sentence |
| Final word recolor | 64→76f → accent color | The sole color event in the shot, landing on the final word as the sentence punctuation mark |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **33f is the absolute limit of compression** (motion-lab prototype: 17f sweep, 6f landing of "5", ~5f fade-in per word), where information density exceeds readability limits; the demo is tuned to 100f. When adjusting duration, scale windows by the **same proportional ratio** (proportions are balanced); do not stretch only the sweep phase.
- **Re-evaluate headline width when changing copy**: the demo uses `TITLE_EM` (estimated line em-width from char widths) to center the headline, and the landing target of "5" is derived from the fixed 0.6em initial slot — when copy changes, only update `WORDS` and `TITLE_EM` to auto-align landing, but recalculate line centering.
- Dial digits must be **identical in size and font weight** (demo: 112px/700): varying sizes read as data visualization rather than an instrument dial sweep.
- Angle design for "5" (i=6 → ang=0) is the foundation of this card: changing sequence length or selecting another hero digit requires recalculating angles so the hero digit evaluates strictly to 0 at sweep stop.
- Light backgrounds preferred: warm white paper background + ink digits + single accent color create this card's crisp feel; dark backgrounds require a complete palette redesign (and blur fade-out produces grey haze on dark backdrops).
- Audio: The sweep brake and the digit landing form two tightly linked rhythmic beats (separated by only a few frames); pair with two distinct short sounds (mechanical latch for braking, crisp snap for landing). Identical consecutive sounds blur into a single indistinct click; see sound-design.md for guidelines.

## Reference Implementation
demos/typography/countdown-arc-scatter/
(CountdownArcScatter.tsx)
