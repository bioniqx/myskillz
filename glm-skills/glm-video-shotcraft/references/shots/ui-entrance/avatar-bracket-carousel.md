---
name: avatar-bracket-carousel
summary: A four-corner focus bracket stays locked mid-sentence while a vertical queue of avatars springs through it three times, each one sharpening and growing as it enters the frame and shrinking, dimming and blurring as it leaves.
use: Capability enumeration for "one slot, multiple roles"; core one-sentence shot for team, identity, preset, or persona products.
duration: ~5.2s (156f @ 30fps)
energy: Medium (Three equidistant switches form a steady metronome; focus bracket pulse is the only decorative motion)
---

## Intention
Listing "our agent can act as director, editor, animator, sound designer" as four lines is just a checklist. Packing it into a single slot in a sentence turns it into a promise plus four proofs: the sentence stays still while only the person in the slot changes. The four-corner focus bracket is key to this technique—it does not rotate, but it pins the viewer's eyes onto that 92×92 box, so the four replacements read as "the exact same slot" rather than "four avatars floating by."

## Motion Core
- Position variable `pos` is an accumulation of three spring segments: `[0.24, 0.46, 0.68].forEach(s0 => pos += seg(t, s0, s0+0.14, k => E.spring(k, 0.25)))`—not discrete index jumps, but a continuous variable, so the distance from each avatar to the slot can be computed at any moment.
- Distance drives everything: `d = |k - pos|`, then `scale = max(0.5, 1-d*0.38)`, `opacity = max(0, 1-d*0.62)`, `blur = min(3, d*2.4)`, `translateY = (k-pos)*76`—four properties originate from a single distance value, so entering/leaving transformations are naturally synchronized without separate timing tracks.
- The queue is stacked absolutely at the `slot`'s 0×0 anchor (`left:-29px, top:-29px` self-centered), vertical displacement relies entirely on `(k-pos)*STEP`; avatars outside the box still render, just hidden by opacity and blur.
- Entrance is another layer superimposed on the rotation: `el.style.opacity = op * seg(t, 0.02+k*0.03, 0.12+k*0.03)`—four cards establish the queue staggered by 0.03 within the opening 0.15, after which this term remains 1 and rotation takes full control.
- Role labels are independent but share `pos`: `opacity = max(0, 1-|k-pos|*2.2)`, decay slope 2.2 is much steeper than the avatar's 0.62—labels disappear completely beyond 0.45 slots of distance, ensuring two labels never appear on screen simultaneously.
- Focus bracket breathing: `breath = Σ sin(seg(t, s0, s0+0.1) * π)`, taking `min(1, breath)` multiplied by 0.07 added to scale; sine envelope makes the pulse peak at the exact midpoint of the switching motion and decay to zero when finished.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Switch points | 0.24 / 0.46 / 0.68, interval 0.22 (≈34f / 1.14s) | The interval is the duration needed to finish reading one role; <0.12 viewers cannot read the label in time, >0.3 the metronome rhythm falls apart |
| Switch travel | Window 0.14 (≈22f), `E.spring(k, 0.25)` | Travel accounts for 64% of interval → rest time ~12f; damping 0.25 gives a distinct single bounce, smaller values shake twice and interfere with adjacent switches |
| Step distance | STEP=76px (bracket 92px, avatar 58px) | Step distance must exceed avatar diameter otherwise adjacent items overlap edges; 76/92 means avatars exiting the frame still show a corner, hinting at queue presence |
| Scale decay | `1 - d*0.38`, lower bound 0.5 | One slot distance shrinks to 0.62; steeper slope makes exit more decisive, but 0.5 lower bound hits ceiling earlier, turning queue into "two stepped sizes" |
| Opacity decay | `1 - d*0.62` | Disappears completely beyond 1.6 slots distance → ~3 avatars always visible on screen; dropping slope to 0.3 reveals all four, weakening bracket "locking" semantics |
| Blur decay | `d*2.4`, upper bound 3px | Blur suggests depth of field, 2.4 slope gives adjacent slot ~2.4px blur; >4px turns adjacent items into blurry patches, unreadable as avatars |
| Label decay | `1 - d*2.2` | Slope must be significantly steeper than avatar's 0.62—labels are text, two translucent sentences overlapping is hardest to read |
| Bracket pulse | Window 0.1, `sin(·π)` × 0.07 | 7% is the feel of a solid mechanical click; >15% bracket steals the spotlight from avatar replacement |

## Known Pitfalls
- Four avatars match three switches: `pos` ends at 3, exactly the final slot. Adding a fifth avatar requires adding a fourth switch (and the last switch must end before 0.86 to leave rest time), otherwise queue end never enters bracket.
- Switch points are hardcoded arrays appearing in two places (`pos` accumulation and `breath` accumulation). Altering cadence requires updating both simultaneously; missing one causes bracket pulse and avatar shift to desync.
- Entrance stagger to first switch interval is only 0.09 (entrance ends 0.15 → switch 0.24). Adding avatars pushes back entrance end point (`0.12+k*0.03`), so 5+ avatars require delaying first switch.
- Avatars use white outline icons + neutral grayscale lighting gradient circles (grayscale layering only distinguishes queue items), accent color only applies to bracket's four SVG corners (and label chip dot)—keep this division when replacing with real avatars; avatar itself should not steal accent color.
- Bracket SVG's four paths and 92×92 viewBox are hardcoded coordinates (`M4,26 L4,4 L26,4`, etc.). Resizing bracket requires recalibrating coordinates; changing container width/height distorts corner markers.
- Sentence "Your ___ agent" (demo: video-shotcraft agent crew Director / Editor / Animator / Sound) uses flex + gap:22px centered, fixed 92px slot width prevents sentence stem from reflowing during switches—verify text width changes on either side do not pull slot off screen center.

## Reference Implementation
demos/ui-entrance/avatar-bracket-carousel/
(AvatarBracketCarousel.tsx)
