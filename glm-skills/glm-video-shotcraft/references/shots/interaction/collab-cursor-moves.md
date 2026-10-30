---
name: collab-cursor-moves
summary: A five-cursor ensemble drifting and typing across a shared board as living collaboration ambience.
use: Canvas scenes with collaboration/multiplayer themes, establishing an ambient warmth of "team presence" across the frame
duration: A ~5.2s (156f)
energy: A Low-Medium (ambient layer, can underpin any duration)
---

## Intention
Most cursor cards in the library are "functional clicks" (cursor-flyover is a single-cursor click-and-tour). This card elevates collaborative cursors with identity nameplates into **actors**: five cursors enter staggered and drift continuously as ambient particles, carrying the entire feeling of "team presence," with one pausing to type (a cameo role). SVG cursors + nameplate chips come at very low cost with high narrative density, serving as the most cost-effective visual proof for collaboration themes.

## Variants
| Variant | Approach | Use |
|---|---|---|
| A cast-ensemble | 5 named colored cursors fly into video-shotcraft storyboard whiteboard staggered via spring (avatar group pops in same frame, sticky notes carry author colors) -> dual-frequency sine drift resident on canvas -> one anchors to insertion point to type briefing card title -> all smoothly gather around card at close | Ambient layer across canvas/whiteboard product videos; adds background vitality of "others are here" alongside primary content |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| A Entrance | 5 cursors staggered with delays 2/7/11/16/22f, spring(damping 15, stiffness 80); nameplates fade in + float up 12px 10f later; top-right avatar group pops in same frame (slot width expands with pop) | Nameplates appearing simultaneously with cursors read like stickers; fading in upon deceleration conveys "arriving and announcing presence" |
| A Drift | Dual-frequency sine superposition (0.055/0.021 rad/f, unique phase per cursor), amplitude +-40/26px | Single-frequency sine reads like a pendulum; dual-frequency out-of-phase conveys "human hand randomness" |
| A Typing cameo | 48–104f types 29 chars (1.6–2.4f/char deterministic jitter, extra 0.9f pause after spaces); cursor arrow anchors to inline insertion point anchor, tracking line wraps; hand remains steady during typing (drift clamped to 0) | Calculating arrow and insertion point separately guarantees misalignment; zero-width inline anchor lets browser typography handle positioning |
| A Gathering | From 98f over 28f smoothly converges around card perimeter (avoiding titles and eyebrow headers), drift amplitude attenuates to 25% | Drift must not drop to zero after gathering—completely static cursors read like a crash |

## Known Pitfalls
- Demo calibrated on custom scene (porcelain whiteboard + sticky notes + briefing card, board tagged with video-shotcraft logo, title "Ship a launch film by Friday.")—parameters are a tuning starting point, not final production lock; re-verify against real assets in initial production.
- Nameplate color = identity encoding; must remain consistent across video (blue = Designer stays blue); changing colors mid-scene makes viewers think characters swapped.
- When changing title copy, preserve character count and space count so typing cadence (per-character jitter indexed by subscript, extra pause after spaces) and ending frames remain aligned.
- Drifting cursors must never obstruct primary content currently being read—ambient layers must yield to the scene; keep drift bounds outside subject safety zone.
- Division of labor with cursor-flyover: that card handles cursor "operating UI" (clicks carry payloads), whereas this card features cursors "performing for you" (motion is narrative); return to that card when cursor needs to click elements.

## Reference Implementation
demos/interaction/collab-cursor-moves/
(CollabCursorMoves.tsx)
