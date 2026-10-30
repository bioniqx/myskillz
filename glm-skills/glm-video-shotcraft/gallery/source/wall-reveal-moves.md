---
name: wall-reveal-moves
summary: Two in-place wall reveals: sequential bento lights and a wireframe drawing itself into a finished interface.
use: Monolithic reveals of feature walls, card grids, and full-page dashboards; sections where content is already in place and should "materialize" rather than "fly in."
duration: ~5s per variant (A 150f / B 150f @ 30fps, including establishing hold and static finish)
energy: Medium
---

## Intention
When asking "how does a wall of content enter," the library previously had only one answer: deck-deal-flyin—high energy, displacement-driven, "items streaming in." But not every wall should stream in: brand segments require dignity, and "from concept to production" requires process. The shared principle of these two variants is **non-displacement batch entrance**—elements materialize in place, layout holds true from frame one, and viewers observe a wavefront of state change sweeping across a wall rather than flying objects.
When selecting, ask: should this wall "flood in" or "illuminate in place"? The former points to deck-deal-flyin; the latter belongs here.

## Variant Selection
| Variant | Method | Application |
|---------|--------|-------------|
| A bento-light-up | Dark 3×2 bento wall (two rows with alternating widths 600/420/420 ↔ 420/420/600, dark card surfaces) sits dimmed on standby; an accent-colored comet trail traces each border, followed by content brightening and rising; after all cells ignite, camera pulls in gently to finish; wall header features video-shotcraft emblem + wordmark with headline "Every shot, tuned in one place." | Dignified content / dark brand sections; steady feature overviews |
| B wireframe-draw-on | Interface sketches first as fine SVG blueprint lines in groups, then an accent glowing vertical line sweeps left-to-right, materializing wireframes into finished software where it passes (demo features video-shotcraft workbench, sidebar logo block sketching viewfinder emblem) | "From design to artifact / from idea to product" narratives; product debut reveals |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Variant A cadence | Hold 20f → cells activate sequentially at 12f intervals (all 6 cells lit by ~96f) → scale 1→1.04 slow push 25f (bezier 0.33,0,0.2,1) → static rest finish | 12f cascade balances per-cell readability against overall momentum; more cells can compress to 8–10f, but uniform spacing provides dignified cadence—avoid card-deal acceleration |
| Variant A single cell | Dim state opacity 0.18 + translateY 20px; SVG rect pathLength=100 traces over 8f: 22% perimeter comet lead (#e8b45e 6px Gaussian glow + #ffe3ae 2.5px bright core) leaving 1.5px fine hairline trail; halfway through trace (+6f), content back-out(0.3,1.4,0.5,1) pops up over 8f to brighten into place; +12f post-trace comet anneals to 0.4 steady fine hairline | Stroke and content pop must **relay rather than synchronize**—starting on same frame reads as cell flickering; mid-trace glow pulse uses `lit·(1−lit)·4` parabola with seed-based subtle peak differences (sine hash, no Math.random) |
| Variant B wireframe trace | Hold 20f → groups complete traces over 30f staggered: sidebar from 20f / header from 30f / 6 cards from 40+i*3f / line chart from 52f; SVG pathLength=1 + dashoffset 1→0, cool gray-blue blueprint #6c7894 (outer frame 1.6px / inner details 1.25px) round, light blue 24px dot grid base + corner crop marks | Group staggering creates hand-drawn feel, simultaneous tracing reads as a printer; card placeholder lines stagger by +3f with length seeds |
| Variant B materialization | 88–118f solid layer clip-path inset(0 right% 0 0) reveals left-to-right over 30f, bezier(0.55,0,0.25,1); leading edge tracks 4px accent vertical line (#ffc46b + dual-layer boxShadow glow), fading in 86–92f, fading out 112–120f; trailing 260px warm gradient glow behind line (residual warmth of freshly developed film) | Vertical line position and clip edge must share single scan driver, desync reads as a rendering glitch; leave ~6f breath between tracing and scanning (82→88f), scanning immediately looks rushed |
| Static hold finish | Pure stillness ≥15f after all movement completes (measured after slow push in A, after scan line fades in B) | Breathing ruling: freeze all properties completely, including glow, shadow, and specular highlights |

## Known Pitfalls
- **Demo calibrated on grayscale placeholder assets—parameters serve as calibration baseline, not final production specs; verify against real assets in production.**
- Accent borders and scan lines in A/B qualify as single-point high-quality lighting effects (compliant with Q4 constraints), but full-wall lighting should occur ≤1 time per video (P4 de-duplication)—using A and B in the same film counts as two full-wall effects; choose one.
- Variant B wireframe geometry must align pixel-for-pixel with solid layer layout (demo hand-aligned to FakeDashboard A); changing assets requires realigning wireframes—misalignment causes elements to jump as scan line sweeps, immediately breaking immersion; modifying brand names or logos also shifts breadcrumbs and elements, requiring wireframe length realignment.
- Both variants represent "materializing in place"; do not mix in displacement fly-ins (e.g. adding translateX fly-ins during cell lighting)—displacement needs belong in deck-deal-flyin; hybridization compromises both styles.
- Variant A dim state opacity 0.18 relies on dark background (#2a2a28); against light backgrounds dimming reads as a washed-out glitch.

## Reference Implementation
demos/ui-entrance/wall-reveal-moves/
(BentoLightUp.tsx / WireframeDrawOn.tsx)

Implementation Status: Both variants possess reference implementations and live Gallery motion samples.
