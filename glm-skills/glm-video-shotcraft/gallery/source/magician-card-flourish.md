---
name: magician-card-flourish
summary: A blue starburst flashes on black for a third of a second, then a card shoots out of the flash, spinning along an arc toward camera before freezing near full frame.
use: Magical entrance for single cards, posters, or covers (opening key visual, hero product card reveal); pure dark stage; visual burst requiring "summoned from thin air" theatricality
duration: 156f (starburst 0.3s + flight 1.6s + freeze/sheen/copy reveal + hold 3.3s; total 5.2s)
energy: High (singular burst beat; completely still after freeze)
tags: ui-entrance, effects
---

## Intention
A magician flourishing a card: a blue starburst flashes, and a card appears summoned from the light—catapulting from infinite distance at frame center (visually a pinpoint), spinning rapidly along an arc toward the camera, and hard-freezing the instant it reaches center into a near full-frame showcase. Three critical magical pillars: **flash leads** (light is the summoning ritual, lasting a crisp 0.3s), **catapult rhythm** (slow-in anticipation -> burst acceleration -> decelerating arc), and **freeze to stillness** (zero deceleration tail, zero rebound; 13 exact rotations guarantee facing camera upon freeze).

## Motion Core
- Opening starburst (refined across iterative user references):
  - X-shaped **diagonal** needle beams (-38 deg / 52 deg start), **dynamically rotating 90 deg** during flash (easeInOut); major axis 840 / minor axis 420 (2:1 ratio).
  - Pure saturated blue beams (#3f9bff->#2277f2 throughout, white reserved for root 5%), each axis comprising three tiers: wide blurred glow envelope + bright main beam + overexposed hairline core.
  - Center is **not a white sphere**: micro pinpoint (26px) + blue halo (140px) + ring of 10 alternating radial spikes (counter-rotating slowly with starburst).
  - Rhythm: brightens 2.5f -> shimmer -> collapse, resolving in 9f (0.3s).
- Catapult flight: Flash origin = landing target (screen left 1/3, cx=700) launching from deep perspective (scale~0.11), true perspective scale=F/(F+z) (z 14000->0); trajectory curve slow-in (first 14% time covers 6%) -> slope-jump burst -> easeOut(cubic) deceleration; single-arch sine arc sweeps top-right (passing future copy position) before returning to target; card carries blue glow in flight, trailing light streaks via motion blur.
- Spin: 13 full rotations along card diagonal axis; first 40% near-uniform rapid spin, trailing 60% angular velocity decays with 2.4 power (spinning slower near camera); integer rotations guarantee front-facing landing.
- Freeze: Full freeze at f=57 (TAKEOFF+48), card height ~86% frame height; instant blue pulse expanding and fading from card perimeter (22f), backlight and main stage lighting snapping on simultaneously (stage dimmed during flash to isolate starburst).
- Sheen sweep: Diagonal sheen sweeps left-to-right once after 8f of solid freeze (screen blend, clipped to rounded corners).
- Card face: Deep navy video-shotcraft "Launch Film" premiere ticket—brand header (logo + lowercase wordmark), centered video-shotcraft logo resting on concentric rings + crosshairs (starburst "imprinted onto card"; rings and crosshairs extend outward from logo perimeter), 58px headline (~100px post-freeze), monospace ticket stub row; holographic foil underneath logo shifts hue with spin angle (shimmering in flight, frozen on landing); card back also features centered logo.
- Right-side copy (post-freeze): Eyebrow NOW SHOWING letterspacing contracts at 63f -> 132px headline "Craft / the shot." rises across 67/74f -> 36px subtitle "Cinematic product videos, crafted by your agent." types word-by-word at 86f.
- Card laid out at freeze dimensions (x1.72) and rasterized via CSS zoom, scaling down for flight—ensuring razor-sharp typography on freeze frame.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Flash duration | 9f (0.3s, precisely tuned; compressed from 1.5s->0.8s->0.5s) | Light is ritual, not hero; >15f steals focus from card |
| Starburst rotation | Dynamically rotates 90 deg during flash (static angle previously rejected for missing rotation) | Rotation must be visible frame-by-frame; >120 deg reads like an airplane propeller |
| Beam color | Pure saturated blue throughout length | Long white segments or fast decay rejected as inaccurate; cyan-blue rejected for lacking deep blue saturation |
| Center core | Pinpoint + glow + radial spikes | **White solid sphere rejected**—center is an optical glow, not a physical ball |
| Trajectory curve | slow-in 14% -> burst -> decelerating arc | Constant speed or plain easeOut lacks physical catapult tension |
| Spin decay | Trailing 60% decelerates with 2.4 power | Uniform spin rejected: "should decay with distance near camera"; integer rotations guarantee front-facing landing |
| Freeze size | Card height 86% frame height (leaving right side for copy) | Initial 1.0x rejected as too small; centered card without copy can expand to 94% |
| Hard freeze | Total freeze with zero rebound | Magic sensation = instant stillness; rebound reads like a toy |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- **Lighting aesthetic precedent**: geometric blocks rejected as cheap effects -> optical realism rebuild -> gaming realism -> user reference image convergence; request visual references early when tuning subtle lighting qualities.
- Engineering gotcha: fine needle beams **must not be placed inside CameraMotionBlur**—rotation motion blur samples create striped ghost artifacts; render flash layer independently of motion blur.
- Engineering gotcha: starburst SVG viewBox must be >= beam length + rotation sweep radius, otherwise tips clip into flat edges.
- Division of labor with card-flip-reveal / deck-deal-flyin: those cards handle multi-card rhythmic card play; this card is a solo summoning ritual, revealing one card at a time.

## Reference Implementation
demos/opening/magician-card-flourish/
(MagicianCardFlourish.tsx)
Source: Custom user specification, converged across multiple iterations
