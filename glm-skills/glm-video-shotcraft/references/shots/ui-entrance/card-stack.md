---
name: card-stack
summary: Eight cards spring up from below the frame one after another and pile into a single stack, then the whole pile fans out into a 3D arc as each card rotates, slides sideways and steps back in depth.
use: Product sections establishing "we offer a complete collection"; establishing shot for card walls, template libraries, or solution lists; also serves as anticipation beat before a logo reveal.
duration: ~5.0s (150f @ 30fps)
energy: Medium-High (Entrance is a sequence of punchy pops; fanning phase consolidates into a single smooth group motion)
---

## Intention
A deck of cards gathers into a single stack before fanning out into an ensemble—the sequence is vital: present the "whole" first, then reveal the "individual." The viewer first absorbs a substantial deck (conveying volume), and only on second glance notices each card is distinct (conveying diversity). Reserving the fanning move for the end ensures it does not compete with the entrance cadence.

## Motion Core
(Demo version: Porcelain template library release—video-shotcraft shot recipe collection, 9 template cards at 320×440, native 1920×1080 coordinates)
- Two decoupled motion layers: entrance (individual spring per card) and fan-out (shared progress curve across all cards). Final transform combines calculated components inside `translate3d(tx, y, tz) rotate(rot)`.
- Entrance: launch frame `2 + stagger(i, 9, 40, EASE.out)`—EASE.out curve clusters arrivals toward the end (thump—thump—thump-thump, accelerating); each card uses `springAt(f, start, {damping:13, stiffness:150})`, `y` lifts from 820px to 0 (starting outside frame), settling in ≈20f; flight carries alternating ±9° tilt settling on landing, with vertical velocity motion blur (≤10px).
- Weight: each card landing (~6f after launch past destination) depresses the stack by 5px (9f sine envelope); resting stack carries deterministic ±3.2° / ±11px offsets, resembling a casually stacked deck; stack compresses 2% during 62–72f as anticipation before fanning.
- Fan-out: `springAt(f, 68, {damping:20, stiffness:95})` serves as the sole fanning clock (subtle overshoot conveys wrist flick inertia), final state `k = i-4`, `rot = k*6.5°`, `tx = k*138px`; `transform-origin: 50% 130%` places pivot below bottom card edge—simulating a deck fanning out around the hand.
- Stacking order = index (`zIndex = i`, left overlapping right like cards held in hand) throughout—top card is always the last card, avoiding top card jumping during fan-out.
- Camera: slow push 1→1.06 during stacking builds deck substance; concurrent pull-back 64→106f to 0.88 keeps expanded fan within frame; ground contact shadow widens from 220px to 760px alongside fan.
- Finale: center card (cobalt solid cover: inverted viewfinder emblem + "Launch", title Launch film) extracts 72px along its axis (overshoot) + 3px cobalt border + single glaze sheen pass (Q4), headline "Start from a shot recipe." (88px) rises word by word followed by subhead, holding 28f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Card count | N=9 (odd number, center card occupies exact midpoint) | 9 cards × 6.5° = 52° total arc is comfortable ceiling; >11 cards must reduce angle to 4–5° to prevent edge cards exiting frame |
| Entrance stagger | 40f span, EASE.out distribution | Accelerating cadence feels like a cohesive cascade; equal intervals feel like roll call, <20f feels like an undifferentiated burst |
| Entrance travel | y 820→0, spring damping 13 | Starting point must sit offscreen; damping <10 bounces multiple times, creating mutual visual jitter |
| Landing press | 5px, sin 9f | Primary source of tactile weight; >10px turns deck into a trampoline |
| Fan spring | damping 20 / stiffness 95 | Subtle overshoot resembles wrist inertia; damping >26 lacks overshoot and feels robotic, <16 causes fan to wobble |
| Fan arc angle | `k*6.5°`, lateral shift `k*138px` | Angle and lateral travel must adjust proportionally: increasing angle without shift causes cards to clip through each other |
| Depth | `tz = i*2`, perspective 1800px | Subtly suggests layering; depth relies primarily on stacking order + two-layer soft shadow |
| Pivot origin | `transform-origin: 50% 130%` | 130% determines distance from grip to cards; 50% 50% degenerates into a pinwheel dispersion |
| Card extraction | 72px overshoot + outline + sheen | Applied exclusively to center card; extraction <40px fails to read as "selected", >120px collides with headline |

## Known Pitfalls
- Two time windows butt end-to-end: final card launches 42f, lands ≈62f; anticipation at 62f, fan-out at 68f. Increasing card count or stagger encroaches on fan-out, creating muddy "turning while still flying" motion—adding cards requires pushing anticipation and fan-out start times back.
- Even card counts yield half-integer `k` (±0.5, ±1.5…), lacking a center card so the finale extraction skews off-center; demo uses 9 cards. If switching to center-over-sides zIndex, watch for top card switching abruptly between stack and fan.
- Cards at 320×440 center via `left = CX-CW/2, top = CY-CH/2`, fan pivot moves with CH; resizing cards requires checking margin safety for edge cards (at camera 0.88, outer corners sit ~100px from frame boundary).
- Card faces are mock template placeholders (generative image + title + mono metadata); replace with real page slices in production. Covers use pale cobalt / mint / ink tones, with only center card in solid cobalt—reserve one clear "hero" card in production.
- Camera pulls back to 0.88 across 64→106f to keep edge cards in frame; cutting to next shot works best after card extraction settles (≈120f) rather than idling on static fan.

## Reference Implementation
demos/ui-entrance/card-stack/
(CardStack.tsx)
