---
name: stroke-segment-build
summary: Disconnected title strokes illuminate in a scrambled order and become readable only when the final segments snap into place.
use: Suspenseful reveals for product names or major milestones at video openings; <=1 time per film; division of labor with type-assembly / draw-svg-trace: those cards showcase "watching letters being built or drawn," while this card focuses on "delayed revelation of meaning"
duration: 165f (5.5s; reveal at f105 followed by 2s hold)
energy: Low start building to medium finish (suspenseful; landing frame serves as energy climax)
tags: typography
---

## Intention
The Alien opening title precedent: titles are not drawn, they "materialize"—deconstructed into discrete stroke segments lighting up out of sequence, keeping viewers guessing through 70% of the duration before the final key strokes click into place, suddenly revealing the word. The "moment of recognition" is the hook, and its power depends on how long illegibility is maintained and how late key strokes are delayed.

## Motion Stages
| Stage | Frame Segment Reference | Content |
|---|---|---|
| 1 Dark stage | f0–12 | Deep purple wall + faint wall wash at rest (not dead black) |
| 2 Scrambled lighting | f12–72 | First 13 segments start via ease-out distribution (intervals tightening from 9f to 3f); each segment features 7f neon ignition flicker (bright - dark - bright - half - bright), settling at 0.58 brightness |
| 3 Breath pause | f72–86 | 14f without new segments, holding only faint electrical hum—the tightest beat of suspense |
| 4 Key segments | f86 / f93 / f99 | S lower spine -> H crossbar -> P bowl base, landing across three distinct beats |
| 5 Revelation | f105 | All tubes surge from 0.58->1, current spiking to 1.25 before settling (signboard's wide glow surges once), text scales 1->1.02, illuminating wall and floor |
| 6 Still hold | f113–165 | Subtitle rises into hold, camera slowly pushing in 1->1.035 throughout |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Segmentation granularity | 4 letters across 16 segments (monoline geometric letters 260x400/char, tube stroke 30, round caps, 4% electrode gaps at terminals) | Too few segments weakens suspense; too fragmented reads like visual noise; S split into dual arcs of 3 segments each |
| Scramble order | Manually choreographed jumping across letters; "legibility key segments" (S lower spine / H crossbar / P bowl base) saved for final 3 segments | Sequential lighting eliminates suspense; early key segments ruin the reveal |
| Ignition cadence | Wide to dense (9f->3f, `stagger(.., EASE.out)`) -> 14f pause -> three beats at 7f/6f | Uniform intervals destroy tension; pause <8f goes unnoticed, >20f feels frozen |
| Illegible phase | First 13 segments (~60% duration) remain unreadable | QA check intermediate frames: "can viewers guess the word?"—if yes, reshuffle order |
| Half-bright to full | Suspense phase 0.58, reveal 1.0 + surge to 1.25 | Suspense phase too bright (>0.8) lacks contrast of "powering on" |
| Landing pulse | scale 1.02 + optical surge | Neon signs are physical wall objects; large scale jumps look fake; delegate impact to light |
| Wall lighting | Ambient light = 0.12 + 0.5 * active segment ratio + reveal/surge | Wall brightens with active tubes for physical plausibility; constant wall light diminishes ignition weight |
| Floor reflection | Mirrored along ground seam, blur 5px, opacity 0.42, fading with distance from seam | Mask authored in local coordinates prior to mirroring; space above seam must remain completely transparent |
| Inactive segments | Conditionally unmounted (not opacity 0) | Prerequisite for true static hold and preventing premature reveal |

## Known Pitfalls
- Demo is a neon signboard on aurora dark stage; adjust ignition curves and half-bright values when adapting to other materials (LED segment displays, glowing outlines).
- Supporting text on dark backgrounds requires light grey—initial top title used dark grey on dark background, rendering it invisible.
- Avoid drawing a separate radial glow for the reveal bloom—it creates a dirty hot spot in the center of text; let the signboard's native glow envelope (conforming to glyph shapes) surge instead.
- Floor reflections render the entire sign twice (each pass with dual SVG Gaussian blurs), doubling render cost; trim reflections first if performance is constrained.
- Character limit: 4–6 letter words are optimal; longer words make illegibility difficult to balance and segment count explodes.
- Relies on the "moment of recognition": title must be a word recognizable to the audience (product names, SHIP, LIVE); made-up words lack the payoff of recognition.
- Audio: segment lighting pairs with brief electrical ticks (sparse, descending volume steps), pause holds low-frequency hum, and landing frame delivers an impact beat + optional riser bed.

## Reference Implementation
demos/opening/stroke-segment-build/
(StrokeSegmentBuild.tsx)
