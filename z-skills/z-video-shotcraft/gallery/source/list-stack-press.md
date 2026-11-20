---
name: list-stack-press
summary: List cards fly up from below, compress the growing stack on every landing, and advance a synchronized counter.
use: Feeds, radars, and inbox shots conveying "fresh incoming items daily"; asset lists emphasizing cumulative growth.
duration: ~3s (18–88f)
energy: Medium
---

## Intention
"Stacks possess physical weight": each time a new card lands, the existing stack depresses and springs back—viewers perceive from physical feedback that "these items are tangible assets accumulating over time." A synchronized counter increments on each landing, reinforcing the sense of volume.

## Motion Core
- **Anticipation (adapted from Disney Principle 2)**: Before the first card ascends, provide a section-level anticipation beat—counter illuminates at zero or micro-scales `scale(0.96)→1` 4–6f before the first card, directing gaze to the stacking zone before cards enter. Applied once at section level, not per card.
- Cards ascend from below screen edge, alternating subtle tilts before leveling out, stacking sequentially to an equidistant cadence.
- Each arrival compresses the entire stack downward by 6px, rebounding over 8f (stackPress pulse—Principle 5 follow-through: kinetic energy transfers into stack then cushions and dissipates, delivering tactile mass).
- Settle across drag hierarchy upon landing (Principle 5): card body locks first → stack rebounds → highlight bar expands (lagging 2–4f)—firing all three on the same frame reads like a texture swap.
- Single glaze sheen sweeps across the completed stack at the finale.
- Screen-space DigitRoll counter scrolls one notch per card landed; camera tracks downward alongside the expanding stack.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Cadence | CUES=[18, 30, 42, 54, 66] (12f equidistant), each flight 22f, bezier(0.45,0.05,0.25,1.12) terminal overshoot | Small card sets (5 cards) work well with equidistant timing; massive card sets require acceleration (compare to deck-deal) |
| Entrance | Ascends 600px from below, alternating ±2° tilt settling to flat, scale 1.06→1 | Alternating tilt breaks symmetry; single-direction tilt looks copied and pasted |
| Stack press | Stack compresses 6px upon next card arrival, rebounding over 8f (pulse [cue, cue+4, cue+8]→[0, 6, 0]) | Essential source of physical weight; removing it reduces stacking to simple layout |
| Shadow | Dual softShadow layers vary with elevation: mid-air elevation ≈ 56, settled 3 (closer to surface when pressed); vertical velocity motion blur during flight | Shadow contracts with height, following shared design language with deck-deal and spotlight |
| Linked highlight | Lags landing by 2–4f, expanding an accent (amber in template) highlighter background across the project title row (y156–176 inside card), blending via multiply (7f grow + 5f fade); final card sits ~12f from cut, compressed to 5f grow + 4f fade | Highlight is secondary motion (Principles 5 and 8): follows main action (landing press-bounce) without competing on same frame; compress tail timing within remaining budget |
| Glaze sheen | 360px wide, rotate 14°, mixBlendMode soft-light; sweeps −500 to 2300 across frames 74→87 after last card settles, clipped to card rounded corners | Sweeps entire stack once at conclusion, never per card (Q4) |
| Counter (digit-roll technique) | Continuous odometer position pos: each card landing advances pos by +1 along number strip, rolling each digit in 8f via bezier(0.25,0.8,0.25,1); scroll distance = pos · lineH across dual 0-9 strips | Desync between counter and landing immediately breaks illusion; **single digit roll must be shorter than landing interval (12f) and finalize before shot cut**—re-mounting components with count keys resets to 0 taking 22f, leaving counter stuck at 4 on final frame; use dual strips + overflow hidden + tabular-nums (tabular prevents horizontal jitter) |
| Camera | Continuous zoom 1.35→0.86 curve tracking downward with stack (fed frame-by-frame to PageCam2D, preventing zero-velocity stops at segmented keyframes) | Frontal camera angle (see known pitfalls); camera tracks purely vertically |

## Audio
Avoid scoring long audio clips for each landing; anchor click-camera upon counter finalization (f648 in template), anchor transition-soft on section entry (f623). If adding pops per card, use three anti-machine-gun techniques (alternating samples, volume stepping, accelerating intervals).

## Known Pitfalls
- Stacking/list informational shots require frontal perspective (Q6)—when stylizing camera angles across a film, this shot was rolled back to frontal view; verify stylized angles per shot rather than applying globally.
- Per-card glint highlight sweeps were rejected twice (Q4); use static accent background bars for highlights and let physical bounce handle dynamics.
- Shares motion vocabulary with history-list-stack (tail of document-typewriter-reveal)—a single technique should only take hero role once per film (P4); when using both, demote one to supporting role.
- Anticipation and drag hierarchy parameters derive from Disney's 12 Principles (distilled in pixel2motion skill); serve as default guidance rather than immutable decrees; user rulings take precedence.
- Anticipation amplitude must exceed visual threshold (deck-deal ruling: subtle amplitudes were imperceptible, requiring 12x amplification to pass)—verify wind-up without stepping frame-by-frame.

## Reference Implementation
demos/ui-entrance/list-stack-press/ListStackPress.tsx (formerly template/src/aifl/live/ScenePapers.tsx)
