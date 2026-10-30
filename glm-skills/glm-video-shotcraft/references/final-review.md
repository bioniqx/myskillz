# final-review — Independent Final Review Checklist

An independent reviewer Agent uses this checklist to verify whether the final render satisfies the baseline criteria for the current creation mode, combined with `aesthetic-rules.md` to check visual technical quality. The reviewer Agent must operate in a clean context without having participated in production; do not provide production rationale, justifications, revision histories, or expected conclusions.

## Review Inputs

- Latest final MP4 render and per-shot keyframes;
- Creation mode: Direct Template, Autonomous Free Creation, or Co-Creation;
- Product video brief and mandatory features to showcase;
- Requirements-to-execution decision table;
- Visual direction, brand tokens, styleframes (or justification for skipping), and forbidden styles confirmed by user (in Co-Creation) or logged by Agent (in Autonomous Free Creation); for Template mode, the original template structure and actual replacement records;
- Feature-to-shot mapping;
- Gallery card names and specific variants specified by user or logged by Agent in design spec;
- Corresponding cards and `style-key` records in `gallery/api/library.json`;
- Exact demo TSX source code located from card documentation;
- Corresponding Gallery reference sample video, or keyframes / contact sheet extracted from reference sample video;
- Final storyboard, subtitles, page states, and SFX schedule;
- Selected `references/shots/*.md`;
- `aesthetic-rules.md`;
- Data compliance specifications.

When any input is missing, mark as "Unverifiable"; do not guess the production baseline. When the index, card documentation, demo source, and Gallery reference video conflict with each other, report the conflict source explicitly rather than picking one arbitrarily as ground truth.

## Checklist Items

### P — Product Goals

- P1: Are product positioning, target audience, and core value propositions clear?
- P2: Does the video focus attention on feature priorities confirmed or logged for the current mode?
- P3: Are there any non-existent, unconfirmed, or misleading feature claims?
- P4: Can execution choices in the requirements-to-execution decision table be traced directly to storyboarding, copy, page states, audio, and assets? Never substitute project rationale with rigid "audience/use case → style" stereotypes.

### F — Functional Completeness

- F1: Does every "mandatory feature" have at least one clearly discernible shot?
- F2: Does each shot deliver new information, without duplicate features or repetitive taglines?
- F3: Do page states enable viewers to understand product functions, rather than presenting purely decorative motion?

### V — Visual Direction

- V1: Do typography, color palette, materials, border radii, lighting feel, and information density match confirmed or logged visual directions?
- V2: Do motion velocity, overshoot, dwell times, and energy curves match confirmed or logged motion personality?
- V3: Has the video drifted from production baselines into Ink Press, cyber neon, or unrelated aesthetics?
- V4: Have any forbidden colors, effects, or brand characteristics been accidentally used?

### S — Shot Cards and Gallery Variants

- S1: Do the shot cards planned in feature mapping actually appear in the corresponding shots?
- S2: When a user requests `CardName · StyleName`, do `style-key`, exact demo TSX, and Gallery reference video point to the same variant, and does the final render use that variant?
- S3: Compared against exact demo TSX and Gallery reference sample, are action syntax, critical durations, easing relationships, and matte timing preserved from the recipe card/demo?
- S4: Does the implementation violate any "Known Pitfalls / Critical Vulnerabilities" noted on the card?
- S5: Are adapted product screenshots, coordinates, and brand tokens natural?
- S6: For styles marked "For reference only, requires custom implementation", was explicit user request obtained and implementation risk noted in the report? For styles marked "Missing preview", did the report avoid claiming fidelity to dynamic samples?

Pixel-perfect identity with Gallery samples is not required. Verification checks whether motion grammar and key parameters remain faithful, allowing adjustments to screenshots, coordinates, copy, brand visuals, and necessary compositions for the target product.

### B — Storyboard Consistency

- B1: Do shot sequence, durations, and feature information match the confirmed or logged final storyboard?
- B2: Are hero actions, page states, asset sources, subtitles, transitions, and SFX consistent?
- B3: Does brand wordmark hold for at least 1 second, and do batch motion endings rest for at least 0.5 seconds?
- B4: Were key shots deleted, replaced, or added without justification after the final storyboard was approved?

### D — Data and Asset Safety

- D1: Are policies regarding real data, fictional data, or desensitization strictly respected?
- D2: Are customer info, personal identities, API keys, internal URLs, or other sensitive details exposed?
- D3: Are real screenshots used when showcasing real product pages, avoiding low-quality hand-coded replicas?
- D4: Are screenshot states, fonts, images, and dynamic data fully loaded without FOUT or skeleton artifacts?
- D5: Do public demo data have verifiable public provenance? Are customer, personal, internal, key, realtime, or sensitive data fictionalized, desensitized, or frozen?

### A — Audio and Rhythm

- A1: Does BGM align with confirmed or logged audio direction, leaving sufficient headroom for SFX and optional voiceover?
- A2: Are SFX locked to true action keyframes without noticeable desync?
- A3: For rhythm-driven music, is cut point alignment error within 3 frames?
- A4: Does the ending energy peak and riser → impact → sparkle phrase resolve properly (if used in storyboard; sparkle beat taken from `sfx/light/`)?
- A5: Do all long samples (>5s, 21 in library) explicitly declare `durationInFrames` to prevent audio trailing beyond action completion?
- A6: Is every SFX audible in the **rendered artifact** (do not rely on preview — preview clamps volume to 1.0)? For soft-recorded assets (peaks <-12dB, 7 in library), check whether they were replaced, pre-normalized, or given >1 gain without clipping max_volume after render.
- A7: Do UI sound effects possess physical material textures rather than synthetic notification tones (S1 test)? If synthetic tones from `sfx/ui/` (`ui-confirm-*`, `ui-*-tone`, `ui-notify-*`) appear, is there a narrative reason ("the system is speaking") documented in project specs (see sound-design 3.3)?
- A8: For videos with BGM, are both versions (with BGM / without BGM with SFX preserved) delivered from the identical timeline (frame-accurate alignment between visuals and SFX)?
- A9: For sync/SFX-dense videos, have output audio track offset and source peak latency been empirically measured and compensated (sound-design §4.6)? Are compensation constants accompanied by measurement logs (pipeline quad-tuple, probe, method, date), and are source analysis values kept separate from output offset (`SOURCE_BEAT0` uncontaminated)? Does post-render verification show no systematic directional bias (music-beat-sync §5b)?

### Q — Visual Technical Quality

Execute `aesthetic-rules.md` in full. Inspect at minimum text sharpness, composition balance, rounded-corner masking, 3D texture crispness, element landing settle, camera jitter, transition seams, cheap lighting effects, readable dwell times, and deterministic rendering.

## Report Format

Use item codes for each finding, attaching frame numbers or screenshots for issues:

```text
P1 ✓ Product positioning and core value propositions are clear.
F2 ✗ Frame 340: Confirmed Knowledge Graph feature does not appear in final render.
V3 ✗ Frame 420: Heavy amber paper material drifts from confirmed deep blue tech direction.
S2 ✗ Frame 515: User selected whip-pan; actual implementation is flash-cut.
Q2 ✗ Frame 615: Body text blurs after 3D push-in; see keyframe f615.png.
```

Conclude with items categorized by severity: Must-Fix, Recommended Optimizations, and Unverifiable. Never substitute itemized verification with unsubstantiated "looks good overall" remarks, and never mark everything passed merely for report aesthetics.
