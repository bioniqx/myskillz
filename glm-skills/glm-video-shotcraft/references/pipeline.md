# pipeline — 8-Stage Production Pipeline

Eight distinct stages, resolving directional decisions before entering expensive per-shot production.
Empirical details are derived from post-mortems of delivered promotional videos (reference template in `template/`).

## Table of Contents

- Stage 0: Product Understanding & Execution Constraints
- Stage 1: Visual Direction & Styleframes
- Stage 2: Feature-to-Shot Mapping
- Stage 3: Storyboarding & Production Gate
- Stage 4: Final Asset Capture
- Stage 5: Shot-by-Shot Implementation
- Stage 6: Sound Design
- Stage 7: Independent Final Review & Delivery

This document serves as the complete pipeline for **Autonomous Free Creation**: assessments in Stages 0–3 are autonomously conducted and documented by the Agent based on project content without awaiting user confirmation at each step, transitioning continuously into Stages 4–7. Any explicit user constraints regarding purpose, audience, features, aspect ratio, audio, or data policies remain hard requirements.

Directly using the Ink Press template bypasses this pipeline; follow the replacement procedure in `template/TEMPLATE.md`. The template documentation borrows only the asset capture methodology from Stage 4.

**When entering this pipeline from `guided-free-creation.md` in Co-Creation mode, do not restart from the beginning.** That workflow has already completed and signed off Stages 0–3; proceed directly to Stage 4 (Final Asset Capture) without re-prompting or redesigning.

Two core execution principles:

1. **The final design spec and storyboard together form the Production Gate.** The storyboard is embedded directly within the design spec (the 4 columns: `| # | Time | Shot | Key Motion |`). Production sign-off locks established business and creative decisions, resolving only unresolved implementation details.
2. **Quality verification is continuous throughout, not deferred to the end.** Each shot implementation concludes with visual inspection of static keyframes via `npx remotion still` (archived by version in `out/qa/`), and full renders are generated after each feedback cycle. Stage 7 formalizes this continuous discipline into an official checklist report against `aesthetic-rules.md`.

Sequence flexibility note: Styleframes may initially use HTML and minimal preflight assets. Critically, **final asset capture prior to shot implementation must be guided strictly by the approved storyboard** — discovering asset misalignments during shot development renders entire scenes obsolete.

---

## Stage 0: Product Understanding & Execution Constraints

Before authoring video code or capturing final assets, conduct a read-only audit of project positioning, core features, UI states, visual design tokens, startup procedures, and data risks. Generate a Product Brief and Requirements-to-Execution Decision Table based on project evidence and user inputs, establishing concrete impacts on video purpose, audience, core value proposition, mandatory features, duration / aspect ratio / language, audio, and data compliance.

In Autonomous Free Creation, the Agent makes dynamic assessments for unspecified items and logs them in the design spec without pausing for user confirmation. If the user specified a soundtrack, analyze rhythm first per `references/music-beat-sync.md`; otherwise, the Agent selects music in Stage 6 based on product and distribution context. Public demo data may be retained once verified as public; customer, personal, internal, credential, realtime, or sensitive data must be fictionalized, desensitized, or frozen.

**Artifacts**: Product Brief; Requirements-to-Execution Decision Table; Explicit data and audio constraints.

---

## Stage 1: Visual Direction & Styleframes

**Objective**: Lock down color palette, typography, lighting atmosphere, and motion personality using minimal-cost artifacts, resolving all directional debates before writing a single line of Remotion code.

**Action Steps**:

1. Generate up to 3 textual visual directions tailored to the target project. Attach a set of **motion personality tokens** to each direction (derived via the "Brand -> Motion Parameters" matrix below), without treating Ink Press as an automatic default.
2. The Agent autonomously selects the most appropriate direction based on product visuals, purpose, and audience, documenting choices and trade-offs in the design spec without pausing for user selection.
3. For the chosen direction, **write zero Remotion code and render zero video**; build a standalone HTML/CSS styleframe page containing 2–3 static 1920×1080 keyframes.
4. Capture screenshots via Playwright/Puppeteer to verify typography, color palette, materials, composition, lighting, and information density. Evaluate easing and camera velocities via motion tokens, Gallery samples, or brief motion tests. If strict brand guidelines or explicit reference videos exist, styleframes may be skipped provided the rationale is documented.
5. If the user provided a reference video: download and extract keyframes with FFmpeg (`select=eq(n,...)` extracting ~100 frames; `tile=4x5` building contact sheets). Perform a motion breakdown for each animation, transition, and visual effect, logging a 3-column table (`Technique | Reference Implementation | Trade-Off`) in the spec — **adapt selectively without forcing mismatched techniques**. Reference images follow the same principle: they capture the mood of a specific shot type, not a global style mandate.

**Brand -> Motion Parameter Derivation**. Do not pick easing and durations intuitively. Map the brand across two axes, starting from the closest preset:

- **Energy Axis**: Low (steady / premium / institutional) <-> High (athletic / startup / entertainment) — dictates durations, overshoots, and squash amplitude;
- **Tone Axis**: Serious (finance / healthcare / enterprise) <-> Playful (consumer / social / children) — dictates path curvature and secondary animation complexity. Product visual design provides direct evidence (sharp geometric forms -> engineering precision; rounded corners + bright accents -> soft and lively); explicit user brand statements supersede visual inferences.

| Preset (Category) | Primary Duration @30fps | Entrance Easing | Overshoot | Squash |
|---|---|---|---|---|
| Professional & Trustworthy (fintech / enterprise / B2B) | ~21f | bezier(0, 0, 0.2, 1) | 1.0 (no bounce) | 0 |
| Refined & Premium (luxury / fashion) | ~48f | bezier(0.4, 0, 0.6, 1) | ≤ 1.02 | 0 |
| Dynamic & Bold (sports / gaming / startup) | ~18f | bezier(0.16, 1, 0.3, 1) | 1.12 | 0.25 |
| Playful & Delightful (consumer / social) | ~27f | bezier(0.34, 1.56, 0.64, 1) | 1.08 | 0.18 |
| Calm & Caring (healthcare / education) | ~42f | ease-in-out symmetric | 1.0 | ≤ 0.04 |
| Approachable & Friendly (SMB / community) | ~26f | bezier(0.25, 0.46, 0.45, 0.94) | 1.04 | 0.08 |

Usage: Select preset -> fine-tune along axes -> record tokens in design spec. Self-check:
① Describe final motion in three words: do they align with brand adjectives?
② The same token set must govern entrances, transitions, and holding pauses simultaneously — a single brand voice throughout; mixing divergent token sets feels disjointed.
If presets conflict with codified case-law precedents, precedents take precedence: landing moments requiring bounce must have y1 > 1; "Professional Trustworthy no bounce" applies to non-landing fades and slides.

**Artifacts**: Styleframes for the selected direction; Palette / Typography / Lighting tokens + Motion personality tokens; (if reference video provided) Motion breakdown table.

**Common Pitfalls**:
- Rendering video proposals for style exploration: overly expensive and creates psychological resistance to directional pivots. Static keyframes suffice.
- Applying reference-driven moves globally: evaluate camera tilts shot-by-shot (dense list and grid shots remain eye-level for legibility).

---

## Stage 2: Feature-to-Shot Mapping

**Objective**: Select the appropriate motion grammar for each mandatory feature, without prematurely authoring the full storyboard.

**Action Steps**:

1. **Compile product feature list and map 1:1 to shots**. Omitting core features forces rework. Each motion technique (fly-in, stacking, card-flip) stars as hero only once; visual homogenization signals rework.
2. Scan frontmatter across all cards in `references/shots/` for purpose, energy, recommended durations, constraints, and required UI states to assign primary and secondary cards per feature. The Agent autonomously decides and documents rationale.
3. Read selected cards in full, resolving exact demo TSX source paths via "Reference Implementation". New shots may be authored if no existing card fits, documenting scope and verification risks in the spec.

**Artifacts**: Feature-to-shot mapping table; selected card names, variants, demo source paths, and reference sample video locations.

---

## Stage 3: Storyboarding & Production Gate

**Objective**: Arrange mapped features and shots into a coherent sequence with a deliberate energy arc, translating it into a frame-accurate implementation plan. In Autonomous Free Creation, the Agent signs off autonomously without pausing for confirmation.

**Action Steps**:

1. Check `references/sequences/` for applicable sequence templates (e.g. `promo-energy-arc.md`); follow the filling workflow to allocate segment budgets and arrange mapped shots: low-energy opening -> alternating feature climbing and breathing pauses -> peak outro.
2. **When a BGM track is designated**: generate the musical architecture schedule first (peak energy points, breakdown beat numbers per `music-beat-sync.md` §2); anchor all shot boundaries to beat numbers, reserving peak hits for the 2–3 major slams; breakdowns naturally serve as brand breathing pauses.
3. Author the full storyboard: shot sequence, duration, feature context, specific UI states, shot cards and variants, hero actions, asset sources, captions, transitions, and SFX. Each shot focuses on a single hero movement.
4. **Reserve hold and rest frame budgets during timeline layout**: brand wordmark landing holds ≥ 1s (30f); batch motion endings rest 0.5s; opening hero movements span ≥ 3s. Rhythm adjustments are one-way: rushing invites rejection, while deliberate pacing never faces backlash.
5. The Agent validates consistency between storyboard, product brief, decision table, visual direction, and shot mapping before approving the gate. Translate the storyboard into a frame-accurate implementation schedule:
   `| shot | from | duration | content |` (or express boundaries in `beatF(n)` for rhythm-synced cuts), designating source files and verification frame numbers per shot.

**Artifacts**: Design spec (including design tokens, motion breakdown, and storyboard); Frame-accurate timeline.

**Common Pitfalls**:
- Storyboarding intuitively without checking feature lists: leads to missing features or homogeneous animations.
- Overcrowding the opening: focus on one hero element and one complete movement arc.
- Omitting rest budgets: packing motion into every frame requires sliding the entire timeline later to insert pauses.

---

## Stage 4: Final Asset Capture

**Prerequisites**: Design spec and storyboard approved at the Production Gate. In Co-Creation mode, user confirmation unlocks this gate; in Autonomous Free Creation, the Agent's consistency check serves as the gate. Preliminary screenshots used for styleframes cannot substitute for final assets.

**Objective**: Capture authentic product assets required across all storyboarded shots, including full-page textures, element cutouts, and coordinate manifests, laying the foundation for 2.5D camera moves and page-space animations.

**Action Steps**:

1. Launch target product local dev server (for desktop apps, use window capture utilities to produce the same three deliverables).
2. Copy `assets/scripts/capture-template.mjs` into the project, configure `BASE_URL` and selectors, and execute to generate the three core assets:
   - **Full-page 2× screenshots**: viewport 1920×1080, `deviceScaleFactor: 2`; settle with `document.fonts.ready` + 600ms pause, extending by 1.5–2s for realtime collaborative pages.
   - **Per-element cutouts**: capture element cutouts via semantic selectors; use transparent backgrounds for floating chips; capture empty backplates for cards flying into empty layouts.
   - **layout.json**: records bounding boxes `{x, y, w, h}` in page coordinate space and page height `pageH` per route, consumed directly by flight target coordinates, masking boundaries, and entrance zones.
3. Support incremental recaptures per page/element. Freeze, fictionalize, or desensitize live data per Stage 0 data policies before final capture.

**Artifacts**: `public/textures/` full-page plates, element cutouts, and empty backplates; `layout.json`; reproducible capture script.

**Common Pitfalls**:
- Bulk capture before storyboard sign-off: page states and asset boundaries remain uncertain, resulting in duplicated capture work.
- Hand-coding HTML replicas of existing pages: replicas must use authentic screenshots; hand-coded UI is restricted to non-replica scenes.
- Capturing dynamic data without freezing, or capturing screenshots without logging layout bounding boxes.

---

## Stage 5: Shot-by-Shot Implementation

**Prerequisites**: A runnable Remotion project (30fps, 1920×1080, `src/index.ts` registering Compositions; initialize via `npx create-video@latest` and copy `assets/lib/` components, or clone from `template/`).

**Objective**: Implement shots sequentially against the frame-accurate schedule, proving quality per shot — verification begins during development, not after completion.

**Action Steps**:

1. **Resolve Before Reading** (Mandatory rule, cannot be skipped): Validate card name and `style-key` against `gallery/api/library.json` -> read full card document -> read exact demo TSX source located via "Reference Implementation" -> copy corresponding components from `assets/lib/`. Save the local Gallery reference video path for implementation comparison and final review. Styles marked "For reference only, requires custom implementation" are not recommended by default; implement only upon explicit user request with risks logged. Styles marked "Missing preview" must not claim fidelity to dynamic samples.
   Demo source holds tuned parameters (easing, timing ratios, matte timing, pitfall evasions) — adapt screenshots, coordinates, and branding to the target product, but never downgrade parameters marked under "Known Pitfalls / Critical Vulnerabilities". Rewriting from card name semantics discards battle-tested tuning, degrading visual quality.
2. **PageCam forms the foundation for all real-page shots**: full-page texture + keyframed 2.5D camera + page-space overlay, with children positioned via page CSS pixels sharing coordinates with `layout.json`.
3. **Static Keyframe Verification (Highest frequency action)**: Designate 2 verification frame numbers per shot in the plan. Upon shot completion, run:
   `npx remotion still src/index.ts <Comp> out/qa/<name>.png --frame=<N>`
   Inspect composition, rendering artifacts, and text sharpness visually before marking complete. Archive keyframes by version in `out/qa/` for direct reference during feedback.
4. **Full Render After Each Pass**: Execute `npx remotion render src/index.ts <Comp> out/promo.mp4`, extracting verification frames via `ffmpeg -i out/promo.mp4 -vf "select=eq(n,...)"`. The operational pattern is: "render still frames for modified shots, then render full video".
5. Pixel-level inspection tools: crop and magnify text to verify sharpness, diff two frames pixel-by-pixel, and measure bounding boxes to verify composition.
6. **Deterministic Rendering Rule**: Forbid `Date.now()`, `Math.random()`, or unseeded `new Date()`. Generate pseudo-randomness via fixed-seed generators (mulberry32 / hash functions seeded from index), guaranteeing reproducible frames and zero inter-render jitter.
7. Continuously verify against `references/aesthetic-rules.md`: landing bounces require y1 > 1, highlights must clip inside border radii, and blurry 3D text points to rasterization pipelines (CSS layout `zoom` rather than transform scale) before camera adjustments.
8. Clarify ambiguous user feedback before editing; revert erroneous commits cleanly via git instead of patching over bad versions.
9. **Interface with Motion Workbench** (`references/workbench.md` §2–3): Maintain a single timeline source of truth (`SHOTS` exported from `timeline.ts` / `Main.tsx` to derive captions, SFX cues, and transitions); expose contextual parameters as defaulted props, locking rhythm invariants; import schedules into `src/workbench.ts` with `component`, `props`, and `schema`. Verify lossless export via `cd workbench && npm run parity` before delivery.

**Artifacts**: Per-shot git commits; `out/qa/` static keyframe archive; Full video MP4 render per pass; `src/workbench.ts` manifest.

**Stage Output**: Full video render + key static frames. Autonomous Free Creation proceeds without pausing for approval; integrate user feedback into subsequent passes.

**Common Pitfalls**:
- Delegating initial review to the user: never deliver without prior keyframe inspection.
- Skipping demo source code to author from scratch: ignores tuned parameters and re-triggers known bugs.
- Adding handheld camera shake to promotional tech videos.
- Broadcasting decorative glints and sweeps across element batches.
- Blurry text during 3D push-in caused by Chromium rasterization downsampling.
- Element fly-ins hovering detached without snapping into layout coordinates.

---

## Stage 6: Sound Design

**Objective**: BGM establishes the energy skeleton, SFX lock to visual keyframes on beat, and timbres embody product promotional polish rather than gaming UI feedback.

**Prerequisites (Most expensive sequencing lesson)**: **Begin only after visual timing is locked.** Any timeline adjustment invalidates the entire SFX schedule. If visuals are revised, re-verifying the full SFX keyframe schedule is mandatory.

**Action Steps** (see `references/sound-design.md`):

1. Consult `references/sound-design.md` and copy audio assets from `assets/audio/sfx/<category>/` (free commercial license; see `assets/audio/ATTRIBUTION.md`). Assets are organized into 16 categories: select category by visual action (camera -> `transition/`, landing -> `impact/`, typing -> `text/`, page flip -> `paper/`, sparkle -> **`light/`**...), then audition within that category. Notice that `sparkle` resides in `light/`.
2. **BGM**:
   - Specified by user: rhythm analysis completed in Stage 0; handle mixing here (attenuate to ~0.34 for SFX headroom, shape head/tail fades via `interpolate`).
   - Unspecified: select a driving electronic bed (tech-house tier) matching promotional keynote character rather than superficial pleasantness. Candidate tracks must be auditioned beneath rendered video; candidate tracks reside in `assets/audio/bgm/`.
   - Wrap BGM `<Audio>` tags with a boolean inputProp (`bgm`, default `true`), decoupled from SFX, ensuring twin renders (with BGM / without BGM) from the identical timeline.
3. **Select SFX Vocabulary by Genre**: camera = whoosh, landing = impact, buildup = riser, highlights = sparkle (directory: `light/`), cuts = transition; forbid gaming sound pack timbres (synth plucks, cartoon boings). Banning gaming timbres does not ban physical action foley (clicks, switches, glass breaks).
   **Audition `ui/` individually rather than granting blanket approval**: only a few files represent physical switches; over half are synthetic notification chimes (tone/bleep/notification) banned by S1 (see `sound-design.md` §3.3). `glass/` contains authentic physical break foley and is fully approved.
4. **Centralized Declarative Keyframing + Relative Offsets**: Store in a single `{ from, src, volume }[]` table, annotating each line with screen actions, wrapped with `<Sequence from={s.from}>`. **Always express `from` via relative offsets** (`SHOTS.x.from + offset` or `beatF(n)`), never bare frame numbers. Shifting shot boundaries automatically updates SFX schedules. **Samples >5s (21 in library) must explicitly declare `durationInFrames`** via Sequence boundaries to prevent audio trailing beyond action completion (§4.1).
5. Eliminate burst repetition via dual-sample alternation, stepped volume attenuation (e.g. pop burst 0.40 -> 0.25), and accelerating intervals matching animation curves.
6. Provide custom foley slots beyond generic swooshes (typing uses keyboard strokes; sequential drops use pops).
7. Practice SFX restraint in rhythm-dense cuts: percussion already provides cadence; anchor only distinct visual actions, reserving major slams for 2–3 peak moments.
8. Finale Cadence: Riser (assembly starts) -> Impact (wordmark lands, peak volume) -> Sparkle (shimmer aftermath, from `sfx/light/`).
9. **Set Volume by Measured Asset Peak**: `volume` is a multiplier, not target loudness. Assets recorded quietly (peaks < -12dB) remain buried under BGM even at `volume=1.0`. Swap for better-recorded assets in the same category, or pre-normalize before importing; apply >1 gain only when necessary, verifying peak levels on rendered output to prevent clipping (see `sound-design.md` §4.1).

**Artifacts**: Video with full audio mix; SFX keyframe table (relative offsets + source + volume + annotations); Audio assets committed with licensing documentation.

**Stage Output**: Full video render with audio mix. Autonomous Free Creation proceeds directly to Stage 7 without pausing for confirmation.

**Common Pitfalls**:
- Designing audio before visuals are locked: collateral rework cost.
- Choosing timbres by UI event semantics (synthetic confirmation chimes): genre misalignment.
- Omitting `durationInFrames` on long samples (>5s).
- Copying 0.2–0.6 volume ranges without verifying asset peak levels.
- Scattering audio intuitively without centralized tables.

---

## Stage 7: Independent Final Review & Delivery

**Objective**: Elevate continuous static-frame and full-video checks into a formal audit, validating that the final render faithfully executes the approved Product Brief, Decision Table, Visual Direction, Shot Mapping, and Storyboard, generating an itemized evaluation against final review and aesthetic rules before final delivery.

**Action Steps**:

1. Render latest cut and extract all keyframes with FFmpeg (at minimum: entrance, peak action, post-settle for each shot). For videos with BGM, render two cuts from the identical timeline: with BGM and without BGM (preserving SFX), using the `bgm` inputProp configured via `props-nobgm.json` (`{"bgm":false}`):
   `npx remotion render … --props=props-nobgm.json`
   Distinguish by filename (`promo.mp4` / `promo-nobgm.mp4`).
2. **Independent Final Review (Mandatory)**: Dispatch an independent subagent in a clean context (via the Agent tool with a brand new context, e.g. general-purpose) to conduct a third-party review. Do not provide production rationale, revision histories, or hints that it "ought to pass". Provide strictly: latest final cuts (both versions if BGM used), extracted keyframes, creation mode, Product Brief, Decision Table, visual direction / tokens, styleframes or skip justification, feature-to-shot mapping, Gallery card names and variants, corresponding `library.json` entries, exact demo TSX source, Gallery reference video or contact sheets, final storyboard, selected shot cards, `references/final-review.md`, and `references/aesthetic-rules.md`.
3. The reviewer Agent executes `final-review.md` across product goals, functional completeness, visual consistency, shot card fidelity, storyboard alignment, data safety, audio sync, and technical quality. Reviewing frame-by-frame and full video, output findings formatted as `F2 ✗ (Frame 340 missing confirmed Knowledge Graph feature)` or `Q2 ✗ (Frame 615 blurry text)`, attaching verifiable frame numbers / screenshots for every issue. Shot adaptations do not require pixel-perfect identity with Gallery samples, but must preserve action syntax, timing ratios, pitfall parameters, and requested variants.
4. Content Audit: Ask "What new information does this shot provide?"; delete redundant shots or duplicate taglines. Rewrite copy against final visuals; provide captions for animated shots, eliminating voiceless voids.
5. Audio-Visual Sync Audit: Review each SFX against video frames to verify zero desync. For rhythm cuts, run post-render retesting per `music-beat-sync.md` §5, ensuring all cut errors ≤ 3f.
6. Remediation loop: storyboard deviations return to Stage 3, visual bugs return to Stage 5, audio bugs return to Stage 6; loop until the checklist passes. Repeat dual-version rendering for the final delivery (with BGM / without BGM).

**Artifacts**: Independent Review Report (`final-review` + `aesthetic-rules` checklist + frame evidence) + Final Video Renders (with BGM / without BGM).

**Deliverables**: Review Report + Final Video Renders.

After delivery, launch the Motion Workbench via `node workbench/scripts/open.mjs <project_dir>` (the browser automatically decomposes the video into multi-track clips for visual fine-tuning and export; see `references/workbench.md`), then present the 1-2-3 delivery wrap-up steps:
① Recommend (optional) crediting the skill author with social handles;
② Invite the user to feature the final video on the showcase page (using approachable phrasing, optionally leaving their own handle);
③ Inform that the video can be exported as a JianYing project draft (execute via `references/jianying-export.md` upon request).
Exact scripts and links are provided in `SKILL.md` "Delivery Wrap-Up".

**Common Pitfalls**:
- Treating acceptance as a late-stage task: this stage merely closes the loop. Without continuous frame checks in earlier stages, accumulated bugs render the checklist ineffective.
- Superficial reports marking everything passed: users will read every word and inspect frames; attach verifiable frame numbers and screenshots to every finding.
- Production agent reviewing its own work: confirmation bias is inevitable; independent subagent review is mandatory.
- Evaluating only visual polish without checking production baselines: omitted features, visual drift, wrong shot variants, and unauthorized data constitute review failures.
