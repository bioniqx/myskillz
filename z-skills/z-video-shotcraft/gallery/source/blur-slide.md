---
name: blur-slide
summary: Title words rise into place one after another as vertical offset, blur, and opacity converge on a single shared ease, with the subtitle following before the title settles.
use: Ideal for almost all paired title/subtitle scenarios; hero section copy on product pages, chapter subtitles; the default text reveal when seeking a "professional yet understated" feel
duration: ~4.0s (120f@30fps)
energy: Low (single-shot convergence, no peak, no loop)
---

## Intention
This is the **default solution** for text reveals — no spectacle, no mechanical gimmick, just placing words gently into position one by one. Its sense of professionalism comes entirely from one thing: the three channels of y, blur, and opacity share the same progress `p` and the same easing curve, so words "emerge from defocus" rather than "slide in and happen to fade in." When a video already has heavy techniques elsewhere (glitch, reels), the title should use this card to yield the spotlight to the hero.

## Motion Core
- Word progress `p = ramp(frame, start, dur, EASE.out)` (quint-out grade), with all three channels bound to the exact same p:
  `opacity = p`, `translateY = (1-p)·dy`, `blur = (1-p)·B`px (in the demo, the lead word's kerning tightening is also hooked to this same p).
- Main title (170px serif, two lines): Line 1 has 3 words starting at 10f, 4f word gap, 22f per word; Line 2 pauses 6f to breathe,
  "feel" at 26f, hero word "cinematic." starting at 30f with a 30f entrance window (settles last); `dy = 64`px, `B = 18`px.
- Subtitle (46px sans-serif, 9 words): starts at 34f, 2.4f word gap, 20f per word, `dy = 26`px, `B = 9`px
  — denser gaps and smaller displacements; **hierarchy comes from amplitude, not duration**.
- Staggered rather than queued: The subtitle begins at 34f, while the main title does not finish settling until 60f, overlapping by 26f —
  queuing reads like two separate beats, while overlapping reads like a single sentence.
- Split by word, not by character: Each word is wrapped in a span via `text.split(' ')`, and `line` uses `gap:0.32em`
  for word spacing (instead of spaces) — character-by-character entrances feel too fragmented, whereas word-level reveals provide a natural "spoken" cadence.
- Demo layout: paper look (warm white paper + ink + vermilion), magazine masthead (video-shotcraft wordmark) / footer hairline framing a page, vermilion all-caps eyebrow →
  170px serif main title (hero word in italic vermilion) → 46px sans-serif subtitle, left-aligned to a 168px grid; in the background, a 5% ink
  760px issue number slowly drifts in reverse for parallax; the text layer undergoes an ultra-slow push-in 1→1.03 (smooth) throughout, and the footer hairline draws from 72f to conclude the hold section.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Word stagger | Main 4f / Sub 2.4f | 3–4f is the sweet spot for "word-by-word"; <2f feels like the entire line enters at once with no stagger; >8f and the audience starts counting individual words |
| Single-word entrance window | Main 22f (hero word 30f) / Sub 20f, `EASE.out` | <10f reads like a hard bounce; >30f makes each word float too slowly, dragging down the sentence |
| y displacement | Main 64px (≈0.38em) / Sub 26px | Unequal amplitude between main and sub creates hierarchy; <0.15em displacement is unnoticeable; >0.6em feels like words fly in from offscreen into a slide |
| Blur channel | Main `(1-p)·18`px / Sub `(1-p)·9`px | This channel creates the "professional feel"; removing it degrades the motion into a generic fade-and-rise; exceeding ~12% of font size turns intermediate frames into blurry color patches |
| Main/sub stagger | Main 10f–60f / Sub 34f–80f | Overlapping ~26f forms "one cohesive sentence"; delaying subtitle start until after main title settles reads like two disconnected beats |
| Font size & weight | 170px serif 400 vs 46px sans-serif 400 | A size difference >2x establishes primary-secondary hierarchy; when weights are equal, differentiate by font family; 600+ weight on subtitles clashes with the main title |
| Ending hold | Subtitle settles at 80f, leaving ~40f at the tail (only ultra-slow push-in and footer finish) | Static hold <8f cuts away before the audience finishes reading |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- **The placeholder copy uses 5 words (two lines) for the main title and 9 words for the subtitle; keep word counts close when replacing copy**: total stagger length
  = `gap × word count`. Doubling the word count pushes the start of the final word back by 2x, squeezing its entrance into the ending hold
  — if exceeding 8 words, compress the gap down to 2–2.5f in tandem.
- All three channels must share the exact same `p`: writing separate easing curves (even with identical shapes) causes misalignments
  where "displacement arrives while still blurry," instantly shattering the smooth feel.
- Word-level splitting requires manual segmentation for non-space-delimited scripts (e.g., CJK): `split(' ')` yields a single block,
  so manually split by semantics into 3–5 spans instead of degrading into character-by-character reveals.
- Each line is an absolutely positioned `flex` row (left-aligned to a 168px grid) with spacing driven by `gap` rather than spaces;
  when updating copy, ensure line 1 does not exceed ~1450px width (~17 characters in 170px serif), or it will collide with the background issue number on the right.
- This is a **low-energy default card**: it serves a different role from glitches/reels in this category, and can and should coexist in the same video
  (use heavy techniques for the hero element, and this card for all other titles).

## Reference Implementation
demos/typography/blur-slide/
(BlurSlide.tsx)
