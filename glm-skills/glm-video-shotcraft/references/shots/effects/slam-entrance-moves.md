---
name: slam-entrance-moves
summary: Three high-energy arrivals: a perspective snap, a score drop, and an impact burst that pushes nearby elements.
use: Heavyweight entry for hero and KPI cards; impact-feedback handles post-landing response, while this card treats the arrival itself as the impact
energy: High
duration: Action phase 6–22f + impact aftershocks ~16f + hold >=45f (demo: A 120f / B 135f / C 140f)
tags: ui-entrance
---

## Intention
The ceiling for entrance intensity in the library had been deck-deal-flyin's "dealing cards"—swift, but lacking weight. This card introduces the "slam" tier in three flavors: Variant A delivers directionality—the card whips in grazing the lens with exaggerated fisheye perspective, snapping flat with the stylish flair of anime Kanada-style choreography; Variant B delivers weight—a KPI card drops from 2.6x scale in front of the lens, triggering shock rings, debris particles, screen shake, and white flashes on the exact same frame with the impact of a sports scoreboard; Variant C delivers propagation—building atop B's triad, shockwave fronts sweep across adjacent cards to visibly shove them aside before rebounding, demonstrating raw physical power through "shaking its neighbors."
Choose according to narrative needs: use A to announce "it has arrived," B to announce "it is heavy," and C to announce "it shook the entire house."

## Variant Selection
| Variant | Method | Use Case |
|---------|--------|----------|
| A kanada-perspective-snap | perspective 260->1800px + rotate3d 62 deg -> 0 + scale 1.8->1 whipping in over 18f (pose settling trails translation), final 5f overshoot +6 deg spring flattening + focus lines, long diagonal shadow squaring up | Confident hero card solo entrance; anime / energetic tones |
| B score-slam | Card drops from scale 2.6 / rotate 5 deg in front of lens over 6f ease-in(quad), destination frame triggering shock ring + debris sparks + screen shake + white flash synchronously, score digits secondary-dropping 3/6f later | KPI / scoreboard heavyweight metric debuts |
| C impact-burst-kit | Hero card slams from in front of lens into empty page slot + B impact triad + shockwave front mathematically calculated by radius-distance sweeping neighbor cards, displacing neighbors 34px outward + rotate ±3.5 deg with damped rebound | "Whole-room shock" when neighboring cards already exist on page |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| A Whip-in | 18f: translateX −1350->0 via EASE.snappy (sudden stop), perspective / rotation / scale follow late-settling curve bezier(.62,0,.3,1) over 16f—card rushes in twisted, snapping flat in the final frames; horizontal SpeedBlur (0.2x velocity, <=26px) + 7 trailing speed lines | Faster than 12f loses fisheye distortion; slower than 24f bleeds kinetic energy; synchronizing pose with translation curves flattens the card before arrival, losing fisheye feel after frame 1 |
| A Settling | rotateY rushes to +6 deg across 15–20f, rebounding to 0 via spring(damping: 16) from 20f + 8px screen shake over 2f + 48 focus lines dissipating outward over 9f + diagonal shadow squaring up; inner card text settles 3f later (title −10 deg skew squaring up) | The snap lives in the overshoot rebound, not the end of translation; focus lines over 10f read like decorative stickers |
| B Slam drop | 0–9f hovers before lens (2.75->2.6, 10px blur, semi-transparent revealing background) -> 9–15f ease-in(quad) slams to 0.965 -> spring(damping: 14) rebounds to 1 | ease-out landing feels like "setting down"; ease-in produces the "slam" |
| B Impact triad | Shock ring diameter 120->1500px over 16f (white core 9->1.5px + gold soft glow) + 14 polygon glass/foil shards flying 280–580px (+16 sparks) + screen shake 18px exponential decay over 5f (primarily vertical) + 2f white flash | Original draft (720px / 10px dust / 8px shake) was imperceptible, boosted x1.5–2 in render; solid black thick rings / black square dust read as stickers |
| B Decoupling core | Ring / debris "expansion" driven by out-cubic, "dissipation" driven by linear frame time | Driving both with out-cubic moves the early phase too fast, vanishing right after expanding |
| C Propagation frame | Calculated from wavefront crossing neighbor card center distance (ring radius 100->1100 over 16f, 514px distance ≈ 3f post-landing); envelope cos(t/2)*exp(-t/8), clamped to 0 at 40f; horizontal motion blur applied on push | Moving neighbors on the same frame as hero card reads like global canvas shake; 3f delay conveys "hit by shockwave" |
| C Hover charge | 0–16f hero card hovers above slot: lifts 20px, scale 1.55->1.6 (smooth), slot contact shadow deepens with elevation, then slams into slot across 16–22f ease-in(cubic) | Static hold during hover reads as "frozen"; charge amplitudes >30px turn into a separate action |
| Depth of field | When B/C are close to camera (large scale), apply blur based on elevation (B <=10px, C <=7px), snapping sharp upon landing | Sharp elements close to the lens fail to convey "dropping down from in front of the camera" |
| Finale | Truly static for >=45f after all shockwaves settle | Double standard hold for heavyweight impacts (matching beat-cut Variant A precedent) |

## Known Pitfalls
- Demo calibrated using video-shotcraft promotional assets (A premiere card / B "Shotcraft vs Keyframes" final score / C specs page Launch film card)—parameters serve as a tuning baseline, verify against real assets in production.
- On light backgrounds (C), shock rings require a white compression disc underlay with the ring itself using saturated accent colors; on dark backgrounds (A/B), use white core + colored glow; white rings on light canvas or black rings on dark canvas are virtually invisible.
- All three variants include screen shake; screen-shake techniques (impact-feedback) permit only one shake source per shot; the three variants are mutually exclusive within a single shot.
- Heavy audio dependency: Variant A's snap and Variant B/C's sonic boom must lock to the exact landing frame (sound-design §4.5); silent versions of B/C triads read as "the card is glitching."
- In Variant C, neighboring cards must rest stably on screen for >=15f before being impacted—displacing neighbors while they are still entering scrambles the causal chain.
- Cap slam entrances at <=2 occurrences per video; firing more than twice dilutes impact until none register (P4).

## Reference Implementation
demos/effects/slam-entrance-moves/
(ImpactBurstKit.tsx / KanadaPerspectiveSnap.tsx / ScoreSlam.tsx)
