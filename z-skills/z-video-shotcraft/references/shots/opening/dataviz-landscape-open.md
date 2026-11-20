---
name: dataviz-landscape-open
summary: Streams of light merge across a dark data landscape while labels hover and a shallow-depth camera glides forward.
use: Brand-level abstract opening ("data universe" metaphor), leading into light-themed product segments or wordmark; division of labor with glow-flyline-moves: that card handles connecting line narratives between cards within a segment, while this card is a full-frame landscape dedicated to openings
duration: 5–8s (opening ambient segment, <=1 time per film; demo 180f)
energy: Low start building slowly (starting position, preserving room for subsequent ascent)
tags: data, camera
---

## Intention
A brand-level opening category proven by the Linear Releases launch film: framing the data universe behind the product as a **dark-stage landscape**—tributary light bundles converging from screen depths into a central trunk (metaphor for "countless workflows merging into one product"). Realism stems from three pillars: (1) Fictional issue/task ID tags floating along lines (demo uses video-shotcraft shot numbers + camera move names: each tributary represents a shot merging into a finished film), prompting viewers to recognize "that's what I see every day"; (2) Heavy depth of field—foreground sweeping past in heavy blur, midground tags crisp and legible, background fading into haze, with three-tier depth transforming flat SVG into physical space; (3) Slow, steady camera flyover—this is an ambient establishing sequence rather than a technical showcase; leave high velocity for later shots.

## Motion Stages
| Stage | Frame Segment (@30fps reference, demo 180f) | Content |
|---|---|---|
| 1 Growth | f0–70 | Trunk draws on from near to far rushing toward vanishing point (36f out-cubic, glowing tip), tributaries grow staggered by 4–6f from off-screen on both sides, merging tangentially |
| 2 Flyover | f0–180 | Camera flies forward low along channel + gentle lateral pan (straddling growth phase), tags erect irregularly staggered across f44–96, bright pulses stream toward confluence along completed lines |
| 3 Handoff | f104–180 | New tags cease appearing; accent glow blooms at vanishing point as headline settles from sky; camera decelerates via Bezier to gentle stop, holding >=30f |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Bundle scale | 8–14 tributaries merging into 1 main trunk (demo 11 lines, including 1 near-field line brushing past lens) | More than ~16 lines reads like a screensaver/tech template; trunk must remain unique (single-hero principle applied to landscape) |
| Ground projection | Lines drawn on authentic perspective ground plane: pinhole projection `sx = 960 + F*(X-camX)/Z'`, `sy = horizon + F*camH/Z'`, F 1100, camera height 220, horizon 0.39 frame height | Planar SVG panning requires manually faking three parallax tiers; true projection delivers foreshortening, parallax, and convergence out of the box |
| Confluence topology | Tributaries merge tangentially into trunk via Bezier (confluence tangent = trunk tangent); trunk path positions vanishing point in right 1/3 of frame | Perpendicular intersections read like circuit boards rather than waterways; centered vanishing point results in stiff composition |
| Depth of field | Segmented by projected depth: Z' <~1000 enters blur layer (blur 11px, stroke width x1.3), midground sharp, Z' >2600 fogs into fade; stroke width = worldWidth * F/Z' | Without foreground blur it reads like a wireframe; without background fogging it clumps into a bright knot on horizon |
| Camera flyover | Forward 950 world units / 180f, bezier(0.3,0.3,0.55,1): moving from start, decelerating to soft stop at tail; layered with lateral drift -140->110 | Too fast becomes a chase shot (crash-zoom territory); forward push without lateral drift weakens depth separation |
| Stroke drawing | Each line sampled equidistantly along arc length and drawn segment-by-segment (per-segment width/opacity), **butt end caps** | Round caps overlap at each joint on translucent strokes, turning entire line into a string of beads |
| Sense of flow | Narrow-peak bright pulses drift slowly toward confluence along line post-growth, visible only in mid/far depth (near segments span wide on screen, stepping discretely) | Lacking flowing elements after growth phase degrades second half into a "static route flyover" rather than a "data stream" |
| Tags | Midground 5–9 tags (demo 6): accent square pin pinned to line + short post + monospace ID pill, scaled by 1500/Z' perspective (clamped 0.7–1.7); distant drawn first, near drawn last | **Post world height must be well below camera height**—when post height ~ camera height, all tags project onto horizon in a crowded row; verify start/end coordinates frame-by-frame |
| Growth rhythm | Trunk 30–40f out-cubic leads, tributaries stagger by 3–6f each | All lines growing simultaneously reads like a loading spinner |
| Settle | Stop adding tags >=15f before handoff; camera decelerates smoothly without abrupt braking; title (eyebrow + two 108px lines) rises word-by-word | Abrupt braking during ambient sequences creates jarring visual hiccups |

## Known Pitfalls
- Reference provenance: Linear Releases opening, single exemplar sample—parameters are guidelines rather than dogma; re-verify against real assets in production.
- Do not use in adjacent segments with glow-flyline-moves: both are "dark-stage glowing lines"; appearing back-to-back makes the film feel repetitive; separate by >=2 light-stage shots if both are used.
- Dark-stage entry and exit costs mirror glow cards: use hidden-cut families from shot-transitions when connecting to light-stage product segments; avoid raw cuts between dark and light.
- Pure white full-brightness lines blur into a spiderweb—separate luminance across tiers (see parameter table); midground is the hero tier; apply 1–2px soft glow to trunk/tributaries for illuminated line atmosphere; zero glow reads like a raw wireframe.
- Tag font size must maintain >=18px equivalent at target resolution, otherwise legibility degenerates into decorative noise.
- Audio: layer risers and low-frequency pad room tone; do not ping tags individually (avoid per-item audio in batches); single whoosh/impact at handoff frame transitions to next shot.

## Reference Implementation
demos/opening/dataviz-landscape-open/
(DatavizLandscapeOpen.tsx)
