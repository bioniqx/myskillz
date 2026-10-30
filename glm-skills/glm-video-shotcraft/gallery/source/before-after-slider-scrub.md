---
name: before-after-slider-scrub
summary: Before and after views share one frame while a fast-then-slow slider reveals the processed result.
use: Feature comparison segments for AI enhancement, optimization, or refactoring ("before vs after" explained in a single shot)
duration: 4–5s
energy: Medium (fast scrub is the impact beat, slow sweep is the reading window)
tags: interaction
---

## Intention
The standard comparison syntax for AI visual product promo videos: the "before" view (low contrast, hazy) and "after" view (crisp, processed) share one frame; a vertical divider bar with a circular handle first whips rapidly from the left edge to 70% (with overshoot rebound), pauses for a beat, then slowly sweeps back at roughly 1/5 speed to let the audience inspect the differences—**the speed contrast between fast whip and slow sweep creates the rhythm**: the fast whip announces "it changed," and the slow sweep proves "how it changed."

## Motion Stages
| Stage | Frame Reference | Content |
|---|---|---|
| 1 Rest | f0–14 | Bar holds at 8%, showing almost entirely "before"; f10–14 anticipates leftward recoil to 6.5% |
| 2 Fast whip | 12f | 8% -> 76% (out cubic) overshoot |
| 3 Rebound | 12f | 76% -> 70% |
| 4 Pause | ~18f | Lets viewers clearly inspect the "after" state |
| 5 Slow sweep | ~48f | 70% -> 40% secondary difference showcase |
| 6 Freeze | Final >=40f | Pure static hold |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Speed ratio | Fast whip 12f vs slow sweep 48f, ~5:1 | Ratios <3:1 lack perceptible rhythmic contrast |
| Reveal | After layer clip-path inset right boundary tracks bar x | Misalignment between bar and reveal edge breaks realism |
| Handle | Circular handle + speed-differential driven scaleX micro-stretch (peak 1.18), returning to 1 at rest | Stretch gives the handle physical weight as it is whipped |
| Before styling | Low-contrast hazy grade | Making "before" unrealistically ugly feels contrived; the deficiency must remain credible (real legacy version or unoptimized state) |
| Badges | Position BEFORE/AFTER badges inside content area | Demo review precedent: early version clipped into sidebar/avatar, creating visual overlap bugs |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Both versions must share identical layout and camera angle—differing layouts read as two separate pages, breaking the comparison (same constraint as theme-switch-moves).
- Use authentic screenshots for both before and after in production (Q1): before is a genuine state with legacy data or disabled features, not a contrived artificial downgrade.
- End the slow sweep at 40% rather than 0%—leave an "after" segment visible in the final freeze (keeping the conclusion on screen).
- Audio: fast whip whoosh + subtle tick on rebound; slow sweep is silent or has a very light friction texture (S4).

## Reference Implementation
demos/data/before-after-slider-scrub/
(BeforeAfterSliderScrub.tsx)
