---
name: glass-pill-dictation-typing
summary: A fixed-width glass pill pops in slightly oversized and settles, glowing with an accent gradient inside that fades out as a placeholder sentence types across it.
use: Entrance for voice/AI input pills; interactive cue shots for "speak to it"; a quiet transitional beat between high-energy sequences
duration: ~3.3s (100f@30fps)
energy: Low (the quietest beat in the video; only light receding)
---

## Intention
Telling a subtle story through "light receding as input occurs": on standby it glows (waiting for you to speak), and the moment you speak it yields that light to text. Across 3.3s it performs only three actions: pop in, type, and light recedes. Any superfluous action (bouncing, color morphing, icon animations) destroys its function as a musical rest.

## Motion Core
- Pill 1240x132, corner radius 66, `padding: 0 20px 0 58px`, **fixed width** (does not stretch with typing); dictation text 56px, 92px circular waveform button on right end.
- Entrance `scale 1.25->1`, snappy (strong ease-out) over 20f; opacity reaches 1 within first 2f—establishing presence before settling; first 14f carries 6px->0 depth-of-field blur (oversized phase reads as "closer to lens").
- Material: `backdrop-filter: blur(26px) saturate(1.3)` authentic frosted glass (diffusing warm flares behind it), top-light bottom-dark white volumetric gradient + 1.5px white border + top-edge fading specular line + bottom-edge inner shadow + dual-layer warm drop shadows.
- Embedded accent light: `linear-gradient(90deg, alpha 0 -> alpha .18 @38% -> alpha .62 @78% -> apricot alpha .95 @100%)` light on left and dense on right, plus a screen-blended highlight in bottom-right corner—light resides **inside** the pill.
- Typing: cursor leads at f2, characters type at constant 2f/char from f8 completing 28 characters; cursor dismissed across f66–74.
- Light dimming `g = 1 - smooth(f10->f72)`, sharing exact window with typing; `g` synchronously drives four elements: inner pill gradient, warm background "sun" flare, floor reflection beneath pill, and waveform button (solid warm -> outlined neutral), outer glow `60g px`.
- Waveform 5 vertical bars base heights `[30,16,24,13,20]` (high left, low right), layered with subtle breath `+-2.4*sin(f*0.5 + i*1.7)`.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Pill fixed width | 1240px (~1.8x total sentence width) | **Fixed width is critical**: stretching with text reads as a chip rather than an input bar |
| Entrance scale | scale 1.25->1, snappy 20f | 1.25x represents "settling back from viewer perspective"; 1.5x becomes an intrusive popup |
| Opacity timing | Reaches full in first 2f (ahead of scale settle) | Fading in synchronously feels like "gradually appearing," losing tactile presence |
| Embedded glow | 90deg, 0 -> .18@38% -> .62@78% -> .95@100% | Glow must reside inside pill; turning into outer glow reads as "pending notification" rather than "ready for input" |
| Typing | 28 characters, steady 2f/char from f8 | Adding easing reads like "hesitating"; dictation streams at constant rate |
| Light dimming | 1 -> 0, f10->f72 smooth | Sharing exact window with typing provides the sole causality: light yielding to text |
| Ambient light tracking | Background warm flare 0.15+0.6g, floor reflection 0.22g | Dimming only the pill while environment remains unchanged fails to register "light receding" on light backgrounds |
| Waveform bars | 5 bars, +-2.4px | Amplitude up to 6px reads as active "recording" state, conflicting with "standby" |
| Cursor | Leads at f2, departs f66–74 | Cursor appearing before text signals "input field ready" |

## Known Pitfalls
- backdrop-filter only blurs layers **behind** it: warm light flares must sit beneath the pill (rendered earlier in same stacking context); when flares sit too far from pill, frosted glass looks like a flat white board.
- Luminance contrast in light scenes is much lower than in dark scenes: embedded light needs apricot .95 saturation with ambient background light receding together, otherwise "light receding" fails; for dark scenes, switch background to near-black and desaturate glow color without changing curves.
- Waveform bars breathe continuously (uncontrolled by g), with differing start and end heights—when used as looping assets, tune frequency to an integer multiple of 2pi/duration.
- Typing progress `floor(p*len + 1e-6)`; that epsilon prevents the final character from dropping due to floating-point errors at integer frames—do not remove.
- WARM and APRICOT variables are shared brand colors for embedded glow, outer glow, ambient flare, and button; update only these two when rebranding.
- When sentence length changes, adjust pill fixed width (maintaining ~1.8–2x sentence width) and typing window accordingly.

## Reference Implementation
demos/interaction/glass-pill-dictation-typing/
(GlassPillDictationTyping.tsx)
