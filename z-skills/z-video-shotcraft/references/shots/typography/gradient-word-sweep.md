---
name: gradient-word-sweep
summary: A gradient light sweeps left to right across a keyword, charging each character with glow that decays behind the wavefront until the whole word breathes.
use: Charging a single verb / value-prop word in a slogan (Supercharged / faster / AI…); typography centerpiece in high-energy segments; slogan frame in dark-field brand films
duration: Sweep charge ~15–20f (must be fast) + steady-state lightning breathing 1–2s; full shot 2.5–3.5s
energy: High (single-word explosive beat, preceding and following elements should yield)
tags: effects
---

## Intention
Within a sentence of white text, only the keyword gets "energized": colorful gradient light sweeps across characters from left to right like an energy injection — brightest at the instant of sweep (the wavefront wake), decaying into a steady state; once filled, fine branching lightning arcs between characters while the word breathes in soft glow. Three critical rules:
**Fast** (sweep charge takes 15–20f; any slower reads as a progress bar), **Wavefront brightest** (freshly ignited characters exhibit the strongest effect, without which the gradient is a static wipe), **Restrained bloom** (AE-style multi-layer glow without devolving into a muddy blob; lightning must stay fine and sparse as an accent).

## Motion Core
- Gradient fill: Keyword uses a dual-layer text structure (white / gradient color); the color layer is revealed by a mask traveling left to right; the slanted mask edge has a slight soft blur (~8% word width).
- Wavefront wake brightness boost: A brightening band of ~34% word width follows the leading edge of the mask, peaking at the wavefront and decaying backward; after fill completes, it fades into steady state across ~10f.
- Bloom glow: 4 layers of bloom (large ambient soft glow + medium halo + inner core + bright core), with steady-state opacity in the 0.55–0.72 tier (empirical testing: the 0.75–0.95 tier was flagged as "overly heavy bloom").
- Lightning: After fill, fine branching lightning arcs between characters in magenta-purple palette (outer halo 6px / mid 2.4px / bright core 1.4px), with mulberry32 seeded random flashes, kept sparse and intermittent (not continuous electric arcing).
- Prohibited: Follower light dots or starbursts traveling with the fill (empirical ruling: a traveling white dot reads as cheap ornament and was deleted).
- Blurred glow layers cannot directly use the text box for mask/clip: blur overflowing the box gets clipped into harsh rectangular edges — the demo encloses these layers in a box expanded 90px in all directions, remapping mask color stops via `calc(PAD + (100% - 2·PAD)·x)` back to text coordinates.
- Demo duration `GRADIENT_WORD_SWEEP_DURATION = 105` (3.5s): entrance uses two staggered lines of blur-slide, sweep charge at 12→30f, 7 scheduled lightning bursts starting at 33f (final burst extinguishes at ~92f), full shot executing an ultra-slow push-in 1→1.025.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Sweep charge duration | 15–20f | Original reference was "very fast"; >28f reads like a progress bar |
| Wavefront boost band | ~34% word width, peaking at wavefront and decaying backward | Zero gradient = static reveal; band too wide = whole word lights up simultaneously, losing "injection" sensation |
| Steady bloom | 4 layers opacity 0.55/0.55/0.62/0.72 | 0.75+ tier was rejected as overpowering; fewer than 3 layers reads as flat color |
| Lightning stroke width | Outer 6 / Mid 2.4 / Core 1.4 @1080p | Doubling width was flagged as "too heavy"; color leans magenta-purple (magenta 216,60,190 palette) |
| Lightning frequency | Sparse and intermittent (≤2 strokes on screen simultaneously, interval >8f; demo schedules 7 events, 1 on screen, interval ≥4–11f) | Higher frequencies read as an electrical malfunction |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Three design precedents (established from verbatim user review feedback): 1) Never use traveling light points during fill; 2) Lightning must be magenta and fine-lined; 3) Keep bloom understated, letting wavefront gradient provide the punch.
- Division of labor with type-rhythm-sync: that card binds to musical beats; this card provides semantic "energy charging" for a single word, which must be the sentence's key selling point.
- Body text outside the keyword remains pure white and static — if the entire sentence moves, the drama of "only this word is energized" is destroyed.

## Reference Implementation
demos/typography/gradient-word-sweep/
(GradientWordSweep.tsx)
Original source: clickup-30.mp4
