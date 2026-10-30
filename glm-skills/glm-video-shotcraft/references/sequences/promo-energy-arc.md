---
name: promo-energy-arc
summary: Full-video energy arc — low-key brand open → single-hero establishment → feature-climbing sequence with breathing title cards → keynote peak outro
use: Default full-video structure for 30–60s multi-feature web product promo videos (fill the skeletal arc during storyboarding before picking shot cards)
segments: 4 segments + 2–4 breathing title cards
---

## Intention

Synthesizes the rhythm rules scattered across R1–R3, Q5, Q8, and P4 into a single, directly applicable full-video curve template.
The reference template video (1085f) and two independent reproductions (900f each) all converged into this exact same structure. It is a solid default, not an absolute mandate: projects may intentionally deviate, but any deviation must be explicitly justified in the project spec.

## Segment Table

| Segment | Duration % | Energy | Responsibility | Candidate Recipe Cards |
|---|---|---|---|---|
| ① Brand Opening | 8–12% (30s video); Opening + Establishment combined up to 20% (template video) | Low | Wordmark imprint + hold ≥1s (R1), handing off cleanly to the product page | brand-ink-open |
| ② Single-Hero Establishment | 12–15% | Medium (highest textural polish, slowest deliberate pacing) | Single hero, one complete movement arc ≥3s (Q5/R3), firmly grounding the product's atomic unit | spotlight-hero-card (+ aesthetic-rules.md Q2 high-DPI rasterization technique) |
| ③ Feature Climbing Sequence | 55–65% | Alternating Mid-High ⇄ Low | Each shot binds a unique feature, and each technique stars only once (P4); breathing title cards inserted between shots as needed | deck-deal-flyin / type-and-filter / list-stack-press / row-embed / document-typewriter-reveal |
| ④ Keynote Peak Outro | 13–16% | Peak (highest across entire video) | Representative elements of all showcased features assemble to surround the wordmark (Q8), sign-off hold ≥1s (R1) | outro-group-photo-launch |

Breathing title card (`paper-title-card`) rules: Insert one card after every 1–2 feature shots; 50–55f (~1.8s) per card; 2–4 cards across the entire video. Use as an introductory title card before major feature reveals (C2).
In the template video, title cards account for 4 out of 10 shots, and 2 cards each in the two reproductions — adjust density based on the number of feature shots.

## Workflow (Replacing Ad-Hoc Deduction)

1. List product features (P4) and count the number of feature shots N.
2. Allocate total frames using the segment table: first deduct budgets for ①, ②, ④, and title cards; split remaining frames across ③.
   Within each shot's budget, **allocate hold/rest frames first** (R1 landing hold ≥30f, batch ending rest 15f, R3) before choreographing motion — do not design motion first and look for gaps later.
3. Alternate energy in segment ③: interleave high-energy shots (deal/stack) with steady-pace shots (interaction/field reading). Place the highest information-density shot (documents/reports) right before the peak outro — the template video and both reproductions placed document/report shots in the 2nd or 3rd to last position.
4. Scan `shots/` frontmatter to pick cards for each slot; read the full card for chosen shots.
5. After arranging shots, select transitions for each boundary (`shot-transitions` technique card patterns), and write them into the storyboard's "Key Motion" column — transition frames are budgeted from adjacent shots.

## Known Pitfalls

- Blindly applying the skeleton as a rigid rule: Segment percentages are empirical observations from the reference template video. Short 15s videos or single-feature products should boldly merge segments, but the ① hold and ④ peak outro ends must never be skipped.
- Stacking only high-energy shots in segment ③: Continuous high energy reads as noisy chaos; alternating intensity and inserting title cards is rhythm itself.
- Writing breathing title cards as duplicate taglines: If a title card duplicates the outro tagline, remove it (P4 rule: outro tagline deduplication).

## Reference Implementation

`template/src/aifl/Main.tsx` `AIFL_SHOTS` segment table (total = 1085f).
