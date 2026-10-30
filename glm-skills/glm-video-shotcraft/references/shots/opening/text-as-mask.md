---
name: text-as-mask
summary: Product footage moves inside oversized title letters before the type expands until the footage takes over the frame.
use: Opening or chapter cards merging brand tagline and product footage; typography acts as the doorway, product lives inside
duration: 165f (entrance 18f + intra-glyph drift 78f + inhale 8f + plunge takeover 24f + settle/hold 37f)
energy: Medium-High (composed drift, explosive single burst during takeover)
tags: typography
---

## Intention
Typography and product footage competing for screen space is an age-old challenge—displaying typography before footage is slow, while overlaying typography on footage feels cluttered. This technique unifies both: glyphs act as masks, revealing product footage exclusively through strokes, allowing viewers to absorb copy and product texture simultaneously; at the conclusion, glyphs expand past frame boundaries, letting footage naturally take over the full screen—telling the story of "stepping through the brand into the product" in a single continuous shot while doubling as a chapter transition. (Shares lineage with transition-travel Style A counter-tunnel: there the camera dives into letter counters, whereas here letterforms expand outward—former moves camera, latter moves doorway).

## Motion Core
- Bright stage (porcelain cold white + key light + vignette) + SVG white-text black-background data-URI assigned to CSS `mask-image`, clipping product footage; matching blurred drop shadow layered beneath glyphs (also via data-URI), making typography feel like a carved window into the stage.
- Window content requires saturated color blocks and bright lines: demo features video-shotcraft dark render dashboard (cobalt->cyan streaming area chart flowing left, frame counter, pulsing render queue histogram; eyebrow is video-shotcraft logo, subtitle "From one prompt to a finished launch film."); during drift, dashboard shifts up 110px so bright lines cross glyph waistline while area gradient fills lower half of letters—white cards or light UI behind white letters read as plain typography.
- Entrance: mask wipes upward from baseline (clip-path bottom edge retracts, 16f) + 1.04->1 settle; eyebrow letterspacing tightens, subtitle rises.
- Intra-glyph drift: product layer scale 1.32 + translateX +150->-150 (f18–96, bezier(0.3,0,0.7,1) soft terminals)—static glyphs, flowing content: the illusion of "a world outside the window" is the technique itself.
- Inhale: f96–104 text scales 1->0.965 (swift), eyebrow/subtitle ease-in exit—anticipation before the major action.
- Plunge 24f (f104–128): mask wrapper `scale(0.965->46)`, interpolating in logarithmic space via t^1.8 (`S = s0*(46/s0)^(t^1.8)`, increasing scale multiplier per frame = accelerating plunge); **transform-origin must anchor within a solid stroke** (demo uses center line of letter L vertical stroke at 1236,546)—anchoring in counter cavities reveals background upon magnification; during plunge, wrapper translates `(960-Ox, 540-Oy)*t`, pulling stroke back to screen midline (otherwise off-center strokes require 30x to cover left edge).
- Content inverse compensation: outer `scale(1/S) translate(-d)` layer (sharing identical origin) offsets wrapper magnification and translation, keeping product visuals free from geometric distortion; dashboard simultaneously settles 1.32->1 with drift zeroing out (expo-out, f104–132, converging 4f after plunge = follower).
- Takeover safety: secondary unmasked full-screen layer sharing identical transform fades in only after stroke fully covers screen (t^1.8 in [0.86, 0.95], S~24x)—fading in earlier casts translucent grey haze over bright background.
- Settle: f132–165 full-screen dashboard holds, streaming chart continuing gentle flow (product alive, not a freeze frame).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Font size / weight | 470px / 900 (system-ui Black, letterSpacing -22) | Strokes are viewports—thin weights choke product visuals inside narrow slits; word width spans ~72% frame |
| Drift speed | ~3.8px/f (300px/78f) | Too fast blurs internal footage; orient drift along information-dense axis |
| Inhale | 8f, 1->0.965 | Plunging without inhale reads as sudden expansion; >0.94 reads as shrinking exit |
| Magnification | 46x (matched to vertical stroke width to frame ratio: 88px stroke requires >=24x to fill frame) | Insufficient magnification leaves stroke edge ghosts visible on takeover frame |
| Plunge curve | Logarithmic space t^1.8, 24f | Linear logarithmic = constant-speed plunge; exponent >2.5 remains static in first half before exploding in final 3 frames |
| Settle | Hold >=30f post-takeover | Takeover completion frame should land on canonical layout |

## Known Pitfalls
- Demo uses video-shotcraft render dashboard designed for shot (Render throughput, sidebar logo)—when replacing with real screenshots, ensure strokes reveal rich colors and bright lines; light pages must be dimmed or switched to dark theme, otherwise letters fail to read as "windows."
- Do not apply stroke outlines or specular highlights to glyphs: variable fonts like system-ui assemble from overlapping contours; strokes draw internal boundary lines across letters like A crossbars.
- Internal product visuals are viewed in extreme close-up—real assets must pass high-resolution rasterization guidelines; low-res screenshots blur inside strokes.
- Changing words or fonts invalidates manual origin coordinates—observe zoom direction post-render and nudge origin if cavity is off-center (same pitfall as counter-drift in transition-travel A).
- Do not combine with transition-travel Style A counter-tunnel in the same film—both embody "a world growing from within letters," reading as repeating the same trick.
- Mask layer and content layer transforms must be driven separately (wrapper expands, content applies inverse compensation); combining into one layer magnifies product visuals 26x into unusable distortion.

## Reference Implementation
demos/opening/text-as-mask/
(TextAsMask.tsx)
