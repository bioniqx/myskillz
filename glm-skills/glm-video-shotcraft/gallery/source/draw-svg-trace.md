---
name: draw-svg-trace
summary: An ink stroke traces an element outline, closes with a dark flash, and hands focus to the revealed content.
use: Calling attention to a single card, chart, or title during entrance; element-level technique (full-page blueprint tracing belongs to wall-reveal-moves Variant B).
duration: 132f (anticipation 10f + trace 40f + dark flash handoff 16f + underline 18f + hold 40f, ~4.4s)
energy: Medium
tags: typography
---

## Intention
"Drawing into existence" is the most natural entrance metaphor in ink-and-paper aesthetics: elements do not fly or fade in, but are sketched on the spot by an invisible pen. While wall-reveal-moves Variant B provides a full-page blueprint version (drawing fullscreen wireframes in segments before lighting up regions), this card serves as its **element-level close-up variant**—a single stroke, a single subject, a single closure with visible pen tip and clear direction, tailor-made for callout moments highlighting "what we discuss next." Its secondary application is title underline growth: the same 18f shorthand technique delivering a hand-drawn stroke under key terms, sharing aesthetic DNA with marker pen tokens.

## Motion Core
- **No perimeter calculation needed**: SVG rect/path sets `pathLength={1}`, `strokeDasharray="1"`, `dashoffset 1→0` (40f Easing.inOut(cubic))—eliminating `getTotalLength`.
- **Pen tip**: Same path overlays three tapering short dashes (0.04 / 6.4px → 0.024 / 8px → 0.011 / 9.6px) with `dashoffset = tipLength − p`, naturally leading the front edge; plus a solid nib with drop shadow positioned precisely along rounded-rect arc length. Without the tip it reads as an expanding border; with the tip it reads as being drawn by hand.
- Anticipation: Opening 0–12f sprouts crop marks at four corners (print registration marks staggered by 2f), atop graph paper dot grid fading toward edges—providing visual structure on frame 1 so viewers anticipate an element being drawn; crop marks bounce outward 22px and fade on stroke closure.
- Closure flash: 50–52f stroke hits solid black + thickens 6→11px, easing out 52–58f back to baseline—deepening and thickening on white backgrounds without glow effects.
- Handoff: 56–66f trace layer fades as hairline border fades in; from 50f onward card paper fills, card lifts from surface (shadow emerges), and content drifts up staggered 3f top-to-bottom from blurred to sharp, while bar chart grows from baseline staggered 1.5f—closure signals drawing completion, followed by content color fill.
- Secondary variant: 74–92f draws a vermilion marker underline beneath key term "100%" (curved hand-drawn path with following tip), holding permanently once drawn.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Stroke speed | Full perimeter 40f (10→50f, inOut cubic with breathing room) | <28f fails to read as "drawing", >60f feels like an idling loader |
| Main stroke / Tip | Main line 6px; three-tier tapering tip up to 9.6px, nib radius 7.5 | Tip thickness ≤ main stroke vanishes into the line |
| Closure flash | 2f punch black + thicken to 11px, 6f settle | Without this hit, completion lacks an ending punctuation mark |
| Hero element size | 1120×660, border radius 28 (stroke rx identical) | Hero occupies ~58% screen width, giving stroke scale; stroke rx must strictly match card border-radius |
| Underline variant | 18f out cubic directional growth, 12px vermilion, ±5px hand-drawn arc, holds permanently | Apply strictly to single key term; ≥2 instances on screen feels like decorative clutter |
| Hold finish | 40f static hold after handoff (92→132f), with 0.9% subtle push | Follows holding rules |

## Known Pitfalls
- Demo calibrated using mock video-shotcraft render report card (paper ink look, "Cuts on the beat / 100%" + per-shot energy bars + logo wordmark signature)—parameters serve as calibration baseline, not final production specs; verify against real assets in production.
- Mutually exclusive with wall-reveal-moves Variant B (full-page blueprint line drawing): pick one per film, combining both feels repetitive.
- Stroke path must strictly match element contour (matching corner radius rx)—tracing with 14px radius against an 8px radius card causes visible shape mismatch during handoff.
- Never fade in content before stroke closure on real assets: revealing content before line completes breaks drawing causality.
- Highlight one subject per callout; queuing multiple elements to trace outlines simultaneously looks like a loading animation.

## Reference Implementation
demos/ui-entrance/draw-svg-trace/
(DrawSvgTrace.tsx)
