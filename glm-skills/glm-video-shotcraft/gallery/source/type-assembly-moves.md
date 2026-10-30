---
name: type-assembly-moves
summary: Three typography assemblies: split-letter rise, drifting convergence, and text flowing along a path.
use: Entrances for large titles / slogans; belongs to the broader title-entrance family alongside type-entrance-moves and document-typewriter-reveal; ≤2 types across full video
duration: 4–5.5s per variant (action segments: A ~56f / B ~104f / C ~110f; full demo duration including hold: A 130f / B 150f / C 160f, exporting respective `*_DURATION`)
energy: A Medium / B Medium-high / C Medium
---

## Intention
Title entrances already offer in-place transformation styles (character drop / typewriter — text morphs within its original footprint). This card introduces the "assembly" family: characters **converge from elsewhere** to form the title, where the motion trajectory itself tells a story.
Variant A (Piano Keys) — letters slide upward from behind an invisible baseline clip, crisp and rational, offering the highest versatility;
Variant B (Title Sequence) — characters drift in from scattered directions with defocus and lock in with deep ink pulses, evoking Stranger Things title sequence ceremonial weight, ideal for brand unveils;
Variant C (Semantic Path) — characters flow along an ascending curve in single file before standing upright, where the path can trace a financial growth chart, uniting typography and data into a single narrative.

## Variant Selection
| Variant | Technique | Use Case |
|---|---|---|
| A split-text-stagger rise | Each letter in overflow-hidden box: translateY(115%→0) with 10% overshoot, delay i×2f, baseline growing synchronously (demo: light background 136px brand tagline "FRAME MOTION.") | Universal default; crisp and rational |
| B drift-assembly convergence | Seed directions ±260–360px + blur 8px + rotation ±24° + depth scale 1.22 drifting into place with stagger, locking frames pulse deeper ink, full word breathes 1.04 after assembly (demo: light background 148px brand name "Shotcraft") | Brand names / cinematic title reveals |
| C text-on-path inflow | String advances along arc length with rigid physical spacing (tail letter leads, tangent rotation, legible in transit), sequentially rising along arc to upper-left title slot upon arrival (demo: midnight dark field revenue chart + metric badge) | When curve carries semantic meaning (growth charts / process flowlines) |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Variant A overshoot | 10% (14f out-cubic rising to -10%, then 6f rebound; original 6% was measurable but imperceptible, amplified in production) | Rebound must be visible at standard playback speed; add y-directional blur during rapid rise phase |
| Variant B lock pulse | Text color deepens to #000 + stroke 0→3px→0 / 8f | Deepening + stroke on white backdrops; do not use glow (design precedent) |
| Variant B drift binding | Displacement (1-p), rotation, depth scale, blur 8(1-p), opacity 0.35→1 share a single p (Easing.out(cubic), 45f/letter, 3f stagger) | Splitting curves causes letters to arrive while still blurry |
| Variant C leveling | Pauses 8f on arrival, then 1.1f stagger left-to-right, 18f upward lift: y uses fast curve with ~4% overshoot, x uses in-out, rotation converges 2f later → trajectory forms an arc; final position typeset from measured character widths | Failing to level leaves text perpetually "pinned to the line," unreadable as a title; overshoot >5% collides with eyebrow |
| Variant C curve | Path evolve (dashoffset proportional to arc length) grows synchronously with lead character; demo formats as financial chart (electric blue 5px stroke + outer glow + area gradient + cyan lead dot with peak pulse + grid ticks + quarter marks) | Drawing curve first and moving text second reads as two disconnected animations |
| Resolution | All characters settled with static rest ≥30f | Rule R1 |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- The title entrance category now encompasses five variants (three here + type-entrance-moves + document-typewriter-reveal); the iron rule of **≤2 types per video** (P4) remains absolute.
- Variants B and C demand high viewer attention — never stack camera moves during their execution; the lens must remain dead stable while text is flying.
- In Variant C, never let characters launch independently: trailing characters will overtake lead characters, clustering into an illegible ball at lower curve sections; advance rigidly along arc length with real glyph spacing so the entire sentence remains legible in transit. When font size exceeds 80px, glyphs clip corners on tight curves; use gentler curves or reduce character count for large type.

## Reference Implementation
demos/typography/type-assembly-moves/
(LetterformDriftAssembly.tsx / SplitTextStagger.tsx / TextOnPath.tsx)
