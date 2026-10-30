---
name: orbit-ring-title-open
summary: Eight 16:9 content cards orbit an ellipse at a constant rate with their contents frozen on the first frame, then all start playing together while the centred headline de-blurs into place and a marker block sweeps across the key phrase.
use: Opening establishing shot = "this product offers an entire ecosystem"; flagship showcase for asset libraries, template hubs, feature matrices, or case studies; grounds a central claim with authentic living product visuals rather than a static grid of screenshots
duration: 150f (5s@30fps; marker block settles at f64 followed by 2.9s steady orbit + slow push-in; HANDOFF_EXIT triggers exit handoff from f118)
energy: Medium (constant orbit is the sole ongoing motion; marker sweep is the single punch beat)
tags: ui-entrance
---

## Intention
When opening with "we offer an entire suite," the common approach arranges screenshots into a grid—yet grids are static, reading as "a pile of pictures" rather than "a living product." This card transforms display into an **orbital carousel**: eight cards orbit an ellipse at constant speed, with cards perpetually entering and leaving the frame, implying "there is always more," while the headline anchors immovably in the center.

The key design choice is that **card contents must truly play**. Static screenshots on a ring look like a generic carousel; running authentic animations turns the ring into "products actively working." However, eight cards playing immediately would overwhelm viewer attention—so cards are **frozen on their initial frame** during entrance, beginning playback in unison only after the ring expands and the headline commences. Viewers first recognize a ring of product surfaces -> read the headline -> then discover all cards are alive.

## Motion Core
- **Orbital positioning**: `theta = -pi/2 + i*2pi/8 + t*0.3`, `x = 960 + cos(theta)*RX*ringScale`, `y = 540 + sin(theta)*RY*ringScale`. RY/RX ~ 0.53 creates an "overhead tilted ellipse"; a true circle reads like a flat dial. Orbital track rendered as a 16% opacity accent hairline, drawn over 0–30f via pathLength.
- **Cards never tilt**: Cards track theta for position only, with transforms restricted to scale without rotation. Depth is governed by `depth = sin(theta)` (+1 = foreground bottom, -1 = background top): `scale = 1 + 0.12*depth`, `zIndex = 10 + round(depth*5)`; background (depth<0) layers `blur(1.6*|depth|px)` + dimming layer (DoF + atmospheric perspective), with foreground catching subtle top light. Scale, z-order, and luminance must derive from the exact same depth to prevent distant cards occluding near cards.
- **Ring entrance**: f0–24 `ringScale 0.62->1` (expo-out, 80% complete in first 1/3) expands from center; cards fade in sequentially, card i fading in over 11f and growing 0.9->1 from frame `2+1.5i`. Expanding while fading reads as "the ring growing" rather than "cards being pasted on."
- **Freeze initial frame then play**: Card content wrapped in `<Freeze frame={max(0, frame - 24)}>`. Before f24, all eight cards hold frame 0; from f24, all enter normal timeline simultaneously.
- **Decoupled internal coordinates**: Card content authored at 960x540, scaled externally via `scale((CW*s)/960)` with `transform-origin: top left`. Components need no awareness of scale reduction, allowing seamless substitution with real screenshots or other library cards without editing component code. Line-drawing cards use `pathLength={1}` so stroke lengths do not alter initial frames.
- **Two-tier headline blur-slide word-by-word**: Top line 64px secondary grey (starts f10, 1f stagger, 27f per word), bottom line 156px hero white (starts f18, 2f stagger, 32f per word—heavier and slower). Each word runs two channels starting together with distinct finishes: de-blur spans full duration (`blur (1-p)*fontSize/6`), while descent completes in first 1/3 (`translateY (1-p)*fontSize*0.22`), quint-out easing. Displacement halting before blur creates tactile "landing then snapping into focus."
- **Marker sweep + color invert**: `spring(frame-50, damping 20, stiffness 190)` drives `scaleX` (capped at 1.03), `transform-origin: left center`, block extending 0.14em beyond word bounds underneath text. Text rendered in two layers: white layer clips left of marker front, ink layer (onAccent) clips right of marker front, mapped via `(m*(W+0.28em) - 0.14em)/W`—sweeping inverts color instantly, reading as "highlighted by marker."
- **Headline scrim**: Dark radial scrim between card layer and text layer dims foreground cards passing behind headline.
- **Hold**: Entire composition smoothly pushes in 2.5% across f40–150 while ring continues steady orbit.
- **Exit (optional, HANDOFF_EXIT)**: Across f118–128, entire headline layer fades `opacity 1->0` + `blur 0->6.5px`, leaving only the rotating ring—enable when connecting to crash-zoom or clean cuts in full videos.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Ellipse radii | RX=720 / RY=380 (cards 400x225) | RY/RX~0.53 is the sweet spot for an overhead tilted ring; ratio -> 1 reads like a flat turntable; ratio -> 0.3 squashes cards into a line |
| Card count | 8 (azimuth interval 45 deg) | 8 cards rotate without mutual overlap at this radius; >=10 cards requires expanding RX/RY |
| Orbital velocity | 0.3 rad/s (5s rotates ~86 deg) | **Do not accelerate because it looks slow**: >0.5 rad/s creates strobe flicker at frame edges and distracts from headline |
| Ring entrance | f0–24, scale .62->1, expo-out | <15f feels like a popup; >30f overlaps ring expansion with headline arrival |
| Card fade-in | Card i starts at frame `2+1.5i` over 11f | Step 1.5f provides clear sequence; >3f pushes final card past headline start |
| Playback start | PLAY_START=24f | Must be >= ring expansion finish; starting earlier allows eight animations to clash during entrance |
| Depth | Scale +-12%, background blur <=1.6px + dimming | Scale >15% turns top cards into icons; blur >3px makes background look muddy |
| Headline | Top line 64px/500 grey + bottom line 156px/600 white | Hero line must be large and heavy to dominate active ring; equal sizes destroys hierarchy |
| Word cadence | Top line 1f stagger / 27f word; bottom line 2f stagger / 32f word | 1–2f stagger conveys collective de-blurring; >=3f reads like a typewriter |
| Marker block | Starts f50, spring damping 20, fluorescent yellow-green #c6f432 | Damping <14 bounces outside bounds; keep as sole high-saturation element on dark stage |
| Subtitle line | video-shotcraft logo + 30px lowercase wordmark + 26px mono "SHOT RECIPE CARDS" (tracking 0.2em), floats up over 16f from f60 | Wide mono tracking reads as product code; matching headline font looks like a redundant third line; avoid transient counters |
| Exit (optional) | f118–128, blur 0->6.5px | Full line de-focuses uniformly; **staggered word exit reads like a secondary entrance** |

## Known Pitfalls
- **Cards must never tilt with theta**. Adding `rotate(theta)` turns the display into a roller coaster, distorting text and zeroing legibility. Cards change position only, not orientation.
- Card contents must carry static skeletons on frame 0 (background, borders, labels, muted tracks). The freeze phase displays frame 0; if animations draw from nothing, viewers see eight empty cards during the first 24 frames.
- `zIndex` must follow depth strictly. Scaling without z-sorting allows DOM order to let background cards occlude foreground cards, breaking perspective.
- Marker block and text form a strict stacking context: block `zIndex:0` + text `position:relative; zIndex:1`. Omitting relative positioning places block over text.
- Headline `white-space: nowrap` is required for marker math—calculations assume highlighted phrase occupies a single line box. Wrapping causes highlight block to fracture across lines.
- The ring is an active background; **do not layer secondary ambient motion on top** (particles, sweeps, breathing gradients). Competing motions ruin visual hierarchy.
- Division of labor with `carousel-3d`: that card uses true 3D (`rotateY + translateZ` + backface-hidden) where cards rotate to reverse, ideal for seamless looping showcases; this card uses 2D pseudo-depth where cards perpetually face forward, ideal for supporting foreground typography.
- Demo cards are generic DOM placeholders (dark cards + singular neon accent, shadows shifting with depth) with zero screenshots; replace with custom components or real screenshots in production without changing orbital logic.

## Reference Implementation
demos/opening/orbit-ring-title-open/
(OrbitRingTitleOpen.tsx)
