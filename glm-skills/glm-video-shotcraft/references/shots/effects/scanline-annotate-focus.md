---
name: scanline-annotate-focus
summary: A bright scanline travels down the page and, as it clears each block, camera framing brackets snap inward onto that region and a monospace caption types out beside it.
use: Analytical shots showing "AI reading your page or brand"; breakdowns of design systems and brand guidelines; product self-explanation sequences
duration: ~5s (150f @ 30fps)
energy: Medium (mechanically calm, paced by constant scanline movement, annotations serving as cadence beats)
---

## Intention
Turn the abstract concept of "analysis" into a visible chain of cause and effect: wherever the scanline travels, that section is framed and named. Viewers follow the "machine's gaze," which demands a constant scanline speed and annotations strictly lagging behind the scanline's passage—**scan first, frame second**. Disrupting this order turns an analytical process into a staged animation.

## Motion Core
- Strict division of color responsibilities: **Brand Color** (demo uses terracotta `#C4552D`) lives strictly within page content, while **Machine Color** (cobalt blue `#2B4FD8`) belongs solely to scanline / brackets / labels / status bar—enabling viewers to instantly distinguish "page content" from "machine vision."
- The page (demo displays video-shotcraft homepage: engraved mark + wordmark, H1, showreel card, CTA, color palette) is housed in a 1560x840 browser window (two soft drop shadows), with status bar above the window; camera pushes in very slowly from 1.000 to 1.035 throughout.
- Scanline sweeps window y: −20->860 from 6->80f at **strictly constant velocity**: 3px light core + 140px fading cyan wash + 18px dot-matrix afterglow; triangular cursors slide along window sides tracking the line, left side reading real-time `Y 0412`.
- Trigger frames derived from bounding boxes: `ft = frameAtY(y + h)` (the exact frame the scanline clears the **bottom edge** of a bbox), sorted by bottom edge and clamped to minimum 4f spacing; demo values: LOGO 19f, NAV 23f, H1 48f, CTA 68f, HERO 72f, PALETTE 77f.
- Reticle brackets: four L-corners (3.5px round stroke) converge onto the bbox from an outer 76px offset via `spring(damping: 15, stiffness: 210)` (single visible overshoot, slightly compressing past bbox before settling); arm length 40->26px shortens 3f later; cobalt blue focus flash (`ft+3->+6`, fill 0.075 + 2px inner stroke) settles across `+6->+18`.
- Label appears at `ft+5`: design-tool style cobalt pill with white text (height 50px, 32px monospace, category 750 weight / sub-item 500 weight · 78% white), text typed at ~2.2 chars/frame, pill width expanding with typing (right edge slightly leading) + white block cursor, floating up 8px->0.
- Status bar counts active detections in real-time `SIGNALS 0n / 06` + scan progress bar; 8f after final block triggers, switches to `BRAND READ` (switching to machine color), resting on full poster for ~60f hold.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Scanline | 74f constant velocity, window y −20->860 | **Zero easing**: adding easing feels like "someone dragging a progress scrubber"; under 60f labels finish too quickly and bunch up |
| Trigger conversion | ft = SCAN0 + (y + h − Y0) / (Y1 − Y0) * (SCAN1 − SCAN0) | Changing scan window requires updating only four constants (SCAN0/SCAN1/Y0/Y1), triggers track automatically |
| Minimum spacing | prev + 4f | Same-row items like LOGO / NAV trigger on same frame; clamping ensures each pops distinctly |
| Reticle convergence | Outer offset 76px -> 0, spring damping 15 | Offset by fixed pixels rather than proportional scale ensures identical convergence across different sized targets; offsets <40px lose the "targeting" gesture |
| Bracket corners | Arm length 40->26px, stroke 3.5px | Arm length exceeding 1/3 of target's short edge creates a full box, destroying the "reticle" metaphor |
| Focus flash | Fill peak 0.075 | Exceeding 0.12 creates a gray box on light backgrounds, reading as "selection highlight" rather than focus confirmation |
| Labels | Starts ft+5, ~2.2 chars/frame, 32px monospace | 5f lag establishes the causal chain that "framing locks before labeling"; drawing full pill width before typing exposes empty blue bars |
| Counter bar | Real-time tally based on fired count, 30px mono | Hardcoded counters drift out of sync when bboxes change; must tally dynamically |

## Known Pitfalls
- **Scanline trigger timing is tightly coupled to target bboxes**: measure `x/y/w/h` targets when changing content; bboxes are measured manually (not auto-measured elements), padding margins by ~12–16px.
- Four label placement options (`right / above / below / belowRight`), with width estimated using monospace char width `CHAR_W = 0.6em`; check whether expanding labels clip adjacent modules or window edges—place labels above wide elements like H1, and right-align labels below top-right targets.
- Use deep, saturated machine colors for scanlines and brackets on light canvases; pale glow lines are virtually invisible on light backgrounds.
- Division of labor with `scanline-assemble-flyin`: that card represents "scan to assemble" (page created from scratch), while this card represents "scan to annotate" (page already exists, performing analysis only).

## Reference Implementation
demos/effects/scanline-annotate-focus/
(ScanlineAnnotateFocus.tsx)
