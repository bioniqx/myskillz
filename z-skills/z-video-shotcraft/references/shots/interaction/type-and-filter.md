---
name: type-and-filter
summary: A real interface types a search, collapses the grid to one result, then clicks through into the detail view.
use: "Operational narrative" segments in feature demos; any interactive flow involving search, filtering, and drilling into details
duration: ~2.5s (118–190f)
energy: Medium (a composed beat following high-energy card-dealing sequences)
---

## Intention
Guiding the viewer to "follow along step-by-step": clearly see what was typed, how the page responded, and where the cursor clicked. This is the only shot in the entire video simulating realistic human operation; rhythm must feel like a human hand, not a script.

## Motion Core
- Camera closes in on search input (zoom 2.0, effective text height ~30px) typing character-by-character, cursor switching from solid to blinking; post-typing breathing beat pulls back to full overview (zoom 1.0) to observe grid convergence.
- Brief breathing pause after typing, then non-target cards sink and fade out staggered in reading order as grid collapses.
- Target card slides into top-row slot, lifting with expanding shadow mid-flight.
- Pointer glides across overview to target card (screen size constant), double-ring accent (amber in template) ripple clicks to confirm, and camera pushes in through card into detail view, handing off to transition.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Typing speed | 3f/character (TYPE_START=128, "nano-lab" 8 chars resolves ~149) | Final locked value after early version reworked for being too fast ("unhurried"); interactive demos follow human pace |
| Breathing beat | ~11f (0.37s) between typing finish and filtering at FILTER_START=160 | Filtering immediately upon typing completion reads like automated script, leaving viewers unable to follow causality |
| Cursor | Solid during typing, then 8f periodic blink; click at 176f, cursor disappears at 185f | Blinking during typing reads as stutter; switching from solid to blink signals "typing complete" |
| Filter exit | 25 non-target cards staggered by 0.4f in reading order, each 5f fade out + sink 8px | Disappearing simultaneously reads like page crash; even 0.4f stagger is sufficient |
| Target card slide | 10f slide into first-row slot, bezier(0.35,0,0.2,1), mid-flight sine lift z 18px, scale +0.02, shadow widening with lift | Destination must be a genuine layout slot; hovering in center of frame looks fake |
| Click confirmation | Two concentric accent ripples (3f start offset, 10f each, radius 14->54/78) + 3px stroke + 40px glow, followed by 16f camera push to zoom 2.2 | Single-ring ripple is too faint to notice; push-in hands off to flash-cut masking page change hard cut (component in assets/lib/FlashCut.tsx, usage: from = cut - 5, straddling 5f on each side of hard cut) |
| Search box | Background patch covers placeholder in texture (preserving magnifying glass icon); text layer overlays input | Typing directly over screenshot texture causes double-vision with baked-in placeholder |

## Audio
Typing segment locks keyboard.mp3 trimmed to 24f via Sequence strictly matching action length; click locks click-camera (loudest in video at vol 0.6, loudness hierarchy); grid fly-away locks whoosh-fast.

## Known Pitfalls
- Initial version was reworked because typing + filtering was "too fast"—interactive shots are almost always drafted too fast; start drafts at 3f/character.
- If target card does not settle into an authentic layout slot and instead hovers above grid, it reads as fake (almost caused entire file rewrite previously).

## Reference Implementation
demos/interaction/type-and-filter/TypeAndFilter.tsx (adapted from template/src/aifl/live/SceneFlyIn.tsx frames 118–190)
