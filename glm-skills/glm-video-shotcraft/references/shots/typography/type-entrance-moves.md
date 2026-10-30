---
name: type-entrance-moves
summary: Letters falling under gravity and bouncing into alignment as a title entrance.
use: Entrances for large titles / chapter title cards; mutually exclusive with type-assembly-moves (assembly style) and document-typewriter-reveal (typewriter style) within the same category
duration: 5s per variant (including hold and static rest; motion segment ~116f, demo 150f)
energy: Medium-high (physical playfulness)
---

## Intention
The title entrance library already includes typewriter style (sober, document feel) and assembly style (words converging from elsewhere); this card introduces physical comedy — characters plummeting from the sky, bouncing off the floor, settling at precarious angles, and snapping into perfect alignment on the final beat, ideal for lighthearted openers (demo drops the brand name "Shotcraft", with subtitle "Every shot lands on the beat." emerging on the snap beat). Title entrances across the same film must be ≤2 types (P4).

## Variant Selection
| Variant | Technique | Use Case |
|---|---|---|
| A letter-drop-physics character drop | Characters stagger from top, accelerating with gravity + dual decaying bounces + landing at skewed tilts, snapping upright in unison on final beat | Lighthearted openers; energetic character-driven title icebreakers |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Drop trajectory | Character i launches at frame 4 + 36·(1 - (1 - i/(n-1))^1.5) (first/last characters fixed at 4f / 40f, intervals progressively compress; demo 9 characters 6.5→1.6f); y = -DROP + DROP·(t/24)^2 (gravity) → 4u(1-u) parabolic bounce 30% → second bounce 9% | Bounce decay ratio 30%/9% is the sweet spot of "springy without chaotic noise"; 3+ bounces reads like rubber jelly |
| Skewed landing | Rotates to seeded hash ±6° upon impact and holds | Tilt angle provides half the physical character; perfectly upright landings read as generic displacement reveals |
| Snap beat | After all letters settle (e.g., frame 110), 6f ease-out collective rotate→0 + scale 1.06→1 | Collective snap is the exclamation mark — staggering the snap destroys the military precision of "standing at attention" |
| Resolution | True static rest ≥20f after motion completes | Rule R1: All properties locked dead during rest phase (including zeroed tilt angles) |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Impact sound is a strong audio dependency candidate (sound-design §4.5): character-by-character frame-accurate Foley doubles perceived physical weight; silent playback works but loses half its punch.
- No real physics collision between glyphs (demo uses independent trajectories per character) — spacing characters apart in layout is sufficient; simulating mutual collision requires prebaked physics simulations with high cost and negligible return.
- Avoid words with descenders (g/j/p/q/y) or adjust individual ground baselines — demo aligns baselines to floor; descenders will pierce through the ground plane.
- Title entrances command high viewer attention — avoid running other high-energy animations simultaneously in the same frame.

## Reference Implementation
demos/typography/type-entrance-moves/
(LetterDropPhysics.tsx)
