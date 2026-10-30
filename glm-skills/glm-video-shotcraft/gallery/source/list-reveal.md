---
name: list-reveal
summary: Menu rows scale into place one after another with a faint overshoot while the whole list drifts slowly upward, keeping the per-item entrance and the group motion on two independent layers.
use: Navigation, sidebar, and settings panel entrances; UI sections where "interfaces self-assemble"; also serves as low-energy background during voiceover setup.
duration: ~4s (120f @ 30fps)
energy: Low (Steady cadence without peaks; maintains visual vitality via upward drift)
---

## Intention
Staggered list item fade-ins are easily prone to feeling stiff: each item freezes once it finishes moving, leaving the screen completely dead between arrivals. This card's solution adds a slow drift to the container that is completely independent of the per-item entrances—individual rows "find their slots" while the whole list "breathes." Viewers clearly read each item while no single frame across the entire shot is frozen solid.

## Motion Core
- Two completely decoupled motion layers: container `translateY(DRIFT/2 − DRIFT·f/(N−1))` consumes only global frame count, maintaining uniform upward drift throughout the sequence (demo: 96px total under 1920 coordinates, +48 → −48, ≈0.8px/f); individual items consume only their local timing windows without cross-calculating.
- Staggered entrances: start cue `2 + i·10f`, window 24f; 10f stagger is one step slower than conventional UI staggers—providing an interval suited for reading rather than rapid cascading; window is 2.4x the stagger → 2–3 adjacent items move concurrently, forming an unbroken wave.
- Placement motion is scale-driven: `scale(0.82 → 1)` paired with `translateY(44 → 0)` + focus blur 8px → 0; viewers perceive items growing into position from blurred states rather than flying up from below.
- Soft overshoot `bezier(0.3, 1.18, 0.5, 1)` (~1.5%)—subtle enough to turn landing from a mechanical halt into a soft latch.
- Secondary elements: icons lag by 2f, right-hand shortcuts/badges lag by 4f; opacity `min(1, lin·2.2)` reaches full solid state at 45% travel.
- Active item (Home) acts as the sole visual highlight: solid porcelain bar + single sheen sweep upon settling (Q4); remaining items use deep graphite fills with hairline strokes.

## Parameter Table (demo in 1920×1080 native coordinates)
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Item count | 6 (Home…Sign out) | Final item starts at 52f, settles at 76f, leaving ~44f for viewers to conclude; >8 items requires compressing stagger to avoid eating into outro |
| Stagger | 10f / item | 10f allows reading each row; compressing to 4f turns into a rapid cascade (different style), extending beyond 16f scatters cadence |
| Item window | 24f | Window is 2.4x stagger → creates overlapping flow; matching window to stagger creates rigid sequential handoffs |
| Initial scale | 0.82 | Scale where "an item is already recognizable"; <0.5 reads as popping from zero, conflating with pop styles |
| Initial displacement / Blur | 44px / 8px | Displacement must remain below row spacing (92px row height + 14px gap) to prevent rows intersecting |
| Overshoot | Soft back ~1.5% | Must be subtle enough to barely register; spring or larger overshoots across 6 rows look cheap |
| Container drift | Uniform 96px throughout (≈0.8px/f) | Total travel is 2x item displacement, but an order of magnitude slower—reads as "breathing"; matching item speed blurs the two layers together |
| Opacity slope | `min(1, lin·2.2)` | Lowering to 1 reveals translucent rows over background, looking muddy on dark palettes |

## Known Pitfalls
- Container drift is uniform throughout, ending at −48px on the final frame rather than 0—this animation **does not return to origin on the final frame**. To loop or match positions with subsequent shots, replace drift with a settle curve or add a counter-deceleration tail.
- Altering item counts requires recalculating stagger: final item starts at `2 + (n−1)·10f` plus 24f window, reserving ≥30f for conclusion.
- Row width 700px with label `nowrap`—longer labels can collide with right-hand shortcuts; expanding copy requires widening rows. Total list height ~644px; verify top and bottom rows stay inside safety margins after drift (demo drift range y 188–928).
- Drift direction (upward) shares direction with item displacement (44px→0, also upward). This alignment is intentional (reinforcing smooth motion), but velocities must maintain an order of magnitude difference, otherwise the shot reads as "everything floating upward together."
- Right-hand headline waits until list reaches halfway (46f) before entering: opening grants sole focus to the list (Q5), preventing viewers from scanning between two targets.
- Icons use monochrome line art; only active item takes solid highlight, with unread badge taking accent color; recalibrate strokes and shadows on light palettes.

## Reference Implementation
demos/ui-entrance/list-reveal/
(ListReveal.tsx: graphite dark palette, sidebar poster with left list + 120px right headline)
