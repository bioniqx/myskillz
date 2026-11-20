---
name: icon-performance-moves
summary: An escalating attention bounce that compresses on landing to call the eye to an icon.
use: Half-screen close-up icon showcases; introducing new features
duration: 156f (5.2s)
energy: Anticipation build-up
tags: interaction
---

## Intention
The first entry in the library's icon animation category: the icon acts as a focal performer under a tight camera, not a passive UI micro-interaction in a corner. Attention-bounce borrows from the macOS Dock vernacular—the video-shotcraft app icon inside the Dock bounces 4 times in place, leaping higher each time (0.35 -> 1.2x icon height), compressing on each landing (final bounce: width 1.2x, height 0.8x) with ripple droplets. Neighboring icons rack-focus out of blur, and on the highest leap the camera gently pushes in 8% (drawn toward it). Once settled, a "New in Shotcraft" feature panel springs open—cutting "user attention" directly into the narrative.

## Method
| Variant | Method | Use Case |
|---------|--------|----------|
| A attention-bounce | Projectile bounce (duration proportional to sqrt(height)) escalating + airborne velocity stretch + 2f landing squash + ripple droplets, neighboring rack focus, peak leap camera scale 1.08 push-in, landing triggers badge + spring-unfolding panel | Feature introduction: "look at me" -> camera follows -> panel opens |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Icon size | 360–400px height (half-screen close-up; demo icon 360px) | Small corner icons perform invisibly—performers must own center stage |
| Escalating bounce | 4 bounces: 0.35 -> 0.6 -> 0.85 -> 1.2x icon height; airtime 14/18/22/26f (proportional to sqrt(height)) | Constant-height bounces read like loaders; escalation conveys "calling louder and louder"; fixed airtime feels weightless |
| Landing squash | 2f contact, compression 0.1 -> 0.2 escalating (final bounce: 1.2x width, 0.8x height), final bounce damped cosine settling | Missing squash = zero perceived weight |
| Camera push-in | Final bounce 72–90f smooth push 8%; neighbors 30–96f defocus to 7px, desaturate 30% | Camera motion enacts the viewer's "drawn-in" perspective |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Discarded bell-swing-alert from the same batch without note—pendulum-style swinging icons show questionable versatility; prioritize bouncing/explosive performance types for icon acting.
- Early versions breached the frame top (peak of final leap clipping); calculate bounce height against top canvas margins in pixels (demo: ground 960, icon 360, final peak 168px, ~119px after 8% camera push).
- Audio: ascending pitch "duk" on each landing, light "ding" chime on panel reveal.

## Reference Implementation
demos/effects/icon-performance-moves/
(AttentionBounce.tsx)
