---
name: title-demote-to-label
summary: A centered headline stands for a beat, then shrinks and slides to the top-left corner to become a section label as content grows beneath it.
use: Chapter openers (headline claims the spotlight first, then yields to content); section transitions in tutorials / feature demos; Variant B adds product cues for text/editor tools
duration: A ~3.7s (112f) / B ~4.5s (134f); demo chains both variants in 246f
energy: Low-medium (editorial layout transformation, atmospheric shot)
tags: transition
---

## Intention
The conventional fate of chapter headings is "enter → vanish → content appears," leaving heading and content disconnected. This card lets the heading **demote rather than exit**: large centered type holds for a beat to declare the topic, then in a single continuous tween scales to 0.3x and glides to the top-left corner, landing as the section label — remaining on screen, but transitioning from protagonist to signpost. Viewers receive effortless spatial continuity: the massive word they just saw is now the label in the upper-left corner, signaling what the section discusses. The content skeleton begins growing while demotion is underway, achieving a zero-dead-air handoff.

## Motion Core
- Demotion is a **single continuous tween**, 26f asymmetric in-out (bezier(0.6,0,0.18,1): decisive takeoff, soft landing):
  scale 1→0.22 (220px title → ≈48px label) + position (960,540)→(216,196) sharing the same curve — splitting into two phases (shrink first, slide second) reads as two disjointed actions.
- transform-origin anchored at left-center; centering correction translate(-50%) smoothly zeros out with the tween (`translate(${-(1-dem)*50}%, -50%)`) — without zeroing out, the destination offsets by half a width.
- Reveal entrance: Title letters rise sequentially from below an invisible mask line (16f/letter, 1.6f stagger), with a vermilion period popping in 10f later with overshoot;
  monospace eyebrow "CHAPTER 01" tightens kerning inward. After revealing, the title must hold static for ≥18f before demoting (demo: 20f with 1.5% subtle push-in) —
  demoting without a hold obliterates the declaration beat. The eyebrow fades out across 6f upon takeoff, while label prefix "01 /" wipes in from the left to take over before settling.
- Staggered content growth (demo: storyboard canvas for video-shotcraft, using chapter titles "Frame." and "Craft.":
  A = 60px intro + three cards [recipe card / user quote / beat grid]; B = 58px script + inline selection → connector line → matched recipe card note): each block wipes in from left (width 0.3→1, text uncompressed) + 30px upward fade-in, staggered from dense to sparse; growth begins at frame 12 of demotion, so content expands while the title is still in flight — this overlap is the source of seamless handoff.
  The full-width divider line draws a few frames later to avoid intersecting the title's flight path.
- Variant B selection highlight: Left edge and width percentages tween independently — width expands 0→100% to cover (10f), left edge advances 0→100% to clear from left (8f); demotion triggers only after highlight clears completely.
- Directional motion blur proportional to positional velocity is applied during demotion flight (0 at rest); Variant B selection uses 20% accent opacity + an insertion caret tracking its right edge.
- Chained sequence avoids white flashes: Sharing a single stage, Section A content exits upward in 12f ease-in → Section B headline reveals in place;
  prior to Section B demotion, Section A label shifts up one row, scales to 0.7, and grays out into "previous section," allowing Section B label to occupy the same slot (pattern for multi-section continuity without stacking).
  (Demo exports `TITLE_DEMOTE_TO_LABEL_DURATION` = 246f, look = paper).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Demotion tween | 26f asymmetric in-out, scale→0.22 (settles at ≈48px) | <14f feels like title was flung away; destination >0.45 crowds content; label <40px is unreadable |
| Hold beat | Static pause ≥18f after reveal | Skipping this beat moves the title before viewers can read it, wasting the demotion |
| Content stagger | Dense-to-sparse, blocks 18–22f, width 0.3→1 | Simultaneous growth reads like a page reload rather than organic expansion |
| Growth start | +12f after demotion begins | Waiting until title fully settles leaves an awkward 8f dead freeze |
| Selection highlight | Wipe-in 10f / hold 10f / clear 8f, 20% accent opacity | Highlight hold <5f reads like a glitch; demoting before clear carries dirty colored blocks |
| Section handoff | Old content exit 12f upward shift; old label 16f upward shift to gray out | Failing to clear old label lands new label directly on top = label graveyard |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Division of labor with 3D space scene-locking (deprecated, spatial style): this card represents continuous 2D editorial typographic demotion (editorial layout style) — use spatial cards when titles inhabit 3D product space; use this card when titles transform into section headers; choose one per video.
- Zero movement allowed along the demotion flight path: the flying title is the sole focal point on screen; content growing beneath its destination does not compete (due to staggered start), but popups or cursors entering simultaneously will cause chaos.
- When chaining multiple sections, **advance labels to new lines without stacking**: the active label shifts upward to yield space to the incoming label, preventing upper-left clutter.
- Variant B text selection simulates an editor environment — applying it to non-editor products carries empty semantics; do not add it merely for visual flair.
- Title copy should contain ≤3 words — after scaling to 0.3x, it must still function as a legible label; long sentences compress into a thin grey streak.

## Reference Implementation
demos/typography/title-demote-to-label/
(TitleDemoteToLabel.tsx)
Original source: perplexity-promo 16–18.5s; Variant B derived from Framer text-selection-title
