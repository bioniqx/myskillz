---
name: panel-grid-moves
summary: An angled comic-panel split that cuts one moment into three framings before resolving to a poster.
use: Using panel splits as a metronome: slicing multiple angles of the same subject into frozen panels on the beat; hitting rhythm points
duration: 156f ≈ 5.2s (full-screen 3/4 angle 20f + 3 slash-cut freeze panels + screen engulf + poster hold)
energy: Medium-high
tags: ui-entrance
---

## Intention
Distinction from `wall-reveal-moves`: that card addresses "how an entire wall enters" (one-time reveal), whereas this card addresses "how panel grids act as a rhythm engine"—splits land on musical beats, and panel transitions serve as drum kicks. Variant A splits: the screen is slashed by three diagonal seams, freezing three camera angles of the same product simultaneously; after a resting beat, the final panel sweeps across to engulf the full canvas—drawing on the split-screen comic vernacular of Scott Pilgrim. Ideal for multi-angle product showcases (demo: a prime lens engraved with video-shotcraft, three commentary panels numbered "Shot 01 / 02 / 03," resolving into a "Craft the shot." poster after the screen sweep).

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A comic-panel-split | Full-screen 3/4 angle 20f -> three 12 deg diagonal cuts slash down every 4f, corresponding panels hard-cut popping in (5f scale 1.07->1 + white flash); three panels = wide / detail close-up / macro of the same subject; 29f freeze sustained by subject's own internal motion; final panel 2f reverse anticipation + 14f screen sweep engulfing canvas into poster | Multi-angle presentation of a single subject; graphic comic-styled sequences |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Diagonal seams | SVG dual-line: ink border + cream paper core (total width 18px), 12 deg angle, each cut draws top-to-bottom over 3f | Cream paper core provides comic book soul; straight vertical seams look like generic split-screen tools |
| A Keep-alive motion | Subject moves internally during freeze: focus ring turns 26 deg, aperture blades close, wide panel pushes in subtly | Completely static panels read like screenshot collages; "the lens is working" offers richer content than camera pushes |
| A Narrative captions | Cream background + 4px ink border + 7px hard drop shadow, −2 deg tilted stamp pop-in, lives inside panels and gets cleared with them | Secondary anchor for comic vernacular; floating above panels breaks the illusion |
| Finale | ~50f poster hold after final copy line reveal (preserving only 1.5% subtle push-in) | R1; align unmasking frames pixel-by-pixel with sweep termination to prevent jumps |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- The three panels must present **different camera angles of the same subject**—stuffing different subjects into panels reads like a bento grid rather than comic panels, destroying semantic clarity.
- Strong audio dependency: three crisp mechanical clicks on each slash (sound-design §4.5); un-synced panel splits are merely layout transitions.
- Render subject as SVG vectors (or high-resolution assets): panel camera angles zoom up to 2.45x; bitmap screenshots will blur (Q2).
- Limit panel grid sequences to <=1 per video—panel visual language is extremely distinctive; two occurrences collide.

## Reference Implementation
demos/rhythm/panel-grid-moves/
(ComicPanelSplit.tsx)
