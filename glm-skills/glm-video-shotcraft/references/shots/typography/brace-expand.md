---
name: brace-expand
summary: A tight pair of braces appears at center, then springs apart and scales up to title size, revealing the text through a clip width bound strictly to the brace gap.
use: Title cards for developer/technical products; chapter openers; minimalist single beats where "a single symbol completes the reveal"
duration: ~4s (120f@30fps: cursor 0–6f → 6f small braces hard-cut → 14f spring open → 40–64f kerning relaxation → subtitle → hold)
energy: Medium (single overshoot is the only peak, remaining stationary)
---

## Intention
Among all title reveal techniques, this card is the most economical: no mask bars, no character-by-character reveals, no displacement — just a pair of braces expanding sideways while the text is "bracketed out." It naturally carries the semantics of code (`{}` are curly braces), so in the context of technical products it reads as "this is the content itself." The critical point is that clip width **must be strictly bound to brace positions**: once text fades in or wipes in on its own, the braces degrade into mere decoration, completely destroying the curtain effect.

## Motion Core
- Frame 0 opens with a blinking input cursor at center (editor semantics, not an empty frame); at 6f it is **hard-cut replaced** (no fade) by a pair of 0.4x braces with inner edges touching "{}" and held stationary for 8f — establishing "this is a pair of braces" first.
- Spring expansion `ex = springAt(f, 14, { damping: 14, stiffness: 130 })`: settles in ~8f after launch, reaches ~9% overshoot peak at ~11f, converges at ~24f, providing a single visible rebound.
- Synchronized scale-up `sc = mix(0.4, 1, ex)`; curtain half-width `x = (HALF - INNER)·ex·sc`, brace centers `±(x + INNER·sc)`
  (HALF=676, INNER=64) — **displacement and scale multiply together**, where scaling up itself also pushes the braces apart; when ex=0, the inner edges of both braces touch exactly.
- Text reveal width `clip.width = 2x` (strictly bound to the inner edges of the braces), with 14px feathering on both sides (feathering scales down when the clip is narrow).
- Text scales synchronously via `scale(sc)`, sharing the exact same sc with the braces; after settling, letter-spacing relaxes from -0.05em to -0.03em (40–64f smooth) — "taking a breath."
- Texture (midnight): monospace 300px electric blue braces + glow (glow peak follows the overshoot, receding across 34–64f), with directional motion blur applied along horizontal velocity during the rapid expansion phase (amount 0.22, capped at 16, 0 when settled); title (in demo: brand name video-shotcraft, all lowercase) 164px 800 weight white-to-cool-blue gradient; background editor dot grid (32px, radial fade) + top light + horizon light band, with a cool-light reflection beneath the braces expanding with the spring.
- Aftermath: eyebrow `// shot recipes for your agent` (monospace 32px cyan) enters with kerning contracting from 44f; subtitle (brand tagline "Frame motion. Craft the shot.") emerges from defocus starting at 54f; full frame undergoes slow push-in 1→1.012 across 70–120f.
- Layout uses strict absolute positioning (braces / clip box / text all compute left from midline 960), **no flex**: width changes continuously throughout, and flex will trigger reflow.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Brace appearance | 6f hard-cut replacing cursor | A hard cut is correct (the symbol snaps into existence); changing to a fade loses the frames needed to register the braces, making expansion feel abrupt |
| Expansion | Spring from 14f damping 14 / stiffness 130 (≈9% overshoot) | Overshoot is the sole peak in the entire shot; damping ≥18 reads like a generic slide lacking outward force; <12 rebounds twice, reading like jelly |
| Half-distance | HALF = 676px (brace center), INNER = 64px (center to inner edge) | Determines accommodated title width: inner cavity = 2·(HALF-INNER) = 1224px |
| Scaling | `mix(0.4, 1, ex)`, braces 300px / text 164px | 0.4 start represents a small font scale; starting >0.8 makes scale-up imperceptible; <0.3 starts braces looking like tiny punctuation |
| Copy width | "video-shotcraft" 164px measures ≈1130px settled (inner cavity 1224px minus edge feathering) | If text is much narrower than cavity, words fully reveal before braces settle, weakening curtain effect; if wider, ends get clipped |
| Kerning relaxation | -0.05 → -0.03em, 40–64f smooth | Represents "breathing after settling"; relaxing widens text, which must remain within inner cavity |
| Motion blur | SpeedBlur amount 0.22 / max 16 | At amount 0.35, peak frame blurs braces into three horizontal streaks, unidentifiable as braces |

## Known Pitfalls
- **Copy length must match HALF**: the clip only crops without scaling — longer titles get both ends clipped by braces, requiring a corresponding increase in HALF (or smaller font size); Chinese text is roughly twice as wide as English per character, reaching limits at ~6 characters.
- Clip width expands from 0, so text **always reveals from the center outwards**: the visual center of gravity must be centered (centered single-line short phrases work best); asymmetrical long/short phrases reveal awkwardly.
- Braces and text must share the exact same `sc`: writing separate scale curves (even with matching values) causes desynchronization during overshoot frames where braces arrive while text continues growing.
- Only one overshoot is permitted: all other motions in the shot have zero overshoot, keeping focus strictly on the "expansion" action; stacking additional back/spring overshoots dilutes impact.
- Clip box height is hardcoded at 220px (leaving top/bottom margins for 164px title); adjust when significantly altering font size to prevent vertical clipping.
- Audio: The expansion beat deserves a crisp, short mechanical/wooden snap-open sound, remaining silent after settling; see sound-design.md for audio guidelines.

## Reference Implementation
demos/typography/brace-expand/
(BraceExpand.tsx)
