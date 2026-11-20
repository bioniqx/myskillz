---
name: page-waterfall-wall
summary: Real page captures flow at different speeds across a tilted 3D wall, creating an endless field of content.
use: Showcasing scale across "multiple pages / features / templates"; montage mid-sections or post-intro product breadth showcases.
duration: 4–6s (Seamless loop; trimmed to section requirements)
energy: Medium (Flowing showcase type)
---

## Intention
A flowing overview: lets viewers absorb dozens of pages streaming past within seconds, communicating sheer scale rather than individual detail.
Division with outro-group-photo-launch: that is a **converging** overview (elements fly in to frame the wordmark for a final portrait, conveying "all part of one unified product"), whereas this card is a **flowing** overview (content streams continuously without freezing, conveying "vast volume yet to explore").
Division with wall-reveal-moves: that is a wall **entrance action**, whereas this card represents a wall's **continuous state**; an entrance card can hand off to this card to continue streaming.

## Motion Core
- Library component `assets/lib/VerticalTicker.tsx`: parent container perspective(1000px) rotateX(20°) scale(1.2) tilts backward into a wall; each column duplicates items `[...items, ...items]` with progress modulo `translateY 0→-50%` for seamless looping; top and bottom vertical gradient masks feather edges.
- Differential counter-flow is the engine of parallax: 3 columns stagger loop durations (such as 12/9/14s), with center column reversing direction—identical speeds in the same direction read as a single rolling texture, while differential counter-flow establishes independent vertical columns.
- Slow camera push nests on outer wrapper (scale 1→1.06 linear across shot); wall loops internally while camera moves unidirectionally—divergent motion axes prevent visual competition.
- Source assets: sanitized screenshots of real product pages (Q1); card-sized modules outperform full-page screenshots—viewers cannot read full pages during motion, whereas modular cards maintain identifiable silhouettes.

## Parameter Table
| Parameter | Typical Value | Tuning Feel |
|-----------|---------------|-------------|
| Column count | 3 (1080p) / 4 (ultrawide) | 2 columns fails to read as a "wall", 5 columns makes individual tracks too narrow and textures blurry |
| Loop duration | Adjacent columns differ by ≥25% (12/9/14s) | Insufficient differential flattens parallax; fastest column <7s feels like aggressive scrolling |
| Direction | Center column inverted (-1, 1, -1 or alternating) | All moving same direction = single giant sheet; inverted column is strongest evidence of independent tracks |
| Tilt / Perspective | rotateX 20° / perspective 1000px | >25° squashes top row text perspective into blur (Q2); <12° fails to convey backward tilt |
| Scale | 1.2 baseline + push to ~1.26 | 1.2 compensates for perspective shrinkage to avoid clipping corners; demo assigns zoom and push to outer CSS zoom layout, preserving screenshot sharpness (Q2) |
| Gradient mask height | 200px | Too short cuts off rows abruptly; too tall leaves fewer than 2 visible rows in viewport |
| Loop period | -50% travel must precisely equal single-replica height (content height + n·gap) | Ensured via marginBottom in library; custom implementations using flex gap risk half-gap frame hitching |

## Known Pitfalls
- **Parameters adapted from external implementation (remotion-3d-ticker), not final production spec; verify against real assets in production.**
- Total items height per column must exceed effective viewport height (otherwise identical slices appear twice simultaneously); never duplicate screenshots across adjacent columns, as identical cards appearing side-by-side reveals asset limitations.
- This card is an atmospheric establishing shot rather than an information delivery mechanism: text only needs to be recognizable as real software interfaces, not fully read; to draw focus to a specific module, hand off to spotlight-hero-card.
- P4 de-duplication: can coexist with outro group portrait in the same video (flowing vs. converging), but waterfall walls should only appear once per film; repeating feels like padding runtime.

## Reference Implementation
assets/lib/VerticalTicker.tsx (core component);
Demo at demos/ui-entrance/page-waterfall-wall/ (PageWaterfallWall.tsx / VerticalTicker.tsx).
