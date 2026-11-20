---
name: row-embed
summary: Content rows descend with perspective, flatten into the page, and flash a thin amber seam at the moment of insertion.
use: Detail and list views where "structured data roots into the page"; batch entrances for row-level content.
duration: ~2s (12–68f)
energy: Medium
---

## Intention
Rows in a detail view do not merely "appear"—they "grow into" the interface. Each row descends from mid-air and seats seamlessly into the page layout, with an accent-colored seam flashing at the instant of insertion acting as a visual onomatopoeia for a mechanical "click."

## Motion Core
- Rows fly in from above according to an accelerating cadence (hitting target slots with momentum + vertical motion blur), leveling out rotateX from an upward angle, with scale slightly overshooting before a press rebound.
- Row slots start covered with true page-background patch fills + faint dashed placeholder outlines; upon landing, patches dissolve to reveal under-textures; slot contact shadows tighten and solidify as rows approach.
- Insertion moment triggers a 2px accent-colored seam expanding outward from center across bottom row edge before fading.
- Camera tilts down slowly and pushes in subtly in parallel with row arrivals; framing remains completely filled by the page throughout.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Cadence | cue = 12/22/31/39/46 (intervals shrink 10→7), flight 12f, last row lands at 58f, accent seam settles at 66f ≤ shot 68f budget | Calculate "when final row lands" before setting cues—stagger × row count must fit budget (matching core math of document-typewriter-reveal) |
| Flight attitude | `perspective(900px) translateY(−120·air) rotateX(16°·air)`, progress easing bezier(.5,0,.8,.75) (retaining speed at impact), scale 1.06→0.995 then 4f press-bounce to 1 | rotateX leveling out is the key cue for "seating"; pure vertical drops read as flat stickers |
| Flight entity | backgroundImage samples full page screenshot, backgroundPosition negative offset clips out individual row | Texture slices preserve typography (Q1)—re-rendered text diverges noticeably from page font rendering |
| Placeholder patch | Row slot covered with page background #f9f6f1 patch (pixel-sampled; pure white reads as a blank board) + 20% dashed slot frame, dissolving 2f post-landing | Without patch, baked-in rows in background screenshot show early, causing fly-ins to look like double vision |
| Insertion flash | Bottom 2px accent seam (feathered ends) expands outward from center over 5f (Easing.out cubic), fades over 8f, with 7px glow | Flash occurs only on bottom edge and only once; flashing all 4 edges reads as selection state |
| Camera | cy 500→740, zoom 1.12→1.25, 68f eased downward tilt + subtle push | Camera move parallels row cascade to create "assembling as you watch" feel; waiting for rows to finish stalls pacing; keep page filling frame to avoid dead margins |

## Audio
Anchor transition-soft on section cut (f475 in template); avoid scoring audio for individual row landings—when row counts are high and intervals tight, per-row pops create machine-gun clutter; rely on visual accent seams for "visual foley" (S2 self-check).

## Known Pitfalls
- Flight destination must match actual page layout slots, seating flush upon landing (Q9)—"fly from air, embed into dashboard"; hovering without landing looks synthetic.
- Lighting effects such as accent seams must stay clipped within host element border radius (Q4 ruling); light bleeding past rounded corners is a hallmark of cheap motion graphics.

## Reference Implementation
demos/ui-entrance/row-embed/RowEmbed.tsx (formerly template/src/aifl/live/SceneDetail.tsx)
