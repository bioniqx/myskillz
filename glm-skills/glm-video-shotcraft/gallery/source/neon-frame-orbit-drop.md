---
name: neon-frame-orbit-drop
summary: After a neon frame draws itself, the camera arcs left to right while every page component drops from the air and lands on the same frame.
use: Grand single-take reveal for a single-page UI (contrasting with sectional tours); hero visual unveiling in dark neon aesthetics; sibling shot to neon-frame-forerun.
duration: Frame trace ~0.5s + rotation & simultaneous drop ~2.5s + settle ~1s; full segment ~4.7s (140f, rotation settles at 128f followed by rest)
energy: Medium-High (A singular sweeping gesture, settling into complete stillness)
tags: effects, camera
---

## Intention
Twin variant to neon-frame-forerun: similarly uses frame-first, content-after structure, but the camera is not static—it sweeps in a continuous arc from the page's left flank to the right flank, while all components drop from the air simultaneously during rotation. The non-negotiable rule is **simultaneous landing**: every component and text block launches on the same frame, descends on the same frame, lands on the same frame, and drops shadows in perfect synchrony—this is the visual syntax of a "monolithic entrance" (review ruling: staggered version rejected as "all components and text should drop from the air and land together"). Staggered landings belong to walkthrough shots (graze-face-tour); revealing an entire page in a single beat requires synchronous landing, and the two timing vocabularies must never be conflated.

## Motion Core
- Neon frame trace: gradient neon frame outlines across ~14f (identical to neon-frame-forerun).
- Perspective arc: rotateY +38° → -26° continuous arc (perspective-origin 30%→64% tracking camera orbit) spanning the entire sequence.
- Simultaneous drop: all elements share a single LAND cue (normalized ~0.52)—lifting into mid-air on the same frame, descending through space on the same frame, and locking to the surface on the same frame; FloatWrap soft silhouette shadows (blur/offset/opacity scaling with elevation) contract in lockstep.
- Background neon tube array frames the stage, stepping down once the main panel settles.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Drop synchrony | All elements launch and land on the same frame (zero stagger) | **Critical**: any stagger slips into walkthrough syntax (review ruling noted above) |
| Camera arc | rotateY +38°→-26°, perspective-origin tracking | Shallow arc reads as camera shake; rotation without drops feels like idle wheel-spinning |
| Rotation-drop coupling | Drop window centered within camera arc | Landing after rotation completes creates two fragmented shots; rotating after landing prevents clean conclusion |
| Elevation / Shadows | Matches graze-face-tour (100–180px, shadows track elevation) | Imperceptible shadow invalidates depth (accumulated rulings) |
| Frame trace | ~14f swift race | Identical to neon-frame-forerun |

## Known Pitfalls
- Parameters tuned over two review rounds with placeholder assets; verify against real assets in production.
- **Rhythmic syntax ruling** (this card and graze-face-tour are mutual counterparts): walkthrough shots use staggered starts + overlapping parallel drops; monolithic entrance shots use strict synchrony across all elements. Picking the wrong syntax triggers rejections on both sides.
- Division with neon-frame-forerun: that shot uses a fixed camera, staggered drops, and page illumination across three synchronized layers; this shot uses camera rotation and synchronous drops. Choose one per section; never chain consecutively to avoid repeating frame motifs.
- Arc rotation approximates camera orbit via perspective-origin rather than true 3D camera transforms; frame glow deformation flattens slightly at extreme angles—consider true 3D setups for wide-angle sweeps.

## Reference Implementation
demos/ui-entrance/neon-frame-orbit-drop/
(NeonFrameForerunOrbit.tsx)
Source clip: None (original synthesis)
