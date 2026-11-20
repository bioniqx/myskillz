# Brand Replacement Round Execution Brief (Round 3, Required reading for all participating agents)

## 0. Background and Objective

After the first two rounds of redesigns, the user made shot-by-shot selections on the comparison page (original / v1 / v2 / drop), recorded in `shot-polish/decisions.json`.
Demos in the repository **have been switched to the user's selected versions** (original from `main`, v1 from `d16a3df`, v2 from current HEAD), and the 66 dropped demos were deleted. The user's request for this round:

> Based on the shots I selected, replace any logos or brand names appearing inside them with video-shotcraft; where appropriate, adapt copy into praise or promotional messaging for video-shotcraft.

Therefore, this round **only replaces content without altering design**: the user picked versions based on visual rendering, so shot technique, motion curves, rhythm, duration, palette, layout, and composition are strictly preserved from the chosen version.

## 1. Brand Assets: `demos/_fixtures/Brand.tsx` + `assets/brand/BRAND.md` (Specification)

- `BRAND`: `name: 'video-shotcraft'`, `short: 'Shotcraft'`, `repo`, brand colors `amber #D3923C` / `ink #171714` / `paper #F5F3EE` / `slate`, wordmark font `font`.
- `<ShotcraftMark size tone="dark|light" frameProgress cutProgress>`: The "Frame Chisel" mark—an open framing viewfinder + amber diagonal cut.
  The two paths `MARK_PATHS.frame` and `MARK_PATHS.cut` can be animated independently (frame traces out first, cut slices in, or outline stroke animation, mask reveal, etc.).
- `<ShotcraftWordmark size tone mark>`: mark + `video-shotcraft` horizontal wordmark lockup.
- `PITCH.en / PITCH.zh`: Brand mottoes (**Frame motion. Craft the shot.**), taglines, features, praise, and showcase copy. Pick from here or rewrite in the same authentic voice.
- Specification rules: Wordmark is strictly **all lowercase** `video-shotcraft` (never all-caps tech wordmark); do not deform mark or alter the diagonal angle; the mark itself takes no glow/gradient/stroke/shadow; amber diagonal remains amber (use `tone="dark"` on dark backgrounds, `tone="light"` on bright backgrounds). Stage lighting around the mark and entry animations (scale, flip, draw, reveal) can proceed normally.
- Import path: `import { BRAND, ShotcraftMark, ShotcraftWordmark, PITCH } from '../../_fixtures/Brand';` (adjust relative path).
- `_fixtures/Fixtures.tsx` FakeDashboard has already been updated centrally; demos using it require no manual change.

## 2. What to Replace

**Must replace (logo / brand name)**:
- Fictional brand names, product names, company names, app names (Lumen, Stride, Northwind, Acme, Orbit…), as well as any lingering real company/product names;
- Replace with `video-shotcraft` or its short name `Shotcraft`.
- Ensure typographic balance and visual hierarchy remain sharp.
