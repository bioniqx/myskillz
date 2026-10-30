---
name: glow-flyline-moves
summary: Three dark-scene accents: ambient glow orbs, connecting flight arcs, and a synchronized orb-to-line relay.
use: Atmosphere and data storytelling for the sole dark-scene sequence in a video: use A for ambient bed, B for data flow, C for background reacting to foreground; Linear landing page aesthetic
duration: A 170f (~5.7s) / B 140f (~4.7s) / C 165f (5.5s)
energy: A Low (ambient floor) / B Medium / C Medium-high
tags: data
---

## Intention
The library's first card built entirely within a **dark environment**. The precedent that "brightening is invisible on white backgrounds" conversely implies: to play with light, step into the dark first. Variant A provides spatial breathing—three large ambient glow orbs drift organically across a dark canvas, swimming behind a central frosted glass card and tinting through the glass, while card edges catch glow as orbs approach, keeping the background alive. Variant B delivers data verbs—luminous arcs strike from Card A to Card B with bright leading heads and fading comet trails, pulsing target outlines upon arrival to give metric relationships directional intent. Variant C solders A and B together—as a flight line lands, the adjacent background glow orb surges in brightness on the exact same frame; atmospheric and event layers **resonate on the same frame**, conversing rather than acting independently (combination critical point: decoupling the resonance frame degrades the effect into two disjointed cards).

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A glow-orb-ambient | Three 760–1200px multi-stop radial gradient orbs (screen blend, no runtime blur), dual sine drift; central 1100x600 frosted glass card (backdrop blur + saturation boost) reveals passing orbs; card edge glow weighted max by orb distance [240,760]px -> [1,0] + directional rim light toward dominant orb | Dark section background bed; card breathing atmosphere |
| B flyline-arc | Dark dashboard dimmed as backdrop, 100-segment sampled bezier arc connecting card centers, 22f out-cubic growth; leading light head + comet tail conditionally mounted during growth, segment opacity fading by distance from head, blended smooth across 10f upon arrival; source anchor lights up, destination node remains lit; landing card stroke pulse + shockwave ring, daisy-chainable | Data flow / metric correlation; dashboard narrative |
| C orb-flyline-relay | A + B soldered: three glass nodes each backed by an ambient orb; orb surge and node illumination share destination frame constants, surging 1 + 1.6x and scaling +12%, rising over 5f and dissipating over 15f; flight line dissolves into a fine dotted line upon arrival | Dark sequence climax; three-station relay finale |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Glow orbs | Teal / deep ocean blue / coral, peak 0.55/0.5/0.42; drift amplitude 280–300px, staggered periods 96–150f | Synchronized periods read as monolithic rigid sway rather than "organic" drift |
| A Glass card | backdrop blur 44px + saturate 1.5; ancestors must not carry filter / opacity < 1 | Ancestors becoming backdrop roots hide orbs behind glass (place entry fade on the glass element itself) |
| A Edge glow | box-shadow 0->90px dominant orb color 0.32 + 1.5px directional gradient rim light | Without edge glow, orbs and card feel disconnected |
| A Convergence | 115–145f out-sine convergence to freeze (amplitude 60/pi, initial slope = 1 for continuous velocity), final 25f truly static | Abrupt single-frame stop reads as a freeze bug; eased convergence yields true rest |
| B Line body | Dark version (demo): white core 3.5px butt segments + 7px/18px dual-layer indigo glow; Light version: white line 4.5px + 9px dark underlay | White line without underlay on light canvas vanishes entirely (precedent); round segment caps create bead artifacts along fading tails |
| B Leading head | White dot r7 + r40 halo + 9-point comet tail, conditionally mounted only during growth phase | Opacity at 0 does not unmount the layer, preventing true rest |
| B Pulse | Stroke expansion out-cubic 6f / dissipation 12f to residual 0.25; dark version brightening (accent stroke + outer glow + subtle card face lift) + 14f shock ring; full static after f86 | No brightening on white canvas—light version uses 0.16 darkening overlay instead |
| C Resonance | Surge begins on exact destination frame (shared constants LIT_B / LIT_C); node brightens to 1 over 8f + stroke pulse residual 0.35 + 20f shock ring | Offsets >2f lose the perceived connection |
| C Timeline | Action completes before f98, orbs ease and freeze 110–140f, final 25f truly static | Atmosphere layer freezes last, event layer settles first |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Switching between dark sections and light ink/paper visual identity carries high cognitive cost—limit dark sequences to <=1 per video, bridging entry/exit with hidden cut families in shot-transitions rather than raw hard cuts.
- Orb drift **must** ease into rest before freezing at the tail—clamping constant velocity creates an obvious abrupt jolt (Variant A out-sine convergence precedent).
- Production brand color adaptation: pair orbs with brand color duos (e.g., blue-violet); grayscale parameters guarantee only luminance balance, hue contrast must be re-tuned.
- When Variant B daisy-chains >=3 lines, switch to Variant C—pure flight lines back-to-back read like generic dashboard templates; resonance imparts authored craft.
- Audio: light hit on each B/C arrival, Variant A remains silent (sound-design §4.5).

## Reference Implementation
demos/effects/glow-flyline-moves/
(FlylineArc.tsx / GlowOrbAmbient.tsx / OrbFlylineRelay.tsx)
