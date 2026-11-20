# Motion Workbench: Visual Fine-Tuning After Video Delivery

`workbench/` is an in-browser timeline editor (multi-track timeline + asset library + inspector panel + Remotion live preview + one-click export), ported from sister project video-talkcraft's `workbench/`.
After rendering the final video, **proactively open the workbench** so the user can adjust shots, extend pauses, edit title card copy, swap sound effects, or adjust pacing directly in the browser without touching TSX code, and export the updated MP4 directly.

**Trigger condition**: After delivering the final video in any mode, run the command below to launch the workbench and provide the local URL to the user, then proceed with the 1-2-3 delivery wrap-up steps (see `SKILL.md`). Do not wait for the user to ask.

```bash
# Execute in skill root; <project_dir> = directory containing package.json / remotion.config.ts
node workbench/scripts/open.mjs <project_dir>
# -> symlinks project src/ and public/ -> generates index -> launches dev server (port 5198) -> opens browser and automatically imports project
```

First run automatically triggers `npm install` (one-off, ~1 minute). The dev server runs in the background; stop via `kill $(cat workbench/.dev.pid)`.
Ports for the two sister skills are decoupled (talkcraft 5199 / shotcraft 5198) and can run simultaneously.

## 1. Three Tiers of Editability: What Can Be Changed & Code Requirements

The workbench decomposes a video into clips (Project → Track → Clip), with three tiers of editability per clip:

| Tier | What Users Can Edit | Motion Code Requirements |
|---|---|---|
| **Time & Layer** (Available on all clips) | Start / Duration (holds last frame if extended) / Speed 0.25×–4× / In-point trimming / Opacity / Scale / Position / Track reordering / Hide layer | Components must be pure functions of `useCurrentFrame()`, all tweens clamped, no `Date.now` / `Math.random` — guaranteed by Skill Iron Law #9. **Existing demos (150 of 152 automatically supported, see §4) and all finished shots can be placed on tracks without code modifications.** |
| **Content & Style** (Inspector Panel) | Copy / Colors / Font size / Position / Toggles / Enums visually adjusted per item | Components expose contextual parameters as **props with default values** and provide a `schema` (field list, see §3). In demos, top-level `CONFIG` constants remain read-only unless refactored — time/layer adjustments only. |
| **Decomposed Import** (One-click multi-track splitting) | Each shot / transition / caption / SFX becomes an independent clip to move, delete, or duplicate | Final project provides a `src/workbench.ts` manifest (§2), with timelines sharing the **single source of truth** with Main.tsx; importing and exporting without changes reproduces the exact original render. |

This maps directly to talkcraft's design: talkcraft duplicated 79 template cards into `gen/*.tsx` (CONFIG → props + schema, with rhythm invariants remaining FIXED), linking final videos via `@kbsrc` and splitting by `SHOTS`/`SFX_CUES`/`WIPE_TIMES` tables.
In shotcraft: all 150 demo components are **connected as-is** (avoiding duplicate maintenance of parameterized copies), and shot-level editability in final projects is declared via **manifest schemas** (§2). Therefore, whether future videos support per-property visual tuning depends on authoring shot components per §3 during production.

## 2. Project Integration Manifest: `src/workbench.ts`

Export a `WORKBENCH` constant with the following structure (TypeScript types located in `workbench/src/cards/manifest.ts`; projects do not need to import types, structural compatibility suffices):

```ts
export const WORKBENCH = {
  name: 'Ink Press · AIFL promo',
  fps: 30, width: 1920, height: 1080,
  total: AIFL_TOTAL,                 // Total frames of final video
  background: '#f2eee6',             // Outermost AbsoluteFill background color in Main
  revision: undefined,               // Optional revision tag; defaults to content hash
  shots: [                           // Shots: from/duration match <Sequence> directly (absolute frames)
    { id: 'morning', label: 'S1 Ink Line Open', from: 0, duration: 220, component: SceneOpen },
    { id: 'card1', label: 'Title Card 1', from: 220, duration: 55,
      component: TitleCardUnit,                     // Prop-consuming component
      props: { text: 'All your team’s research, *one* place to go.' },  // Actual value in render
      schema: [{ type: 'textarea', key: 'text', label: 'Copy', default: '' }],
      durationProp: 'duration',                     // Injects clip duration into this prop (fade-out tracks duration)
      cardId: 'title-card', cardName: 'Title Card' }, // 4 title cards share 1 card definition
    // ...
  ],
  transitions: [...],                // Transition layers (flash cut / light beam), same structure
  captions: [...],                   // Captions / voiceover overlays
  overlays: [...],                   // Persistent overlays across video (grid / vignette)
  sfx: SFX.map(s => ({ from: s.from, duration: 90, src: `audio/${s.src}`, volume: s.volume })),
  bgm: [{ from: 0, duration: TOTAL, src: 'audio/bgm.mp3', volume: 0.34 }],
  order: ['transitions', 'captions', 'overlays'],   // Layer z-index order (top -> bottom)
  original: AiflMain,                // Original composition for parity comparison
};
```

**Exemplary Parameterization**: In the reference template, all six scenes + title cards + lower-thirds export `*_DEFAULTS` (copy, font size, palette) and read them as defaulted props. The manifest schema directly references these objects: modifying values in the inspector updates the screen immediately, while easing curves, key timings, and camera paths remain locked. Top-level constants (`CONFIG` / constants) in demos can be exposed similarly via `DEFAULTS + Partial<typeof DEFAULTS>`.

**Single Source of Truth**: Every table in the manifest is imported directly from `Main.tsx` (`SHOTS` / `CAPTIONS` / `SFX` / title card copy), rather than maintained redundantly. Reference: `template/src/workbench.ts` + `template/src/aifl/Main.tsx` (all data exported, guaranteeing parity).

**Version Check**: When opening with `?import=project`, re-importing occurs only if stored `source` differs from `manifestKey(manifest)`. Key = name + total frames + `revision` (or content hash of schedule/labels/props/SFX). Modifying shot placements, copy, audio, or components registers as a new revision; the previous state is pushed to the undo stack (accessible via Cmd+Z).

**Grouping Rules**: Units with the same `cardId` (or component reference) share a single "Project Unit Card" in the library, allowing multiple instances to be placed on tracks. `label` is the display name on the track. Card ID is `proj:<kind>:<cardId|firstUnitId>`. If a collision occurs, later groups append `~2` with a console warning.

**Asset Paths**: Paths like `sfx[].src` are always relative to project `public/` (the workbench symlinks project `public/*` into its own `public/`). `*word*` markers in copy follow the Ink Press emphasis DSL (`parseWords`); other projects may define custom DSLs. Any string, number, or boolean prop can enter the inspector panel.

## 3. Authoring Shot Components for Future Editability

When implementing shots in pipeline Stage 5:

1. **Contextual parameters → props (with defaults)**: Copy, colors, font sizes, positions, toggles, data arrays (multiline DSL). **Keep rhythm invariants constant** (spring overshoot, stagger gaps, easing curves, camera paths) — these define motion quality, and exposing them invites degradation.
2. **Utilize `duration`/`dur` props**: Fade-outs and exits must calculate dynamically from duration. Declare `durationProp` in the manifest so extending a clip moves the exit animation rather than freezing prematurely.
3. **Maintain a single timeline source**: `SHOTS` in `timeline.ts`/`Main.tsx` is the sole source of truth; derive SFX cues, captions, and transition points from it and export them.
4. **Pure functions and determinism**: Do not assume absolute durations via `useVideoConfig().durationInFrames`. Normalized time hooks (`useT()`) are an exception and correctly handled by the workbench (extending clip slows motion proportionally).
5. Run `npm run parity` (§5) before final delivery to ensure lossless decomposition.
6. **Ensure live preview performance**: The Remotion Player composes in real-time without awaiting offline rasterization. Giant procedural gradients (thousands of pixels) or `backdrop-filter` in 3D layers with animated zoom can cause rendering drops in Chrome. Isolate decorative heavy repaints using `getRemotionEnvironment().isRendering`: use full fidelity during export, and lighter solid fallbacks during preview (see `SceneFlyIn.tsx` `METAL_PREVIEW`). Parity tests compare render output, ensuring validity.

Supported schema field types: `text` / `textarea` / `number` (min/max/step/unit) / `slider` / `color` / `select` (options) / `boolean`, defined in `workbench/src/cards/types.ts`.

## 4. Motion Library (demos/) in the Workbench

`scripts/gen-index.mjs` scans `demos/<category>/<card>/<component>.tsx`. Any component exporting `<Component>: React.FC` without mandatory props is indexed as a card (150 of 152 demos connected: `ClipCardLooping` requires external mp4 video and `page-waterfall-wall/VerticalTicker` is a helper component; both skipped). Metadata (name, category, summary) is pulled from `gallery/api/library.json` + `translations.js`. Previews use `gallery/media/<style>.mp4` (or fall back to live Player loops).
Duration resolution chain: demo exported `*_DURATION|*_DUR` → card markdown `duration:` `NNNf` → internal `const *DUR*` → default 150f. Stored in `DEMO_MODULES[].durationSource`.
Demos default to empty schemas (time/layer editable, internal properties read-only).

The workbench includes 4 built-in parameterized native cards: Generic Text, Ink Press Title Card, Lower-Third Subtitle, and Warm White Flash Transition (`workbench/src/cards/inkpress/`).

## 5. Export, Studio, and Lossless Parity Verification

- **Export Final Video**: Top bar "Export Video" launches Remotion CLI within the dev server to render the project into `workbench/exports/`. Before rendering, `public/` is dereferenced and copied to `.render-public/` (Remotion static server restricts symlinks). Export config matches template: JPEG frames, ANGLE GL, concurrency 4.
- **Remotion Studio**: `cd workbench && npm run studio` provides compositions for `Main`, `ProjImported`, `ProjOriginal`, plus dedicated compositions per card (schemas converted to Zod for official Inspector controls).
- **Parity Verification**: `npm run parity -- --frames 150,240,470,1000` renders matching frames from `ProjImported` and `ProjOriginal` for pixel-by-pixel diffing (requires Python 3 + Pillow). Pixel difference < 0.1% passes. Exit codes: 0 match, 1 diff, 2 indeterminate (missing Pillow / unexecuted). Run after modifying manifest or `Main.tsx` timelines.

## 6. Known Boundaries

- Clips may overlap on the same track (layer hierarchy represented across multi-track). Speed adjustments use linear remapping (no curve remapping).
- Motion library cards are timed at 30 fps (`CARD_FPS`), while project unit cards adopt project fps (`CardDef.sourceFps`). When dragging onto mismatched fps projects, `clipDefaultsFor` scales duration and adjusts playback speed inversely; media cards (`timing: "realtime"`) scale duration without altering playback rate. Freeze does not alter `useVideoConfig().fps`; cards utilizing seconds-based springs (`spring({fps})`) may experience rhythm drift in non-30fps projects (noted in inspector; project units remain unaffected).
- `open.mjs` only restarts dev servers it initiated (`.dev.pid` verified via process command line). If the port is occupied by an external server, it exits with an error because `@proj` Vite aliases are locked at launch.
- Audio clips clamp to total project duration upon import.
- Grayscale textures required by demo cards (`textures/live/*.png`): uses project's `public/textures` if available, otherwise symlinks `demos/_textures`.
- Project `src/` is bundled into the workbench via symlink; `react`/`remotion` resolve to workbench node_modules (Remotion 4.0.484 / React 19). If the project uses packages beyond `@remotion/three`, `three`, `@remotion/motion-blur`, or `@remotion/google-fonts`, install matching versions in `workbench/`.
- Division of labor with JianYing export (`jianying-export.md`): JianYing serves users editing in external NLE suites; the Workbench serves users seeking browser-based adjustments and parameterized shot tuning without opening a heavy NLE.
