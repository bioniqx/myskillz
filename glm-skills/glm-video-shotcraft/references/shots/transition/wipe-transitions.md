---
name: wipe-transitions
summary: A geometric wipe: twelve staggered vertical blinds flipping in a wave.
use: Universal transitions where both outgoing and incoming pages remain stationary while a geometric boundary sweeps across to execute the handoff; independent of composition elements, usable anywhere.
duration: Prior state ≥20f + wipe ~56f + settle ≥40f, approx. 4.4s (132f).
energy: Medium
---

## Intention
The transition library already features three distinct families: travel moves (diving through), hidden cuts (occluding the cut), and physical slabs (the page as a solid entity). This card introduces the fourth family: **geometric wipes**—both outgoing and incoming pages remain stationary while a geometric boundary sweeps across the frame to execute the handoff. The geometry of the wipe defines its semantic character: vertical strip sweeps embody "venetian blinds flipping vane by vane to turn the page." Contrast with shot-transitions Variant C (portal mask wipe): Variant C relies on real in-page UI elements as masks (dependent on composition), whereas this card is purely geometric—its positioning lies in its universal versatility. Perfectly suited for lateral momentum and page-turning semantics.

## Variant Selection
| Variant | Method | Application |
|---|---|---|
| A blinds-slice | 12 true 3D vanes, each 160px wide (preserve-3d dual panels: front face displays Scene A slice, back face displays Scene B slice pre-rotated 180°, backface-visibility: hidden), sharing a 1900px perspective and rotating around their vertical axes rotateY(0 → 180°) in a staggered wave; edge-on rotation reveals deep shadow channels behind each vane | Page-turning / forward-progression semantics; pages with horizontal reading vectors |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Wave stagger | Starts at 24f; vane i launch frame = 24 + 28·(i/11)^0.78 (stagger interval tightens from 3.4f → 2.1f, accelerating through the wave); each vane driven by physical spring damping: 13 / stiffness: 75 (~13f to reach 180°, with ≈5° overshoot settling back) | 4–5 vanes must be rotating simultaneously to read as a cohesive "wave"; EASE.out stagger creates an initial 9f gap, leaving the eye waiting after the first vane and making the wave feel sluggish |
| Vane surface lighting | Faces turning away from key light darken by 0.5·sin θ (gradient across vane width); faces turning toward key light catch a screen specular glint at ~35°; vane perimeter carries a 2px highlight proportional to sin θ; the dark channel (#1d1712 → #120d0a) revealed edge-on serves as the boundary line | True 3D dark channels + surface specular highlights naturally form the "bright leading edge" of the wipe, eliminating the need for an artificial SVG seam line |
| Unmasking | Once the final vane's spring settles (|θ − 180°| < 0.3° for 4 consecutive frames, demo ≈80f), unmount all 3D vane layers and display Page B directly | Setting opacity to 0 does not equal unmounting; lingering clip-path or 3D layers destroy true static hold, and text inside 3D transforms lacks 2D vector sharpness |
| Settle | ≈50f settle after unmasking (≥40f; masthead hairline redraws once, camera settles from 1.02 back to 1) | R1 |

## Known Pitfalls
- Demo was calibrated and passed on grayscale/placeholder assets—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- Wipe boundaries must carry a highlight edge—a wipe without an illuminated leading boundary looks like a generic PowerPoint slide transition; this technique relies on dark channels revealed edge-on + 2px rim highlights along vane borders to serve as the boundary.
- Geometric wipes should appear ≤2 times per full video; avoid using consecutively (repeating "a boundary sweeping past" feels like a template).
- Unmasking must strictly wait until the final vane's spring settles (≈80f); unmounting even a single frame early causes a jarring visual snap.
- Contrast between the two pages must be stark (demo: warm-white paper vs. full-bleed vermilion; the two pages represent consecutive spreads of a video-shotcraft publication, masthead bearing the video-shotcraft wordmark, switching giant type "Frame." → "Craft."); the layout grid should ideally align with vane width (12 columns × 160px)—flipping between pages of the same color palette reveals only the dark channels without a satisfying wipe impression.
- Vignettes and grain should only be rendered once on the outermost master layer, never inside individual page slices (otherwise each vane slice carries an isolated gradient slice, creating ugly banding at seams).

## Reference Implementation
demos/transition/wipe-transitions/
(BlindsSlice.tsx)
