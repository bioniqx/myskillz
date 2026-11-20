---
name: element-body-moves
summary: A contact shadow that separates during lift, giving interface elements physical weight.
use: Providing physical presence beyond mere positional changes; establishing tangible proof of card hovering during 2.5D camera moves and card callouts.
duration: Variant A 150f (~5s)
energy: Variant A Low-Medium
---

## Intention
Motion cards in the library typically govern "changing positions"—fly-in, slide, bounce, while the elements themselves remain rigid bodies. This card governs **changing physical presence**: providing credible proof of hovering—as a card lifts, its contact shadow directly underneath simultaneously enlarges and diffuses, lifting paper off the surface to support 2.5D camera moves with physical staging. Unlike CameraMotionBlur (which handles shutter streaks), surface lift represents bodily depth.

## Variant Selection
| Variant | Method | Application |
|---------|--------|-------------|
| A contact-shadow-lift | On oblique overhead desk view (rotateX 24°→20°), card lifts translateZ 96px along surface normal + scale 1.05; shadow consists of two independent surface entities at z=0 (contact core + ambient shadow) expanding, blurring, fading, and shifting away from light source during lift; callout card lands 8f in-cubic + 2f micro-press, while final selected card springs up and hovers in mid-air | Card callout emphasis; depth staging for 2.5D sequences |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Variant A lift travel | 2D: −28px + scale 1.08; 2.5D oblique angle: translateZ 96px + scale 1.05 (screen visible displacement 40–50px) | Strict constraint: screen visible displacement <12px is prohibited |
| Variant A shadow | Independent div (2D uses elliptical radial gradient; 2.5D uses matching rounded rect + blur): contact core alpha 0.32→0.14, blur 3→25px; ambient shadow alpha 0.09→0.22, blur 14→54px, shifted bottom-right; card itself has no outer box-shadow | box-shadow follows the card, failing to convey "shadow remaining on the surface" |
| Variant A landing | scale 0.99 micro-press for 2f, then 5f rebound to 1 | Landing without compression reads as a weightless float |
| Hold finish | Final selected card hovers ~50f | To loop, set final card to settle back identically |

## Known Pitfalls
- Demo calibrated on grayscale placeholder assets—parameters serve as calibration baseline, not final production specs; verify against real assets in production.
- Micro-travel amplification rule: original 8px lift was imperceptible, requiring 28px to pass review—never reduce below 12px in production; omission is preferable to weak execution.
- Lift only one card at a time in Variant A—lifting two cards simultaneously deprives viewers of a clear focal subject.
- Audio: subtle intake on lift / gentle tap on landing.

## Reference Implementation
demos/ui-entrance/element-body-moves/
(ContactShadowLift.tsx: porcelain oblique angle tabletop with three video-shotcraft shot recipe cards "Pick your shot.", sweep—sweep—select, selected hero is Logo sting with emblem)
