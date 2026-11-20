---
name: outro-group-photo-launch
summary: Elements from the film assemble around the wordmark as a crane settle, stage light, and gold dust create a launch-event finale.
use: Outro / brand finale; "family portrait" closing shot for multi-feature products
duration: ~4.8s (145f)
energy: Peak (highest energy point of the entire video)
---

## Intention
Recalling one representative element from every featured function for a group photo, with the wordmark taking center stage as the grand finale—before exiting, the audience remembers that "all of these capabilities belong to a single product." Execution must be keynote-grade: energy pushed to the absolute peak of the video.

## Motion Core
- 9 page elements (nav / cards / content rows / search bar / metric bar / doc header) fly in with rotation from all four quadrants; flight paths apply speed-scaled directional blur, landing solid on contact (tightening contact shadow + 1.5% micro-compression, no individual glowing, Q4).
- Wordmark (demo: video-shotcraft logo + wordmark, with brand motto eyebrow) enters via letterpress letter-by-letter; ensemble elements "step back" to yield focus; divider rule draws out with extension rays shooting from ends.
- Crane camera move: photo layer assembly drops into frame via rotateX 4 deg -> 0 + scale, transitioning into an ultra-slow push-in.
- Keynote atmosphere trinity: opening light streak sweep, stage backlight behind wordmark, and ascending gold dust particles.
- Background page blurs into depth-of-field environment.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Element fly-in | 9 elements cued from frame 4 every 3f, flying 12f each; origin offsets +/-360–500px; render order = cue order so later arrivals stack on top | Every showcased feature must have a representative element (Q8 self-check item); viewers will notice any omission |
| Fly-in easing | bezier(0.34, 1.4, 0.44, 1) | Code comment lesson: old bezier(0.25, 0.9, 0.3, 1) "never crossed 1" and had no real overshoot—landing requires y1 > 1 to rebound |
| Flight posture | Flight rot x 2 -> settled rot (within +/-5 deg), scale x 1.12 -> 1; directional blur scaled by screen speed (0.3 x px/frame, capped at 22); landing contact shadow tightens + 1.5% micro-compression at cue+9 -> 16f | Settled angles bounded within +/-5 deg—the ensemble must look organized without being rigid |
| Step back | Ensemble opacity -12%, saturation -8% across 42–50f when wordmark enters | Supporting cast must yield focus to the lead; otherwise 9 elements overwhelm the wordmark |
| Crane move | `perspective(1400px) rotateX(4 deg -> 0) scale(1.06 -> 1)` drops over first 40f, transitioning into slow push +0.035 (in-out launching from zero velocity at 36f for seamless handover) | Crane amplitude is subtle (4 deg), which is sufficient to convey camera descent; larger swings cause disorientation |
| Atmosphere trinity | Light streak 2–14f (600px wide overlay, peak opacity 0.12); stage backlight 42 -> 50 -> 58f at 0 -> 0.5 -> 0.25; gold dust: 20 warm-glow particles 2.4–4.2px, opacity 0.35–0.7 subtle sparkle + 6 foreground defocused bokeh orbs, all parameters index-derived deterministically | Particle and lighting parameters must be derived deterministically (hard rule: renders must be 100% reproducible); >30 dust particles starts looking like snow |
| Wordmark | Demo uses video-shotcraft glyph + lowercase wordmark (brand font 118px): glyph stamps at 38f, letters delay = 42 + i * 1.8 over 8f with letterpress; rule grows 58 -> 70f with 190px extension lines shooting over 8f and fading over 6f; letter tracking breathes 62–66f; background page blurs 0 -> 14 within 24f; 30f sign-off hold after landing | Hold wordmark lockup motionless for at least 1 full second (R1 rule); keep outro clean with no explanatory captions (C1 exception) |

## Audio
Fixed three-beat phrasing: cinematic riser leads into the assembly (pinned at f945 in template) -> deep whoosh impact nails the wordmark stamp (f980, volume 0.55, full-film peak) -> sparkle pings the rule extension (f1005). This is the only structural phrase never modified since template lock (S2 rule; see sound-design 4.3).

## Known Pitfalls
- Initial outro drafts are almost always too conservative (Q8: quiet signature -> group photo -> keynote finale 3-tier escalation)—begin drafting directly with keynote specifications: full crane motion, stage backlight, and dust particles.
- Architecture precedes effects: establish the "fly in from all quadrants into group photo" structure before layering atmosphere; stacking effects without skeleton fails.
- Cross-check outro tagline against copy beneath the wordmark (P4 deduplication rule); a single phrase should only appear once in the film.

## Reference Implementation
demos/outro/outro-group-photo-launch/OutroGroupPhotoLaunch.tsx (formerly template/src/aifl/live/SceneOutroLive.tsx; see template/src/aifl/Main.tsx timeline for the 30f sign-off hold duration)
