---
name: depth-layer-moves
summary: Layered parallax rails: three speed tiers slide past to build depth, and the hero floats up as the rail settles.
use: Sections where flat screenshots need "physical depth": card groups, lists, or horizontal page tours
duration: 4–5.5s continuous (demo 165f)
energy: Medium (tactile quality)
---

## Intention
Panning an entire page is "looking at a page"; layered depth is "standing inside the page's space." Parallax rails add depth to horizontal panning (the Disney multiplane camera principle, matching Linear promo aesthetics).

## Motion Core
- **Parallax rails (3 layers + 0x text layer)**: A single drive displacement multiplied by layer coefficients—background full page (0.35x + scaled up one step + blur 5px + desaturation 0.7 + gradient haze thicker at top and lighter at bottom, receding into environment), midground real card group (0.7x, primary reading layer, no blur, two layers of soft drop shadow cast onto "desktop"), foreground floating elements (1.4x + blur 7px + deep drop shadow + speed-scaled horizontal motion smear, rushing past camera). The demo (MultiplaneReal) uses a sand warm beige theme: foreground contains 5 enlarged terracotta / ink tag pills (extracted from real tags on the cards), while the frame pins a static headline layer (0x: video-shotcraft logo + wordmark eyebrow, "Your page, in depth." at 120px)—text stays still while the world moves, making parallax significantly easier to read.
- The rail has a destination: total drive is reverse-calculated so card4 lands exactly centered when the midground settles, using asymmetric in-out (bezier 0.45, 0, 0.18, 1) over 130f; after settling, the hero card lifts up (elevation 6 -> 26, 1.035x, lagging position convergence by ~8f) + terracotta border + "In focus" corner badge, turning the tail frame into a poster; foreground pills are arranged in world space so only two remain clipped at the bottom frame edge at rest.
- Do not dismantle real page layout: keep the entire page intact as a layer, separating independent elements into their own layers via clipping—layer relationships represent "depth of field", not "tearing the page apart".

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Parallax coefficients | 0.35 / 0.7 / 1.4 (+ 0x text layer) | Gradients must differ by >=2x to be distinguishable; <=4 layers to avoid cognitive overload |
| Layer anchors | Foreground/background blur + desaturated background + atmospheric haze | Without blur and saturation anchors, it looks like loose stickers floating around |
| Rail destination | Drive reverse-calculated to center hero | Constant-speed panning without an endpoint looks like a screensaver; give the hero card an elevation lift once settled |

## Known Pitfalls
- The primary reading layer must be high-resolution texture without blur—the audience is actively reading it.
- Full-screen real-time `filter: blur()` updated every frame is extremely expensive (measured at >3x longer render time): apply blur to small elements within layers, never to a full-screen container layer.
- Parallax combined with PageCam 3D rotation (angled parallax) is unverified; render a still frame to confirm before production.
- Parameters were calibrated on placeholder assets and require re-verification upon first production use.

## Reference Implementation
demos/camera/depth-layer-moves/
(MultiplaneReal.tsx)
