---
name: light-play-moves
summary: Two controlled light effects: a spotlight sweep that reveals the title and a single sheen pass across a card.
use: Treating light as an expressive brushstroke (sweeping / brushing): dark title reveals (A), crowning hero cards (B)
duration: A 170f ~5.7s / B 150f ~5s
energy: A Medium / B Low
tags: typography
---

## Intention
The library previously treated "light" solely through spotlight-hero-card as a single pin-point highlight. These two variants systematize light into two brushstrokes with distinct responsibilities: Variant A is **sweeping**—a swinging conical beam illuminates a headline that is barely visible in the dark, lighting up wherever it travels (distinguished from spotlight-hero-card, which highlights a card, whereas this sweeps text); Variant B is **brushing**—a 45 deg specular sheen glides gently across a deep ink hero card once, clipped by rounded corners as a silent coronation.
All variations require dark canvases or dark hero elements—**brightening is invisible on white backgrounds** (precedent), which serves as the bedrock of this entire card.

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A spotlight-sweep | Dual-layer identical text: dim version 0.07 persistent, bright version radial masked to light spot, pendulum spotlight swings 2.5 cycles before damped settling at center, iris expands to full illumination (demo headline "Craft the shot.", concluding on video-shotcraft wordmark) | Dark headline reveal opening |
| B sheen-sweep | Deep ink card (demo: titanium black metal card, etched with monochrome video-shotcraft logo and wordmark) turns toward light source while 115 deg specular band sweeps once, clipped by overflow hidden rounded corners | Single coronation moment during a hero card's static hold |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Contrast | Dim version 0.07 vs full bright 1.0; demo pairs warm white #f8efe2 serif against burgundy-black velvet backdrop (#1a0a0d->#070203), backdrop itself illuminated only within the beam | Contrast is everything in this variant; dim version >0.15 eliminates the "illuminated" magic |
| A Light beam | 360px ellipse (hard core + wide soft penumbra), pendulum: x = 960 + 600*sin(theta)*env, theta begins at -pi/2 (far left), 50f period, runs 2.25 cycles to f121; y follows concave downward arc (lowest point 44px at center); envelope smoothly decays to 0 after first round-trip, x and velocity zeroing out at f121 concurrently (pure sin halts abruptly at maximum center velocity); light warmup flashes twice over 4–10f | f121–141 iris opens 360->1080px to full brightness (out-cubic), light cone collapses linearly into soft top ambient light (decoupled expansion/dissipation precedent) |
| B Specular sheen | 2x card width, 115 deg gradient: broad soft glow 0.14 + narrow bright core 0.5 (warm white, screen blend), swift single pass across 58–90f; card rotates Y 21 deg -> 14 deg concurrently (turning toward light = physical motivation for sweep); brushed metal texture and etched logo bright copy revealed under same mask | 0.5 core rings loud and clear against titanium black without blooming; bidirectional clamp + conditional mounting ensure exactly one pass |
| Unmounting masks | Sheen sweep (B) is conditionally mounted and unmounted immediately after pass; Variant A light cone dissolves into permanent soft top light | Opacity 0 residual layers still trigger per-frame compositing—unmount unused lighting layers directly |
| Finale | A ~30f / B ~55f hold; hold segment preserves only subtle micro-motion (A dust motes and top light breathing, B card rotates Y another 1.5 deg) | No handheld camera shake (Q3) |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- **Total lighting effects across video <=2 occurrences**—light degrades perceived quality faster than anything else; flashing on every card reduces work to cheap templates.
- Variant B passed high-standard retry: prior rejection (2026-07-13 precedent) addressed poor execution at the time, not an unviable path; four rigid constraints = single focal point + hero element + rounded corner clipping + single sweep only; violating any single constraint returns to the rejection zone.
- Dark backdrop is foundational: both variants strictly require dark backgrounds or dark hero elements; skip this card on white backgrounds.
- Variant A and spotlight-hero-card are mutually exclusive in the same video, as both share the "spotlight" vocabulary.

## Reference Implementation
demos/effects/light-play-moves/
(SheenSweepRetry.tsx / SpotlightSweepReveal.tsx)
