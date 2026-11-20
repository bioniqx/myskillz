---
name: crash-zoom-punch
summary: A six-frame push races from a wide view to a target close-up, ending with either an elastic overshoot or a heavy impact stop.
use: Feature section "calling out" shot—pins the viewer's gaze instantly onto the target card/module; use impact stop for highest emphasis level
duration: ~0.5s action + holds before and after (6–11f action, hold >=30f before to establish overview, hold >=45f after to read close-up)
energy: High (instant impact, not sustained high energy)
tags: effects
---

## Intention
A slow push-in (spotlight-hero-card) says "please look", while a crash zoom says "LOOK AT THIS!"—slamming from overview to close-up in a single beat, leaving the viewer no choice. Landing styles come in two variants: elastic rebound conveys bounce ("look here"), while impact shake conveys weight ("this is the one"), chosen by emphasis level.

## Motion Core
- Zoom accelerates rapidly with 6f ease-in (e.g. 1 -> 2.6), while cx/cy simultaneously ease-in to converge on the target center.
- Rebound variant: zoom overshoots, then recovers 3–6% over 5f (2.6 -> 2.45).
- Impact variant: high-frequency camera shake + exponential decay starting from the impact frame (amp 14px, tau ~ 1.8f, settling dry in 6f), no rebound.
- Motion blur **only covers the crash zoom phase** (impact shake stays crisp): the demo uses custom time-sampling (shutter ~ 200 deg, subframes stacked with equal weighting opacity 1/(i+1), subframe count adapting to current frame displacement, capped at 40), configured with "echo spacing <= text height" (Round A precedent); `<CameraMotionBlur>` also works, but its semi-transparent stacking makes background colors look muddy/yellowish on near-static frames. CrashZoomReal's small page text is only ~14px, so echo spacing is compressed to <=6px (up to 44 layers), and high-speed frames add <=4px micro-blur between layers to smooth discrete echoes into continuous streaks.
- 6–8f anticipation pull-back ~3–4% before the push (recoil before the charge); wide hold phase adds ~2–3% ultra-slow creep.
- Rebound variant demo (CrashZoomReal) staging: browser window on a warm black ember stage (tilted back 11 deg, orange backlight + floor reflection); before the crash zoom, four orange corner brackets converge from +150px out to lock the target card (calling it out in the wide view first); the crash zoom uses the same curve to pull the tilt back to square; on the landing frame, a warm exposure flash fires (exponential decay ~8f) with 86% perimeter darkening + target card rim light; after the rebound settles, the camera smoothly pans left 320px to move the card aside, revealing large readouts on the right rail (232px numbers + captions), ending on a complete poster frame.
- Impact variant demo (CrashImpactReal) staging: lime dark tactical HUD—a real page cropped into a front-facing monitor screen on a subtle grid stage; a fluorescent reticle scans and hops in the wide view (card1 -> card5 -> card4, 8f snappy each), tightens over 28f to lock and displays a LOCK tag before the crash zoom fires (0.76 -> 2.35, subframe spacing <=8px, capped at 36); the impact frame is a true shock frame—1f fluorescent flash outside the card -> 1f afterglow -> near black (the only full-screen impact in the entire film), with two fluorescent shockwave rings expanding from the card perimeter; the card does not float or glow (slammed solid). After shake settles, a scanline sweeps across the card face once, and left/right HUD readouts (TARGET / OWNER / STATE and a 250px monospace "P0") stagger into place, holding for 42f at frame 126.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Crash zoom duration | 6f (4–8f) | >10f reads like a standard push-in, losing impact |
| Target zoom | 2.4–2.8 | Final framing should place the target card at 60–75% of screen area |
| Rebound amplitude | 3–6% of zoom | Too large reads like a bouncy toy |
| Shake envelope | 14px * e^(-t/1.8) | Amplitude must exceed visual threshold (perceptibility precedent); >20px reads like a glitch |

## Known Pitfalls
- The endpoint must be a high-resolution texture slot (card4-hires level)—it remains in tight close-up after the zoom; low-res screenshots blur text (Q2); prepare the endpoint using Q2 high-resolution rasterization first.
- Do not mix the two variants: rebounding followed by screen shake looks like a mistake; use crash zoom <=2 times per video (P4 deduplication principle).
- Parameters were calibrated on placeholder assets and require re-verification upon first production use.

## Reference Implementation
demos/camera/crash-zoom-punch/
(CrashImpactReal.tsx / CrashZoomReal.tsx)
