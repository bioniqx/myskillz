---
name: aurora-bloom-bg-flip
summary: A soft purple-orange aurora blob rises from the bottom of a light frame, then the whole background slams dark in under half a second while the copy blur-swaps to a new line.
use: Narrative turning points ("For many years... -> everything changed"); the pivotal beat shifting from prelude to main emphasis in brand films; chapter transitions between light and dark palettes
duration: ~5.2s (156f @ 30fps)
energy: Low to high (first 2/3 builds anticipation; the darkening snap delivers the primary accent)
---

## Intention
Treat "background inversion" as an accent mark: let the aurora slowly rise over the first 56% so viewers adapt to the light canvas, then snap the entire screen to near-black in under 0.4s—this impact reads more decisively as "turning the page" than any zoom or white flash. The copy swap must lock immediately after the inversion, leaving a distinct gap between lines so viewers absorb the visual change before reading the new message.

## Motion Core
- Three `blur(60px)` blob layers rise from the bottom of the frame: primary purple `rgba(107,79,224,.85)` at 90%x85%, orange core `rgba(217,122,74,.9)`, and white blending perimeter `rgba(255,255,255,.8)`.
- Rise `seg(0.04->0.56, outCubic)`: `translateY 32%->−6%` + `scale 1->1.25`.
- Inversion `flip = seg(0.57->0.64, inOutQuad)` (normalized 0.07 ≈ 0.36s): background `mix([236,236,236] -> [10,10,18])`, blob opacity 1->0.4 compressed into an afterglow, white blending perimeter layer directly removed via `1 - flip`.
- Orange core drifts laterally with independent `translateX ±8%` (2.2 cycles across the shot), creating internal relative motion within the blob rather than a monolithic block move.
- Phrase A word-by-word `blur 0->8px` + fade-out (starting at t 0.40, stagger 0.04, duration 0.10 each, inQuad); Phrase B word-by-word `outQuint` blur-in (starting at t 0.70, stagger 0.05, duration 0.11 each), settling from DEEPP purple to white within 0.09, resting motionless for ≈0.5s after settling at t ≈ 0.90.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Blob blur / size | blur(60px), main layer 90%x85%, container inset −10% | Blur below 40px exposes circular outlines, reading as "colored balls" instead of "ambient light" |
| Rise phase | translateY 32%->−6% + scale 1->1.25, t 0.04->0.56 outCubic | Occupying over half the total duration is intentional: longer buildup gives the flip greater impact |
| Inversion duration | t 0.57->0.64 inOutQuad ≈ 0.36s | **Critical core**: stretching to 1s turns an accent beat into a sluggish gradient transition |
| Canvas color | #ececec -> #0a0a12 (not pure black) | Pure black introduces banding artifacts around the afterglow blob edges |
| Blob dimming | opacity 1->0.4, white blending layer zeroes synchronously | Failing to dim the blob results in overexposed blown-out purple/orange mud in dark scenes |
| Orange core drift | translateX ±8%, 2.2 cycles across shot | Exceeding 15% makes it visibly obvious that "a single ball is moving" |
| Phrase A blur-out | Word-by-word stagger 0.04, duration 0.10 each, inQuad, blur->8px | inQuad accelerates the exit, reading as "swallowed by light" |
| Phrase B blur-in | Word-by-word stagger 0.05, duration 0.11 each outQuint + purple->white within 0.09 | Color settles slightly after entry, turning white upon rest as a "final lock" cue |
| Phrase gap | Phrase A exits t ≈ 0.58 -> Phrase B enters 0.70 (≈0.6s textless) | Cross-fading blurs the two phrases together; an empty gap clearly signals "a new chapter" |

## Known Pitfalls
- The white blending layer (blobC) works only over light backgrounds; it must be suppressed via `1 - flip` during inversion, otherwise it leaves a gray haze in dark scenes.
- DEEPP/PURPLE is the **intrinsic light color** of this effect, not an arbitrary brand slot. To adapt to project branding, all three blob layers plus Phrase B text colors must be updated as a unified set; changing only text color decouples it from the background.
- Demo copy reflects video-shotcraft's narrative transition ("Promos took weeks" / "Meet video-shotcraft", matching word counts and lengths of reference "For many years" / "everything changed"); word-by-word stagger rhythm depends on word count and length, requiring interval adjustments (0.04/0.06) when editing copy.
- Canvas background must be updated frame-by-frame via JS `background` (`mix()` computing solid color) rather than CSS transitions, ensuring deterministic colors when seeking to arbitrary frames.

## Reference Implementation
demos/effects/aurora-bloom-bg-flip/
(AuroraBloomBgFlip.tsx)
