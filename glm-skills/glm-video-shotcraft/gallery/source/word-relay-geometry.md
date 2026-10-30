---
name: word-relay-geometry
summary: Three benefit words hand off in turn, each with its own geometry — a spinning dashed circle, three interlocking circles that trim into view, and a metallic sheen that resolves to pure white.
use: Three-part value proposition statements (Faster / Tighter / Stronger); brand values segments; mid-section momentum requiring "a distinct world for each word"
duration: ~6.0s (180f@30fps: three segments ≈60f each, overlapping by 6f)
energy: Medium-high (3-beat progression + continuous geometric motion + background particles, zero static frames)
---

## Intention
A three-part value proposition easily devolves into three hard-cut title cards. The relay approach pairs each word with **a bespoke geometric motif tailored to its meaning**: a spinning dashed circle represents rotary speed ("Faster"), three interlocking circles trimming and contracting represent precision grip ("Tighter"), and a metallic sheen sweep represents hardened substance ("Stronger") — the geometry itself argues on behalf of each adjective. The third word receives elevated hero treatment (chrome sheen sweep + snapping to solid white) because it delivers the conclusion. Floating ambient dust, unified stage lighting, and a bottom 3-segment progress bar stitch the three beats into a single continuous space, avoiding the disjointed feel of three isolated slides.

## Motion Core
(Demo: graphite dark field cinematic title card, vocabulary Faster / Tighter / Stronger, native 1920×1080 coordinates)
- Three segments scheduled by frame: Faster 2→62, Tighter 56→122, Stronger 116→180; each segment has a 14f entrance (snappy, `scale 1.06→1` + 10px unblur) and a 10f exit (strong ease-in exit, `scale 1→0.86` + 12px defocus); the 6f inter-segment overlap ensures a fluid baton handoff rather than a hard cut; the final segment has no exit, holding static for 22f after resolving to white.
- Three layers per word (230px/800, static font Helvetica Neue): `outline` layer `-webkit-text-stroke:2px` + transparent fill, `fill` layer solid white — **outlines land first, fill reveals second**; all three layers share `padding: 0.08em 0.1em 0.28em`, preventing mask/background-clip from clipping descenders on 'g' or the right edge of final letters to leak underlying stroke layers.
- Fill for the first two words wipes horizontally via a ±7% soft-edged `mask-image` (starting 10f after entrance, lasting 18f, swift), while outline opacity drops synchronously to 0.2 to retain subtle ghosting.
- Geometry for Faster: Large dashed circle (r=400, `dash 10 16`) + outer 120-division tick ring (r=452, slow counter-rotation); enters across 22f expanding snappy from 0.4 to 1 while spinning an extra 160° to brake into position (flywheel physics), thereafter continuing a perpetual slow rotation; a 16-segment fading white comet streak races along r=400 at 7.5°/frame — "speed" is perceived through the differential velocity of the two rings and the comet.
- Geometry for Tighter: Three solid circles (r=218) with `pathLength=1` + dashoffset trim growth, launching around their respective centers via `rotate(-90 cx 0)`, staggered at delays 0/6/12f, each taking 22f (out), with a glowing pen-tip dot extinguishing upon completing stroke; starting at 92f, the circle centers contract from spacing 340 to 300 over 14f (swift), brightening upon lock while four diamond rivet glints pop in with overshoot at intersection points — "tightness" is a visible physical clamping action.
- Stronger features no auxiliary geometry: at 120f, outline transitions to a vertical chrome gradient (bright crown — dark waist — bright foot); across 124→148f, a narrow white band with warm champagne tint (`100deg`, `background-size:300%`) sweeps left to right; across 146→158f, it snaps to pure solid white accompanied by a bloom pulse, while a horizontal light streak below expands snappy from 0.2 width and stage key light brightens in sync — elevated hero treatment reserved solely for the concluding word.
- Below the title, a 40px subtitle delivers product proof (words rise sequentially via rise; demo features three promotional claims for video-shotcraft), with upper-left monospace counter "01 / 03", upper-right engraved logo + lowercase video-shotcraft wordmark, and bottom 3-segment progress bar (label-grade texture); camera executes an ultra-slow push-in 1→1.025 smooth throughout (no camera jitter).

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Segment timing | Each ≈60f, overlapping by 6f | ~2s per word is the lower limit to "read text + perceive geometry"; overlap <3f feels like a hard cut; >12f causes words to fight on screen |
| In/out windows | In 14f snappy / Out 10f exit | Exits shorter than entrances ensure decisive departures; using ease-out curves on exits feels reluctant and sluggish |
| Outline → fill | 18f swift, ±7% soft edge, outline retains 0.2 | Retaining subtle outline ghosting creates tactile depth; dropping to 0 flattens type; window >30f feels like a slow loading bar |
| Dashed circle | r=400, `dash 10 16`, scale 0.4→1, spins extra 160° to brake | Braking provides the primary proof of velocity; scale start >0.7 loses the sense of organic growth |
| Comet streak | 7.5°/frame, 16-segment fade | Must travel >8x faster than the ring to communicate speed differential; <8 segments breaks tail into dashes |
| Trim growth | Staggered 6f per circle, 22f each | Phase difference is critical for interlocking feel; simultaneous growth reads as three unrelated circles |
| Contraction | Spacing 340→300 (14f swift) + intersection rivets | Displacement <20px is imperceptible; >60px squashes circles into an unreadable clump |
| Sheen sweep | `100deg`, `background-size:300%`, 24f smooth | 300% ensures the highlight band spans only a fraction of letter width (= metallic specular); base chrome gradient is mandatory to avoid sweeping across flat grey |
| Snap to white | 12f + bloom pulse + baseline light band | The sole concluding elevation in the sequence; removing it makes all three words equal, depriving the sequence of a resolution |
| Typography & color | Word 230px/800, subtitle 40px, geometry `rgba(236,238,244,.42)`, graphite dark field | Geometry must be dimmer than text to preserve hierarchy; brighter geometry steals the spotlight |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **The three words must share identical syntactic structure (demo uses comparative adjectives, 6–8 letters each)**: Segment durations are equal; geometry coordinates (circle radii, center spacing) are hardcoded, so longer words breach the dashed circle or collide with interlocking rings — adjust `r` and contraction spacing if modifying vocabulary.
- `-webkit-text-stroke` is a vendor-prefixed property supported in Chromium/WebKit; in Firefox, the stroke layer renders transparent (words vanish). Remotion renders via Chromium with zero issues, but verify in development previews.
- SVG trim normalized via `pathLength=1` has incomplete support on some older browser engines for `<circle>`, rendering circles instantly complete without growth — verify a test frame in target engines.
- Exit trim subtracts exit segment progress directly from entrance trim progress: placing windows too close (segment length <40f) triggers retraction before expansion finishes, drawing only partial circle arcs.
- The sheen layer and fill layer are stacked DOM nodes: switching relies on opacity crossfading; insufficient overlap between `white` and `sh` windows causes 1–2 frames where both layers are semitransparent, resulting in dull grey text.
- Elevated hero treatment can only be awarded to the third word: applying chrome sheen to all three words destroys the climactic resolution (aligning with P4 anti-repetition principles). Audio: three entrances act as three rhythm points; the third word snapping to white warrants a heavy impact sound; see sound-design.md.

## Reference Implementation
demos/typography/word-relay-geometry/
(WordRelayGeometry.tsx)
