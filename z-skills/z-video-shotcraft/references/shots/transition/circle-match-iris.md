---
name: circle-match-iris
summary: An iris expands from a circular UI element and lands on a matching circle in the next scene.
use: Seams between scenes where the foreground has a circular element (avatar/icon/circular button) and the background has a circular hero subject (donut chart/circular progress ring); transition technique card.
duration: 5.5s / 165f (entrance + focal lock 40f + anticipation 7f + circle match & iris bloom 37f + sweep 58f + static hold 47f).
energy: Medium-high
---

## Intention
A standard iris wipe opens from an arbitrary point on screen, communicating nothing more to the audience than "the page changed." This card fuses the iris wipe with a **match cut**: the iris must detonate outward from the exact center of a **real circular element** in the foreground, expanding to reveal a circular chart in the incoming scene that anchors onto that exact same circle. The audience perceives that "the avatar circle transformed into the chart circle," allowing the geometry itself to carry the narrative progression (this person → this person's metrics). This is the UI-native realization of the match cut: grounded not in visual coincidence, but in semantic circle-to-circle alignment. Like the travel transition trio, the incoming scene is pre-present within the outgoing foreground, but anchored by an abstract geometry rather than a container.

## Motion Core
- **Strict concentric alignment between scenes is non-negotiable**: The anchor center coordinates are hardcoded as a unified set of constants (demo: `CX=540, CY=540`, calculated as leaderboard row left edge + padding + rank column width + avatar radius). The avatar, ripple rings, `clip-path circle`, incoming scene ring, and dial scale all reference this identical constant pair—calculating coordinates independently inevitably leads to visible concentricity drift.
- **Focal Guidance**: Competing rows are dimmed to ~32% brightness while the anchor row is highlighted; the avatar performs two scale pulses + emits two expanding halo rings (initiating at 18f / 30f); the camera applies an ultra-slow 3% push-in using the anchor center as its `transform-origin` (keeping the anchor stationary on screen), followed by the avatar contracting to 0.9 across 40–47f as an anticipation prep.
- **Circle Match = Solid Disc Hollowing into a Ring**: At the instant the iris opens, the incoming scene's ring stroke width equals its diameter (visually indistinguishable from the solid avatar disc). Across 28f, the radius expands from 36 → 300 while the stroke width contracts to 44px (`expo-out`), its color transitioning from fluorescent solid fill to a dark track; the iris radius equals the ring's outer perimeter + an ease-in accelerated outward bloom (+2400px across 54–84f), meaning "the expanding ring forces open the iris"—the circle match must lock in place before the iris consumes the full screen.
- The outgoing page simultaneously scales up from 1.03 → 1.22 centered on the anchor while dimming (`ease-in`), bordered by an outer drop shadow along the iris perimeter + a fluorescent rim sheen that appears exclusively during the initial bloom window—making the incoming scene visibly "press down" onto the outgoing page.
- **Ring Sweep**: `strokeDasharray = sweep × circumference`, starting from the top with `rotate(-90deg)`. Across 60–118f, it ramps from a slow start into a long tail reaching 87%; a 200px center counter increments in lockstep with the sweep, accompanied by a soft glow trailing the stroke tip.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Anchor pulse | 2x scale 1 → 1.16 + dual halo expansion (starts 18f / 30f, 22f each) | Without focal guidance, the audience cannot locate the origin center when the iris opens |
| Circle match | Solid disc → ring: r 36 → 300, stroke 72 → 44px / 28f expo-out | If the ring and iris grow independently, "avatar transforms into chart" becomes illegible |
| Iris expansion | Ring outer edge + 0 → 2400px / 30f bezier(.62,0,.32,1) | Faster than 20f makes the circle match unreadable; center offset >10px immediately shatters the illusion |
| Outgoing pushback | scale 1.03 → 1.22 + brightness 1 → 0.45 / 34f ease-in | If the outgoing page stays static, the incoming scene looks like an overlaid round sticker |
| Sweep | 60–118f reaching 87%, bezier(.4,0,.12,1), synchronized numeric counter | If numbers and sweep desync, they read as two detached animations; too fast (<40f) makes digits blur past unreadably |
| Outro settle | 47f static hold after sweep completes (retaining only 0.06°/f dial drift + arc breathing) | R1 |

## Known Pitfalls
- The demo is a handcrafted weekly video-shotcraft publishing leaderboard (dark stage with fluorescent green; Scene A creator ranking → Scene B weekly production goal ring)—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- On real production assets, measure anchor coordinates via devtools/rulers; what you measure is often the element box rather than the visual center—for padded avatars, extract the content disc center; if a test render shows slight misalignment, adjust constants directly rather than blindly trusting the initial measurement (same precedent as the letterform counter center in `transition-travel`).
- The foreground anchor must be a **true circle**: using a rounded rectangle (`border-radius < 50%`) produces an obvious shape mismatch the moment the circular iris blooms; if a production screenshot uses a rounded rectangle, patch it with matching solid background before overlaying a true circle.
- Semantics must align as a pair: avatar → personal data, product icon → product metrics—matching circle to circle is merely the form; "the contents of this circle expanding into its detailed manifestation" is the underlying justification that makes the match cut succeed.
- Adhere to the single-technique-per-seam rule from `shot-transitions`; because this card includes an integrated chart growth sequence, do not layer additional entrance animations onto the incoming scene inside the circle.

## Reference Implementation
demos/transition/circle-match-iris/
(CircleMatchIris.tsx)
