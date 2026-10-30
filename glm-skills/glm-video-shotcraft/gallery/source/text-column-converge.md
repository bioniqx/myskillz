---
name: text-column-converge
summary: Two words pinned at opposite screen edges hard-swap through options, then slide together exactly once to lock into the final phrase.
use: Sections where feature lists converge into product name / slogan ("NEW × sequence of features → NEW <product name>"); keynote-style recaps, version number reveals
duration: Cycling 7–16f/word × 8–9 words + convergence ~36f + static hold after subtitle; full sequence ~5–6s
energy: Medium-low (machine rhythm, small-type specification list aesthetic, not aggressive slamming type)
tags: outro
---

## Intention
Two words pinned at opposite screen edges confront each other like directory index headers, leading viewers to assume they are just cycling subtitles; only when the final word settles do they realize the left and right halves belong to the same sentence — a single continuous convergence reveals the entire cycle in retrospect as dramatic suspense. The critical requirement is to **pin positions dead**: during the cycling phase, word coordinates do not budge by a single pixel, and left/right screen margins are strictly identical (reference measured at 412 vs 413 @1280); any progressive contraction prematurely spoils the convergence, diluting a reveal into a progress bar. Convergence is permitted to happen exactly once, and must occur strictly after the final word settles — this is a concluding reveal, not continuous animation.

## Motion Core
- Left edge of left word and right edge of right word are pinned dead at equal screen margins (reference measured at 412/413px @1280, scaled ×1.5 → 618/1302 @1920); the right word always anchors to its right edge regardless of text length changes.
- Word swaps are pure hard cuts with irregular dwell durations (16/12/9/8/7/8/10/12f, humanizing machine rhythm); zero contraction of spacing occurs during cycling (precedent: progressive contraction version was rejected by users and reworked).
- **The singular convergence**: ~10f after the final word settles, a ~1.2s (36f) ease-in-out (cubic) continuous slide carries both words inward to lock centered on the screen midline.
- Final convergence point is calculated from monospace character advance (0.6em + letterSpacing × character count), interlocking the two words with exactly one space between them, with zero overlap, zero gap, zero stamp scaling, and zero secondary correction movements (demo: video-shotcraft cycles through 8 feature words, ending with lowercase wordmark video-shotcraft, target computed as `NEW ` + wordmark character count; small subtitle reads the second half of brand tagline: "CRAFT THE SHOT.").
- ~18f after locking, an italic subtitle appears almost as a hard cut (4f fast fade, zero displacement), sharing the left margin and font size of the main line.
- Texture: cool-toned dark field + ultra-faint top light + vignetting / grain; 1-frame brightness flash on each word swap; NEW remains secondary grey during cycling, brightening to primary color alongside convergence progress; horizontal motion blur added proportional to convergence slide velocity (≤4px, 0 at rest); demo duration 180f (exports `TEXT_COLUMN_CONVERGE_DURATION`).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Screen margin | 618px @1920 (**measured from reference**: 412/413 @1280 ×1.5) | Margin delta >2px reads as unaligned; equal screen margins form this card's identity — do not alter to golden ratio |
| Word dwell | Irregular 7–16f | Uniform dwell reads like a rigid metronome; <7f is too fast to read words |
| Convergence trigger | Final word settled +10f (measured from reference: 32.4→32.7s) | If settled pause is too short, convergence begins before viewers realize "this word is no longer changing" |
| Convergence duration | 36f ease-in-out cubic (**measured from reference**: ~1.2s continuous slide) | <24f feels like an abrupt snap; >50f drags out |
| Interlock advance | 0.6em + letterSpacing / character, monospace font | Proportional fonts make advances unpredictable, causing overlapping text or unwanted gaps |
| Font size | 42 @1080p (**measured from reference**: cap height ~20/720) | This section conveys the precision of a spec sheet; enlarging past 60+ turns into heavy display type (use outline-word-fill for heavy type punches) |
| Subtitle appearance | Locked +18f, 4f fast fade, zero displacement (appears directly in reference between 34.4→34.6s) | Adding slides or slow fades steals focus from the convergence |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Overlaps in domain with type-rhythm-sync (typographic attribute cadence) / beat-cut-moves (hard-cut rhythm): those cards treat "cycling itself as the core content"; this card relies strictly on **pinned coordinates + final singular convergence** as a concluding reveal, where cycling serves merely as preparation. If a scene lacks an interlocking reveal, do not use this card.
- Convergence is allowed only once — versions with progressive step-by-step contraction per word were disproven against the original reference and deleted; do not revive them.
- Monospace font is mandatory (demo uses SF Mono); proportional fonts prevent accurate interlock calculation.
- The reference video features a 1-frame brightness flash during word swaps (typewriter carriage-return sensation); the demo preserves this 1f brightening; flashing >1f reads as a glitch.

## Reference Implementation
demos/typography/text-column-converge/
(TextColumnConverge.tsx)
Original source: raycast-teams.mp4 28–36s
