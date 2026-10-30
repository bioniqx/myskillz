---
name: chip-grid-single-select-blackout
summary: Five option chips fade in, then a single grey press frame flashes before the chosen chip turns solid black with a tiny bounce while the others drop to eighteen percent without moving.
use: Interactive demonstration for single-select, subscription plan, or tier selection; causal shots showing "what happens after selecting this"; pricing and checkout parameter flows
duration: ~5.5s (165f@30fps)
energy: Medium-Low (the sole burst is that single grey flash frame; everything else is restrained)
---

## Intention
A 1-frame grey flash + 3-frame invert-to-black breaks down the two distinct states of real UI `:active -> :selected` into an explicit performance. Viewers see "finger presses" followed by "system confirms," rather than a vague gradient fade. The remaining chips drop to 18% opacity while their **positions remain strictly locked**: once rearranged, viewers will assume the page refreshed, destroying the semantics of "single selection."

## Motion Core
- 5 chips centered in 3+2 two-row layout (1080p native: height 96, corner radius 48, gap 22, 36px font, fixed widths 346/364/476/236/330), rising snappy at 3f intervals starting at 8f; top eyebrow title + 84px question arrive first.
- Cursor moves from bottom-right along swift arc to target chip between 26–54f (causal preview), pressing at 56f.
- **1-frame press grey flash**: Exclusively on frame FS=56, `rgba(120,128,146,.5)` overlay.
- **Invert-to-black**: 57->62f linear (5 frames) drives background white -> ink-black `#0b1020`, border, and text ink -> white, while checkmark grows from 0 width simultaneously.
- **Press rebound**: `sc = 1 + sin(pr*pi)*0.04`, pr traverses 57->66f—sine curve guarantees start and end settle precisely back to 1.
- **Deselection downgrade**: 57->66f outQuad crushes opacity to 18%, while `transform` remains strictly `none`.
- Hero lighting: Subdued cobalt blue ground light blooms beneath target chip after turning black (awarded only once to the hero), shadow deepening and enlarging with elevation.
- **Resolution**: From 101f onward (~1.5s post-selection), remaining chips zero out over 9f; black chip moves smoothly up to y=330 over 18f, scales to 0.88, and realigns to center line (geometry calculated from fixed widths, no runtime measurements); question simultaneously glides up and fades out to yield space.
- Settlement: Original price $42.00 rises at 108f -> strikethrough strikes it out and fades to grey at 118f -> discounted price $34.44 rises character-by-character from 116f (180px) -> cobalt blue "Save 18% · billed $413.28 yearly" pill pops with overshoot at 128f; hold across 134–165f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Entrance | From 8f, 3f interval, 16f snappy each | 5 chips fully placed within 1s, preserving time for selection sequence |
| Selection frame | FS = 56f (~1/3 of total duration) | Front section reads question, back section observes outcome; earlier than 40f leaves viewers insufficient time to read options |
| Grey flash | 1 frame, rgba(120,128,146,.5) | **Strictly one frame**: 2 or more frames reads like a hover highlight, not a press |
| Invert-to-black | 57->62f linear (5f) | Linear is intentional: adding easing gives "turning black" a gradual sensation, feeling too soft |
| Press rebound | 1 + sin(pr*pi)*0.04 over 9f | 0.04 is extremely subtle; reaching 0.1 turns it into a bouncy button, stealing focus |
| Deselection downgrade | Drops to 18%, position transform:none | **Locked position is essential**: dropping to 18% in place reads as "unselected" rather than "disappeared" |
| Resolution trigger | Starts at 101f (~1.5s post-selection), 18f smooth in-out | 1.5s is the minimum dwell time for viewers to register the selected state; compressing to 0.5s feels rushed |
| Upward narrow | Moves to y=330, scale->0.88, horizontal offset realigns to center | Without center compensation, upward shift leaves it offset to the left, reading as "dragged away"; scaling below 0.85 reduces font under 32px |
| Settlement order | Original price -> strikethrough -> current price -> savings pill, staggered by 8–10f | Display old price before striking out so viewers perceive the causality of "getting cheaper" |

## Known Pitfalls
- Re-centering displacement of selected chip is calculated from fixed chip widths (no runtime offsetWidth measurement)—update width lookup table when modifying copy, otherwise text overflows or shifts off-center upon elevation.
- Other chips must explicitly specify `transform: 'none'` rather than relying on flex reflow; otherwise remaining chips slide horizontally when zeroing out.
- Placeholder content: 5 billing cycle names (Annual billing ... Nonprofit rate) + settlement "$42.00 -> $34.44/mo, Save 18%", all replaced in production; excessively long option names break fixed widths (third option "Two-year commitment" acts as stress test).

## Reference Implementation
demos/interaction/chip-grid-single-select-blackout/
(ChipGridSingleSelectBlackout.tsx)
