---
name: icon-field-colorize
summary: A grid of grayscale icons staggers in to fill the screen, holds a beat, then brand-color bands ripple down and light the whole field at once.
use: Opening sequence laying out product capabilities (icons = functional universe) before flooding with brand color; feature showcase pages, ecosystem/integration scale overviews, lead-in before opening logo
duration: Entrance ~45f stagger + hold ~10f + color flip 12–45f + terminal hold; total segment 3–6s (demo 170f: color flip 30f tier + title lockup + terminal hold 1s)
energy: Medium (entrance is build-up; color flip instant is the sole burst)
tags: ui-entrance, outro
---

## Intention
Establishing sheer abundance with grayscale first—hundreds of small icons stagger into the frame, with grayscale ensuring they read as ambient background texture without stealing focus; holding for a beat lets viewers register "the screen is packed," followed by brand color sweeping downward in rapid horizontal waves, illuminating the grey world in an instant. The linchpin is that **colorization is not a simultaneous hard cut across frames**: analysis of the original video proves multiple color waves sweep downward within ~0.5s (blue blankets the field first, followed by orange/green/red covering lower tiers), settling into a layered four-color horizon—the wave provides velocity and direction, whereas a raw cut merely reads like changing slides.

## Motion Core
- Icon field: 150–200 icons arranged in a grid (half-step alternating rows), randomized across 3–4 grayscale tiers; mulberry32 determines grouping, grayscale, and shape; demo packages icons into keycap-style rounded squares—in dark stage, grayscale = unpowered dark keycaps (warm black base, hairline border, top edge catching light, dark grey glyphs); color flip = powering on: entire keycap turns into glowing color block + dark glyph + matching glow.
- Emergence batches grouped by distance from screen center (75%) + noise, expanding outward from center.
- Emergence: 10 staggered fade-in batches (4.4f between batches + <=3f intra-batch jitter), each featuring 0.6->1.06->1 micro-spring (single overshoot and settle) + 10px upward float.
- Still beat (~18f): lets "full coverage" register; last 10f dims field by 12% as anticipation (inhale), snapping back when first wave arrives.
- Color flip: Multiple color waves advance by row, row offset ~1.4f + column tilt 0.25f + per-icon <=1.5f jitter (slanted wave front rather than rigid rows); each wave sweeps downward from its start row, trailing waves covering lower bands -> final multi-color gradient bands.
- Single keycap color flip 4f: New color **fills keycap via clip-path from top to bottom** (matching wave direction, avoiding opacity cross-fade) + 1.22x sine pop, followed by a 5f screen white flash + glow overshoot upon fill, giving the wave front an electrified feel.
- Light spill: As each row illuminates, the stage floor behind is washed in horizontal light bands of matching hue (intensity = percentage of row illuminated), making the field genuinely glow.
- Resolution: Once light settles, a radial vignette dims center stage (preserving peripheral glow), while video-shotcraft wordmark (eyebrow) + two-line 132px title "Every shot, / one place." rises word-by-word; ensure second line stays within vignette bounds to prevent text edges clashing with bright keycaps.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Icon count | 170 (17x10 @1080p, grid pitch 108x106, keycaps 66px) | <100 loses "open field" sensation; >250 makes individual keycaps too small to see color pop |
| Total emergence | ~48f (10 batches x 4.4f + trailing fade-in 7f) | Too fast reads as sudden flash; >60f exhausts audience patience before payoff |
| Color flip duration | Original ~12f full sweep; demo ~30f | Faster is punchier; extend only for slower, explanatory contexts |
| Waves and colors | 4 waves, sunrise palette in single color family (gold -> amber -> orange -> coral red) | 1 wave = single color illuminate works; four disparate hues (blue/orange/green/red) look like a rainbow, while tonal gradients feel like a brand |
| Row offset | 1.4f/row + col 0.25f tilt | Row offset >3f reads like a document scanner; 0 = instant hard cut |
| Color pop | 1.22x sine 4f + clip fill | Without pop, wave front is imperceptible; >1.4x keycaps collide |

## Known Pitfalls
- Demo calibrated on hand-drawn minimalist icons—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Do not cross-fade colors with opacity: stacking translucent warm tones on dark backgrounds passes through muddy olive/sludge tones; use clip wiping instead; white flashes must trigger only after new color fills keycap, otherwise flashes over translucent layers turn dull grey.
- **Colorization must not be an instantaneous single-frame cut**: verified frame-by-frame as rapid sweeping waves (Bear app 25fps analysis: blue->orange/green/red completes in ~0.5s); hard cut loses illumination feel.
- Icons must use recognizable solid glyphs (heart, star, bolt, checkmark...); abstract color blocks fail to convey "functional universe."
- Division of labor with theme-switch-moves: that card handles dark/light UI theme toggling; this card handles brand color illumination across decorative icon fields without carrying UI semantics.

## Reference Implementation
demos/opening/icon-field-colorize/
(IconFieldColorize.tsx)
Source: bear-app.mp4 ~0.0–3.0s
