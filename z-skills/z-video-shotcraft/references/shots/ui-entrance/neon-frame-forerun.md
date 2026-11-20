---
name: neon-frame-forerun
summary: A neon frame races ahead to outline the scene in steep perspective while components drop from above and the page brightens as they land.
use: Ceremonial entrance for UI panels in dark brand films (frame arrives first, content drops in after); debut of primary feature sections; openers for neon/cyber aesthetics.
duration: Frame trace ~0.7s + brighten & drop ~2.7s + background extinction settle ~1s; full segment 4–4.7s (demo 140f)
energy: Medium-High (Three layered motions compounding, all serving a unified entrance)
tags: effects
---

## Intention
Frame first, fill second: the neon outline races around the boundary like runway lights to stake out real estate, proclaiming "content is arriving here." As the page brightens from pitch black inside the frame, components drop in from above with shadows—viewers watch the interface being seated into the frame. The three motion layers (frame trace / page illumination / component drop) must **lock into tight synchronization**: component landing progresses in lockstep with page illumination, concluding slightly after, with frame glow merging into panel rim glow. Background neon tube echoes extinguish during the final phase, handing full luminosity to the hero element.

## Motion Core
- Neon frame: steep perspective rectangular frame; two white-hot leading heads race outward top-and-bottom from left-edge center (20f, swift takeoff, braking to collide at right-edge center with a flash). Tubing uses 4-tier layered strokes for glow (wide soft bloom / medium bloom / color core / white-hot core) avoiding blur filters for sharp, cheap rendering; upon completion, core line reduces to hairline as frame glow merges into panel rim glow.
- Page illumination: page surfaces from black only after frame closes (16–30f), transitioning from dark to bright (24–84f smooth) as a cool-purple shadow mask sweeps away from left to right, conveying "neon light charging the page."
- Component drop: **true 3D suspension**—panel and components sit within preserve-3d; components translateZ 120–170px, casting matching soft silhouette shadows onto the panel (higher elevation yields larger, softer, fainter shadows cast toward bottom-right). Brightness adjusts via leaf node brightness filters without applying filter/opacity to 3D parents (which would flatten 3D context). Each item drops over 24f with acceleration + cushioned landing; landing cues span 54→104f staggered from sidebar top-down to main panel top-down (dense to sparse), settling ~20f after illumination.
- Background: five echoing frames stepping backward in depth (translateZ stepping back, scaling outward) form a neon tunnel; frames ignite sequentially from near to far after outer frame closes (deterministic fluorescent flicker); mid-section tubes extinguish first, followed by outer tubes during 94–118f.
- Camera: rotateY −30° → −12° (0–96f EASE.out long deceleration), drifting 1.5° during hold phase.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Frame trace | 20f dual-head race (swift) | Single-head trace reads as illustration; >30f leaves viewers waiting |
| Suspension elevation | translateZ 120–170px, shadow tracks elevation | Review rule: insufficient height + premature start = imperceptible shadow (amplified 1.7x and delayed in v3 revision) |
| Drop window | 24f per item; landings 54→104f, settling ~20f after page lit | Landing before page is lit = dropping furniture in a pitch-black room; lagging too far reads as disjointed scenes |
| Stagger | Staggered starts, overlapping parallel descents (EASE.out distribution, dense to sparse) | Sequential serial waiting rejected across all drop rulings |
| Background extinction | Mid-segment bright, tail extinguishes; each tier flickers off in 6f with 7f tier gap | Omitting extinction fails to isolate hero; extinguishing on same frame reads as a blackout |
| Drop granularity | Card/row tier (brand, 4 navigation items, greeting, 3 metric cards, 4 task rows) | Finer granularity increases rendering cost; fewer, larger elements enhance readability |

## Known Pitfalls
- Demo calibrated on grayscale placeholder assets—parameters serve as calibration baseline, not final production specs; verify against real assets in production.
- Suspended component dropping is a signature technique; this card shares FloatWrap pattern with graze-face-tour—imperceptible shadows render the technique pointless.
- Division with brand-frame-snap: that card focuses on crisp snapping cadence of a brand frame; this card is an entrance ceremony combining precursory framing with component seating, where the frame serves as prologue.
- Derivative variation note: camera rotation variant (curved left-to-right orbit + concurrent drops) was refined to require all components dropping synchronously, converging into neon-frame-orbit-drop.

## Reference Implementation
demos/ui-entrance/neon-frame-forerun/
(NeonFrameForerun.tsx)
Source clip: clickup-30.mp4
