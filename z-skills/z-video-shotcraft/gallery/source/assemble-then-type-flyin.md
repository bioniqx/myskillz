---
name: assemble-then-type-flyin
summary: Textless component shells fly in from every direction onto an empty dark grid, then every character arrives from 3D space with its own large rotation and settles into position.
use: Openings where a page or poster "grows itself"; capability showcases for typography and layout products; two-stage narrative from wireframe to finished design
duration: ~5.6s (168f @ 30fps)
energy: Medium-high (sparse during wireframe phase, dense during text phase, monotonically rising toward the finale)
---

## Intention
Split "page generation" into two semantically distinct stages: first assemble the wireframe skeleton (frames, cards, dividers, color blocks, all textless), then populate the text. Text characters arrive with individual 3D rotational landings because the skeleton stage uses only 2D planar translation—the two stages must inhabit different motion dimensions, otherwise viewers cannot register that "this is step two."

## Motion Core
- The assembled demo result is video-shotcraft's dark launch page (graphite look; film gold accent2 is the sole accent color; navigation bar features engraved mark + video-shotcraft wordmark; headline is the brand tagline "Frame motion. / Craft the shot."), in 1920x1080 native coordinates. At frame 1, 12-column layout guide rules appear first, fading out after the skeleton completes.
- 10 skeleton components (navigation bar, colorist desk card + film frame block, engraved mark, three color wheel rings, divider, CTA, secondary button, three metric blocks) fly in sequentially at launch frames 6/10/15/19/23/27/31/35/39/44, each with 16f `EASE.overshoot` snapping into place, with `from` translation 120–420px + ±7 deg rotation (rotation settles 4f later).
- Skeleton motion applies directional motion blur based on real velocity (px/frame) (`SpeedBlur` x0.32, capped at 18px), decaying to 0 when stationary.
- 19 text blocks begin sequentially across start frames 58->114: 112px serif headline lands first (58/66), followed by navigation, eyebrow, explanatory copy, button text (76–95), metric numbers (96–102), and finally mono micro-annotations everywhere (104–114).
- Character-by-character 3D: each character holds deterministic seed-randomized `dx ±260px / dy ±200px / dz −200->−760 / rotateX ±170 deg / rotateY ±190 deg / rotateZ ±120 deg`, driven by `perspective(900px) translate3d + rotateX/Y/Z`. Each character takes 16f `EASE.snappy` to land, with depth-of-field blur based on defocus distance during flight; when `a >= 1`, transform resets directly to `none`.
- Adaptive character stagger within blocks: `step = clamp((128 - start - 16) / charCount, 0.35, 1.6)` frames—guaranteeing that regardless of block length, all characters finish landing before frame 128, leaving a 40f static breathing tail (1.5% very slow push-in).
- The final "print proof" flourish upon settling: CTA charges from stroke into solid gold fill (118–132), film visual wipes from log gray to warm graded final look along a vertical gold line (124–146), and three color wheel control points slide synchronously from neutral to graded positions.
- All randomness originates from `rand(i) = frac(sin(i * 127.1 + 311.7) * 43758.5453)`, deterministic and seekable.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Skeleton timing | 10 items, launch frames 6->44 (4–5f intervals) | Skeleton phase occupies the first 30%; compressing within 20f blurs together with the text phase |
| Skeleton fly-in | overshoot, 16f, translation 120–420px + ±7 deg | Same technique as `scanline-assemble-flyin`; removing the scanline requires relying on sequence timing to communicate order |
| Skeleton trails | Directional motion blur, velocity x 0.32, capped at 18px | Appears only during rapid motion; permanent blur reads as out-of-focus |
| Inter-phase gap | Skeleton complete (f50) -> text start (f58) leaves 8f gap, guide rules fade out concurrently | Without this half-beat pause, viewers cannot register that "this is the second step" |
| Text start points | Headline 58/66, micro-annotations 104->114 | Large text landing first is a readability mandate: if small text lands first, viewers focus on small text |
| Per-character translation | dx ±260 / dy ±200 / dz −200->−760 | dz is the primary driver for "arriving from afar"; giving only dx/dy degrades into flat planar scatter |
| Per-character rotation | rotateX/Y/Z each ±120–190 deg | Large angles provide the tactile feel of "flipping in flight"; ±30 deg merely looks like jitter |
| perspective | 900px (declared on each character's own transform) | 112px headline with 600px causes excessive distortion; above 1400px the 3D depth virtually vanishes |
| Character interval | clamp((128 - start - 16) / n, 0.35, 1.6) frames | Upper bound of 1.6f is the lower threshold for "individually discernible characters" |
| Landing cleanup | a >= 1 -> transform: 'none' | Omitting cleanup leaves compositor layers for 19 blocks, causing frame drops in long videos |

## Known Pitfalls
- Character spans must follow normal layout flow (`display: inline-block`) with animation modifying transforms only—never use absolute positioning for character layout, or text edits will break everything.
- Space characters must be explicitly passed as non-breaking spaces (in code: `ch === ' ' ? '\u00a0' : ch`), otherwise empty inline-block spans collapse to zero width, losing word spacing.
- `start` uses 19 hand-tuned values; when updating copy (especially with large character count changes), verify that the final block still finishes landing before f128; `step` only guarantees constraints within blocks, not across blocks.
- Content uses video-shotcraft's sample landing page (headline / metrics / color wheel annotations); replace with project assets in production. GOLD (`#e4c58a`, graphite accent2) is the accent slot; CTA text color must switch from gold to dark upon charging.
- Distinction from `scanline-assemble-flyin`: this card has **no scanline**. That card relies on a scanline to explain assembly sequence; this card relies on a two-stage "skeleton first, text second" narrative. Do not conflate the two.

## Reference Implementation
demos/effects/assemble-then-type-flyin/
(AssembleThenTypeFlyin.tsx)
