---
name: canvas-materialize-moves
summary: Two materialize moves: table rows arc out of a panel and morph into canvas cards, and a typed prompt grows a cascading diagram tree.
use: Narrative sequences in AI/collaboration tools where "generated results land on a canvas"; Style A demonstrates "existing content transitioning into a new form of existence," while Style B demonstrates "a structured tree growing from a single sentence"
duration: A ~5s (150f) / B ~6s (180f)
energy: Medium
tags: ui-entrance
---

## Intention
Existing generation narratives in the library only cover "typing inside a window" (document-typewriter-reveal, where documents write themselves) and "charts coming alive" (chart-live-moves), with no vocabulary for **content leaving its container and materializing as new entities on an open canvas**. This card fills that gap: the canvas is the stage, and generated objects are actors entering the scene. The linchpin of Style A is cross-container morphological transition—identical content shifts from "row" to "card," with position, width, height, corner radius, and layout interpolating synchronously along a single spring, so viewers register "it flew over and transformed" rather than "one deleted, another added." The linchpin of Style B is cascading hierarchy: lines lead nodes, and levels feed subsequent levels; structural clarity stems from sequential progression rather than simultaneous appearance.

## Variant Selection
| Variant | Approach | Use |
|---|---|---|
| A panel-to-canvas (row-to-card spill) | Cursor checks boxes one by one -> button pressed -> three rows lift then fly out staggered along upward arcs, cross-fading row and card forms mid-flight, landing with tilt angles and squash on touchdown; panel row slots collapse into dashed placeholders | Batch import / one-click to board: content migrating from list state to spatial state |
| B diagram-cascade (cascading generation tree) | Prompt typed character-by-character (border confirms upon completion; streaming border glow indicates generating after submit) -> drop line from prompt base connects root (gradient stroke hero) -> 2 children -> 4 grandchildren pull out level-by-level from top ports; angled connector lines with comet heads lead by 10f; camera pulls back from prompt close-up to reveal full tree; entire tree breathes once after assembly | AI-generated architectural diagrams / mind maps / ER diagrams: growing a tree from a single prompt |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| A Checking boxes | 14/24/34f staggered (cursor clicks each in swift arcs), spring(damping 11, stiffness 300) pop + checkmark draws over 7f | Checking is the "anticipation"; without it viewers don't know what is about to fly; checking simultaneously reads as static selection |
| A Launch stagger | Button pressed at 52f; three rows lift at 56/62/68f (4f: scale up 2% + deepen shadow) before launch (6f stagger) | Flying simultaneously reads like copy-paste; stagger >12f makes trailing rows look left behind; flying without lifting reads as deletion |
| A Flight interpolation | spring(damping 17, stiffness 95, mass 0.9); position follows quadratic Bezier with midpoint elevated by 220px; width/height converge 3f later | Linear flight reads as flat translation rather than "spilling out"; midpoint lift <100px loses arc feel; synchronizing size with position loses the parent-first/child-second weight hierarchy |
| A Form transition | Row 626x104 -> Card 486x300, corner radius 18->24, rowOp fades at u in 0.08->0.4, cardOp lights at 0.5->0.8 | Cross-fading two sets of content must be staggered—both states visible at mid-flight reveals the trick |
| A Landing tilt | -2.5 / 1.8 / -1.2 deg, landing 6f scaleY 0.97 squash and rebound | Completely straight reads like grid typesetting; >4 deg reads like scattered clutter |
| A Velocity blur | SpeedBlur amount 0.32, max 14 (oriented along arc velocity direction) | Active only during flight phase; returns to zero upon landing |
| B Typing | 0.95-1.2f per char irregular, space pauses 1.7f; prompt border turns purple upon completion to confirm, +4f submit button pressed | Constant-speed typing reads robotic; lacking confirmation state removes the causal link between "typing finished" and "generation started" |
| B Camera | Opening 1.3x zooms in to center prompt; 72f smooth pull back to 1.0 after submit | Without zoom-in, bottom half remains empty for first 2s; zoom-out must sync with cascade so tree grows inside newly revealed space |
| B Cascade timing | Root = submit +14f, tier interval 22f, siblings staggered by 5f; nodes spring(damping 14, stiffness 190), scale origin = top-center (pulling out from port) | Tier interval <12f reads as instantaneous dump; siblings on same frame read as duplication; center scale reads like modal popups |
| B Connector lead | SVG rounded corner paths (parent bottom port -> midline -> child top port) draw over 16f ease-out, leading child nodes by 10f; comet light dot on line head | "Lines leading nodes" establishes causality; lines trailing nodes feel like an afterthought |
| B Closing breath | Last node +22f onward, scale 1->1.03->1 centered at tree core (smooth, 28f), background aurora brightens one step in sync | Breath is the period ending "tree completion"; >1.06 reads as scaling glitch |

## Known Pitfalls
- Demo calibrated on grayscale/placeholder assets—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Division of labor with chart-live-moves: that card handles the intrinsic vitality of data charts (flowlines/point clouds/axis bursts), whereas Style B captures the **birth process** of structural diagrams—a living diagram != a generating diagram; do not use Style B to present existing charts.
- In Style A, row slots must collapse into dashed placeholders—if original slots remain intact after rows fly away, "migration" degenerates into "duplication," losing semantic meaning.
- In Style A, cross-fade timing (rowOp off before u~0.45, cardOp on after) is critical to prevent visual artifacting; springs overshoot and u may briefly exceed 1, so clamp all content opacities.
- In Style B, breath origin must be the visual center of gravity of the tree (demo 960,620) rather than screen center; otherwise it reads like full-screen zoom.
- In Style B, comet heads sample path length: use SVG elliptical arcs (A commands) rather than quadratic Beziers for corners so arc lengths can be calculated accurately, keeping the comet head pinned to stroke tip.

## Reference Implementation
demos/interaction/canvas-materialize-moves/
(DiagramCascadeBuild.tsx / PanelToCanvasMaterialize.tsx)
Source: miro-promo 84–92s (Style A) / 104–116s (Style B)
