---
name: riso-print-hits
summary: A risograph impact: a single misregistered colour split that snaps into alignment.
use: Emphasis hit for titles and cards, serving as an ink-and-paper analog to digital glitch flashes; 1–2 standalone climax hits per video
duration: 4s (120f, single hit)
energy: High
tags: typography
---

## Intention
RGB chromatic aberration glitch flashes (part of impact-feedback Variant C) belong to the language of phosphor screens, conflicting with paper-and-ink aesthetics. This card provides a printmaking equivalent: the element splits into two monochrome risograph printing plates (demo: fluorescent pink x blue; using `multiply` for physical ink depth rather than `screen` fluorescence, blending into dark ink when aligned), mimicking an off-register risograph that shakes before snapping sharply into perfect registration—delivering identical impact while grounding physical imagination in ink on paper. Single hit: splitting on crash stop, damped oscillation, hard cut into alignment, stamping authority onto a key landing. Demo features a two-color riso promotional poster for video-shotcraft ("CRAFT IT / LOUD." + 3-column feature highlights, with monochrome engraved mark at stamp center).

## Method
| Variant | Method | Use Case |
|---------|--------|----------|
| misregistration-hit single | Title crashes in over 8f, splits into two plates offset ~40px in opposite directions, shakes with 44f damped oscillation before hard cutting into alignment + scale pulse + "ON REGISTER" circular stamp drops | 1–2 signature hit stamps per video; headline / hero text arrival moment |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Dual plates | Two riso inks: fluorescent pink #ff4fa3 + blue #1f5fc4 (multiplying into deep violet). `mix-blend-mode: multiply` on recycled paper (#f3eee2 + static paper fibers/ink grain) with opposite offsets; registration zeroes both offsets into alignment | Multiply blending creates the tactile impression of "misaligned ink layers"; screen blending immediately turns into electronic glitches; choose complementary hues that multiply into near-black, avoiding plain grays (which read as drop shadows) |
| Misregistration envelope | `offset = A*cos(2*pi*t/18)*exp(-t/60)`, A=(20,8)px opposing on both plates (300px title); hard cut to zero at frame 72 | Critical core: alignment is a **hard cut snap**, not a smooth fade—snapping to zero at ~11px residual offset creates the physical snap; smooth fades lose the register hit |
| Crash-in | 8f Easing.in(cubic) crashing in from off-screen, splitting on the exact impact frame | Splitting must lock to the crash-stop frame—delaying by even 2f reads as two disconnected events |
| Register pulse | Frame 72 hard-snap scale 1.03->1 over 4f; circular stamp drops scale 1.5->1 on same frame; page hit creates 1.2% hitch recovering over 10f | The stamping beat; omitting it deprives alignment of physical weight |
| Scope | Misregistration applies only to the title; background elements (sun, colophon, metadata) remain registered | Splitting the entire screen reads as a system glitch rather than printmaking |
| Finale | Truly static for >=40f after alignment | R1 |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- **Misregistration amplitude perceptibility precedent (verified in render)**: the original vocabulary draft of ±5px is virtually invisible to the naked eye at normal playback on 1920-wide canvases—start at >=16px per plate (32px total separation) for perceptible separation (20px/40px for 200–300px headlines); when in doubt, render extreme versions for review (perceptibility priority).
- Semantic overlap with impact-feedback Variant C (negative impact frame)—use this card for paper-and-ink aesthetics, and Variant C for gaming/anime aesthetics; never combine both in the same video (P4).
- Mixing horizontal and vertical offsets (primarily X with slight Y) feels more authentic to printing registration errors; purely horizontal offset reads like horizontal vibration.
- When 300px headline text uses negative tracking (−0.045em), horizontal strokes of adjacent glyphs may touch (e.g., F->T top bar in CRAFT), creating a hairline antialiasing seam—nudge tracking on the preceding character by an extra ~0.01em so strokes overlap cleanly.

## Reference Implementation
demos/effects/riso-print-hits/
(RisoMisregistrationHit.tsx)
