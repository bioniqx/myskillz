---
name: value-stagger-gradient
summary: Sixteen bars rise in a staggered sweep where height, hue, travel distance and blur are each spread as a gradient across the row, then a second beat re-origins the stagger at the center so the pulse amplitude fans out symmetrically.
use: Demonstrating craft and parametric motion capabilities; directly applicable as entrances for data grids, audio visualizers, or equalizer interfaces.
duration: ~5.0s (150f @ 30fps)
energy: Medium-High (Beat one is a continuous rollout; beat two's center pulse is an explicit sharp peak)
---

## Intention
Stagger is typically used merely to offset time. This card demonstrates that stagger can also offset **values**—a single index dictates both "when it moves" and "how much it moves." The two beats form a controlled experiment: beat one originates at the first index (gradient unfolds monotonically left-to-right), while beat two relocates origin to the center (gradient unfolds symmetrically across the central axis). Viewers perceive not two disparate animations, but a single recipe with an adjusted parameter. Code captions on screen update synchronously to reflect the corresponding stagger invocation, rendering the concept explicit.

## Motion Core
- Core helper is an 8-line `staggerVal(i, n, a, b, ease)`: normalizes index to `k = i/(n-1)` then executes `lerp(k, a, b)`—equivalent to anime.js `stagger([a, b])` value mode, with optional ease curves for non-linear gradients.
- Static gradients (evaluated once in setup): hue `staggerVal(i,N,200,320)`, maximum height `staggerVal(i,N,92,32)`—16 bars naturally form an incline stepping from blue to purple and tall to short.
- Dynamic gradients (evaluated per frame): displacement `staggerVal(i,N,46,14)`, blur `staggerVal(i,N,8,2)`—first bar travels 46px with 8px blur, while final bar travels only 14px with 2px blur. **Every bar has distinct travel within the same entrance.**
- Beat one time stagger: `d = i*0.02`, `e = seg(t, 0.06+d, 0.28+d, E.outCubic)`—from index 0, 16 bars distribute across a 0.3 window; `opacity = e`, `filter = blur((1-e)*b0)`, `translateY((1-e)*y0)` + height `hMax*e` (bottom-anchored height growth prevents scaleY squashing rounded corners); all three driven by the same e.
- Beat two origin shift: `distC = |i - 7.5| / 7.5` is normalized distance to center, `w = seg(t, 0.56 + distC*0.13, +0.18)`—center bar initiates first, wave propagates toward outer edges, representing `from:'center'`.
- Beat two amplitude gradient: `amp = lerp(1-distC, 0.06, 0.42)`, center bar pulses 42% while edge bars pulse only 6%; `pulse = sin(w*π)` is a transient pulse, layering into height `hMax*e*(1+pulse*amp)` and `brightness(1+pulse*0.55)`.
- Syntax-highlighted code snippet swaps phrases vertically across ~5f at t≈0.52 (old phrase drifts up and fades, new phrase ascends from below), switching from `scale: stagger([1, 0.35])  hue: stagger([200, 320])` to `pulse: stagger([.06, .42], { from: 'center' })`—landing precisely between the two beats.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Bar count | N=16 (`left: 8+i*5.4%`, width 3.4%) | 16 bars provides sufficient gradient granularity; <8 bars feels like "different values" rather than a slope, >24 bars requires recalculating spacing |
| Time stagger | `d = i*0.02` (≈3f / bar, 0.3 total) | 3f creates fluid cascade; >0.05 turns into sequential roll call, eroding cohesive gradient |
| Single-bar travel | Window 0.22 (≈33f, outCubic) | Duration is 0.73x total stagger → ~10 bars moving concurrently for most of beat; duration < stagger total isolates individual bars |
| Height gradient | `stagger([92, 32])`px | 2.9x difference between ends forms distinct slope; <1.5x loses gradient perception, >4x makes tail bars invisible |
| Hue gradient | `stagger([200, 320])` | 120° span (blue→purple); <40° span lacks impact, >200° wraps around red, making slope feel circular |
| Displacement / Blur gradient | `stagger([46,14])`px / `stagger([8,2])`px | Core evidence of "value stagger"—setting these to constants reduces motion to standard stagger entrance |
| Beat two origin | `from:'center'`, `distC*0.13` | 0.13 is propagation delay from center to edges (≈4f); zero pulses all bars at once, rendering `from` parameter meaningless |
| Pulse amplitude gradient | `lerp(1-distC, 0.06, 0.42)` | Center 42% / edges 6% is a 7x ratio, producing distinct wave shape; boosting edges makes whole row swell together, obscuring center origin |
| Brightness pulse | `brightness(1 + pulse*0.55)` | 55% boost ensures readability on dark grounds; uniform across bars intentionally—stacking too many simultaneous gradients overwhelms focal clarity |

## Known Pitfalls
- Beat one and beat two meet end-to-end: last bar entrance ends at `0.28+15*0.02 = 0.58`, while center bar pulse begins at 0.56. Adding bars or increasing stagger encroaches into pulse phase, muddying the two beats—adding bars requires delaying 0.56.
- Edge bars beat two window is `0.69→0.87`, leaving ~0.13 (20f) of complete stillness before t=1. This provides reading time for viewers to observe the final state gradient, not dead space.
- Denominator `C=(N-1)/2` in `distC` divides by zero when N=1; `staggerVal` guards via `n<=1 ? 0`, but `distC` does not—setting N=1 yields NaN.
- Bar layout `left: 8+i*5.4%` and width `3.4%` are tailored for N=16 (right edge of bar 16: 8+15*5.4+3.4 = 92.4%). Changing N requires recalculating percentages to prevent overflow or left clustering.
- Subtitle is an anime.js API string, serving as **craft demonstration** rather than content. For production promos, replace with meaningful headlines or remove—otherwise audiences read raw code.
- Bottom 16 indicator dots (`bottom:17%`, opacity 0.35) are static decorations and do not animate; `left` offset `+1.2%` centers with 3.4% bar width; modify alongside bar widths.
- Dark backdrop (`#0a0b10`) + high-saturation bars (85%/66%) + 12px glow operate as a unified system; on light themes glow and brightness pulses vanish, requiring saturation or shadows instead.

## Reference Implementation
demos/ui-entrance/value-stagger-gradient/
(ValueStaggerGradient.tsx)
