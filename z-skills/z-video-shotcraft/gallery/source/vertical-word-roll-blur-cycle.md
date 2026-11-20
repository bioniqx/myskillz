---
name: vertical-word-roll-blur-cycle
summary: The closing word of a tagline rolls vertically through a three-line reel, neighbouring rows blurring into grey depth while the settled word takes the accent color.
use: "Crafted for ___" / "Built for ___" sentence stems + audience/target enumeration value props; crisp, clean beat in light-background brand videos
duration: ~5.0s (150f@30fps: static hold → 3 word cycles → full group fade-out at tail)
energy: Medium (steady 3-beat cadence, no peak)
---

## Intention
Swapping the concluding word of a sentence works best via a vertical reel rather than crossfading: a reel carries inherent **directionality** (flipping upward like pages), signaling to the audience that "more is coming." This card's two identity signatures are the **vertical blur** on neighboring rows (simulating cylindrical depth of field and mechanical defocus) and the **landing tint** (grey → accent color, declaring "this is the answer"). The sentence stem (demo: `Crafted for`) remains completely motionless throughout — the viewer's eyes stay fixed on the reel; any movement in the stem dissolves the sense of enumeration.

## Motion Core
- Positional progress `p` accumulates across 3 window segments: `STEPS = [0.16, 0.36, 0.56]`, each window lasting 0.11 (~16f, ~0.55s), with 0.09 static holds between segments for reading words.
- Each segment uses a **blended easing curve**: `0.7·E.outQuint(u) + 0.3·E.outBack(u)` —
  outQuint provides "fast-start, ultra-slow finish" mechanical deceleration, while the 30% outBack contribution delivers a subtle landing overshoot and settle.
- Reel position `translateY(ROW - p·ROW)`, ROW=44px, mask height `ROW·3`=132px (revealing three rows) — the active center row is perpetually the second row of the mask.
- Three distance-driven channels, `d = |i - p|`:
  - blur: `3d` when `d<1`, `3 + 2·min(d-1,1)` when `d≥1` (max 5px); demo uses SVG `feGaussianBlur stdDeviation="0 b"` blurring strictly along the vertical axis, with additional ≤4px vertical motion blur layered during rotation based on reel speed (0 at rest).
  - opacity: `1 - 0.65d` when `d<1`, otherwise `max(0.1, 0.35 - 0.23(d-1))`.
  - color: `mixHex(ACCENT_DIM, ACCENT, clamp01(1 - 2.4d))` — **strictly dark when d>0.42**, so the accent color ignites solely at the exact instant of settling; remaining muted grey throughout transit.
- Tail resolution `seg(t, 0.9, 0.985)` fades out the entire group (stem + reel), leaving no ghost artifacts for the next shot.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Vocabulary | 4 words (Launches → Demos → Promos → Every Shot), 3 transitions | Final word is the conclusion (widest word), first three are examples; >5 words make viewers count beats; <3 words fail to establish an enumeration |
| Beat timing | `[0.16, 0.36, 0.56]`, window 0.11 (~16f) | Inter-segment pauses 0.09 (~13f) allow reading words; beats that are too fast to read are useless; window >0.18 overlaps old and new too long |
| Easing blend | `0.7·outQuint + 0.3·outBack` | outQuint supplies mechanical braking; the 30% outBack gives a tactile landing "latch"; pure outQuint feels like sliding on glass |
| Row height / viewport | ROW 44px, mask `44×3`px, word width 190px | Revealing three rows provides cylindrical depth (one row reads as a fade); width hardcoded to 190 to avoid pushing stem; widen if words are longer |
| Neighbor row blur | Neighbor 3px, farthest 5px, **perceived strictly vertically** | Blur is the proof of cylindrical depth; removing it degrades the motion into flat sliding text; >8px smears neighbor text into unreadable grey bars |
| Landing tint | `1 - 2.4d` mapping ACCENT_DIM → ACCENT | Factor 2.4 restricts color change strictly to the landing instant; <1.5 shifts color mid-scroll, diluting the punchline feel |
| Typography | Stem and reel both use 30px/800, `letter-spacing:-.5px` | Must match identically — reel words larger than the stem read as two separate elements rather than one sentence |
| Tail fade-out | `seg(t, 0.9, 0.985)` full group | Holds static for ~40f after final word settles before fading; cutting immediately wastes the enumeration |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **Mask width is hardcoded at 190px**: When updating copy, the longest phrase (demo: `Every Shot`, multi-word strings require `white-space: nowrap`) must fit inside to prevent clipping; conversely, if all words are very short, excessive blank space on the right shifts the sentence center leftward — measure width when swapping copy.
- Avoid large variances in word length: Mask width is fixed (this card does not use adaptive widths; that belongs to pill-chip-slot-cycle-handled); deltas >2x leave short words looking isolated.
- The sentence stem must remain pinned: The demo uses `flex + gap:14px` because constant mask width never exerts force on the stem — if modified into an adaptive-width reel, the stem must switch to absolute left-anchoring, or it will sway left and right.
- Progress `p` is **accumulated** across the three window segments, so segments must never overlap: overlapping causes p to jump an entire row in a single frame, resulting in skipped steps.
- Division of labor with pill-chip-slot-cycle-handled: that card uses dark capsules with adaptive expansion (words as badges); this card uses bare words in a reel (words as sentence components) — keep only one per film.
- Audio: Each landing is a rhythm point paired with a light mechanical switch sound; use alternating samples across the three landings to prevent machine-gun repetition; see sound-design.md.

## Reference Implementation
demos/typography/vertical-word-roll-blur-cycle/
(VerticalWordRollBlurCycle.tsx)
