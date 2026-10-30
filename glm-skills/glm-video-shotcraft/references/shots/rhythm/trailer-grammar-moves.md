---
name: trailer-grammar-moves
summary: A trailer bumper hook: three 9-frame rapid cuts, a beat of black silence, then the opening title card.
use: Opening hook for trailers (cold open): packing three attention-grabbing shots before the main film, followed by a silent beat before the formal title
duration: A ~4.7s (140f)
energy: A High
tags: opening, transition
---

## Intention
Rhythm cards in the library manage distinct segments: beat-cut governs cut placement, and rhythm-interrupt governs interruptions. This card governs **structural trailer moments**—not how an individual shot moves, but how major joints of the entire film connect: Variant A serves as the opening hook—stuffing three hyper-engaging shots into 0.9 seconds before the main feature, followed by a silent beat of black void before opening the title—a "trailer for the trailer."

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A trailer-bumper | Three 9f equal-length hard cuts (0/9/18), each shot carrying internal scale 1->1.04 slow push to stay alive; 27–33f pure black silence, title fading in over 16f at 33f with 44px out-cubic rise (demo title features video-shotcraft wordmark + brand tagline) | Opening hook before main feature; cold open |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Rapid cuts | Three equal 9f cuts, zero transition; Shot 3 zooms into center Top pages card at 2.2x close-up (CSS zoom, preserving crisp text) | Cadence relies on equal durations; all three shot compositions must differ noticeably |
| A Subtle push | Linear scale 1->1.04 within each shot | Three consecutive static frames look like a slideshow—critical core |
| A Blackout | 27–33f pure black #000 empty div, 6f duration | Placing anything inside the blackout destroys the "beat of silence" |
| Finale | Variant A rests static for 77f (>=40f) | Frame freezes completely after letter tracking settles (63f), achieving true rest |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Variant A blackout must remain purely black and empty (sharing lineage with drop-blackout precedent)—the blackout is a breathing pause, not another title card.
- In Variant A, an audio hit strikes on each cut, with total silence across the blackout (sound-design §4.5).

## Reference Implementation
demos/rhythm/trailer-grammar-moves/
(TrailerBumper.tsx)
