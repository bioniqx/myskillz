---
name: picker-carousel-feature-cycle
summary: A vertical mobile-style picker holds its focus pill still while the list passes through it, each item decelerating hard into place and resting for several frames before the next.
use: List shots reading out feature names or use cases sequentially; interactive demonstrations of "picking one option"; showcasing picker-style controls in mobile products
duration: ~3.6s (108f@30fps)
energy: Medium (every snap serves as a beat marker, advancing at a steady 5-beat pace)
---

## Intention
Crafting the physical sensation of "selection": the focus frame remains stationary while content rolls through and snaps into place. Each item must **truly pause for several frames** upon stopping—continuous scrolling reads like a loading animation, while pauses convey "this item is selected." Distance attenuation (simultaneous decay across opacity, font size, and grayscale) is the sole method to keep viewer gaze locked onto the center row.

## Motion Core
- Viewport 300x170px (5 rows x rowH 34), focus pill fixed at row 3 position (`top: rowH*2`), white background + 1px `#E3E3E6` border + `0 2px 8px rgba(0,0,0,.06)`.
- Total progress `t 0.05->0.95` partitioned evenly into STEPS=5 steps; step displacement `outQuint(min(1, local/(1-HOLD)))`, with HOLD=5/14 tail segment completely motionless (each step ~0.65s = travel ~0.42s + pause ~0.23s).
- List translated as a whole `translateY(rowH*2 - pos*rowH)`—content moves while pill has zero displacement.
- Distance attenuation (`d = |i - pos|`) split into three bands: opacity 1->0.55 when `d<=1`, 0.55->0.18 when `1<d<=2`; fontSize 17->14px (based on `d/2`); color uses INK when `d<0.5`, MID when `d<1.5`, and `#B9B9BE` further out.
- Inline icon opacity `max(0, 1 - d*1.6)`—only the focused row displays an icon.
- Settle breath on pill: `scaleY 1 + sin(min(1, land/0.6)*pi)*0.06` (where `land` >0 only within HOLD segment, breathing strictly after snap completes).
- Viewport top and bottom feature 26% alpha fade masks (`mask-image` transparent->opaque) for natural item entry and exit fading.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Row height / visible rows | rowH 34px x 5 rows, focus on row 3 | Visible row count must be odd, otherwise focus row is not visually centered |
| Steps | STEPS=5, uniform across window t 0.05->0.95 | 5 beats is comfortable upper bound for 3.6s; 7 beats compresses each to 0.46s, making it illegible |
| HOLD | 5/14 ~ 0.357 (tail pause ~0.23s per step) | **Critical linchpin**: zeroing HOLD turns motion into uniform scrolling, losing "snap" semantics |
| Snap easing | outQuint (applied to local/(1-HOLD)) | Rapid deceleration of outQuint provides "magnetic snap" feel; outCubic feels too soft |
| Opacity attenuation | 1 -> 0.55 (d<=1) -> 0.18 (d<=2) | Retaining 0.55 on adjacent rows lets viewers sense adjacent content; dropping to 0.3 feels isolated |
| FontSize attenuation | 17->14px, based on min(1, d/2) | Font size delta provides secondary depth; opacity alone feels flat |
| Icon visibility | max(0, 1 - d*1.6) | Only the focused row shows an icon, providing secondary marker for active item |
| Pill breath | scaleY 1->1.06->1, resolves within 0.6*HOLD post-settle | 0.06 is the upper ceiling; any larger reads as pill moving on its own, overshadowing content |

## Known Pitfalls
- Pill must be a **fixed layer with zero `translateY` displacement**; `scaleY` breath must not include displacement either, otherwise focus frame drifts and "content traversing focus" collapses.
- Driving distance attenuation via `fontSize` triggers per-frame reflow (row height is fixed so layout does not jump); if row height is set to auto it will jitter; rowH must be hardcoded.
- Use `mask-image` for alpha fading rather than overlaying solid background patches: if background has gradients or flares, patch masks reveal rectangular seam boundaries.
- Outer left 24x24 square app icon (dark base + inverted video-shotcraft logo) positioned relative to screen center via `margin:-12px 0 0 -186px`; modifying viewport width requires updating 186px offset.
- ITEMS consists of 7 video-shotcraft feature names ("Shot recipe cards", etc.); swapping for other feature names impacts centering—if a single line exceeds 300px, reduce font size rather than wrapping lines.

## Reference Implementation
demos/interaction/picker-carousel-feature-cycle/
(PickerCarouselFeatureCycle.tsx)
