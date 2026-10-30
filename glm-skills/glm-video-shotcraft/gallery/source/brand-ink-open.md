---
name: brand-ink-open
summary: Ink crosshairs draw in, the wordmark stamps letter by letter, a subtitle types on, then the lockup holds and lifts away.
use: Brand opening; any title sequence that establishes the brand identity before entering the product
duration: ~2.8s (83f)
energy: Low (starting position, leaves climbing room for subsequent shots)
tags: typography
---

## Intention
Establishing brand memory on the very first beat: before any product visual appears, viewers clearly recognize and remember the name. Quiet, paper-and-ink texture, with a complete moment of stillness.

## Motion Core
- SVG crosshairs draw on (pathLength dashoffset), vertical first then horizontal, fading out once drawn.
- Wordmark letterpress letter-by-letter: scale presses from large down to 1 + blur->0, with accent color (amber in template) glint slash flashing across base.
- Kicker subtitle types on character-by-character, accent block cursor blinking periodically.
- Lockup holds completely static for a full 1 second, then floats upward + shrinks + fades out as a whole, handing off to dashboard.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Crosshair draw | Vertical 0->9f, horizontal 8->18f, fade out 24->34f | Must fade out after drawing; lingering crosshairs compete with wordmark for focus |
| Wordmark letters | Char i delay=10+i*3, 12f; scale 1.6->1 (origin center bottom) + blur 6px->0 | "Opacity + displacement/scale + blur->0" is the universal entrance triad; missing blur feels harsh |
| Kicker typewriter | 0.7f/char (starts 28, finishes ~43.4), cursor blinks every 2f, stops blinking at 74f | 0.7f/char applies only to decorative micro-copy; body interactive typing requires 3f/char (refer to type-and-filter, reworked previously for feeling too fast) |
| Brand hold | Frames 46->76, exactly 1 full second | Hard baseline: viewers explicitly requested "hold for 1 second after appearing"; shorter than 1s risks rework |
| Exit | 7f float up 40px + shrink 12% + fade out | Exit is faster than entrance—viewers have already read it, dragging it out dissipates momentum |

## Audio
Brand settling pins transition-soft (template pins at f12); brand->dashboard camera movement pins whoosh-fast (f78). SFX locked to exact frames with declarative table management; timbre draws from cinematic vocabulary rather than gaming UI taps.

## Known Pitfalls
- Hold must be given to wordmark settling moment, not regular text/content cards—previously mistakenly added to regular content cards and promptly rolled back; confirm target before acting on ambiguous "hold" feedback.
- Opening energy must start low: overall video energy curve starts low -> builds through middle -> peaks at outro; excessive opening flair suppresses subsequent build-up.

## Reference Implementation
demos/typography/brand-ink-open/BrandInkOpen.tsx (adapted from template/src/aifl/live/SceneOpen.tsx frames 0–83)
