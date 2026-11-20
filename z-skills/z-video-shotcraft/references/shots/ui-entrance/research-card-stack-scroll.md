---
name: research-card-stack-scroll
summary: Dark paper cards drop into the center every twelve frames and pile along a downward-right axis, squashing on landing while only the topmost card renders its full text as the rest blur into the stack.
use: Communicating scale for "processing vast literature / ingesting massive document volumes"; capability shot for research, search, and batch-processing products.
duration: ~4.8s (144f @ 30fps)
energy: Medium-High (Uniform high-frequency cadence without single explosions, maintaining steady pressure)
---

## Intention
The message to deliver is "volume," but presenting 13 cards simultaneously reads as an impenetrable wall. Restructuring into an assembly pipeline: cards arrive one by one, each actively read (the top card always renders complete text), and once parsed, sink into the pile with increasing blur. Viewers perceive a continuous processing throughput rather than a static stack. The background grid sliding downward at matching velocity provides velocity reference—without it, accumulation reads as "cards shrinking in place."

## Motion Core
- Timeline uses absolute frames rather than normalized t: internal `F=144`, card local frame `e = t*144 - i*12`; all choreography (entrance, stacking, depth) anchors to a fixed `PER=12` frame beat.
- Entrance is a brisk 6-frame motion: `seg(clamp((e+6)/6), 0, 1, E.outCubic)`—note start cue `e=-6`, meaning cards launch 6 frames before their nominal beat arrives, traversing `translateY(-40→0)` + `scale(0.94→1)`.
- Landing squash: when `e ∈ [0, 1.6)`, y-axis scale multiplies by 0.97 for just 1.6 frames—too brief to look like rubber deformation, reading as solid physical impact.
- Stacking drift: post-landing `drift = e/12*30`, shifting downward 30px and rightward by `XOFF=9`px per beat to establish a subtle downward-right diagonal axis; the axis ensures 13 cards display tangible deck depth rather than concentric stacking.
- Depth decay: `depth = min(1, drift/(30*3))`—decays fully across three beats, applying `blur(depth*4)` + `brightness(1-depth*0.25)`; further down `(drift-30*3.2)/(30*1.6)` pulls opacity to 0 for disposal.
- Exclusive focal subject: `focus = floor(f/12)`, where only the card matching `i === focus` displays its body (author line + 4 abstract skeleton bars), while remaining cards hide body content via `opacity:0` to expose only title bars—keeping exactly one actively read document at any instant.
- Background grid: `translateY((f/12*30*S) % 24)`, derived using the same `GAP=30` as card drift, locking grid and cards to identical velocities; modulo 24px delivers seamless looping.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Cadence | PER=12 frames / card, 13 cards | 12f is lower bound for "tight yet legible"; <8f titles are unreadable, >20f loses volume feel and becomes a slow gallery |
| Entrance travel | 6 frames (outCubic), advance offset -6 frames | Duration is half the cadence interval → each card settles before next arrives; duration ≥ PER causes two cards flying at once |
| Entrance displacement / scale | `translateY(-40→0)`, `scale 0.94→1` | 40px against 96px card height is compact—cards drop into place rather than flying across frame; 0.06 scale difference avoids reading as popups |
| Landing compression | 1.6 frames, y-axis ×0.97 | 3% squash is precisely perceptible; >6% or >3f duration feels like rubber deformation |
| Stacking axis | y+30px, x+9px per beat | Ratio of 9/30 sets axis slope; zero x creates concentric vertical stacking, flattening physical thickness |
| Depth decay | `depth = drift/90`, blur 0→4px, brightness 1→0.75 | Fully decays within 90px (3 beats) → leaves ~3 cards semi-legible on screen; longer decay stacks too many blurry cards, dirtying frame |
| Card recycling | Fades out once `drift > 96px`, reaching 0 in 48px | Recycling too early causes cards to vanish mid-frame; recycling too late leaves all 13 cards active, driving up DOM and blur costs |
| Coordinate system | Logical 420×250, wrapper `scale(min(W/420, H/250))` | Pixel values defined in logical coordinates, adapting to canvas resizing; card 296×96 and font 9.5px are logical units |

## Known Pitfalls
- Card volume and cadence are coupled: `13 cards × 12 frames = 156 frames > F=144`; last two cards are still entering at t=1, so final frame is not completely static. To achieve a frozen hold finish, restrict cards to `F/PER - 1` (≤11 cards under 12f cadence).
- `focus = floor(f/12)` can reach upper bounds (at f=144, focus=12, targeting final card)—verify focus does not point to invalid indices when adjusting card count or timing, which would leave no card sharp.
- Time constants assume 144 frames (`F=144`, `fr=f/F`). Altering duration requires scaling F proportionally, otherwise cadence stretches and loses 12-frame density.
- Titles are 13 realistic academic paper titles; `preprint:24xx` IDs derive from index; replace with real document titles in production; skeleton bar widths use deterministic pseudo-random seeds (`rand(i*5+k)`), avoid Math.random.
- Dark cards (`INK` background + `#2A2A2A` stroke) over light `#FAFAFA` ground establish the required contrast; on light cards, `brightness(0.75)` depth decay is barely perceptible, requiring opacity or grayscale decay instead.

## Reference Implementation
demos/ui-entrance/research-card-stack-scroll/
(ResearchCardStackScroll.tsx)
