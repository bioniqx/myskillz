---
name: neon-triple-marquee
summary: Three rows of outlined neon giants scroll in opposite directions across the full screen, lighting up in turn on a one-third phase offset.
use: Outro theme word repetition sections; shooting the "lingering resonance" of a three-word slogan; background musical sequences without voiceover
duration: 4–5s (demo 150f: 18f staggered ignition + loop body + 18f staggered power-off + 8f dark hold)
energy: Medium-high (continuous flow + sequential pulses, no abrupt impacts)
tags: typography
---

## Intention
A single marquee line is merely web decoration; stacking three lines in counter-directions and cycling luminance in phase becomes "theme words marching in review before the audience." The critical core is **alternating illumination**: at any given moment, only one line is the neon protagonist, while the other two recede into subtle stroked silhouettes—all three blazing at once is a signage malfunction; rotating illumination is a recap. Counter-scrolling creates an "immersive enclosure": top and bottom rows roll right while the middle row rolls left, pinning the viewer's gaze in between as words stream continuously from both edges, conveying "there is no end to these three principles."

## Motion Core
- Seamless loop: duplicates are spaced via absolute positioning at fixed unitW intervals, wrapped via `(frame * speed) % unitW`—constant linear velocity (marquee cards are exempt from the anti-linear rule).
- Three-tier hollow neon tube type: `-webkit-text-stroke` with transparent color—unlit glass tube (matching color, 0.3 opacity, constantly lit to preserve three-line structure) -> energized color tube (stroke expands 6 -> 10px + 3 drop-shadow glow tiers at 9/36/90px) -> near-white thermal core (2 -> 3.8px); luminance simultaneously drives color spill onto the brick wall behind (screen blend, illuminating brick mortar)—adjusting only opacity without glow fails to convey "energized neon."
- Alternating phase cycle: 42f period with a 14f slot per line; slot duration is 16f (2f overlap with next line to avoid total blackouts); each slot begins with 2f strike flicker (0.6 -> 0.25 -> 1.0), 3f ramp to peak, plateau, and final 5f ease-in power-off—ensuring "one bright, two dim" holds true at all times.
- Camera: entire wall is set in a 3D plane with perspective 1700 at an angle, smooth ultra-slow pan-in rotateY -17 deg -> -9 deg + scale 1 -> 1.05; wet ground beneath the wall reflects an inverted mirror of the bottom row (blur 3px + gradient fade mask) alongside light pools breathing in sync with row luminance.
- Row color scheme: ice cyan / magenta / sodium amber (#38d9ff / #ff3d9a / #ffae34) against a blue-black brick wall (#0a0b14); middle row runs in reverse slightly faster (9 / 11 / 9 px/f).
- Power-on / power-off: opening lines run deterministic strike sequences at 0/5/10f; from 124f onward, rows power off top-to-bottom staggered by 6f with two flickers, resolving to unlit glass tubes on a dark poster (never fading to pitch black).
- Typography: Avenir Next Condensed Heavy 286px (fallback DIN Condensed / Impact), word spacing measured via canvas, separated by hollow diamond glyphs (borders match current tube color and thickness).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Font size / line height | 286px condensed, 290px line height filling the wall | Line gap >80px reads as three banner ads instead of a word wall |
| Scroll speed | 9 / 11 / 9 px/f, middle row reversed | Condensed text is denser and runs one tier slower than wide fonts; >20px/f makes words unreadable light bands; uniform direction reads as flat page pan |
| Pulse period | 42f, 14f slot per row + 2f overlap | Period <30f creates chaotic flashing; >70f breaks the round-robin rhythm; omitting overlap creates an unlit blackout every 14f |
| Luminance range | Unlit glass 0.3 + energized stroke 6 -> 10px + 3 glow tiers | Unlit opacity <0.2 makes unlit rows vanish, losing the 3-row architecture |
| Bloom | 3-tier drop-shadow: 9/36/90px in bright state + 0.55 wall spill | Single layer or <20px looks like stroked text, not neon; lack of wall spill looks like screen graphics rather than physical lights mounted on a wall |
| Angled view | rotateY -17 deg -> -9 deg, perspective 1700 | >25 deg bunches distant words into an illegible knot; 0 deg flattens the view, losing depth |
| Power on / off | In: staggered 5f ignition; Out: staggered 6f cutoff from 124f | Hard cuts look like truncated footage; fading all rows at once lacks the ceremony of switching off lights |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- Division of labor with page-waterfall-wall: that card uses vertical screenshot cascades to convey "content volume"; this card uses horizontal counter-scrolling words to deliver "thematic echo"—the assets are words, not pages, placed at the outro rather than mid-video.
- Division of labor with outro-group-photo-launch: the ensemble photo is a peak climax shot (element family portrait + launch event finish); this card is an outro recap setup or a lightweight alternative climax; the two can run in sequence (this card -> fade out -> ensemble photo) but should not overlap.
- Keep replica redundancy: calculate count via `ceil(1920/unitW) + 3`—short words (<=4 characters) have small unitW; insufficient duplicates expose gaps on the right during wrapping.
- Custom brand palettes: all three rows can share brand colors distinguished by luminance, but glow contrast must match or exceed the demo's ratio of 0.3 unlit to energized full bloom; otherwise alternating cycles cannot be distinguished.
- Drop-shadow glow inside a 3D tilted plane is computationally intensive (demo 1080p renders 150f in ~7s); reflections render only tube geometry without glow to remain fast.

## Reference Implementation
demos/outro/neon-triple-marquee/
(NeonTripleMarquee.tsx)
Original source: clickup-30 61–64.5s
