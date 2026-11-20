---
name: typewriter-moves
summary: A three-act typing narrative: a plain word, a hesitation and deletion, then a faster retype of the selling point.
use: Slogan/value-prop title cards, negative framing copy; text entrance with built-in temporality
duration: ~5.3s (160f)
energy: Medium-low
tags: opening
---

## Intention
Typing is the only text entrance with built-in temporality — characters arriving one by one is rhythm itself,
requiring no auxiliary motion effects. Variant A treats typing as a **monologue**: typing out a mediocre word
(in demo: "just a slideshow" beneath the eyebrow Introducing video-shotcraft) → pausing in hesitation
→ backspacing to delete → retyping the true selling point ("your cinematic crew") with greater speed. This hesitation-negation-declaration
three-act drama draws all its emotional punch from the speed differentials between the three gears.

## Variants
| Variant | Technique | Use Case |
|---|---|---|
| A error-retype | Types at 2f/char → pauses 16f with cursor blinking twice → deletes at 1.5f/char → retypes at 1.5f/char without hesitation; cursor stays solid during typing/deleting and blinks only during pauses | "Second-thought" correction drama for slogan cards; negative-framing copy |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Character cadence | substring(0, floor((f - start)/step)), frame-deterministic with zero interpolation | Any smoothly eased typing reads as a generic software loading animation |
| Three-tier speed | Types at 2f/char, deletes at 1.5f, retypes at 1.5f with zero hesitation | The speed differential must be palpable — uniform typing speed reads as a bug rather than drama; this is critical |
| Cursor three states | Solid during typing/deleting = decisive; blinking twice across 4f half-cycles during pauses = hesitating; blinking twice after completion before conditional removal | The cursor acts as the actor's expressive face; blinking at constant speed throughout completely eliminates hesitation |
| Typography | Fixed-width span per character (60px monospace slot), left-edge anchored | Proportional fonts or full-string width measurement causes jittery reflow on every frame |
| Resolution | Static rest ≥50f | Even 0.05 residual cursor opacity destroys true static rest |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Strict audio dependency: Keystroke clicks must align frame-accurately per character, with lower pitch on backspaces (sound-design §4.5) — silent typing machines degrade into plain subtitle players.
- ≤1 time per film — rethinking and correcting is a one-time dramatic pivot; doing it twice sounds like stuttering.
- Must use either monospace fonts or character-by-character fixed-width spans; otherwise, the full line reflows as each character arrives, causing the text to spasm.

## Reference Implementation
demos/typography/typewriter-moves/
(TypewriterErrorRetype.tsx)
