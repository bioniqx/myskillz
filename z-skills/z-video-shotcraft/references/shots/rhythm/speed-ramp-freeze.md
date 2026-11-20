---
name: speed-ramp-freeze
summary: A freeze used for on-screen annotation before motion resumes.
use: Pausing to direct viewer attention to a key focal point during card streams or long lateral pans; tutorial explanations and evaluation contexts
duration: Full freeze-annotate sequence 158f (≈5.3s, freeze phase 67f >= 45f)
energy: Medium-high (velocity contrast itself delivers the energy beat)
---

## Intention
Constant linear flow reads like a slide deck (R2); continuous fast motion prevents viewers from absorbing key points (R3). Freeze-annotate halts motion decisively mid-flight—circling the highlight with a marker before resuming. The technical root is frame remapping (slope equals velocity), while the semantic intent is "pausing the class to highlight the board."

## Motion Core
- Source animation runs at constant speed, while output frames apply non-linear remapping to source frames (slope = velocity): flow phase slope 1 (26px/source frame) -> freeze phase slope 0 -> unfreeze phase smootherstep; **blur dynamically links to velocity**—applying directional blur based on remapped real velocity (`SpeedBlur`, bypassed when |v| < 8px/f), with freeze phase rendering bare; CameraMotionBlur multisampling tints canvas textures and is avoided here.
- Freeze phase slope = 0 (instantaneous transition with zero ease-in—freezing must be crisp); freeze frame issues "pause activated" signals: 3f white shutter flash, four-corner reticle snapping inward, timecode switching from LIVE to PAUSED and freezing; accent marker draws an unclosed super-ellipse outline over 10f (stroke-dashoffset, 1.08 loops) around the target + 6f arrow stem + 3f arrowhead pointing to focal point, with `feTurbulence` (scale ≈ 6) imparting hand-drawn jitter, followed by a 68px bold callout + hand-drawn underline + signature; unfreeze phase smootherstep (ease-in departure) traverses one card over 22f with average slope >1 compensating for lost time, ink fading out over 8f while leaving a comment pushpin pinned to the card corner as it exits.
- Target card aligns to screen center and is "picked up" (lifted + scaled 3–5% + deepened shadow), while remaining cards dim and desaturate; with card width at 600px, 2x card textures are downsampled, keeping every card crisp (scrutiny/annotated subjects must remain razor-sharp and centered).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Freeze duration | >=45f | Shorter durations fail to establish scrutiny (R3 lean slower over faster) |
| Unfreeze compensation | smootherstep 22f to traverse one card (average slope >1) | Sluggish unfreezing drags the entire film; without speed compensation, time consumed by the freeze reads as a dead stall |
| Callout stroke | 10f draw + jitter scale 6 | Too slow feels like a loading animation; missing jitter feels like mechanical vector plotting |
| Pause cues | Shutter white flash 3f + 4-corner reticle + PAUSED timecode | Without cues, viewers cannot distinguish an intentional freeze from a playback freeze |

## Known Pitfalls
- SFX cues lock to **output frames**, not source frames (visual events take place on the output timeline); foley slot: marker scratching audio during freeze (S4), left unassigned in baseline and supplied in production.
- Freeze-annotate occurs <=2 times in a 30s video (restraint principle).
- Parameters calibrated on placeholder assets; verify against production footage during initial run.

## Reference Implementation
demos/rhythm/speed-ramp-freeze/
(FreezeAnnotateReal.tsx)
