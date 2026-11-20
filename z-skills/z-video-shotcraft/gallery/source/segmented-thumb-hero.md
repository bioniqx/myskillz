---
name: segmented-thumb-hero
summary: An oversized segmented control gets a close-up: a cursor slides in, presses, and the white thumb snaps to the other segment as icons swap with a spring.
use: Announcement shot for "mode switch / binary choice" features (e.g., video-shotcraft Prompt->Film, Chat->Agent); macro shot where a single UI micro-interaction sustains an entire shot
duration: ~3.5s (demo 110f: float-in 18f + cursor 24f + click + slide 8f + icon pop + hold)
energy: Medium (micro-interaction close-up; refined without overpowering)
---

## Intention
When switching to a new product mode, conventional shots replace the entire screen. This card does the inverse: magnifying a segmented control to 1080px wide in extreme close-up, where **the 8-frame thumb displacement itself is the narrative**—"we crossed from A to B." Without surrounding page context, the control becomes the stage. The causal chain is complete: cursor glides in (someone arrived) -> press + ripple (decision made) -> thumb slides (world responds) -> new icon pops up (new identity established). All four beats are essential: omitting the cursor makes the UI move itself; omitting the icon pop leaves the switch unrewarded.

## Motion Core
- Control close-up dimensions 1080x220, floating up from 200px below via spring (damping 14 / stiffness 120), large drop shadow tightening upon landing (24->12px).
- Cursor is an oversized outlined arrow (130px, white fill with ink border): 24f Easing.out(cubic) sliding from off-screen bottom-right onto target segment; press scale 1->0.86->1 (3f down, 4f return).
- **Thumb strictly 8f** Easing.out(cubic) (demo 52->60f)—restoring original video feel; these 8 frames form the heartbeat of the shot, with all preceding and succeeding beats serving it.
- Dual actions trigger simultaneously upon arrival: new icon pops with overshoot via spring(damping 10, stiffness 220); old icon collapses over 6f Easing.in with width simultaneously zeroing out so text flows naturally.
- Click ripple: 3px accent-colored fine ring expands and fades over 12f from click point (cursor tip) via Easing.out(quad)—ripple confirms press occurred; click without ripple looks like cursor passing by.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Control dimensions | 1080x220, thumb inset 16px | Shrinking below <600px wide loses close-up nature; thumb displacement loses physical weight |
| Thumb duration | 8f Easing.out(cubic) | >14f reads like slow-motion tutorial; <5f reads like teleportation, losing the "slide" |
| Cursor slide-in | 24f from off-screen, ease-out | Linear or <14f reads like cursor was flung in; starting point must originate off-screen |
| Press | scale 0.86 + ripple 12f | Sliding thumb without press breaks causality, reading as autoplay |
| Icon pop | spring damping 10 / stiffness 220 | Damping <8 bounces three times, stealing focus from thumb; uncollapsed old icon forces text outside control |
| Closing hold | Static hold on new state >=30f | Cutting immediately after switch prevents viewers from registering new mode |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Division of labor with cursor-flyover: that card shows cursor clicking and pushing in within a full page (with context), while this card isolates the control in background-free macro close-up—both can coexist in one film, but avoid filming both page and macro versions for the same click.
- Icon collapse must zero out width instead of scaling alone—scaling alone leaves empty gaps preventing text reflow, creating "ghost seams" inside control (width and scale drive synchronously in demo).
- Use caution with controls with 3+ segments: thumb sliding across multiple segments in 8f is too fast to read docking, while extending duration ruins tactile feel—this card works best with binary toggles.
- Ripple ring must layer above thumb in zIndex with center locked to click point—traveling with thumb turns it into a thumb trail, corrupting semantic meaning.
- Production asset swap: replace segment labels/icons with real feature names; however, "new segment icon carrying expression" (demo smiley clapperboard) delivers half the reward sensation—plain line icons feel noticeably muted.

## Reference Implementation
demos/interaction/segmented-thumb-hero/
(SegmentedThumbHero.tsx)
Source: perplexity-promo 2.3–5s
