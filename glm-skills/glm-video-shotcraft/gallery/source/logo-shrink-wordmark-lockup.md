---
name: logo-shrink-wordmark-lockup
summary: A neon slit ring shrinks fast into a solid white O with an overshoot brake, slides left to make room, letters stagger in one by one, and an accent slogan fades in below.
use: Outro brand lockup: collapsing full-screen visual energy into a standard "icon + wordmark + tagline" lockup
duration: ~4.4s (132f@30fps; collapse 0.1–1.2s, clear space 1.5–2.1s, letters 2–2.7s, tagline 3.2–3.7s)
energy: Medium (impactful collapse phase resolving into steady settling cadence)
---

## Intention
The outro's signature stamping ceremony: a full-screen neon ring collapses with kinetic energy into a compact icon, healing its split gap and turning solid white (transitioning from show mode to standard brand identity), then steps through standard lockup assembly—icon steps left, wordmark glides in letter by letter, and tagline resolves below. The audience sees the brand "settle firmly" out of pure motion.

## Motion Core
- Main collapse curve: scale 5.4 -> 1 (t=0.02–0.28, inOutCubic), layering a `sin(pi) * 0.06` overshoot brake over t=0.26–0.37—expanding 6% at the impact moment before easing back ("braking with inertia").
- Gap healing and color transformation run synchronous with collapse (t=0.10–0.28): neon glow fades out, stroke cuts from #dfe9ff across midpoint to #fff, and solid white O fades in—the three-layer crossfade completes mid-shrink, arriving at destination as a pristine white mark.
- t=0.24–0.32: the white O crossfades into the video-shotcraft glyph (reversed-white edition, on beat with the brake and shockwave; already scaled to final size upon swap); the ring rotates on the inner layer while the outer mark layer only scales without rotation, keeping the 45 deg chamfer angle perfectly constant.
- t=0.34–0.47: the icon shifts left to make room (inOutCubic, -90.5px = half the full lockup width minus half an icon), clearing space to the right of the central axis for the wordmark.
- Wordmark `video-shotcraft` (15 characters, 22px / 700, all lowercase) slides in staggered via `0.46 + i*(0.24/15)`: opacity 0 -> 1 + translateX 8px -> 0, each lasting 0.10s outCubic.
- Tagline uses brand motto `FRAME MOTION. CRAFT THE SHOT.` (accent color `ACCENT`, 12.5px wide tracking) fading in as a single line across t=0.72–0.84 without character stagger—positioned one hierarchy tier below the wordmark.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Collapse scale | scale 5.4 -> 1 | Initial scale determines dramatic compression ratio; <3 lacks impact, >7 blurs outside the frame initially |
| Brake overshoot | +6%, sine envelope 0.26–0.37 | Cutting it feels like a hard freeze; >10% turns jelly-like |
| Healing window | 0.10–0.28 (in sync with shrink) | Healing must complete prior to landing; changing color after landing feels unready |
| Left shift | -90.5px (derived from `WORD_W` / `GAP` / `ICON`), 0.34–0.47 | Seamlessly hands off to initial letter entry (0.46); leaving a gap creates awkward waiting dead-time |
| Letter stagger | `(0.7 - 0.46)/n` (15 chars = 0.016s/char), 0.10s each | 5-letter short words can expand to 0.035s/char; with more characters, reverse-calculate interval via `(0.7 - 0.46)/n` so all characters launch before 0.7 |
| Tagline entrance | 0.72–0.84 full line fade-in | Intentionally not staggered per character: tagline is a footnote, not the hero; `ACCENT` constant adapts to project palette |

## Known Pitfalls
- `WORDMARK` = `BRAND.name`, tagline = `PITCH.en.motto`; when replacing brand names, letter stagger pacing depends on character count (auto-calculated); when tagline character counts vary, adjust tracking to prevent overflow or sparse gaps.
- The icon uses a two-tier structure: SVG dual-arc slotted ring (glow / color) heals into a solid white O, crossfading on brake into the clean video-shotcraft glyph (clean, unbloomed); when adapting other logos, never allow the logo to spin with the ring.
- Left shift distance is coupled to wordmark width: `WORD_W` is the measured width of the wordmark line (remeasure when changing font/size); `SHIFT` and `ROW_LEFT` are derived from it to ensure the lockup centers precisely in frame.
- There is no loop-back reset; designed as the definitive final shot of an outro; if looping is required, add a 1s freeze frame after t=1.

## Reference Implementation
demos/outro/logo-shrink-wordmark-lockup/
(LogoShrinkWordmarkLockup.tsx)
