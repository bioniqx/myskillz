---
name: word-relay-filmstrip
summary: A filmstrip of page cards steps vertically while a serif word relay swaps only its verb, each swap aligned to the center of the current card.
use: "Single subject × multiple capabilities" enumeration sections (Shotcraft frames / builds / ships…); portfolio / case-study flows; multi-scenario product walkthroughs
duration: ~1.5–2s per word period × 3–4 words; demo 180f (6s)
energy: Medium-low (editorial temperament, rhythm driven by tactile "click" of word swaps)
tags: ui-entrance
---

## Intention
On the left sits the evidence (page screenshot filmstrip), on the right sits the thesis (large display typography): each time the verb swaps, the filmstrip steps down by one frame to present fresh evidence — copy and visuals annotate each other. The core requirement is **stepped motion**: the left column remains completely static normally, advancing exactly one card height solely at the instant of a word swap (stepping = the physical action of changing evidence); continuous scrolling degrades the left column into decorative background noise, robbing word swaps of their tactile "click." The second requirement is **alignment**: the vertical midpoint of the large text block must align with pixel-level precision to the midpoint of the active page card; any vertical deviation collapses the disciplined elegance of the editorial layout.

## Motion Core
- Stage: graphite near-monochrome dark field with warm champagne gold accents; left column: equal-height page cards (940×530, spacing 105) arranged vertically, strictly alternating black and white (dark and light) cards to emphasize stepping motion; within the swap window, cards advance exactly one card height over 18f asymmetric in-out (EASE.swift), with zero displacement during all other frames and vertical motion blur applied during the rapid transit phase.
- Depth of field: Based on distance from focal point `dist = |cardTop - 275| / 635`, adjacent cards dim by `0.68·dist`, scale to 0.94, and blur ≤3px — bringing new evidence into sharp focus as it steps into view.
- Right side: Serif typography (Didot style, 140px) across two lines — the primary subject noun "Shotcraft" remains roman and secondary ink throughout, while italic white verbs execute in-place relays:
  old verb grays out over 10f → lifts out from top mask edge across 8f ease-in starting at swap point (exit first); new verb rises letter-by-letter from bottom mask edge starting at swap point +7f (1.2f stagger, gold period arrives last; enter second); exit precedes entry with zero overlapping ghost frames (precedent: v2 ghosting "resebuilds" was caught and corrected).
- Gold leader line: Points from right edge of active card to text midline y=540, retracting across 6f at swap start and redrawing over 16f at swap point +10f; monospace index "01 / 03" above text block and 32px evidence footnote below swap synchronously with the verb.
- Alignment: Two line boxes of 154px each, `top = 540 - 154`, centering the combined height at active card top + card height/2 = y540 @1080p (calibrated to the exact pixel).
- Scroll-swap synchronization: Scroll start = old verb begins graying out; scroll finish = new verb settles into place.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|---|---|---|
| Page cards | Equal height (530px @1080p), alternating dark/light, ~half-screen width | Unequal heights or matching palettes obscure stepping; cards too narrow lose evidence weight |
| Word period | ~45–60f per word | <40f cuts off reading and blurs filmstrip; periods need not be strictly identical |
| Scroll window | ~16–18f asymmetric in-out, exactly one card height | Continuous scrolling violates the core requirement; over/undershooting reads as mechanical failure |
| Word relay | Old verb lifts out 8f after graying → swap point +7f new verb rises letter-by-letter (16f/letter, 1.2f stagger) | Same-frame crossfade produces ugly ghosting; gap >10f feels like dropped frames |
| Vertical alignment | Text block center = active card midpoint (pixel-exact) | Review precedent: "text height and center of middle page must align"; delta >8px is visibly jarring |
| Typography | Serif Didot style; verbs italic white, noun roman secondary ink | Sans-serif loses editorial refinement; verb must be brighter than noun as it is the changing element |
| Neighbor defocus | Dims 0.68·dist, scales down 6%, blurs ≤3px | Failing to dim allows neighbor cards to fight active card; blur >5px renders cards unrecognizable |

## Known Pitfalls
- The demo was tuned on placeholder copy — parameters serve as a tuning baseline, not a final production lock; verify with real assets during initial production.
- Division of labor with text-column-converge: that card handles left/right confrontation and concluding convergence; this card handles vertical evidence flows + in-place relays, with zero convergence or final reveal.
- Division of labor with pill-slot-cycle: that card handles cycling UI pill badges; this card represents an editorial-grade typographic and visual alignment layout system.
- Production assets: Page cards should feature authentic product screenshots (demo uses crafted mock layouts — storyboard script / render pipeline / final PR review, each verb resting on its corresponding evidence card; residual gap acknowledged); screenshot brightness must be manually categorized to ensure legible alternation.

## Reference Implementation
demos/typography/word-relay-filmstrip/
(WordRelayFilmstrip.tsx)
Original source: perplexity-promo.mp4 ≈76–90s
