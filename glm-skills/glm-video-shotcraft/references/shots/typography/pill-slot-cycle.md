---
name: pill-slot-cycle
summary: A fixed sentence keeps its trailing pill slot spinning like a slot machine through feature words until the final word locks the sentence.
use: The most elegant solution for feature enumerations (faster than itemized lists, more semantic than character reels); one-sentence value props with multiple verb phrases
duration: Entrance 12f + 21f per beat × word count + resolution 14f + hold; 6 words ≈6.7s (demo 200f, including 48f complete sentence hold)
energy: Medium (steady metronome, no peak)
---

## Intention
Listing six capabilities with an itemized list requires six rows, taking six beats of sequential fades that consume the entire screen. Word slot cycling condenses them into **a single slot within a single sentence**: the sentence stem "One skill to ___" (in demo: Storyboard it → Capture the page → Move the camera → Cut on the beat → Design the sound → Render the film) is the promise, each rolling pill badge in the slot is proof, and finally the pill launches away as "do it all." locks into place — evidence completed, conclusion stamped. The structure carries an innate three-act narrative: promise → enumeration → resolution. The critical requirement is that the sentence stem **remains completely motionless**: the viewer's eyes stay locked on the slot; any movement in the stem scatters the sense of enumeration.

## Motion Core
- Sentence stem is absolutely positioned with left edge anchored dead — **never use flex centering**, as pill width changes will trigger stem reflow (an early bug turned design precedent).
- Each beat is 21f (~0.7s): first 8f execute transition, followed by 13f static hold — the hold segment allows viewers to read words; unreadable beats defeat the purpose of swapping.
- Entrance: translateY 120→0 + blur 14→4→0, Easing.out(cubic);
  Exit: translateY 0→-130 + blur 0→10, Easing.in(cubic) accelerating upward
  — incoming words decelerate into place while outgoing words accelerate away, establishing an upward "page flip" directionality.
- Inside the slot, an invisible placeholder pill (visibility hidden) holds the container width, while incoming and outgoing pills overlay via absolute positioning — slot width adapts naturally to active words without jitter.
- Resolution beat: Final pill shoots upward (7f ease-in), while "do it all." enters from +90px below with Easing.back(1.4) overshoot — the sole overshoot in the entire shot, reserved for the conclusion; once landed, the full line glides smoothly to center across 26f (stem stays left-anchored during enumeration, moving only after the conclusion is complete), restoring normal word spacing between "to" and "do".

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Beat duration | 21f per word, 5–7 words | <16f is too fast to read phrases; >28f loses metronome drive; 8+ words make viewers count beats |
| Transition window | First 8f of each beat | Stretching to 12f+ keeps old and new on screen too long, looking like competing pills |
| Flight distance | In +120px / Out -130px | <80px feels like a stationary flash swap; asymmetric travel (exit slightly farther) makes departures decisive |
| Motion blur | In ≤14 / Out ≤12px vertical blur, calculated from real velocity (0 at rest); In rotateX -38°→0, Out 0→34° rotating along drum | Removing blur feels like a stiff bounce; >20px smears intermediate frames into colored blocks |
| Resolution overshoot | Easing.back(1.4), 14f | >2 makes conclusion look like a cartoon bounce; zero overshoot creates no tier separation from enumeration |
| Ending hold | Complete sentence holds static ≥45f | This sentence is the goal of the entire sequence; failing to hold renders the enumeration pointless |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- This card performs full-word pill cycling embedded within living sentences (not character-level or numeric reels) — use only when copy follows a "stem + verb phrase" structure; do not force-fit onto pure numbers or standalone headlines.
- Division of labor with typewriter-moves: typewriter builds sentences character-by-character; this card swaps modular parts within an established sentence — both can coexist in a film, but avoid chaining on the same line of copy.
- Division of labor with type-rhythm-sync: that card modulates properties of existing text to audio without swapping content; this card actively swaps content — when syncing with audio, simply align beat points with drum hits, avoiding redundant font-weight pulses.
- Keep pill phrase lengths comparable (demo longest: "Capture the page" / "Design the sound") — length variance >2x causes abrupt width jumps that jerk sentence balance.
- Concluding phrase must match stem font size and weight exactly (demo uses 96px/800 for both) — if "do it all." is larger than the stem, it reads as an unrelated new title rather than a sentence resolution.

## Reference Implementation
demos/typography/pill-slot-cycle/
(PillSlotCycle.tsx)
Original source: notion-ai 4.5–8.5s
