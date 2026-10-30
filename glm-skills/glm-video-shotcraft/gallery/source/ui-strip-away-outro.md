---
name: ui-strip-away-outro
summary: After Publish is clicked the editor UI evaporates layer by layer from the edges inward, leaving one button to slide center, grow, and hand off to the wordmark.
use: Outros with "publish / complete" semantics; product finales conveying "one click and all complexity vanishes"
duration: ~4.8s (144f: cursor in place 34f -> evaporation ~40f -> button solo -> wordmark handoff -> wordmark hold >=1s)
energy: Medium (quiet operation upfront, continuous exit mid-shot, no sudden impact)
---

## Intention
Standard shot library finales are additive: outro-group-photo-launch flies in elements for a group photo; logo stings freeze before playing an easter egg. This card provides the sole "subtractive" path—a single click detonates the entire UI's departure, leaving only the semantic focal point (the clicked button) in a black void, translating "publishing = complexity vanishes to zero" into motion narrative. Two critical rules: **evaporation must be orderly**—progressing from periphery to center every 4f per layer, each carrying directional displacement (dispersing outward offscreen); chaotic order or simultaneous extinction looks like a power outage; **the button is the sole survivor and must migrate**—during evaporation, it glides from the toolbar corner to the screen center, enlarging by 1.5x while white glow intensifies against the darkening stage, completing its elevation from "UI control" to "ceremonial protagonist," before finally fading out to hand the dark stage over to the wordmark.

## Motion Core
- 6 evaporation layers: sidebar -> inspector panel -> canvas cards -> toolbar outer wings -> canvas backdrop -> toolbar center; staggered every 4f starting +4f after the click; each layer uses STRIP_DUR 14f with Easing.in(quad) departure acceleration, combining fade + directional displacement + 0 -> 7px evaporation blur (sidebar -140, 0 / panel -90, 20 / toolbar wings -/+80, -60 / canvas backdrop 0, 40 / toolbar center 0, -50).
- 4 cards on canvas stagger by an extra 3f each, with alternating left/right displacement (+/-70px)—disappearing as a large monolith looks like a layer being deleted; breaking apart in pieces feels like genuine "evaporation."
- Darkening background: gray background fades to #111110 over 20f starting at +20f in sync with canvas backdrop evaporation.
- Button: click compression pulse via spring (damping 12, stiffness 220); glides toward screen center via position/size interpolation during evaporation (18f, inOut cubic), scaling by 1.5x with white glow expanding 30 -> 70px as background darkens; fades out over 12f starting at +52f.
- Wordmark handoff: fades in at +62f via spring (damping 14, stiffness 90) with 86% -> 100% scale, locking the final frame in the dark void.
- Cursor fades out within 10f after click—the lead actor has changed, and the cursor must exit.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Inter-layer stagger | 4f x 6 layers | Simultaneous cutoff reads as power failure; >8f drags into slow demolition, diluting ceremony |
| Layer duration | 14f, ease-in acceleration | ease-out departure reads as "drifting away" rather than "evaporating"; >20f feels sticky |
| Evaporation order | Periphery -> center, button's layer last | Emptying center first feels like a glitch; losing the button layer early collapses the composition |
| Displacement | 50–140px, directional outward | Pure fade without displacement reads like adjusting opacity; uniform direction reads as a screen-wide pan |
| Button migration | 18f slide to center + scale x1.5 + glow intensification | Without migration it remains a tiny corner button on a black screen (looks like an accidental leftover); migration must precede fade-out |
| Wordmark handoff | Enters ~10f after button fades out, spring lockup | Sharing frame with button creates competing foci; empty dark void >20f feels like playback ended |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Division of labor with outro-group-photo-launch: the ensemble photo is an "additive" peak finale (full cast curtain call for multi-feature products); this card is a "subtractive" outro (single-action semantics, growing progressively quieter)—choose based on product tone; do not combine both in one video.
- Each evaporating layer must represent a **semantically complete UI zone** (sidebar / panel / toolbar); slicing layers by pixel rectangles exposes awkward structural fragments during staggered departures.
- Button migration must maintain highest zIndex throughout—any evaporating layer floating across the button's front breaks realism.
- Trigger action must convey "finality" semantics (Publish / Ship / Done); triggering full UI evaporation with Save or generic confirmations misaligns semantic weight with visual drama.
- Use the authentic brand accent color on the button in production (original reference uses Framer blue; demo uses placeholder indigo)—the contrast of button and halo against the black void creates the protagonist aura; weak coloring fails the elevation.

## Reference Implementation
demos/outro/ui-strip-away-outro/
(UiStripAwayOutro.tsx)
Original source: framer-ai 33–36.5s
