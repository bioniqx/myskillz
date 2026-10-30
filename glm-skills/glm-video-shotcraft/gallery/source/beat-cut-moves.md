---
name: beat-cut-moves
summary: A three-flash freeze montage: white flashes hard-cut through different crops of the same subject and settle on the key number.
use: Highlight sequences turning the "cut" itself into a drumbeat; award-style paparazzi ceremony, crowning key metrics
duration: Total 140f ≈ 4.7s (live asset 30f + 3 flashes + 70f hold)
energy: High
tags: transition
---

## Intention
The library's rhythm vocabulary historically governed velocities "within a single continuous movement" (speed-ramp-freeze pauses and unfreezes a single take) and "hold durations after settling" (R-series breathing precedents), with no terms governing **how cut points are arranged across multiple shots**. This card fills that void: hard cuts employ zero transition easing, turning the cut intervals themselves into musical notation—three white flashes with tightening intervals (22f -> 18f), reading as a paparazzi shutter burst (Variant A). It does not conflict with R-series precedents: R governs pauses after settling, whereas this card governs cut arrangement; the cutting flurry must conclude with an ample resting hold to restore breathing space. Note that this is a deliberate exception: the pace preference precedent mandates "slowing down," so the harder the cutting flurry strikes, the longer the concluding hold must be.

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A paparazzi-flash freeze | Three white flashes each hard-cut to different crops of the same asset (wide -> card close-up -> "Take 1" macro), focus bracket locking the next crop before flash, shutter aftershocks settling, third flash resting on macro close-up (demo: video-shotcraft "Shot of the Year" medal card against tiled video-shotcraft logo/wordmark backdrop) | Highlight ceremonial moments: award-style paparazzi bursts, crowning key numbers and pivotal phrases |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Three flash cuts | 30/52/70 (tightening interval 22f->18f); 30f slow push on "live asset" (subtle flashes on backdrop cameras) pre-flash highlights post-flash freeze | Pre-flash state must be alive; static assets before flashes fail to register as a "freeze" |
| White flash layer | Each flash opacity 0.95->0 with 4f ease-out decay; flash frame ±2px seed hash full-screen jitter | Starting at 0.95 delivers photographic flash pop; decay >6f turns into soft glow transition, losing shutter feel |
| Shutter aftershock | Incoming view scale 1.03->1 over 6f ease-out recovery + −16px settling to zero | Aftershock conveys "camera recoil from the snapshot"; without it, flashes look like slideshow slide changes |
| Three crops | CSS zoom focal changes on identical frame: 1.0 wide / 1.6 card / 2.8 macro ("Take 1") | Progressive push provides narrative direction; scrambled order (macro -> wide -> macro) reads like an editing mistake; avoid slicing mid-line text |
| Focus prep | Reticle contracts from 1.3x to target crop bounds (screen coordinate projection) 8f before next flash, locking champagne gold 3f pre-flash | Acts as an "anticipation beat": viewers know where the next snapshot will land, making the flash feel like a shutter click |
| Finale | Macro holds 70f after third flash, with only 1->1.015 subtle push-in + HUD "SAVED" fading in | Three flashes deliver heavy impact; provide more than double standard hold duration; frozen stills are photos, avoid internal motion |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- **Strong audio dependency**: cut points must pin strictly to music beat markers with shutter clicks on every flash; silent versions degenerate into visual jitter; pin frames per sound-design.md §4.5 relative to shot start, not absolute timeline frames.
- The three crops must be "progressive zooms of the same frame" rather than three unrelated images—viewers must maintain visual recognition throughout; do not use across disparate products or scenes.
- Flash cutting flurries occur <=1 time across the entire video (P4 restraint principle): this is the loudest punch in the film; repeating it invalidates the first.
- The pace preference precedent mandates "slowing down"; this card is a deliberate exception—the concluding hold (70f) is a hard floor, not a suggestion: more is better than less.
- True hard cuts = render corresponding views based on frame intervals with zero transition frames; slipping in even 2f crossfades destroys hard cuts, immediately muddying the rhythmic cadence.

## Reference Implementation
demos/rhythm/beat-cut-moves/
(PaparazziFlash.tsx)
