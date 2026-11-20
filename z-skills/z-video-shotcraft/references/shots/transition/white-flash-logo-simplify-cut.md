---
name: white-flash-logo-simplify-cut
summary: A liquid six-color gradient wordmark shimmers in place, the frame flash-burns to white with a blur-and-brightness pulse, and a flat gradient wordmark fades in and settles on the white.
use: Brand sequence resolution (flamboyant demonstration → pristine lockup); transition beat shifting emotion from technical virtuosity to authoritative declaration.
duration: Approx. 4s (120f@30fps; showcase 0–34f · anticipation 34–46f · whiteout surge 44–54f · exposure recovery 54–76f · lockup 72–96f · hold through 120f).
energy: Medium-high (a single pulsed accent, flanked by serene static stages).
---

## Intention
First deliver unabashed luxury (an iridescent liquid-metal wash rippling across the letterforms, swept by an angled specular glint), then deploy a white flash to "purify" the mark into a flat, monochromatic logo—communicating to the audience that "the spectacle has concluded; this is its true, authoritative identity." Dimensional reduction serves as visual rhetoric: shifting from emotional texture to rational brand recognition. Both versions share identical font size and layout coordinates, registering as "the same wordmark being purified," rather than an arbitrary image swap.

## Motion Core
- **Liquid Layer** (demo wordmark is "video-shotcraft", 190px font size, 700 weight, all lowercase, center y=500): A single span stacks four background layers, all clipped via `background-clip: text`—
  1. Iridescent base `background-size: 300%` flowing gently at 1.1% per frame;
  2. Vertical dimensional shading (bright top, deep bottom);
  3. Mid-body chrome specular band;
  4. Angled glint sweeping across once during 6–34f (Q4: granted strictly once to the hero element, clipped precisely within letter contours);
  Matching-color bloom beneath letterforms (blur 38px) + floor specular reflection (0.22 opacity, linear gradient mask); entire frame applies a gentle push-in from 1 → 1.035 across 0–44f.
- **Anticipation (34–46f, `EASE.exit` accelerating)**: Wordmark brightness climbs from 1 → 1.7, bloom intensifies; a horizontal anamorphic lens flare stretches outward from the letter core (wide soft halo + 4px sharp bright core with feathered ends).
- **Whiteout Surge (44–50f)**: A radial white sphere expands outward from the letter core to engulf the entire screen (radius 80 → 1580px, quadratic ease-in, visibly swallowing the wordmark over the final 3 frames); 50–54f holds pure white (breathing room), executing the scene cut on the 50f full-white frame.
- **Exposure Recovery (54–76f)**: White overlay clears from 1 → 0 (quint-out, fast then slow, mimicking the eye adjusting to intense glare)—the underlying flat wordmark is already in position, performing only a subtle 1.03 → 1 focus contraction.
- **Lockup**: Amber 96px accent bar draws outward from center across 72–86f; engraved lens emblem above the wordmark sketches in across 74–96f (viewfinder opens first, amber diagonal stroke cuts in after); brand tagline "Frame motion. Craft the shot." rises word by word (starting at 78f); ultra-slow camera creep from 1 → 1.01 across 96–120f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Whiteout surge window | 44–50f radial expansion (t² ease-in) + 50–54f pure white | Whiteout must enter rapidly; a uniform screen fade reads like a soft cross-dissolve, whereas detonating from the letter core conveys "the letter itself is overexposing" |
| Anticipation | 34–46f, brightness ×1.7 + anamorphic flare | Cutting anticipation makes the flash feel unprompted, like a dropped frame; adding box-shadow to the flare core produces a dark border artifact (verified in testing) |
| Exposure recovery | 54–76f, white layer fades via quint-out | Substituting a flat wordmark fade-in for recovery introduces a secondary "text emerging from white" action; recovery ensures the wordmark feels like it was "there all along" |
| Flat logo entrance | 1.03 → 1 (snappy, 52–78f) | >1.06 reads as the mark popping forward; simultaneously fading opacity stacks two competing reveal mechanics |
| Wordmark dimensions | Liquid / flat identical at 190px, sharing center anchor (15-character wordmark sized to fit screen width; short 4-letter words can scale up to 300px) | Mismatched positions or sizes make it look like a generic asset swap rather than an organic metamorphosis |
| Brand constants | `PAPER` / `FLAT_INK` / `FLAT_ACCENT` (defined at file header; demo standardized to video-shotcraft's editorial paper / studio ink / lens amber) | Swapping in project palette completes integration; the iridescent liquid layer is usually preserved (it represents "the spectacle," not the brand); the emblem appears only in the flat stage without liquid texturing (brand guidelines forbid gradients/glows on official marks) |

## Known Pitfalls
- The scene cut occurs precisely on the 50f full-white frame (rendering dark stage vs. paper base conditionally); the white layer must not recede before 50f, otherwise both scenes will be visible simultaneously.
- `WORD = BRAND.name` (15 characters); changing words requires recalibrating font size `FS`; liquid layer / bloom / floor reflection / flat layer share unified wordStyle and wordText.
- When the wordmark uses +0.03em tracking, the crossbars of "f" and "t" kiss, revealing an anti-aliasing seam artifact at large sizes—the demo resets tracking after "f" to zero to overlap the strokes.
- Pairing the whiteout with an SFX hit is mandatory (impact / bright whoosh); a silent whiteout reads like dropped frames.
- Specular glints must be strictly clipped within the letterform (`background-clip: text`)—overlaying a loose radial light blob spills outside the glyphs, hazing the black background with an unappealing white fog (Q4 light leak violation).
- The second half transitions to a bright paper background—if the subsequent shot is a dark stage, chain an appropriate transition or cut directly from this card's outro hold.

## Reference Implementation
demos/transition/white-flash-logo-simplify-cut/
(WhiteFlashLogoSimplifyCut.tsx)
