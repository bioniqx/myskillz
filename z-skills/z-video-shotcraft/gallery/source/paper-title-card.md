---
name: paper-title-card
summary: A sentence stamps onto paper word by word, highlights one amber italic term, and closes with a short rule.
use: Chapter transitions / value-proposition title cards; introductory cards preceding major feature reveals; breathing spaces throughout full videos
duration: 1.7–1.8s (50–55f)
energy: Low (breathing beat, separating high-energy sequences)
tags: transition, rhythm
---

## Intention
Offers the audience a one-sentence breather between product feature sequences, clearly communicating "what you will see next and why it matters." The letterpress stamping tactile texture unites the title card with paper-and-ink product interfaces in the same visual world.

## Motion Core
- Single-sentence copy enters word by word: scale presses down from large to 1 + blur→0 + opacity (letterpress stamp recipe); demo copy uses the video-shotcraft tagline "Direct the film. / Let the agent shoot it." (accent word *shoot*); word lists support `br` for hard breaks, keeping line lengths balanced without orphan words.
- Exactly one keyword per sentence: italic + accent color (amber in template video).
- Accent-colored short rule contracts across scaleX 0→1 to conclude.
- Full card fades out at tail to hand off; optional monospace metadata subtitle + DigitRoll numbers can be attached.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Word-by-word entrance | Word i delay = 4 + i·4, 9f, bezier(0.2,0.75,0.3,1); scale 1.28→1 + blur 7px→0 + opacity | Scale start 1.28 is the sweet spot for a "letterpress stamp" feel — compare with dark-field TitleCard using 40px upward shift + blur 10, sharing light and dark variants of the same recipe |
| Keyword | Italic + accent color oklch(52% 0.115 65), exactly one accent per sentence | Two accents equal zero accents; choose a feature name or primary benefit word (C2) |
| Underline | 16→34f scaleX 0→1, 220×6px accent color | Underline signals resolution; its appearance warns that this card is concluding |
| Duration | Standardized at 50–55f (~1.8s) across all 4 cards in full film | Standardized duration — the time required to read one sentence; longer drags rhythm, shorter cuts off comprehension |
| Typography & layout | 116px / serif; paper backdrop oklch(97.5% 0.008 82) + center warm radial light; 8f tail fade-out | Paper background + warm lighting shares palette with product UI, ensuring cards never feel like ad interruptions |
| Subtitle row | Monospace small text + DigitRoll (demo: "12 shots rendered today"); see list-stack-press card for digit-roll counter parameters | Subtitle with concrete numbers offers the highest credibility; number roll must settle before card fade-out begins (lesson learned) — schedule beats counting backward from fade-out frame |

## Audio
Title card entrances uniformly anchor swoosh-quick (template video anchors four title cards at f220/565/725/885 to the same sound) — identical SFX for matching elements enforces vocabulary discipline (S2); the card itself features no landing impact, reserving energy for surrounding shots.

## Known Pitfalls
- Copy must be concrete: feature product names + tangible benefits; abstract metaphorical words were rejected by users during reviews (C2 — "one board" → "one place to go", added "Paper Radar"); rewrite copy against final shots once visuals lock (C1).
- Major feature scenes require preparatory title cards (C2 precedent: document scenes must be preceded by an intro like "Every project, linked to your weekly report") — title cards are chapter signposts, not mere decoration.

## Reference Implementation
demos/typography/paper-title-card/PaperTitleCard.tsx (originally template/src/aifl/PaperTitleCard.tsx, parameterized: words/sub/subDigits accept custom copy)
