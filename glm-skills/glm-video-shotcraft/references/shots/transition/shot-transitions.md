---
name: shot-transitions
summary: Three handoff recipes for matching scene energy: flash cut, braking whip pan, and portal mask wipe.
use: Any shot-to-shot junction (technique card: select one variant per seam during the storyboard phase after arranging shots).
duration: n/a (technique card; frame allocations for each variant are detailed in the parameter table, deducted from adjacent shot budgets).
energy: n/a (technique card, does not consume an energy slot).
---

## Intention
Individual shot cards in the library manage only their own entrance and outro settle; how shots connect with one another has historically lacked explicit vocabulary—naked hard cuts at seams bleed away the cinematic atmosphere painstakingly cultivated shot by shot. Universally acclaimed launch videos (e.g., Linear Releases/Agent, reverse-engineered frame-by-frame on 2026-07-11) feature zero bare cuts: scene changes rely on spatial depth journeys, focus relays, or blackout title-card pauses. This card codifies three foundational recipes: white flash over hard cut, whip-pan using motion blur to mask scene swaps, and portal window zoom entering detailed environments.

## Variant Selection
| Variant | Method | Applicable Seams |
|---|---|---|
| A Flash Cut | Camera pushes in on the outgoing shot; a single-frame white flash straddles the edit point to mask the page swap | Interactive transitions between page-to-page layouts with similar energy levels (already available in library, incorporated here) |
| B Whip Pan (Braking Variant) | Camera whips horizontally to the next scene in a single beat, blurring the mid-section beyond recognition to disguise the cut; brakes hard before landing with an ease-out long tail slide | High-tempo, rapid-fire feature montages (lightweight high-energy to high-energy transfers); ideal when the landing shot contains content meant to be read |
| C Portal Mask Wipe (Depth Variant) | A real in-page element (e.g., card) zooms to become a full-screen viewport, out of which the incoming scene expands to take over | Semantic seams: feature overview → detailed drill-down ("clicking into this card to enter its world") |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A flash-cut | assets/lib/FlashCut.tsx, from = cut frame − 5, 5f on each side | Usage details in type-and-filter card; white flash exists purely to mask hard cuts, never as decorative flash (Q4) |
| B Whip Pan Braking Variant | Origin hold ≥20f → first 70% of distance consumes 30% of time (blurred phase, peak ~300px/f) → remaining 30% of distance glides to a stop on an ease-out long tail ~48f; integrate displacement from a single continuous velocity curve (3f launch + exponential decay), never chain segmented ease-outs (which cause velocity bumps at handoffs); apply directional motion blur proportional to instantaneous speed (_fixtures/Polish's SpeedBlur, sd ≈ 0.085 × speed, capped at 64px), active only during whip phase; reference implementation binds this identical displacement curve to a mechanical roller index counter (Nº 02 → 09) and a ruler scale moving past a fixed playhead, lifting the target card to 1.2x scale upon settling for legibility | Ideal when the landing shot contains content to be read—the long tail grants viewer eye tracking time to settle; long tails >60f steal entrance time from the incoming shot, keep it brisk; scale travel distance to ensure peak velocity ≥300px/f, otherwise blur will be insufficient to hide the cut; stitch both scenes along the same horizontal baseline (identical page-space y); CameraMotionBlur sub-frame accumulation shifts yellow in 8-bit and forms stepped echo ghosting, do not use for light-mode UI whip pans |
| C Portal Mask Wipe portal-wipe | Target card elevates in anticipation (−10px, 1.03x, neighbor cards dim) → window expands over 40f using bezier(0.7, 0, 0.3, 1) ramping slow to fast; incoming scene counter-compensates from ~0.42 scale up to 1 (sharing identical parameter t with window geometry); card surface fades within the first ~28% of travel (opacity 1 − t·3.6, any slower drags out full-screen residual text ghosting); incoming scene uses **strictly 2 layers** of parallax (background panel coefficient 0.08 + foreground 2 cards 0.3, zero blur); once portal transit concludes, 8f soft deceleration → static hold ≥30f to absorb the new scene; best practice: incoming scene represents the "expanded universe" of the clicked card's cover (reference implementation: video-shotcraft Workspace project card with Cobalt Blue waveform cover → identical waveform landscape in a viewership forecast world + glass panel + 2 floating metric cards, curves drawn synchronously with t) | Window geometry and interior scene must be driven synchronously, as desync shatters the illusion; layer count and spread are paramount for legibility—a 3-layer + 0.85 spread + blur prototype was rejected, passing only after simplification; must reach a complete halt post-transit, as continuous parallax drift undermines reading the incoming shot |

## Known Pitfalls
- Annotate the chosen transition variant for every seam during the storyboard phase (recorded in the "Key Motion" column); postponing until the per-shot phase forces timeline shifts across the entire sequence—transition frames are deducted from adjacent shot budgets, adhering to hold budget rules (R3).
- Do not stack transitions: use only one technique per seam; adding white flashes during a whip pan's blur phase or during a portal wipe reads as an amateur visual error.
- B/C variant parameters were calibrated on placeholder assets and refined with real assets; they represent singular benchmark cases—in case of conflict with precedent rulings, precedent rulings take precedence.
- For Variant C, the incoming scene inside the window must semantically represent the "detailed world" of the clicked element (in production, link to genuine detail screenshots)—stuffing unrelated scenes breaks continuity, degrading the technique into a gimmicky wipe; ensure the expanding element uses high-resolution source textures (Q2, as it is subjected to an extreme close-up throughout).
- Variant C depth parameters are an initial baseline tuned on handcrafted placeholder UI (video-shotcraft Workspace / Viewership Forecast World) and have not been validated on real screenshots; reference implementation: demos/transition/shot-transitions/PortalWipeV2.tsx.

## Reference Implementation
Variant A: template/src/aifl/Main.tsx flash-cut layer (component assets/lib/FlashCut.tsx);
Variant B (whip pan braking variant): demos/transition/shot-transitions/WhipBrakeReal.tsx;
Variant C (mask-wipe portal depth variant): demos/transition/shot-transitions/PortalWipeV2.tsx.
