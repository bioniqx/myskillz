---
name: beat-step-list-theme-cycle
summary: An adjective list steps up one row per beat while a fixed center pill catches each word and the background recolors on the same beat.
use: "One product, many personalities / themes" showcases (adjective runs like modern / playful / expressive); the highest rhythmic density section in the film; syncing to musical beats
duration: Setup 30f + 18f per beat x beat count + ending hold; 4 beats ≈ 4.7s (demo 140f)
energy: High (three channels jumping in unison every 0.6s delivers high density energy)
tags: typography
---

## Intention
Switching a theme color once is a feature demo; switching every 0.6 seconds three times in a row—with "selected row + pill color + canvas background" jumping in unison on the exact same frame—creates a metronome. It produces the highest rhythmic density in the entire video using the most economical variable switches. Two requirements are non-negotiable: first, **all three channels must lock to the exact same beat**—if any channel lags by even half a beat, the synchronized jump degenerates into three disjointed animations; second, **the boundary between jumping and sliding**—the jump window occupies only the first 6f of the beat, with the remaining 12f resting completely static. Beats must "jump," not "slide"; a smoothly scrolling list is merely a list.

## Motion Core
- The pill remains **fixed** at viewport center row, while the list's translateY steps up one row per beat—visually reading as "the pill leaps to the next row to catch a new word," while physically the world moves around the pill.
- Beat length is 18f (0.6s @ 30fps ≈ 100 BPM), with the snap window occupying only the initial 6f: `snap(t) = 1 - (1 - x)^3.2` (steep ease-out), remaining frames resting static.
- Unified single-source driver across all three channels: a single `tInBeat` drives list translation, pill/canvas RGB cross-mix, and pill squash—one clock, forbidding independent curves.
- Theme pairs cycle beat-by-beat (demo: "Make it modern -> playful -> expressive -> BOLD -> yours.": bone white/espresso -> orange/plum -> iris/indigo -> mint/teal -> sunflower/navy); pill color and canvas color are curated light/dark pairs, not random colors. Each theme also carries a distinct font for the selected word (sans-serif / rounded / italic serif / all-caps Futura) switching on beat—communicating "diverse personalities" rather than just color swaps.
- Pill = optical lens: outside the pill sits the uniform muted white list; inside sits a clipped duplicate of the same list (dark text + theme font); words switch color and typeface only when crossing the pill's boundary. Pill width = measured word width + padding, interpolated with the same `tInBeat`.
- Pill landing squash: vertical 1.14->0.96->1, horizontal inverse 0.97->1.01->1, completing within the initial 6f; catching moment triggers pill brightening + colored glow pulse (exponential decay over ~3f).
- Unselected words attenuate based on distance from viewport center (adjacent rows 42% white, −15% per additional row distance, slight font scale-down, distant rows defocused); top and bottom canvas color gradient masks fade the viewport edges—gradient colors must sync dynamically with `bgColor`, as hardcoded colors expose seams during transitions.
- Element layer echoes (optional): corner theme counter `03 / 05` and color swatch rows advance on the integer beat, without applying any full-screen canvas impacts.
- 30f static setup before the first beat—let viewers clearly absorb that "this is a list" before the metronome begins striking.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Beat duration | 18f (BEAT_LEN, tune to match audio track BPM) | <12f viewers cannot read words amid color flashes; >26f the cadence scatters into isolated displays |
| Snap window | Initial 6f of beat, ease-out exponent 3.2 | Windows >10f or gentle curves turn "jumps" into "slides," collapsing the metronome into a scrolling list |
| Beat count | 3–4 beats | 5+ beats leads to viewer fatigue; 1–2 beats fails to establish the "metronome" persona |
| squash | Vertical 1.14->0.96->1 / Horizontal inverse 0.97->1.01->1 | Without it, the pill feels like flat texture recoloring; >1.2 bounce overpowers the color change |
| Canvas color delta | Adjacent theme backgrounds must share lightness with contrasting hues (all dark) | Lightness jumps (dark -> light) read as screen strobes rather than theme shifts |
| Setup / Finale | 30f static hold upfront; hold >=30f after final beat | Missing setup causes the first beat to look like a bug; cutting immediately after final beat lacks resolution |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Division of labor with `theme-switch-moves`: that card handles the ceremony of a single theme shift (sweeps / ripples, telling a story once), whereas this card uses rapid consecutive theme shifts as a metronome—use that card for "dark mode feature," use this card for "creative breadth / theme diversity."
- **Strong audio dependency**: beat points must align with drum kicks (adjust `BEAT_LEN` for BPM); silent three-channel jumps look like erratic interface glitches.
- List length must exceed beat count by >=2—leave unselected words below the list as padding; stopping on the final beat with an empty bottom row exposes raw layout boundaries.
- Do not evaluate selected states using "integer beat checks": during the 6f snap window, incoming words below the pill turn dark prematurely, exposing seams. The demo uses a pill lens (clipped duplicate)—word color and font are governed by geometry boundaries, while color transitions track decimal `tInBeat`.
- Pill width is hardcoded to measured word widths (re-measure when changing fonts/sizes), preventing words from clipping edges or floating in empty space.
- Use system font stacks: Chrome does not recognize `ui-rounded`, use Arial Rounded MT Bold for rounded fonts with sans-serif fallback.

## Reference Implementation
demos/rhythm/beat-step-list-theme-cycle/
(BeatStepListThemeCycle.tsx)
Original source: bear-app 22.3–24.6s
