---
name: tear-streak-transitions
summary: A high-energy tear: horizontal glitch strips whose displacement hides the hard cut.
use: High-energy page transitions: digital glitch / disruption semantics; strip-level tearing that keeps page integrity intact while pushing energy to the max.
duration: Prior state ≥40f + tear 16–24f + settle ≥40f, approx. 4.5s (135f).
energy: High
tags: effects
---

## Intention
This card governs **strip-level digital tearing**—the page is sliced into horizontal bands moving at high velocity, yet the content within each band remains intact. This represents a taste boundary defined by repeated review rulings: fragmented block transitions were struck down three times in succession (doom-melt vertical drip, pixel-dissolve black tile flips, and facade-block 3D tumbling bricks were all eliminated), whereas strip-based transitions passed. Fragmented blocks read as "the page is being destroyed," whereas horizontal strips read as "the page is undergoing high-velocity motion"—maintaining structural integrity while driving kinetic energy to its peak. Horizontal tear: strips jitter with left/right displacement + dual-color silhouette ghosting (a restrained take on RGB split: two monochromatic silhouette duplicates of the page content rendered strictly in the scene's two accent colors, offset by ±12px). Ideal for system disruption or instantaneous state-flip semantics—the demo applies it to a state transition where a deployment console snaps from "Rolling out 99%" to "is live."

## Variant Selection
| Variant | Method | Application |
|---|---|---|
| A glitch-displace | 16 horizontal strips of unequal height (outer container clip + inner full-page translateY counter-alignment); each strip's translateX is driven by library standard hash h(i*31 + f*7) producing ±70px jitter, layered with dual-color silhouette ghosting + glowing scanlines; hard cuts to Page B at 54f amidst full-amplitude jitter, shaking for 6 more frames until resetting cleanly at 60f | Glitch / disruption semantics; instantaneous state flips (going live, switching releases); violent page transitions before a climax |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Jitter amplitude | ±70px, energy distributed across strips (~20% stationary / ~30% full throw / remainder subtle flutter), displacement mapped through power 0.6 to push values toward extremes; solid background layer underneath prevents revealing gaps | Peak-frame strip displacement must be glaringly obvious—±12px offsets fail to register as a tear; uniform jitter across all strips resembles water ripples |
| Envelope | 44–47f out-cubic surge → plateau → 54–60f linear dissipation | Impact precedent: out-cubic expansion, linear decay |
| Ghosting | ±12px dual-color silhouettes (monochromatic copies of page content in scene accent colors, screen blend mode, displaced synchronously with strips, applied only to high-displacement strips) | Jitter without ghosting is just shaking, not a glitch; silhouettes must render only foreground content without background fills to avoid muddying dark stages |
| Cut edges / Scanlines | 1.5px bright highlight on top edge, 3px dark gradient on bottom edge for strips with >25px displacement; 2 full-width glowing scanlines at random heights per frame | Drawing edge highlights on every strip makes the screen resemble ruled notebook paper—reserve highlights for heavily torn strips |
| Cut concealment | 54f exposure 1.28 / 55f 1.12 + 1.6% full-screen impact scale impulse recovering over 6f; 30–31f two thin strips twitch ±12px as an omen | Omens act as preparation: the audience senses something unstable before the full tear detonates |
| Unmasking | At 60f, conditionally unmount strips, ghosting, scanlines, and filters to display raw Page B directly | Setting opacity to 0 does not equal unmounting; lingering filters destroy true static hold |
| Settle | 75f (aftermath 40f: grid ripple waves in cyan-green, counter ticking, metric card rises + hold 35f) | R1; aftermath motions occur strictly within the page content layer, completely free of tearing elements |

## Known Pitfalls
- Demo was calibrated on a procedurally generated dark-mode console page (midnight look)—parameters are the starting point for tuning, not final production lock; must verify against real production assets on first use; on light-background pages, switch silhouette ghosting to multiply blend mode to maintain visibility.
- **Strips, never fragmented blocks**—future variations must strictly adhere to horizontal strips: individual bands remain cohesive and must never shatter into tiles, bricks, or falling debris (three-in-a-row rejection ruling, see Intention).
- High-energy transition; mind your energy budget when sharing a film with whip-pans or crash zooms—crowding high-energy transitions together dilutes impact across the board.
- The hard cut is hidden within peak-amplitude jitter (cut at 54f, settled by 60f)—exposing the cut frame on a static hold forfeits the cover of the glitch.
- Strip layers must possess an opaque background (gradient + dot matrix); vignettes and grain should only be rendered once on the top master layer—transparent strips cause ghosted overlaps with the underlying page, and moving vignettes along with individual strips exposes the seams.

## Reference Implementation
demos/transition/tear-streak-transitions/
(GlitchDisplace.tsx)
