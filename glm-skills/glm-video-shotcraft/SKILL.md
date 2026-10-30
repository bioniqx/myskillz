---
name: glm-video-shotcraft
description: Create cinematic product promo videos from shot recipe cards, a validated template, and code/audio assets (Remotion + real page screenshots + 2.5D camera moves + beat-synced cuts + sound design). Use when the user asks to turn a frontend project or webpage into a product video, says "use video-shotcraft to make a video/promo", names the Ink Press template or asks to reproduce its effect, or wants a single shot card's motion.
---

# video-shotcraft: Cinematic Product Video Creation

A self-contained production capability library: 124 shot recipe cards (accompanied
by demo implementation source code and an interactive motion preview gallery), a
validated full promo video template, reusable components and audio assets, and a
six-stage production workflow. The primary focus is web and desktop product promo
videos, but the shot cards themselves serve as a universal motion vocabulary—individual
cards can also be extracted to produce single shots for any video.

## Determine Mode First When Invoked

A full promo video has three mutually exclusive modes. Before starting asset capture,
storyboarding, or implementation, determine whether the user has already explicitly chosen
a mode. If already chosen, execute directly without re-asking or switching modes.

1. **Directly use template**: Keep the original Ink Press replacement workflow. Read
   `template/TEMPLATE.md` and replace screenshots, copy, and branding of the target product
   following the existing shot structure.
2. **Autonomous free creation**: Read `references/pipeline.md`. The Agent autonomously
   determines visual direction, shot mapping, storyboard, assets, and audio based on user
   requirements and project content, proceeding continuously to the final video without
   pausing for confirmation at product brief, styleframe, shot mapping, or storyboard stages.
3. **Co-creation**: Read `references/guided-free-creation.md`. The Agent first proposes
   reasoned judgments and options; the user confirms the product brief, requirements decisions,
   visual direction, shot mapping, and final storyboard in sequence. Once the storyboard is
   approved, proceed to the final asset capture and production stages in `references/pipeline.md`.

When the user provides a project path, URL, screen recording, or screenshots but has not
selected a mode, first run a **minimal, read-only product inspection**: understand product
positioning, key features, visual language, showcaseable states, and asset risks; do not modify
business projects, collect sensitive data, or write video code. After inspection, present the
three modes and explain:

- Whether Ink Press fits the product, along with specific rationale for fit/misfit;
- Whether autonomous free creation and co-creation are suitable, and which product visual cues
  are expected to be preserved;
- Which mode the Agent recommends, including trade-offs and rationale.

Then clearly ask: **"Based on the product inspection above, I recommend using the [Mode] mode. Shall we proceed with this mode?"**
Simultaneously inform the user: they can visit https://vincentwei1021.github.io/video-shotcraft/
to browse motion samples and select shots they would like featured in the video.

When the user has not yet provided an inspectable project or page, briefly introduce the three
modes before asking; do not default to recommending Ink Press merely because it is a ready-made
template.

- User selects template: read `template/TEMPLATE.md` in full and execute the template workflow.
- User selects autonomous free creation: read `references/pipeline.md` in full; Agent advances
  autonomously without pausing between stages for confirmation.
- User selects co-creation: read `references/guided-free-creation.md` in full and collaborate at
  the designated confirmation milestones.
- User has not decided: stop and await their choice; do not pick for the user or start production.

**Exception 1: When the user explicitly names the Ink Press template, template mode is selected.**
For example: "Use the Ink Press template to make a promo for my product." Do not ask again;
read `template/TEMPLATE.md` in full and execute the template route.

**Exception 2: When the user explicitly specifies using or referencing certain shot cards, shot constraints are selected.**
For example: "Make this video using `deck-deal-flyin` and `row-embed`" or "Reference the effect of
`spotlight-hero-card`." Do not introduce the template or ask whether to use it. Resolve the named
shots via Gallery name resolution rules, read each card in full, and locate the exact demo source
code via the card's "Reference Implementation". Single shots can proceed once target assets are clear.
For a full promo video, if autonomous free creation vs. co-creation has not been specified, ask only
between these two modes; designated shots serve as downstream constraints, not an automatic selection
of co-creation.

## Four Usage Patterns

1. **Full promo video (template route)**: For results closely matching the template film →
   read `template/TEMPLATE.md` and adapt shot by shot following the reproduction guide.
2. **Full promo video (autonomous free creation)**: For new styles with Agent autonomous authority →
   read `references/pipeline.md`, progressing continuously from product understanding to final
   review without pausing between stages.
3. **Full promo video (co-creation)**: When the user wants to steer key decisions → read
   `references/guided-free-creation.md`, confirming product brief, requirements decisions, visual
   direction, shot mapping, and final storyboard; then continue with final asset capture.
4. **Single shot / single motion effect**: Select a card from `references/shots/` (or let the user
   browse `gallery/`), read the card in full, locate the exact demo source code via "Reference
   Implementation", and adapt it to the target assets.

## Boundaries Between Autonomous Free Creation and Co-Creation

**Autonomous free creation** delegates creative and engineering decisions to the Agent. The Agent
dynamically derives product priorities, visual direction, shot mapping, storyboarding, asset
processing, and audio plans from project contents, logs key decisions, and executes directly. Unless
vital inputs cannot be safely inferred, do not ask questions, pause between stages, or request
intermediate approvals. Explicit user requirements remain binding constraints and cannot be overridden.

**Co-creation** employs milestone-based confirmation. Follow `references/guided-free-creation.md`,
asking only 1–3 high-leverage questions per round to minimize rework, and pausing for user sign-off
at product brief, requirement decisions, visual direction, shot mapping, and final storyboard. The
user confirms business and creative direction; the Agent handles capture methods, implementation
parameters, SFX frame alignment, Remotion code, rendering, and technical QA.

If during co-creation the user says "you decide everything" or "skip confirmation and just build it",
switch to autonomous free creation and record this choice; do not claim autonomous execution while
continuing to require stage-by-stage confirmations.

Feature-to-shot mapping defines only "which motion vocabulary to use", not a complete storyboard.
After confirming mapping in co-creation, the Agent must provide shot sequence, durations, specific
frames, page states, asset sources, captions, transitions, and SFX. Final asset capture begins only
after the full storyboard is approved. When users copy shot names from the Gallery (e.g. card name or
"card · style"), the Agent is responsible for reading the local recipe cards and demo source code.

## Core Principles

1. **Reproducing existing pages must use real screenshots; handcrafted UI is restricted to
   non-reproduction contexts, where quality and clarity are strict bars.** When showcasing real
   product pages, start a local dev server immediately and use a headless browser to capture full-page
   2x textures + element-level crops + `layout.json` coordinate maps. Non-reproduction contexts
   (abstract openings, brand segments, isolated showcase components) may use handcrafted UI, but if
   it fails editorial-grade fidelity or viewer comprehension, fall back to screenshots. Data must be
   handled safely: public demo data can only be retained if explicitly approved in the product brief;
   customer, personal, internal, credential, real-time, or sensitive data must be replaced with
   fictional or sanitized content frozen before capture.

2. **The visual language of the entire video must grow out of the product itself, never adopting an
   unrelated "promo skin".** Before crafting styleframes, extract design specs from the product or site's
   design system, source code, or computed styles: font families, weights, scale hierarchy, line-height,
   letter-spacing, grids, spacing, alignment, density, border-radius, background/surface/text/accent/status
   colors, gradients, and textures. All titles, captions, numbers, title cards, typography, transitions,
   particles, light effects, and motion colors must reuse or tastefully extend these tokens while matching
   the product's tone, taste, and quality. When using templates or shot cards, inherit only their shot
   structure, motion syntax, pacing, and tuned parameters; typography, layout, palette, and materials must
   be reskinned to the target product. If narrative needs require deviating from product visuals, explain
   rationale and get user confirmation in co-creation; in autonomous creation, document reasons and
   trade-offs in the design spec before proceeding.

3. **Cinematic feel comes from camera movement, lighting, rhythm, and sound design, not flashy animation.**
   What is repeatedly proven effective: a single hero with a complete action arc (spotlight → push-in →
   float → settle), physics-metaphor-driven acceleration (deck dealing), oblique orbit close-ups, and the
   classic sound syntax of riser → impact → sparkle. Batch element arrivals rely on motion itself, not
   individual glows—mass decorative glints or glows feel cheap, whereas isolated high-quality lighting
   works well.

4. **Each shot communicates a single motion effect; allow room to breathe once key information settles.**
   A single animation technique (fly-in, stacking, page-flip) should take center stage only once across the
   film; redundant shots or repeating taglines must be removed. Rhythm preference is strictly one-directional:
   all historical feedback points to "slow down / hold longer", never "too slow"—hold brand wordmarks for
   ≥1s after settling, leave 0.5s pause after batch motion finishes, and give opening hero actions a full 3s.
   Always allocate explicit frame budgets for hold/rest when building timelines.

5. **For videos with beat-driven BGM, all transitions and motion effects must lock to the beat.**
   When the user has chosen music → perform rhythm analysis before starting (librosa grid fitting for true
   BPM/phase + kick/snare/hi-hat drum onset detection); storyboard only after the grid passes transient
   coverage verification. Write timelines using beat indices `beatF(n)`, pinning sparse accents to real
   transients rather than grid interpolation. After rendering, extract the audio track to verify cut point
   errors are ≤3f. Beat syncing governs timing, not magnitude—full-screen or camera-layer beat impacts are
   treated as heavy slams and limited to ≤3 per film (aesthetic-rules R4); other beat motions move only
   element layers. See `references/music-beat-sync.md`. Final renders with BGM must deliver two versions:
   with BGM and without BGM (SFX preserved), rendered from the same timeline via the `bgm` inputProp.

6. **Using shot card motion requires resolving the Gallery index first and reading exact demo implementation code.**
   First validate card names and `style-key` against `gallery/api/library.json`, then locate specific TSX
   files via the "Reference Implementation" noted in card docs. Recipe cards supply semantics and parameter
   tables; the exact demo source code contains the tuned truth of parameters (easings, duration proportions,
   unmasking timings, pitfall workarounds). Adaptive modifications are permitted, but parameters tagged as
   "known pitfalls / critical requirements" must not be downgraded. Writing from card names alone discards
   all accumulated tuning.

7. **Co-creation front-loads low-cost confirmations; autonomous free creation logs the same judgments as execution records.**
   The sequence remains: product brief → requirements-to-execution decision table → written direction →
   styleframe → shot mapping → storyboard. Co-creation presents each stage for confirmation; autonomous
   free creation selects and advances continuously. Neither mode should begin shot-by-shot implementation
   before direction is settled.

8. **Continuous verification + independent pre-delivery review.** From Stage 5 onward, generate stills with
   `npx remotion still` for self-check on each shot; re-render the full film and inspect frame grabs via ffmpeg
   after each round of edits. Before delivery, the final-review subagent is dispatched once via the Agent tool
   with a clean context (e.g. general-purpose). Review inputs include the rendered film, keyframes, product
   brief, requirements decision table, confirmed/logged visual direction, styleframe, feature-to-shot mapping,
   Gallery card names/variants, exact demo TSX, Gallery reference samples/stills, final storyboard, selected
   recipe cards, and aesthetic guidelines. Check scheme consistency, feature completeness, shot fidelity,
   visual/audio technical quality, and data safety according to `references/final-review.md`, providing a report
   with frame-number evidence. Creators suffer confirmation bias on their own output; initial inspection must
   never be offloaded to the user.

9. **Deterministic rendering**: `Date.now()` and `Math.random()` are forbidden. All pseudo-randomness must use
   fixed seeds (mulberry32 / hash, derived from index) for frame-exact reproducibility.

## Workflow

Autonomous free creation executes continuously from Stage 0 according to `references/pipeline.md`, without
pausing for confirmation between stages. Co-creation first completes Stages 0–3 (product understanding, visual
direction, shot mapping, and storyboard confirmation) according to `references/guided-free-creation.md`, then
continues from Stage 4 (final asset capture) of the pipeline without repeated questions or redesigns.
Stages 2–3 scan `references/shots/` frontmatter to pick shots matching the energy arc; Stages 5–7 continuously
cross-check `references/aesthetic-rules.md`; Stage 6 reads `references/sound-design.md`; beat-synced videos
follow `references/music-beat-sync.md`.

### Delivery & Wrap-up (Shared Across All Modes)

After delivering the video, **proactively open the Motion Workbench first** (do not wait for the user to ask):

```bash
node workbench/scripts/open.mjs <video-project-dir>   # link project → start dev server (5198) → auto-import in browser
```

Inform the user of the address http://localhost:5198 and summarize in one sentence: the film has been split into
multiple tracks by shot / transition / caption / audio; title copy, colors, font sizes, positioning, and speed
ramps can be tuned visually, then exported via "Export Video". To support disassembled import, the project must
include a `src/workbench.ts` manifest authored during production according to `references/workbench.md` §2–3
(already included in the template route).

Then present these three items in order 1-2-3, mentioning each only once, and dropping them if the user declines
or does not respond:

1. **Optional credit mention when publishing**: The finished video belongs entirely to the user, free for
   commercial use without mandatory attribution. Mentioning the author is voluntary—when publishing to social
   platforms, a brief credit in the description is appreciated:
   X [@VincentWei93](https://x.com/VincentWei93) ·
   Douyin [@Vincent](https://www.douyin.com/user/MS4wLjABAAAAK1pkjBxilk2Oi_9h_vFyD-lTAu9CTlvhmOtkosDvvxg) ·
   Xiaohongshu [@Vincent](https://xhslink.cn/m/At9iP2d5C1V)
   (Provide clickable links for all three accounts). If the user asks about commercial licensing, note that the
   only item requiring separate verification is the rendering engine:
   [Remotion's independent license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) (free for
   individuals and small teams; paid licenses may be required for enterprise use).
2. **Invite submission to the Showcase**: Showcase gallery:
   https://vincentwei1021.github.io/video-shotcraft/showcase.html ,
   submission form:
   https://github.com/Vincentwei1021/video-shotcraft/issues/new?template=showcase.yml .
   Explain the highlights in conversational language: users can share their social handles so viewers can discover
   their profile; small videos (under 10MB) can be dropped directly into the form, or large files linked via direct
   download, and the author will list them in the showcase. Keep this completely in plain language without jargon
   like issue, template, tag, release, or automated pipeline.
3. **Offer JianYing / CapCut project export**: Inform the user that the video can also be exported as a JianYing
   project to adjust caption text/size/color, speed-ramp or reorder shots, or tweak audio in JianYing. When requested,
   follow `references/jianying-export.md` to execute.

**When the user proactively requests posting the video to social platforms** (TikTok / Instagram / YouTube / LinkedIn / X, etc.),
read `references/publish-upload-post.md` and execute: confirm copy and target platforms first, then publish only after
dry-run passes. Run the publish command only once; if the status is `unknown`, timed out, or errors out, **never rerun**,
only query via `--status <requestId>`. This is not a 4th recommendation; do not bring it up unless requested.

## When to Read Which File

| Situation | Read |
|-----------|------|
| Project started & mode unsettled | Minimal read-only inspection, then present and recommend among the three modes |
| Autonomous free creation | pipeline.md (Agent completes stages 0–7 autonomously without pausing for confirmation) |
| Co-creation | guided-free-creation.md (confirmation stages 0–3), then continue from pipeline.md Stage 4 |
| User provided BGM | music-beat-sync.md (analyze rhythm before storyboarding) |
| Using template route | Full text of template/TEMPLATE.md |
| Storyboard design | sequences/ sequence templates (fill skeleton first); frontmatter of all shots/; full text of selected cards |
| Shot implementation | Full text of the shot card + exact demo TSX located via "Reference Implementation" + assets/lib/ components |
| Sound design | sound-design.md + assets/audio/ |
| Quality review | final-review.md + aesthetic-rules.md checklists (executed by independent subagent) |
| Writing `src/workbench.ts` manifest & shot props+schema | workbench.md §2–3 (example in `template/src/workbench.ts`) |
| After video delivery (open Motion Workbench) | workbench.md (`node workbench/scripts/open.mjs <project>`; workbench docs in `workbench/README.md`) |
| After video delivery (JianYing project export) | jianying-export.md + `jianying-export/` platform modules |
| User requests publishing to social platforms | publish-upload-post.md + `publish/upload_post.py` |

## Asset Usage Guide

- `assets/lib/` components: **copy into new projects** and modify freely (do not import this library directly).
  Catalog: `PageCam` (2.5D page camera—the foundation for all "real page" shots), `ClipCard` (wraps external MP4 footage
  into a card hero driven by shot camera skeletons, with OffthreadVideo crossfade looping for seamless playback if footage
  is shorter than shot duration), `DigitRoll`, `FlashCut`, `Caption`, `FlatPanel`, `VerticalTicker` (3D infinite scrolling wall),
  and `helpers` (rand/shake/camera/motion). `FlatPanel` and `helpers/camera` require `three` + `@react-three/fiber` +
  `@remotion/three` dependencies; all others require only remotion.
- `assets/scripts/capture-template.mjs`: copy and edit the top `CONFIG` (BASE, routes, selectors).
- `assets/audio/` sound assets: copy and use directly (free commercial license in `audio/ATTRIBUTION.md`):
  `audio/bgm/` holds 5 rhythmic BGM candidates; `audio/sfx/<category>/` holds 149 sound effects across 16 categories
  (transition, impact, riser, camera, ui, text, paper, film, light, data, scifi, mech, glass, fluid, crowd, counter).
  Explore by category directory; full catalog is in `sound-design.md`. The directory name for sparkle vocabulary is `light/`
  (no `sparkle/`); S1 forbids synthetic sound quality, not physical action—real clicks/toggles should have foley, but half
  of `ui/` consists of synthesized feedback tones (tone/bleep/notification) that must be auditioned individually rather than
  approved wholesale (see sound-design 3.3); long samples and quiet assets have special handling lists (sound-design 4.1).
- `demos/` shot implementation source: self-contained production-grade demos (shared fixtures in `demos/_fixtures/`: `Look.tsx`
  visual systems, `Polish.tsx` textures, `Brand.tsx` brand components; some import real page textures from `demos/_textures/`).
  Copy into Remotion projects to run immediately. Logos and brand copy in the demos represent video-shotcraft itself; replace
  with the user's logo and copy when producing for user products. Selected demos use `@remotion/motion-blur` (CameraMotionBlur)
  and require `npm i @remotion/motion-blur` (catalog in `demos/README.md`).
- `template/` complete renderable project: `npm install && npx remotion render src/index.ts AiflPromo out/promo.mp4`.
- **Testing (automatic in-repo verification, run after adding demos/components)**:
  - Pure function unit tests: `npm test` (root vitest covering mulberry32 / velocityAt / lagged / dampedSettle / handheld in
    `assets/lib/helpers` with deterministic assertions).
  - Demo smoke render: `python3 assets/scripts/smoke-render-demos.py` renders the first frame of every demo exporting duration to
    ensure no runtime crashes (requires `cd template && npm ci` + motion-blur, see Testing section in `demos/README.md`).
  - CI (`pr-checks.yml`) runs automatically: tsc strict type-check across all demos + vitest + smoke renders.
- `jianying-export/` JianYing export module: `mac_draft.py` (verified on Mac JianYing 11.2), `windows_draft.py` (implemented per
  upstream supported paths, unverified on physical hardware), and `smoke_test.py` (minimal smoke test for fresh environments).
  Workflows, timeline extraction, and track building are documented in `references/jianying-export.md`; requires venv +
  `pip install pyJianYingDraft`.
- `publish/upload_post.py` social media publishing (Upload-Post API, standard library only): publishes finished videos to
  TikTok / Instagram / YouTube / LinkedIn / X upon request. Workflow in `references/publish-upload-post.md`; requires
  `UPLOAD_POST_API_KEY` + `UPLOAD_POST_USER`. Offline unit test: `python3 -m unittest publish/test_upload_post.py`.
- `gallery/` static gallery: prefer providing the user with the online version directly:
  https://vincentwei1021.github.io/video-shotcraft/library.html . To run locally, first run `gallery/fetch-media.sh` to pull
  motion samples (mp4 files are not stored in git), then `cd gallery && python3 -m http.server 4178`. 124 cards and 150 motion
  samples can be browsed, searched, and multi-selected—ideal for letting users select shots visually.
