---
name: ui-to-brand-morph
summary: Two UI-to-brand morphs: an icon flips flat and blooms into a logo mark, and an input field contracts into a capsule as glyphs assemble the logo.
use: Brand finale / penultimate outro shot; visual argument that "the UI you use every day is this very brand"
duration: A ~4.3s (130f) / B ~5.6s (168f)
energy: Medium-high (finishing touch, told through a single complete transformation)
---

## Intention
The brand outro library previously provided two main avenues: brand-ink-open is an opening draw-and-stamp, while outro-group-photo-launch gathers elements for an ensemble photo (assembling without morphing). This card adds a third: **product UI elements themselves morph into brand symbols**—Variant A flips an icon flat to become the logo mark (in-place entity exchange); Variant B gathers the input field that appeared repeatedly throughout the film into the brand logo after its final send action (multi-element drop-in assembly). The audience sees not just "a logo appeared," but realizes "the tool we just used is the brand itself"—the causal chain itself serves as the brand argument.

## Variant Selection
| Variant | Approach | Use Case |
|---|---|---|
| A icon-flip-bloom | Icon anticipation wobble -> Y-axis scaleX flattens into vertical slit (dual ghost trails + blur) -> entity swaps at thinnest frame, mark blooms from slit via overshoot spring, amber chamfer slices in at 45 deg -> mark shifts left to make room, wordmark settles letter by letter | Single-icon products; large morphological difference between icon and logo requiring a magical "flip-to-transform" reveal |
| B input-morph-assemble | Cursor clicks send -> text flies off, mark ink floods input box from send button -> 5 parameters (x/y/w/h/r) spring-contract into vertical stroke of viewfinder frame -> top crossbar, bottom crossbar, and amber chamfer drop staggered from offscreen into dashed construction slots to assemble the logo -> clears space for wordmark | Films where rectangular UI elements like inputs or cards are the hero; logos decomposable into geometric primitives |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Anticipation | 12–34f tilts -12 deg / +14 deg / -18 deg -> 0 deg, inOut(sin), transformOrigin pinned at bottom 78%; ground contact shadow shifts with tilt and narrows when flattened | Increasing amplitude communicates windup energy; a single wobble fails to register as preparation |
| A Flattening | 34–46f Easing.in(cubic), scaleX 1 -> 0.04; dual afterimage layers opacity 0.22/0.14 + blur 6px lagging by 0.12/0.24 | Acceleration is key to the whip-like snap; constant speed feels like a generic card flip; 0.04 is the thinnest moment where the entity swap occurs |
| A Bloom | From 46f, spring (damping 11, stiffness 130) drives mark scaleX 0.04 -> 1 (with overshoot); from 53f, chamfer spring (damping 16, stiffness 170) slices along 45 deg (cutProgress 0 -> 1) | The mark blooming from a closed vertical slit naturally continues the "flip past thinnest frame" motion; scaling the whole mark directly breaks causality; delaying chamfer by 7f creates the second beat—appearing alongside frame fails to convey "carving" |
| A Wordmark | Mark shifts left -471px across 64–82f (wordmark starts at mark + 187, centering whole lockup); letter-by-letter 2.6f stagger, 12f per char: scale 1.9 -> 1 + blur 14 -> 0 (snappy), origin on baseline; 112px brand font 700, +0.03em tracking (mark height ~ 2.1x font size) | Matching original: letters settle from large to small, blurred while large, crisp upon landing (coupled scale + blur settling letter-by-letter), not a horizontal wipe; stagger <2.4f makes the scale transition unreadable |
| B Send feedback | Cursor enters at 20f, presses with scale 0.84 + button flashes white 6f; text flies off top-right with 11f ease-in acceleration (+760, -420) + rotate -9 deg + motion trail | Departure must accelerate—constant speed reads as sliding rather than "sent" |
| B Color flood | 28–40f mark ink expands from send button via circular clip-path to fill input field (solid color throughout) | Gradient opacity fills pass through muddy semi-transparency; text must fly away before flooding, otherwise dark text clashes on dark ink |
| B Morph | From 30f, spring (damping 15, stiffness 95): 1040x132 r34 -> 89x330 right angle (viewfinder vertical stroke, squashing horizontal bar directly into vertical bar) synchronizing 5 variables, with <=3px motion streak scaled by spring speed; input box drop shadow withdraws in sync with morph | All 5 variables must be driven by the exact same spring; separate interpolation breaks alignment mid-flight |
| B Three-piece drop | Top crossbar / bottom crossbar / amber chamfer drop staggered at 58/72/86f (14f intervals), each via spring (damping 13) from -760px offscreen into slots; slots draw dashed construction outlines 10f prior (expanded 10px), fading out 14f after landing; speed-stretched / rebound-squashed (origin on bottom), carrying airborne shadows that flatten on landing | Stagger creates the cadence of "assembling"; simultaneous drop reads as rain; without slot preview, landing positions feel arbitrary |
| B Settle | From 108f, mark shifts left over 20f and scales to 0.7 (making room for 15-char wordmark), construction grid exits, 110px wordmark rises letter-by-letter (1.5f stagger) from baseline, slogan rises word-by-word; entire group pushes in ultra-slowly by 2% from 124f | Stillness after landing creates dead frames; per-beat scale breathing risks looking like jitter |

## Known Pitfalls
- The demo destination logo is the video-shotcraft glyph (A: soft light bright ground + amber chamfer; B: Swiss grid bright ground + cobalt construction lines)—parameters are calibration baselines, not production finals, and must be re-verified with real assets.
- In Variant A, entity exchange must occur on the thinnest frame with scaleX <= 0.05—swapping early reveals overlapping ghost shapes, breaking the magic.
- In Variant A, wordmark uses letter-by-letter scale + blur settling with 2.6f stagger; when adapting longer wordmarks, determine interval after reviewing at normal playback speed according to perceptibility standards.
- In Variant B, the mark is split into vertical stroke (= input field) + top crossbar + bottom crossbar + chamfer—in production, decompose the target brand logo into 3–4 primitives; too many primitives feels like particle confetti rather than structural assembly.
- In Variant B, anti-aliasing accumulates where same-color primitives overlap, causing a 1px stepped seam; upon completion (108f), replace vertical stroke + crossbars with a single unified path of identical geometry.
- Do not stack competing animations during morphing: the transformation itself carries all narrative weight.
- Division of labor with outro-group-photo-launch: that card gathers all film elements around the wordmark (assembly); this card transforms UI elements into the brand symbol (mutation). Choose one per video.
- Audio: Variant A gets a whoosh on flattening and crisp snap on bloom; Variant B gets a send click, pop on each landing piece, and silence during wordmark resolution.

## Reference Implementation
demos/outro/ui-to-brand-morph/
(IconFlipBloomLogo.tsx / InputMorphsIntoLogo.tsx)
Original source: A perplexity-promo 88–91.5s / B slack-promo 40–41s

Implementation status: Both variants have reference implementations and dynamic gallery samples.
