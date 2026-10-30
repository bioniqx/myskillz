---
name: product-card-progressive-assemble
summary: A product card builds itself field by field as image, title and pills pop in, the old price gets struck through while an accent new price springs out, and highlighter blocks sweep across the copy.
use: Capability showcases on product/item detail views; primary shot for narratives around "structured extraction," "autofill," and "data assembling itself."
duration: ~5.7s (172f @ 30fps)
energy: Medium (Dense sequence of micro-events without a single explosion; maintains forward momentum via continuous slow camera push)
---

## Intention
Fading in a detail card directly merely tells viewers "here is a card." Assembling it field by field transforms the card into a **form actively being filled in real time**: as each field snaps into position, the viewer's attention is guided step by step through the card's information architecture—where the image lives, where the title is, where the price sits, and where body highlights lie. Price strikethrough downgrade is the sole semantic event in the entire sequence (representing a transformation rather than a mere appearance), which is why it is staged at the most prominent position mid-sequence.

## Motion Core
(Demo: porcelain aesthetic, native 1920 coordinates; 1520×840 detail card spans 79% screen width; featured product is video-shotcraft itself: studio photo with emblem, title Shotcraft, value props and palette swatches)
- Field schedule uses absolute 30fps frame numbers: cursor arrives at image 8 / title 20 / pills 30 / price 42 / body 76 / color swatches 96 / button 114; fields start settling 2f after cursor arrival; intra-group intervals are 3f (pills, body lines, swatches), while inter-group gaps span 10–20f—timing cadence visually organizes information hierarchy.
- Autofill cursor: cobalt 2.5px outline box + 6px ambient glow + AUTOFILL badge, interpolating position and size between adjacent field bounding boxes via asymmetric in-out (`cubic-bezier(.4,0,.2,1)`, 6f); finally docks into button (ease-in 8f fade-out). This is the only lighting effect in the shot.
- Skeleton slots: light gray skeleton placeholders fill slots prior to arrival, fading out in sync as content lands—reinforcing "a form being populated" rather than "elements popping in."
- Dual arrival styles: `rise` (upward travel 10–26px + 6px→0 de-focus fade-in, expo-out 14f) for image/title/price/body; `pop` (spring damping 13, scale 0.4→1 with distinct overshoot) for pills and swatches; smaller elements pop, larger blocks rise.
- Price downgrade at f62 ($449 holds 18f after settling): over 6f, simultaneous "scale 1→0.46 + gray out + 9px strikethrough line drawing from left"; from f63 cobalt new price "Free" (Apache-2.0 open source) springs in (damping 14) from 1.18 down to 1, followed by OPEN SOURCE chip sliding in at f69.
- Highlighter sweep: cobalt 16% background block `scaleX 0→1` (left origin), starting at f86 / f90 for 6f each—faster than field arrivals, reading as a pen stroke sweeping across text.
- Action button: ink-black fill expands left-to-right over 12f starting at f116, with label fading in at f122.
- Full card breathing: `scale 1→1.035` (asymmetric in-out) across 0–132f; entrance 0–14f scale 0.96→1 + upward 30px; tail holds static for 40f.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Field timeline | Cursor 8/20/30/42/76/96/114, arrival +2f | Homogeneous fields stagger by 3f, distinct categories gap by 10–20f; uniform intervals feel like a robotic roll call |
| Cursor jump | 6f, swift in-out, synchronized box morphing | <4f reads as a telemetric flash; >10f cursor lags behind fields, turning "anticipatory extraction" into "post-hoc selection" |
| Field arrival travel | 14f expo-out | Duration exceeds group interval → multiple fields in a category move concurrently, feeling like a fluid wave |
| rise displacement | 10–26px (scaled to font size) | Large headlines move more, captions move less; >40px fights against forward camera push |
| pop | Spring damping 13, 0.4→1 | Pills and swatches are compact so overshoots do not collide with neighbors; using pop for large blocks looks unpolished |
| Price downgrade timing | f62 (18f hold after price lands) | Must leave ample time to register original price; rushing reads as if the product was always on sale |
| New price spring | Damping 14, 1.18→1 | Sole zoom-rebound event in shot; lower damping wobbles twice, competing with adjacent strikethrough |
| Highlighter sweep | 6f, `scaleX` from left | 5–6f captures hand marker speed; >12f reads as a background gradient fade |
| Card slow push | `scale 1→1.035`, 0–132f | Spread over 4.4s acts as pure breathing; >8% pushes card into frame edge |

## Known Pitfalls
- Field bounding boxes (cursor targets) are hardcoded absolute coordinates: modifying font size or copy requires updating box definitions in table `F`, otherwise cursor misaligns with text.
- Final field settles at ~f128, leaving ~1.3s with subtle push—this is reading time for viewers to take in the assembled card, not dead space to cut.
- Three body lines enforce `white-space: nowrap` (34px, width ≤ 700px). Applying longer text or other languages risks overflowing card margins; recalibrate font size and line lengths accordingly.
- New price and discount chips use absolute positioning (x estimated for 112px bold digits); changing price digit counts requires layout adjustment to prevent chip clipping digits.
- Content represents video-shotcraft demo copy ($449 strikethrough to Free, feature copy, brand color swatches; $449 is illustrative); the structural field assembly itself is the reusable asset. Real product data alters field counts, requiring timeline reorganization.
- Highlighter start cues (f86/90) lag row arrivals (f78/81) by 8–9f; adjusting row timings requires synchronizing highlighters to prevent highlighting before text arrives.
- Cobalt BLUE is the sole accent color (cursor + new price + chip + highlighter); swap accent tokens for client branding while keeping remainder neutral.

## Reference Implementation
demos/ui-entrance/product-card-progressive-assemble/
(ProductCardProgressiveAssemble.tsx)
