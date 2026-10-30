# template/ — Production Template Ink Press: Editorial Paper & Ink Product Promo (36.2s)

A validated full promo video project serving as a template for faithful reproduction: swap in screenshots and assets from a target web or desktop product, adapt shot-by-shot following this guide, and achieve equivalent production fidelity.

- Specifications: 1920×1080 @ 30fps, 1085 frames (36.2s), SFX-only (version without BGM)
- Style: Paper & Ink with Amber accents (paper background `#f2eee6`, ink typography, serif display headlines, amber accents)
- Running: `npm install && npx remotion studio src/index.ts` (preview) / `npx remotion render src/index.ts AiflPromo out/promo.mp4` (render)
- QA Stills: `npx remotion still src/index.ts AiflPromo out/qa/f150.png --frame=150`

## 1. Film Structure (AIFL_SHOTS in src/aifl/Main.tsx)

Energy arc: Brand opening (low) → 3 feature segments alternating with breathing title cards (medium-high / low) → finale assembly building to peak energy. Two wordmark milestones (opening, outro) hold for a full 1s after settling.

| # | Frames | Duration | Scene File | Content | Corresponding Shot Card |
|---|--------|----------|------------|---------|-------------------------|
| 1 | 0–220 | 7.3s | live/SceneOpen.tsx | Ink trace + wordmark letterpress opening → dashboard wide view → spotlight hero card (float + sheen sweep + settle) | brand-ink-open / spotlight-hero-card (hi-res rasterization in aesthetic-rules.md Q2) |
| 2 | 220–275 | 1.8s | PaperTitleCard.tsx | Title Card 1: "All your team's research, one place to go." | paper-title-card |
| 3 | 275–465 | 6.3s | live/SceneFlyIn.tsx | Deck close-up orbit → cards deal into grid → scroll → search typing → filter → click push-in | deck-deal-flyin / type-and-filter |
| 4 | 465–565 | 3.3s | live/SceneDetail.tsx | Detail page macro close-up, rows embedding progressively | row-embed |
| 5 | 565–620 | 1.8s | PaperTitleCard.tsx | Title Card 2: "Paper Radar…" (including DigitRoll numeric counter) | paper-title-card |
| 6 | 620–725 | 3.5s | live/ScenePapers.tsx | Paper radar list stack-press + counter settling | list-stack-press |
| 7 | 725–775 | 1.7s | PaperTitleCard.tsx | Title Card 3: "Every project, linked to your weekly report." | paper-title-card |
| 8 | 775–885 | 3.7s | live/SceneWbr.tsx | Weekly report "writing itself" typewriter reveal + historical reports popping into sidebar | document-typewriter-reveal |
| 9 | 885–940 | 1.8s | PaperTitleCard.tsx | Title Card 4: "The whole team, on the same page." | paper-title-card |
| 10 | 940–1085 | 4.8s | live/SceneOutroLive.tsx | Defocus → element ensemble assembly → stamped wordmark slam (riser → impact → sparkle) → 1s hold | outro-group-photo-launch |

Overlay layers (managed declaratively in Main.tsx, exported for `src/workbench.ts` manifest import to support multi-track editing; see ../references/workbench.md):
- **TITLE_CARDS**: Copy table for 4 title cards (`*word*` = amber italic emphasis word parsed via `parseWords`); card 2 includes subtitle + rolling numbers
- **CAPTIONS**: Bottom full-width explanatory captions (6 entries across absolute frame table) overlaid on feature sections, omitted on title cards and outro
- **FLASH_CUTS / FlashCut**: Warm white flash transitions at 4 cut points, `from = cut_frame - 5`, spanning 5f on each side
- **SFX Table**: 30+ entries of `{from, src, volume}`, annotated with corresponding on-screen actions; long keyboard samples truncated using Sequence duration (`sfxDuration`: 24f / 44f)

## 2. Shared Foundational Components

| File | Purpose | Key Details |
|------|---------|-------------|
| live/Scene*.tsx · PaperTitleCard · Caption | Each scene exports `*_DEFAULTS` (copy, font sizes, palette) read via defaulted props; `src/workbench.ts` schemas reference this object directly for property panel editing. Easings, timings, and camera keys remain internal | When swapping products, edit DEFAULTS rather than scattered literals; colors use sRGB values from original tokens (ink `#13110f`, amber `#955905`, gray-ink `#65635f`, dark amber `#ae6700`) |
| live/PageCam.tsx | 2.5D page camera—the foundation for all real-page shots | Full-page screenshot + keyframes `{frame, cx, cy, zoom, rotX/Y/Z, persp}` interpolated camera motion; children positioned in page CSS px coordinates (sharing layout.json coordinates); **3D mode uses CSS `zoom` for layout-level magnification** (transform scale causes downsampling blur; see aesthetic-rules.md Q2); optional depth-of-field top gradient blur |
| PaperTitleCard.tsx | Title card breathing intervals | Serif display headline with word-by-word reveal; accent words in amber; supports DigitRoll counters |
| FlashCut.tsx | Warm white flash transition | Covers only 10f across hard cuts; not used as decorative lighting |
| Caption.tsx | Bottom full-width narrative captions | Monospace small text with tracking; subtle push-in on entry/exit |
| DigitRoll.tsx | Odometer counter roll | Rolls digit by digit until settling |
| live-layout.json | Page element coordinate map | Stores element `{x, y, w, h}` (page CSS px system) + page height; imported by scenes for flight targets and mask positioning |

## 3. Asset Catalog (public/)

- `textures/live/*.png`: Full-page 2x screenshots (projects-full / detail-full / papers-full / wbr-full), element crops (card1–10, paper1–5, float-*, nav), empty backgrounds (projects-empty), hi-res close-up crops (card4-hires, captured at 4x)
- `audio/*.mp3`: 11 SFX used in this film (Mixkit, licenses in ../assets/audio/ATTRIBUTION.md)

> Note: Template screenshots originate from an internal research tool (fictional demonstration data). Before distributing final promo videos, replace all assets with target product screenshots.

## 4. Product Adaptation Guide (Fastest Path to High Fidelity)

1. **Asset Capture** (detailed capture method in `../references/pipeline.md` Stage 4):
   Copy `../assets/scripts/capture-template.mjs` into target project, update BASE_URL and selectors, and generate the trio: full-page 2x textures, transparent element crops, and `layout.json`. Align asset filenames with template conventions (projects-full / detail-full / …) to drop directly into `public/`.
2. **Update Layout Coordinates**: Replace `src/aifl/live-layout.json` with new layout JSON. All scene flight targets, mask dimensions, and floating elements read from this file; animation follows updated coordinates.
3. **Shot-by-Shot Adaptation** (following the Section 1 sequence):
   - For each shot, **read the full recipe card + scene source code first** to understand parameter semantics;
   - Mandatory updates: PageCam keys (reframe cx/cy/zoom for new layout), crop filenames, card counts, slot loops, and copy;
   - Do not alter: easing curves, duration proportions, hold frame budgets, or SFX alignment structures—these embody the core polish.
4. **Copywriting**: Update `TITLE_CARDS` table (`*words*` for emphasis), CAPTIONS table, and outro brand/tagline. When shot structures change, update `src/workbench.ts` synchronously (`scene(...)` for new scenes, `title(...)` for title cards), then run `cd ../workbench && npm run parity` to confirm non-destructive disassembly.
5. **Quality Review**: Generate stills with `npx remotion still` after modifying each shot (at least entry midpoint, action peak, and settled hold); render full film and inspect frame grabs via ffmpeg; cross-check against `../references/aesthetic-rules.md`.
6. **Duration Adjustments**: When adding or removing shots, shift `from` frames in AIFL_SHOTS (single source of truth); shift absolute frame numbers in CAPTIONS/SFX/FlashCut accordingly. Finalize video timing before re-aligning SFX tables.

## 5. Quality Checklist (Mandatory Standards for Reproduction)

- Text remains razor sharp under 3D / magnification: 2x full-page textures + PageCam CSS zoom + 4x close-up crops for hero elements
- Mandatory breathing space: brand wordmark holds for ≥30f after settling; batch motions leave ≥15f pause at rest
- Each animation technique plays hero only once across the film
- Flying elements land accurately into real page slots (layout.json coordinates), never hovering in empty space
- SFX uses cinematic vocabulary (whoosh, impact, riser, sparkle, transition); game UI sounds forbidden; outro ends with riser → impact → sparkle
- If BGM is added, deliver two versions: with BGM and without BGM (SFX preserved). Wrap BGM `<Audio>` with `bgm` inputProp, rendering the no-BGM version via `--props=props-nobgm.json` (`{"bgm":false}`)
- Deterministic rendering: no `Math.random()` or `Date.now()`; all randomness uses fixed seeds
