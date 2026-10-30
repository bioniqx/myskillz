# guided-free-creation — Guided Co-Creation Workflow

The Co-Creation mode is designed for scenarios where the user wishes to participate in key business and creative decisions for the product promo video. It delegates product briefing, requirements decisions, visual direction, shot mapping, and the final storyboard to the user for explicit sign-off, leaving video engineering and execution to the Agent. Autonomous Free Creation mode does not read this file and bypasses these step-by-step confirmation gates.

## Table of Contents

- Product Brief and Safe Asset Preflight
- Requirements-to-Execution Decision Table
- Visual Direction and Styleframes
- Feature-to-Shot Mapping
- Gallery Shot Name Resolution
- Storyboard Sign-Off and Production Gate

## 1. Product Brief

Begin with a read-only audit of the target project without authoring video code, modifying project files, or capturing sensitive content. Inspect the tech stack, entrypoints, start commands, routes, primary components, interactive states, APIs, UI copy, CSS visual tokens, external dependencies, and data risks. Determine which product features can be conveyed clearly through real UI states.

Output a pre-filled Product Brief table authored by the Agent. Each row must provide an initial assessment or recommendation alongside explicit justification; do not leave fields blank for the user to fill out from scratch.

```text
Current Stage: Product Understanding

| Dimension | Agent Assessment or Recommendation | Justification |
|---|---|---|
| Project Positioning |  |  |
| Target Audience |  |  |
| Video Purpose |  |  |
| Core Value Proposition |  |  |
| Mandatory Features to Showcase |  |  |
| Available Pages / UI States |  |  |
| Above-the-Fold Value Hook |  |  |
| Target Duration / Aspect Ratio / Language |  |  |
| Music / Voiceover |  |  |
| Data Compliance Policy |  |  |
| Visual Cues |  |  |

Requires Confirmation:
1. List only items that cannot be determined from existing project materials or user statements.
2. For items with clear recommendations that still require user approval, present "Recommendation + Justification" first, then formulate the targeted question.
```

Field Completion Rules:

- If determined from README, codebase, routing, page states, copy, or computed styles, fill in the assessment and evidence directly without asking;
- If reasonably inferred from project context, provide a dynamic recommendation, rationale, and specific options for user selection;
- If impossible to assess from existing materials, state "Cannot be determined from current materials" and include it in the confirmation questions below;
- Ask only 1–3 high-impact questions per turn; omit artificial "confidence score" metrics;
- Recommendations must derive directly from the target project or UI pages, avoiding generic cookie-cutter answers.

Once the user approves the brief, conduct an **initial safe asset preflight**: capture only the minimal screenshots or CSS tokens required to construct styleframes. Do not perform full cutouts, bulk exports, or final asset ingestion yet. Public demo data may be retained only if explicitly approved in the brief; customer, personal, internal, credential, realtime, or sensitive data must be replaced, desensitized, or frozen first. Avoid re-asking for clearly established information.

## 2. Requirements-to-Execution Decision Table

Consolidate confirmed user requirements, project evidence, and the Agent's execution choices into a single traceable table. This is not a static "audience -> style" mapping: every row must articulate evidence grounded in the current project and user inputs, allowing non-standard, creative recommendations.

```text
Current Stage: From Requirements to Production Decisions

| Confirmed Requirement | Project / User Evidence | Affected Execution Scope | Agent Recommendation | Needs Confirmation |
|---|---|---|---|---|
| Video Purpose |  | Narrative structure, information density, CTA |  |  |
| Target Audience & Context |  | Scenarios, language, pacing, feature priority |  |  |
| Core Proposition & Mandatory Features |  | UI states, shot selection, copy |  |  |
| Duration / Aspect Ratio / Language |  | Shot count, caption density, composition |  |  |
| Music / Voiceover |  | Rhythm, pauses, SFX headroom |  |  |
| Data Compliance Policy |  | Capture, mocking, masking, final audit |  |  |
| Visual Direction |  | Design tokens, textures, transition tone |  |  |
```

Record only rows that directly impact the current video. Keep unresolved items under "Needs Confirmation" (limiting questions to 1–3 per round); never re-prompt for previously confirmed items. All downstream visual direction, shot mapping, storyboards, asset capture, sound design, and final review must trace back to this table and remain documented in the design spec.

## 3. Visual Direction

Extract typography, color palette, border radii, information density, lighting mood, and motion personality from pages, source code, or computed styles. Confirm visual direction in two rounds:

1. Propose up to 3 textual visual directions tailored to the target project. For each direction specify: Name, one-line visual thesis, 3–5 keywords, typography / color / textures, motion personality, justification, and design trade-offs. Include Ink Press as a candidate only if the product genuinely fits editorial, paper, or narrative textures; never include it solely because it exists in the repository.
2. The user selects 1–2 shortlisted directions or delegates the decision to the Agent. Build a standalone HTML/CSS styleframe comparison page for the shortlisted directions: present 2–3 static 1920×1080 keyframes per direction (e.g. Brand Open, Core Feature, Brand Close), leveraging real product assets or extracted tokens, without writing Remotion code or rendering video.
3. Capture side-by-side styleframe screenshots using Playwright/Puppeteer to showcase typography, palette, textures, composition, lighting, and density. Obtain user approval on the final visual direction before proceeding to feature-to-shot mapping.

Styleframes validate static visual grammar; they do not independently prove easing curves, camera velocities, or rhythm, which must be judged via motion tokens and Gallery reference samples. If motion differences cannot be decided textually, generate brief motion tests. When the user provides strict brand guidelines, explicit reference videos, selects Ink Press directly, or explicitly delegates visual choice to the Agent, styleframe comparison may be skipped provided the rationale is documented.

## 4. Feature-to-Shot Mapping

List product features first, then scan frontmatter across `references/shots/` for purpose, energy, recommended durations, and constraints. Recommend primary and secondary shot choices for each mandatory feature:

| Feature | Primary Shot Card | Secondary Shot Card | Visual Intent | Required UI State |
|---|---|---|---|---|

The user may accept, substitute, remove, or authorize the Agent to select. Once mapping is settled, read the selected cards in full and locate the exact demo TSX source via the card's "Reference Implementation". New shots may be authored if no existing card fits, but scope and verification risks must be documented. Gallery styles marked "For reference only, requires custom implementation" are not recommended by default; they may be authored only upon explicit user request with risks documented in the spec.

This mapping table is not a storyboard and does not authorize production kickoff upon confirmation. It merely establishes "which feature uses which shot grammar". Proceed to Section 5 to elaborate sequence, durations, UI states, specific actions, assets, captions, transitions, and audio.

## 5. Gallery Shot Name Resolution

The Gallery (https://vincentwei1021.github.io/video-shotcraft/) serves as a visual index for browsing and selecting motion samples; all shot definitions and reference implementations reside directly in this repository. Users do not need to describe animations manually; they can copy and provide the shot name.

Process incoming shot names in this exact sequence:

1. Read `gallery/api/library.json`, validate `card-name` against `cards[].name`, and validate `style-key` against `styles[].key`; do not substitute fuzzy guesses for index validation;
2. Locate and read the full `references/shots/*.md` file using the `source` field in the index;
3. Resolve the specific style variant to the exact demo TSX file using the path in the card's "Reference Implementation"; if only a directory is listed, inspect exports, comments, and style semantics to pinpoint the file;
4. Resolve `styles[].media.url` to the reference sample video (if local MP4 is absent in `gallery/media/`, run `gallery/fetch-media.sh` or refer to the online Gallery URL); log Card Name, `style-key`, Card Document, Exact Demo TSX, and Reference Sample in the design spec;
5. If the card depends on shared components, read and copy the relevant files from `assets/lib/`;
6. Preserve tuned easing curves, timing ratios, matte timing, and "Known Pitfalls / Critical Vulnerabilities" from the demo;
7. Replace only target product screenshots, layout coordinates, UI copy, brand tokens, and necessary framing parameters.

Names copied from the Gallery generally take two forms:

```text
spotlight-hero-card
shot-transitions · whip-pan
```

- Card Name Only: Use the card's default variant; if variants diverge substantially, recommend a specific variant matching context and product personality, explaining why;
- `CardName · StyleName`: Prioritize the exact variant specified by the user; read its implementation without substituting another style;
- Non-Existent Name: Report the mismatch and provide the closest valid card name in the repository; never invent animations based on name strings;
- Marked "For reference only, requires custom implementation": Do not proactively recommend. If requested, clearly state that no reusable implementation exists, build per recipe parameters and sample video, and note risks in the spec;
- Marked "Missing preview": Source code can be read and used, but do not claim verification against dynamic samples.

Never re-implement approximate animations from card name semantics alone. Card documents provide semantics; demo source code holds parameter ground truth. After the user selects multiple shots, map them to features before generating the full storyboard.

## 6. Storyboard Sign-Off and Production Gate

Assemble confirmed features and shots into a detailed storyboard containing at least:

```text
| # | Time / Frames | Feature Context | Shot Card | Hero Action | Asset Source | Caption / SFX |
```

Verify that each shot focuses on a single hero movement, brand wordmarks hold for ≥1 second, batch motion rests for ≥0.5 seconds, and duplicate taglines or repeated hero animations are eliminated. User sign-off on the storyboard and final design spec forms the **Production Gate**: previously agreed business or creative choices are locked, resolving only unresolved implementation details.
Perform final full-scale asset capture (full-page 2x screenshots, element cutouts, layout.json), translate the approved storyboard into a frame-accurate timeline, and proceed through `pipeline.md` Stage 4 (Final Asset Capture), Stage 5 (Shot-by-Shot Implementation), Stage 6 (Sound Design), and Stage 7 (Final Review).

Persist the approved Product Brief, Requirements-to-Execution Decision Table, Visual Direction / Tokens, Styleframes (or skip justification), Feature-to-Shot Mapping, Gallery Cards / Variants, Final Storyboard, and Data Compliance Policy as a stable design spec (or pass in full during final review handoff) to serve as the evaluation baseline for `final-review.md`. An independent reviewer Agent must not be left guessing user approvals from fragmented chat transcripts.

## Defaults and Fallback Rules

When the user grants full creative delegation, derive parameters dynamically from product materials: generate visual directions from CSS tokens, select shots from core features and page states, recommend duration / aspect ratio / language from distribution channels and reading density, and recommend music from brand energy. Fall back to 30–38 seconds at 1920×1080 only if the project and user inputs contain zero relevant clues. Determine data policies by project risk: retain public demo data; fictionalize or desensitize customer, personal, or internal data. Submit the storyboard for record before initial rendering unless the user explicitly requests skipping intermediate reviews.

## Per-Turn Response Format

```text
Current Stage:
Confirmed:
Needs Confirmation This Turn:
Deliverable Upon Confirmation:
```
