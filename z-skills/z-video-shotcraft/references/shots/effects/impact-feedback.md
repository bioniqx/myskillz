---
name: impact-feedback
summary: Two impact layers: a combo counter with damage feedback, and a full anime-style impact frame.
use: The "hit instant" when elements slam into place or collide—adding arcade-grade juice to drops and crash stops; select variant along the intensity ladder
duration: n/a (element-level technique piggybacking on landing actions; frame budgets detailed in parameter table)
energy: High (instantaneous impact)
---

## Intention
When elements slam into place without a tactile "impact moment," landings feel like bland slide-deck fly-ins. Game juice (Vlambeer's screen-shake philosophy) and anime impact frames offer the same answer: bite into time during those few hit frames to transmit kinetic impulse to the viewer. The two variants form an intensity ladder: Variant B uses local freeze frames layered with damage numbers and jumping combo counters, turning a feature list into a fighting-game combo with strong narrative clarity; Variant C delivers the heaviest punch—a 3f negative color inversion with radiating focus lines upon crash-stop, representing the highest, most stylized emphasis.

## Variant Selection Table
| Variant | Method | Use Case |
|---------|--------|----------|
| B hit-counter combo count | Three cards slam in sequentially; each hit = 2f freeze frame + floating damage numbers + xN combo counter escalating in size; demo frames "damage" as production hours saved by each video-shotcraft feature, drifting into card footers | Feature combo sequences—framing "many capabilities" as combo hits; rich gamified language |
| C anime-impact frame | 3f full-canvas negative inversion + radial focus lines + chromatic aberration on crash-zoom stop, withdrawing completely on frame 4 | The single climactic blow of the entire video; peak emphasis tier |

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| B Cadence | Three cards spaced 28f apart (anim time 30/58/86), 10f ease-in(quad) drop before hit; 2f global freeze on each hit (background diagonal scroll freezes concurrently) | Uniform spacing establishes the rhythmic cadence of a "combo" |
| B Damage numbers | Hits lower-middle of card, scale 1.45->1 + floats up 150px past card edge, fades over 12f after 4f; font size escalates 88/104/124px, yellow italic + hard drop shadow | Fading >16f drags, obscuring the next hit; launching above card top collides with corner counters |
| B Counter | Pulse peak 1.3/1.45/1.6, rotate −2/−4/−6 deg, font size 140/166/196px, exp(-t/2.4) decay; three heat bars illuminate step-by-step | Escalating intensity is vital—identical sizes fail to communicate "hitting progressively harder" |
| C Crash-stop | 6f anticipation pullback to 0.985, then crash-zoom 6f ease-in(cubic) to 2.25x (card height 454x2.25 approx 95% canvas height, borders avoiding frame clipping), card center converging to dead center; motion blur temporal sampling + sharp center copy | Crash-zoom parameters follow crash-zoom-punch card |
| C Impact frame | 3f from crash-stop: invert(1) grayscale(1) contrast(1.45) + 34 thick wedges + 22 fine needle focus lines (updating pattern each frame, inner tips radially faded to clear focal point) + red/cyan negative copies screen-blended with ±8px offset; full retreat on frame 4, outer canvas dimmed for one beat | 3f is the sweet spot—at 4f viewers start deciphering the negative image, breaking the illusion |
| C Recovery shake | 6px exponential decay starting at frame 4 (tau approx 2.2f), settling within ~12f | Amplitude must cross the visual perception threshold (perceptibility precedent) |

## Known Pitfalls
- Parameters calibrated on placeholder assets; verify against production footage during initial run.
- Variant B freeze frame **must be global**—background scrolling must freeze concurrently, otherwise time does not feel "suspended" and the card simply looks like it dropped frames. Driving all layers via a unified remapped frame `df` is essential; only effects that must continue during freeze (such as flash frames) run on raw frame `f`.
- Frame remapping shares technology with speed-ramp-freeze; avoid stacking both cards in the same shot—conflicting remappings distort rhythm into glitching.
- Variant C negative frames are intensely aggressive in ink-and-paper aesthetics—limit to one climax per video, and lock frame-accurately with impact SFX (foley via sound-design); a silent negative frame looks like a rendering bug.
- Variant B carries strong arcade gaming vernacular (damage figures and combo multipliers are explicit gaming tropes); use cautiously when product tone is formal.
- In Variant B, cumulative freeze frames push real clock frames beyond animated frame numbers; budget shots using `real_hit_frame = anim_hit_frame + accumulated_frozen_frames` (demo `HITS_REAL`).

## Reference Implementation
demos/effects/impact-feedback/
(AnimeImpact.tsx / HitCounter.tsx)
