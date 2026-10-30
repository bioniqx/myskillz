---
name: timeline-travel
summary: The camera accelerates along a horizontal version timeline, raises cards at each stop, then brakes sharply on the final milestone.
use: Changelog, milestone, or product evolution sections (another way to shoot "we ship continuously"); complements scroll-brake-moves: that card is a vertical list brake, this card is a horizontal time journey
duration: 4–5s
energy: Medium-high (acceleration to sudden brake rhythm profile)
tags: camera
---

## Intention
Shooting a product's release history as an expedition along a chronological axis (reference: The Kingdom opening title sequence): the camera executes a three-stage variable speed pan (gentle launch -> sprint -> abrupt brake) as v1.0 / v2.0 / v3.0 markers flash by, each raising a card via spring pop off the baseline—history rushes past outside the window, braking sharply on "today" with a punch-in. Speed itself communicates rapid development; the abrupt halt signals "now is what matters most."

## Motion Stages
| Stage | Frame Reference | Content |
|---|---|---|
| 1 Rest | f0–12 | Empty axis + first tick stationary |
| 2 Accelerated transit | ~f12–100 | World layer translateX piecewise easing: gentle launch -> sprint -> final 12% abrupt deceleration |
| 3 Card pop-up | Mid-transit | Cards begin popping 6f before camera reaches tick (spring damping ~11 with distinct overshoot), pivoting up via scaleY around bottom edge |
| 4 Brake and punch-in | 10f from brake frame | scale 1 -> 1.28 pushes in on final milestone (out cubic), leading into >=30f static hold |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Speed ramp curve | Input breakpoints [0, 0.15, 0.88, 1] -> output [0, 0.055, 0.9, 1] | Middle segment must be fast enough to create travel sensation; uniform speed looks like a cheap slideshow |
| Pop-up timing | Pops 6f before camera arrives at tick, reverse-queried via camXAt | Popping upon arrival means the audience has already missed it; popping too early feels like a teaser |
| Tick density | 3–5 primary milestones + intermediate secondary tick dots | Secondary dots act as reference objects for speed; deleting them destroys the sensation of velocity |
| Brake punch-in | 1 -> 1.28 / 10f | Braking without a push-in just feels like "stopping"; pushing in conveys "we have arrived" |

## Known Pitfalls
- The demo was calibrated on grayscale/placeholder assets; parameters are starting points, not production finals, and must be re-verified with real assets.
- If mid-stage sprint is fast enough to blur cards, layer CameraMotionBlur (covering only the high-speed segment, Round #8 precedent).
- Front-load the post-brake static hold budget: the demo's initial 25f hold failed standards; shifting the brake frame earlier solved it—reserve >=30f for the tail segment before back-calculating travel timing.
- Each popping card is an information container: in production, display authentic version highlight screenshots or concise copy; travel velocity must ensure at least the final two cards remain legible (Q6 kindred rule).
- Audio: light rhythmic tick on each card pop, heavy impact on abrupt stop (S2 kindred rule).

## Reference Implementation
demos/data/timeline-travel/
(TimelineTravel.tsx)
