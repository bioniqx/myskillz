---
name: lead-word-zoom-assemble
summary: The lead word fills the frame at 2.3x and keeps drifting toward the viewer, then a single curve recedes it to size while the line slides left and the trailing words are pushed into their slots — pivoting on the lead word centre and the measured baseline.
use: "Introducing" title cards for brand/product names; keynote-style opening second shot; single-sentence claims requiring "let one word fill the frame first, then assemble the full sentence"
duration: ~2.8s (84f@30fps; sentence assembled at f36, shift up and subtitle at f32–46, hold 26f, final 12f crash)
energy: Medium-high (opens with frame-filling large type, but features only one motion arc throughout with no secondary shock)
tags: opening
---

## Intention
The most common mistake with title cards is fading in the entire sentence at once — the viewer receives five words simultaneously and remembers none of them. This card turns reading order into a **physical sequence**: first showing a single word so massive it fills the frame while continuously pushing toward the viewer, forcing them to read it; then that word recedes to its final scale and position within the sentence as the rest of the line grows around it. By the time it settles, the viewer has registered the key term twice.

The true secret to the tactile feel is not the easing curve, but the **pivot anchor**. As the lead word travels from screen center to the third character position in the row, anchoring `transform-origin` at the row box center causes scaling and sliding to pull the text in opposing directions, producing visible baseline jitter in the final frames. Anchoring `transform-origin` horizontally at the lead word's center and vertically at the baseline locks those two coordinates completely, ensuring the row merely recedes in size with zero wobble.

## Motion Core
- **Two scaling phases combined into a single scale curve**:
  `scale = interpolate(f, [0,12], [2.3, 2.3·1.06], PUSH_EASE) + interpolate(f, [12,24], [0, 1-2.3·1.06], ZOOM_EASE)`.
  Phase 1 is the hold push-in (`cubic-bezier(.25,1,.5,1)`, decelerating to peak); Phase 2 is the recede (decelerating from peak to final scale 1). Writing these as additive terms rather than branching conditionals eliminates velocity discontinuities.
- **Receding and sliding share ZOOM_EASE** (`cubic-bezier(.5,0,.05,1)`, heavy ease-in-out, zero bounce):
  `translate = interpolate(f, [12,36], [slideDistance, 0], ZOOM_EASE)`. Both actions must read as **one cohesive movement**; using separate curves makes them feel like two disjointed beats: "scale down first, then slide over."
- **Calculating off-center distance**: `slideDistance = lineWidth · (0.5 - leadRatio)`, where `leadRatio` = horizontal center of the lead word as a fraction of full line width. For the lead word to sit dead center initially, the full line must be offset rightward by this distance.
- **Measured pivot anchor**: At mount time, `delayRender` suspends rendering to measure three values: row `offsetWidth`, lead word `offsetLeft + offsetWidth/2`, and the baseline. The baseline is measured via a **zero-sized inline-block ruler**
  (the `offsetTop` of `<span style={{display:'inline-block',width:0,height:0}}>`), which is far more accurate than heuristic approximations like `lineHeight × 0.8`. Once measured, `continueRender` unblocks, setting `transform-origin` to `${leadRatio*100}% ${baseline}px`.
- **Subsequent words are pushed in, not faded in**: Word i (i≥1) starts pushing in at
  `pushStart = 12 + 6 + (i-1)·4`, with `translate` moving `0.5em → 0`
  (`cubic-bezier(.22,.8,.36,1)`, quick start, long landing), and opacity fading in over just 2 frames. Fade-in must be extremely short; otherwise, words appear to "dissolve in" rather than being "pushed into their slots."
- **Inter-word spaces must be placed outside inline-block elements**. Appending spaces inside word spans causes row boxes to collapse them, resulting in words colliding after settling (an upstream bug fixed here).
- **Three-act scene resolution**: At f32–46, the full row executes `translateY 0→-56px` (outCubic), while the subtitle fades in and rises 16px **within the exact same window** — the vertical space yielded by the row is immediately occupied by the subtitle with zero dead air; f46–72 holds completely static for 26f; f72–83 executes a full-scene `scale 1→1.2` + `blur 0→9px` + `opacity 1→0.45` (ease-in-quad), crash-zooming into defocus to hand off to the next shot.
- **Texture (demo)**: The lead word enters with 8px→0 defocus in the first 6 frames; the receding phase applies transient defocus proportional to scale velocity (≤3.5px, returning to 0 when settled); background uses a low-contrast mesh of indigo main light + warm ambient reflection, with grain and subtle vignetting.
- **Accent word**: Swap accent color for an exact matched word (in demo: the brand name `video-shotcraft`). The brand word naturally commands emphasis upon slotting into place, requiring no secondary animations.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Lead word initial scale | initialScale 2.3 | 2.3 lets the lead word slightly overflow horizontally (reading as "too massive to fit"); <1.8 feels like "slightly large text," losing impact |
| Push-in | pushScale 1.06, fills 12f hold | 6% is the minimum perceptible amount of "still advancing toward viewer"; >1.15 reads as a reverse bounce during recession |
| Hold duration | 12f | Duration the lead word owns the screen; <8f is insufficient to read a long word; >20f breaks sentence rhythm |
| Recede duration | 12f, ZOOM_EASE | Shares curve with leftward slide; giving recede a faster independent curve causes the row to shrink first and slide second, breaking into two beats |
| Leftward slide | assembleDuration 24f | Twice as long as recede: text scale settles while position continues drifting; this "gliding tail" provides cinematic polish |
| Subsequent word delay | wordDelay 6f (after recede begins) | Release subsequent words only after the lead word begins receding; releasing at same frame clusters words into visual clutter |
| Word stagger | wordStagger 4f | 4f reads as "sequentially pushed into place"; 0 brings the entire tail at once, reverting to a generic sentence reveal |
| Word push-in | wordDuration 12f, wordPush 0.5em | 0.5em represents "just outside its slot"; >1em reads as flying in from offscreen, clashing with the lead word's inward momentum |
| Word fade-in | wordFade 2f | Deliberately brief; >6f makes words dissolve in softly, destroying physical mechanics |
| Typography | 96px / 600 / -0.03em | Negative kerning keeps large type tight when scaled 2.3x; positive kerning on large type looks like an outdoor banner |
| Upward shift + subtitle | f34–50, -56px, subtitle in same window | Both actions must share the same window: shifting first and showing subtitle second creates an awkward dead pause |
| Static hold | 22f | Readability pause after settling; under 15f viewers cannot finish reading the subtitle |
| Crash-zoom | Final 12f, scale→1.2, blur→9px | This is the first half of a transition; its momentum must match frame 1 of the next shot; looking "unfinished" in isolation is expected |

## Known Pitfalls
- **Incorrect pivot anchor causes baseline jitter**: `transform-origin` must strictly be the pair "lead word center % + baseline px." Using row box center (`50% 50%`) causes scaling and sliding to pull against each other, producing jarring baseline jumps in the final frames.
- Never estimate the baseline: Heuristic rules like `lineHeight × 0.8` vary by several pixels across fonts, which magnifies into a ten-pixel wobble when scaled 2.3x. Reading `offsetTop` from a zero-sized inline-block ruler is the only reliable method.
- The entire line **must** maintain `opacity: 0` during `delayRender`: Otherwise, frame 0 before measurement flashes an unaligned giant word, creating a dirty glitch frame in the final video.
- Layout is measured dynamically at mount time, meaning **results depend on fonts in the rendering environment**: Cross-platform font fallback shifts line width and lead-word ratio; hardcode the three measured values as constants if cross-environment variance is unacceptable.
- `scale` and `translate` are written as separate CSS properties (not the `transform` shorthand); mixing them causes one to overwrite the other. Merging into `transform` requires enforcing `translate → scale` execution order manually.
- Placing inter-word spaces inside word spans causes row boxes to collapse them; this bug is subtle at small sizes, but at 96px words visibly collide.
- The lead word must be a **short word**: ~10 characters like "Introducing" is ideal; words exceeding 14 characters overflow screen edges at 2.3x scale, cutting off the ends.
- Apply accent color to only one word: Colorizing multiple words confuses visual focus and degrades the landing punch into generic "colored titles."
- The final crash-zoom is the first half of a transition, not a resolution. Used alone at the end of a video, it feels abrupt — replace crash with a static hold or fade-out if ending a sequence.

## Reference Implementation
demos/typography/lead-word-zoom-assemble/
(LeadWordZoomAssemble.tsx)
