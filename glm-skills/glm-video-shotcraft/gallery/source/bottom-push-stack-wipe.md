---
name: bottom-push-stack-wipe
summary: Each new scene pushes up from the bottom edge with its own saturated background color, physically shoving the old scene out of frame.
use: Section-change backbone for multi-chapter product promos (each chapter features one selling point with one distinct background color); paragraph transitions requiring a "page-turn rhythm" running throughout the entire video.
duration: Demo three consecutive pushes 170f (~5.7s); single push 26f + in-chapter hold ~1.2s.
energy: Medium
---

## Intention
In wipe-transitions, a boundary sweeps across while both the old and new pages remain stationary; in page-turn, the old page splits open like double doors and slides out. This card introduces a third physical dynamic: **the new chapter shoves the old chapter out**—the two screens maintain rigid contact, moving at identical speed in the same direction, like vending machine push-stacking. The crux is "moving the entire screen along with its background color": the background color + window card + decorative strips are fused into a single slab that pushes in from the bottom edge, communicating to the audience that "the world has changed" rather than just "a card was swapped." A heavy ease-out (fast enter, slow settle) gives the push an authoritative "thunk" landing; the 40px seam shadow along the top edge serves as physical evidence of contact between the two screens. Chaining three consecutive pushes with fully saturated background colors turns the chapter transitions themselves into the metronome of the entire video—the original Slack promo relied entirely on this single technique as its structural backbone.

## Motion Core
- Each chapter is a full-screen layer: `translateY` pushes from +1080 to 0, while the old chapter is synchronously shoved to −1080—the displacements of both layers remain strictly synchronized with identical easing, as any speed differential reads as "sliding clip-through".
- Push-in easing = heavy ease-out `cubic-bezier(0.12, 0.9, 0.2, 1)` (fast entry, slow landing), completing in 26f (~12f already reaches 95%); chapter i's y = (1 − self push-in progress) × H − next chapter push-in progress × H, a single unified formula handling both entrance and exit; the entire stack applies directional vertical blur proportional to velocity.
- The new chapter's top edge carries a 56px gradient seam shadow (using a hue-matched dark tone of the new chapter from 0.42 → transparent, cast onto the old chapter) + a 2px rim light along the new chapter's top edge, fading to zero once settled—the physical tactile sensation of "pushing out" relies entirely on this detail.
- Demo adopts the "Swiss Poster" style (product: video-shotcraft, one chapter per selling point): Chapter 0 opens in near-black, followed by three chapters in Cobalt Blue #2d4cff / Vermilion Orange #ff4d1f / Acid Lime #cdf23a (with dark text), separated by ~120° hue intervals; each chapter features an eyebrow label + a 116px ultra-bold two-line headline + 40px description on the left column, paired with a custom-designed large-type UI card on the right column (dialogue with agent / beat-matching timeline / delivery pipeline); the palette is lit from top-left and shadowed at bottom-right, sharing the same light vector as card shadows.
- In-chapter animations are strictly staggered from the push-in: headlines only rise from below the line 12f after the push begins (once it reaches 95%), and subtle UI motions (typing → message pops in / soundwave handoff with current shot / delivery steps checked off one by one) take place during the hold.
- Push intervals are ~44f (in the demo, pushes start at 22f, 66f, and 110f); off-screen layers are unmounted in a timely manner; the final section features a 28f ultra-slow 1.5% push-in.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Push duration | 26f, heavy ease-out | <20f reads as a flash cut; linear constant speed reads like a rolling shutter door, losing all "thunk" weight |
| Inter-chapter hold | ~18f static + push tail, ~44f total in-chapter stay | The chapter interior is the content stage; <25f gets shoved away before the viewer can register the details |
| Seam shadow | 56px on top edge, 0.42 chapter-tinted dark gradient + 2px rim highlight | Without it, the two screens look like overlapping slides; >80px reads as the new chapter carrying a black bar |
| Background color | One saturated color per chapter, high hue contrast between adjacent chapters | Same-hue adjacent chapters make "chapter change" read as a "minor adjustment"; grayscale chapters can only serve as Chapter 0 |
| Pinned content | Window cards / decorative strips use intra-chapter absolute coordinates | If content is positioned relative to the viewport, it floats above the push animation, breaking the illusion |
| Push chain count | 2–4 chapters | A single push lacks rhythm; >4 chapters causes the audience to start counting background colors, inducing fatigue |

## Known Pitfalls
- The demo was calibrated and passed on grayscale/placeholder assets—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use.
- Division of labor with wipe-transitions: that card keeps both old and new pages static while a geometric boundary sweeps across (neutral, fits anywhere); this card moves both pages in a rigid physical push (tangible physics, carries innate chapter rhythm)—use wipe-transitions for one-off seams, and this card for the video-wide backbone.
- Peer selection alongside the three shot-transitions: this card carries medium energy with a fixed upward trajectory; transitions requiring wide energy disparities (such as entering the outro) should yield to flash-cut.
- Unidirectional motion is the source of structural rhythm: all chapters throughout the video push upward from the bottom; changing to left-push or top-push mid-way shatters the metronome—if directions vary, do not use it as a backbone.
- While push-in is active, both chapters share the screen as full-screen layers—interior animations (card entrances, etc.) must avoid the 26f push window (wait until at least 95% settled), otherwise both chapters moving simultaneously deprives the eye of an anchor.
- For production, use saturated tiers of brand color palettes; when background saturation is insufficient, the subordinate relationship of window cards "pinned to the colored base" fails to register, degrading into "individual cards changing backgrounds independently."

## Reference Implementation
demos/transition/bottom-push-stack-wipe/
(BottomPushStackWipe.tsx)
Original source: slack-promo 22–27s
