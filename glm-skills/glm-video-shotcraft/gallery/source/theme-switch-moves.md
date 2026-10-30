---
name: theme-switch-moves
summary: Two theme-change patterns: a diagonal sweep that recolors content in place, and a command-palette ripple with a clear cause and effect.
use: Narrative segments for dark mode / theme switching; identical UI "changing colors before your eyes" rather than cutting to a new scene
duration: A 140f (4.7s) / B 156f (5.2s)
energy: A Medium / B Medium-High (combo variant features complete causal chain)
---

## Intention
Two filming methods for dark/light mode switching. A (standard in Notion/Figma/Linear): a 15-degree diagonal boundary with bright light sweeps across the screen (in demo, sweeping from switch on right toward left); as boundary passes, light elements switch to dark **in place**, with dual themes briefly coexisting across identical layout—viewers witness "the same UI reskinning," not a transition. B (combo variant): Cmd+K palette receives "dark" and Enter is pressed; palette collapses into a bright dot, and dark ripples **radiate from that dot** across full UI—establishing a fully legible causal chain of "command triggers reskin." Critical combo requirement: ripple origin must match palette collapse point, and trigger frame must be collapse completion frame.

## Variant Selection
| Variant | Approach | Use |
|---|---|---|
| A theme-sweep-toggle | Close-up on header day/night toggle (zoom 2.0): cursor presses, knob springs to moon (sun retracts rays and grows crescent) -> dark world clip-path polygon sweeps diagonally at 15 deg from switch side (64f, bezier(.3,0,.35,1)), while camera pulls back to full overview over 30f; boundary = twilight line: white-hot core line + sunset orange twilight band widening with speed on light side + cool blue glow on dark side; "lights on" finishes sweep (today pill / current time line / window rim light illuminate sequentially) to settle | Direct demonstration of theme features |
| B palette-theme-ripple | Palette drops via spring -> human-cadence character input -> Enter triggers CRT shutdown collapse (vertically squashing into bright line, then horizontally into bright dot) + dot and horizontal afterglow hold 5f -> circular clip radius 6->1260px ripples outward with strong ease-out, 3px white-hot ring + coral outer glow / white inner glow + echo ring lagging by 4f, dark version settles at 1.035->1, camera exhales and pulls back in rhythm | Highlight beat linking command palette and theme |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Dark mode creation | Manual key-by-key mapping against palette (custom dark values for bg/card/border) | Filter-inverted dark modes are incorrect (images/avatars become negatives) |
| A Diagonal over-sweep | Diagonal line expanded 400px in world coordinates for polygon calculation, endpoint crossing bottom-left | Failing to over-sweep leaves residual light triangles in corners |
| A Causality | Sweep origin hugs switch; boundary crosses switch ~6f after press; camera pulls out from switch close-up | Boundary appearing from afar or lagging by >10f fails to convey "triggered by this switch" |
| A Poster frame | Camera reaches full overview (40f) before twilight line crosses midline (~44–50f) | Pulling back too late prevents viewing day and night coexisting on screen, reducing technique to plain close-up |
| A Settle | Post-sweep night-only lights turn on sequentially (today pill / current time line / window rim light) | More semantic than scale 0.99; avoid stacking full-screen white flashes |
| B Causal anchoring | Bright dot rests at collapse point for 5f (+ horizontal afterglow); ripple origin = point coordinates, start frame = dot end frame | Offset origin or desynced frame severs "command -> reskin" causality (critical combo requirement) |
| B Ripple radius | End value ~ distance from center to furthest corner x 1.1 (demo 1260px) | Excessive end value (e.g. 2000+) flashes through early curve, making circular shape illegible |
| B Light layer | Conditionally unmounted upon sweep completion | Prerequisite for true static hold |

## Known Pitfalls
- Demo calibrated on video-shotcraft UI designed for shot (A release week production schedule / B sample gallery)—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Both versions must match layout pixel-for-pixel—any layout discrepancy reads as "switching to another page," invalidating technique.
- Production on real pages: capture authentic screenshots for light and dark versions separately, avoiding fake inverted filters.
- Use theme switching <=1 time per film: it is a feature narrative rather than a transition; repeated switching reads like a demo accident.
- Audio: Style A sweep uses a long whoosh; Style B Enter uses confirmation click + ripple expansion into whoosh (Foley prioritization).

## Reference Implementation
demos/interaction/theme-switch-moves/
(PaletteThemeRipple.tsx / ThemeSweepToggle.tsx)
