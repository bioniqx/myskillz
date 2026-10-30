---
name: scanline-assemble-flyin
summary: The page starts as an empty dark grid; a scanline descends and each component flies in from off-screen to snap into place behind it, with motion blur and a bright edge flash on landing.
use: Openings where a "page generates itself"; core capability demos for AI website builders and automated layout tools; capability narratives from blank canvas to finished product
duration: ~5.2s (156f @ 30fps)
energy: Medium-high (scanline remains steady, but each incoming component delivers an impact beat with rising density)
---

## Intention
Provide a credible construction sequence for "generating a page": the scanline acts as a construction progress bar, and components flying in from off-screen serve as construction actions. The golden rule is that **the scanline completes its pass on the exact frame the final component snaps into place**—finishing the scanline early or letting component arrivals drag out destroys the causal link of "scanning drives assembly."

## Motion Core
- Frame 1 presents the full "blueprint": full-screen blueprint grid (24px fine lines alpha 0.045 + 120px major lines alpha 0.085), 1640x860 artboard dashed border with dimension annotations, and dashed slot placeholders for each component (labeled with micro-text like `H1 820x250`)—viewers see "what is being built and where" upfront.
- Scanline sweeps artboard y: −20->880 across 8->92f at **strictly constant velocity**: white core + electric blue 3-tier glow, fading out 60px past artboard edges; 180px grid trailing behind the line illuminates, and **the page background is "painted" on** (artboard surface mask descends following the scanline).
- Landing frames derived from slot bottom edges: `land = frameAtY(y + h)`, sorted by bottom edge with minimum 4f spacing; 14f flight duration **launches in advance** so components and scanline arrive at the slot simultaneously. Measured demo values: NAV 19f, BADGE 29f, H1 55f, BODY 66f, MEDIA 75f, CTA 79f, STATS 88f.
- 7 components originate from dedicated off-screen positions: navigation from top (0, −260), badge / H1 / body from left (−620…−980), media card from right (+900, +80, 6 deg), CTA / stats row from bottom (+420…+460); snapping into place via `EASE.overshoot` with ~8% overshoot, rotations of ±2–7 deg zeroing out concurrently.
- Flight applies directional motion blur via `SpeedBlur` (0.32x velocity, capped at 18px) based on centroid displacement, zeroing out 4f after landing.
- Landing: slot dashed lines vanish within 4f; four-corner electric blue L-brackets (arm length 22px) snap inward from 20px offset to 10px, flashing bright across `land+1->+4` and collapsing across `+5->+14`; omitted on full-width navigation.
- Status line tallies `BLOCKS 0n / 07` with live stopwatch; after final block lands, switches to `✓ BUILT`, stopwatch freezes, blueprint grid fades to 30%, media card (galaxy reel footage) steps up in brightness, followed by ~50f hold.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Scanline | 84f constant velocity, artboard y −20->880 | Scanline finish must slightly trail final component landing to convey "scanned means finished" |
| Trigger conversion | land = SCAN0 + (y + h − Y0) / (Y1 − Y0) * (SCAN1 − SCAN0) | Changing scan window requires editing only four constants; flight duration FLIGHT represents advance launch; omitting it produces "moving only after scanline has passed" |
| Minimum spacing | prev + 4f | Items with adjacent bottom edges like MEDIA / CTA land concurrently without clamping; clamping restores "item by item" rhythmic cadence |
| Fly-in travel | Off-screen 260–980px, matched to component entry direction | Travel <200px reads like "nudging into place" rather than arriving from off-screen |
| Fly-in rotation | ±2–7 deg | Exceeding 12 deg feels like "tumbling," failing to snap neatly into slots |
| Fly-in easing | EASE.overshoot, 14f | Overshoot provides the tactile sensation of "magnetic snapping"; pure ease-out feels like sliding |
| Motion blur | Directional SpeedBlur 0.32x velocity, <=18px, clearing upon settling | Isotropic blur reads as out-of-focus rather than speed; omitting reset leaves permanent blur layers |
| Landing brackets | Outer offset 20->10px, arm length 22px, 3f bright / 9f decay | Brackets serve as visual proxies for audio clicks; full-frame stroke flashes look like debug boxes and firing 7 times violates Q4 |

## Known Pitfalls
- **Trigger timing is locked to slot boxes in PLAN**: re-measure component boxes when changing page templates, otherwise components fly in before the scanline arrives.
- Components use slot origins for absolute positioning in `Fly`; bracket layers are SVGs inside components (`overflow: visible`); if components declare `overflow: hidden`, outer brackets get clipped—place media card clipping on an inner container instead.
- Painting the page background uses a linear-gradient mask on the artboard surface (tracking scanline y); the blueprint grid is a separate layer; both follow the scanline, so do not mask the grid or the area below the line becomes dead black.
- Shares the "scanline as causal driver" concept with `scanline-annotate-focus`; the two cards can daisy-chain (assemble first, annotate second), but reverse scanline direction or leave a distinct pause between them to avoid repetition.
- Page content uses video-shotcraft's landing page (engraved mark + wordmark nav, "Shoot the / launch film." H1, sample reel card); accent colors (electric blue / cyan) derive from LOOKS.midnight, updated via variable L.

## Reference Implementation
demos/effects/scanline-assemble-flyin/
(ScanlineAssembleFlyin.tsx)
