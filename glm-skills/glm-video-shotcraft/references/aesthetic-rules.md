# Aesthetic Rules (Case-Law Precedents)

Origin: Empirical precedents distilled from real-world rework on multiple promotional videos (reference template in `template/`).

**Usage**:
- Each rule = Rule (one actionable mandate) + Precedent (user verbatim quote / rework trajectory) + Self-Check Question. All three elements are mandatory.
- In `pipeline.md` Stage 7 acceptance, **verify every single rule sequentially**, outputting a self-check report in format: `[ID] ✓` or `[ID] ✗ (Location)` (Location = shot name / frame number).
- Rules may be intentionally broken for specific stylistic requirements, but every violation must be explicitly documented in the project specs (identifying which rule was broken and why).
- Code system: R (Rhythm) / Q (Quality, Camera & Composition) / S (Sound) / C (Copy) / P (Process). IDs are immutable once published; new entries are appended only.

## Table of Contents

- Rhythm (R)
- Quality, Camera & Composition (Q)
- Sound (S)
- Copy (C)
- Process (P)

---

## Rhythm (R)

### R1. Key information must breathe upon settling; brand wordmarks hold for at least 1 full second
**Rule**: Elements bearing core information (title cards, metrics, full grid layouts) must rest motionless for ≥1s before cutting; breathing pauses belong primarily to brand memory anchors (the wordmark landing moment), never squandered on ordinary content cards.
**Precedent**: User: "Hold for one second after the first title displays", "Not the first title card, I mean the AI Field Lab animation at the opening and ending — hold for 1 second after it appears". Initial revision paused the wrong object and had to be reverted; final resolution held both opening and ending wordmarks for 1 full second each.
**Self-Check**: Does every screen meant to be remembered by the audience have a completely static breathing moment? Is the pause allocated to brand/key information, or casually spent on ordinary elements?

### R2. Perceived speed comes from acceleration, not linear velocity; crowd motion needs physical metaphors, closing with a 0.5s pause
**Rule**: Fly-ins and scrolls must employ non-linear easing with non-uniform staggering; linear motion reads as cheap slide decks. Bulk arrivals should use "accelerating" hard beats, preferably bound to a physical metaphor (like card dealing from a deck), pausing motionless for 0.5s after board completion before cutting to the next beat.
**Precedent**: User: "As cards stack downwards, it should get faster and faster, scroll speed should accelerate, pausing for 0.5s at the end", "The final speed isn't fast enough... cards should fly into their slots in sequence, snapping into place faster and faster". An abstract scrolling flood failed to converge over 5 rounds; switching to a deck-dealing metaphor passed in a single round.
**Self-Check**: Is any element moving in a uniform linear trajectory? Does batch entry accelerate, and does the sequence end on a resting breath?

### R3. Lean slower rather than faster: default first cuts one notch slower, hero movement arcs ≥3s, interaction paced to human speed
**Rule**: The opening hero movement (a complete arc: focus → hover → settle) requires at least 3 seconds. Simulated interactions (typing, filtering, clicking) must match real human operating speed so viewers can follow each step mentally. Allocate hold/rest frame budgets during initial timeline drafting — first drafts are almost always rushed.
**Precedent**: Six independent pieces of feedback across the video requested "slow down / pause", with zero feedback ever complaining it was "too slow". User: "The first shot is still too fast, slow it down to 3s", "Typing in the search box and filtering cards happens too fast, slow it down". The opening was expanded to a 3s macro opening, and the interaction segment adjusted to unhurried type-and-filter.
**Self-Check**: Watch each shot as a first-time viewer: is anything hard to catch? Could a user follow along and mentally replicate the interaction?

### R4. Beat constraints govern timing, not amplitude: full-frame beat impacts ≤3 across entire video, default to element layer only
**Rule**: In rhythm-driven BGM cuts, "cutting on beat" does not mean "pounding the canvas on every beat". Impacts affecting the full frame or camera layer (full-screen scale bumps, screen shakes, flash frames, negative inversions) are managed as major slams: ≤3 across the entire video, locked to the strongest hits in `music-beat-sync.md` §2b, with ≥16 beats between adjacent impacts. Other beat animations apply strictly to the hero element layer. Beat-pump bursts are capped at ≤4 consecutive beats, ≤1 occurrence per video. The kick hit list is a candidate pool, not an automated trigger. **Count by set-piece technique application, not internal sub-events**: a single card application (e.g. paparazzi 3-flash, trailer-bumper 3-cut) consumes one quota; the card's internal burst rules and global caps apply as documented without being re-counted per frame.
**Precedent**: User feedback (2026-08-22): "If music is added, the camera shakes with the rhythm, degrading the viewing experience" — root cause was mapping music kicks directly to full-screen pumps on every beat. In strong electronic tracks with kicks on every beat, repeatedly "slamming" the camera layer created nauseating vibration. Parallels Q3: Q3 prohibits noise-based handheld jitter; this rule prohibits rhythm-based canvas jitter.
**Self-Check**: Play back any 8 consecutive beats in high-energy sections frame-by-frame: is the whole frame pulsing in scale or translation on every beat? Count full-frame/camera impacts: are there more than 3? Does each match the strongest hit list?

---

## Quality, Camera & Composition (Q)

### Q1. Existing product pages must use real screenshots; hand-coded UI is restricted to non-replica scenes meeting publication quality; handle data per risk policy
**Rule**: Whenever depicting existing product pages, first capture real pages using a headless browser (full-page texture + element cutouts + coordinate JSON); never hand-code approximate simulated replicas. Non-replica scenes (abstract intros, brand moments, standalone components absent from the live page) may use hand-coded UI, but publication-grade quality (evaluated against Q10) and communicative clarity (instantly legible purpose) are mandatory gates; if unachieved, revert to screenshots. Public demo data may be retained only if explicitly approved in the product brief; customer, personal, internal, credential, realtime, or sensitive content must be fictionalized, desensitized, or frozen first. This policy applies equally to hand-coded assets.
**Precedent**: User: "I want real pages with motion added", "Do not use real data, create fake data, never mention client names". Switching to authentic dashboard reconstructions scrapped a full afternoon of hand-crafted mockups. Clarification (2026-07-13 user ruling): "Not everything must come from real page screenshots; hand-coded UI components are fine as long as quality and communicative clarity are guaranteed" — narrowing the rule to "do not hand-code replicas of existing pages".
**Self-Check**: For each UI element: is it replicating an existing page? If yes, is it derived from screenshots? Does hand-coded UI pass Q10 scrutiny? Does source data conform to the agreed data policy without exposing unauthorized private or sensitive details?

### Q2. UI textures in 3D perspective must be rasterized at native display size before scaling down; investigate texture resolution pipeline first when text is blurry
**Rule**: In 3D scenes, rasterize UI textures at 2–4× display dimensions and downsample in 3D (scale up via layout-level CSS `zoom` rather than CSS transform scale). When text blurs, inspect the rasterization pipeline before adjusting camera or Depth of Field (DoF).
**Precedent**: Three rounds of user revisions: "Cards are noticeably blurry", "Still not sharp enough... visible pixel blocks", "Text clarity in shot 1 is still unresolved". Tuning DoF proved ineffective; switching to native-size rasterization achieved true 4× sharpness, and adopting CSS zoom across all 3D page planes solved it permanently.
**Self-Check**: Inspect keyframes frame-by-frame on zoom/perspective shots: are there pixelated artifacts along text edges? Is source texture resolution ≥2× the rendered screen size?

Technique Breakdown (distilled from `hires-rasterize-3d-text`, reference: `template/src/aifl/live/PageCam.tsx`):
- **Root Cause**: Chromium rasterizes 3D composite layers at 1920 layout width and scales up on the GPU. Downsampling before upscaling guarantees blur, regardless of camera or DoF parameters.
- **Solution**: Scale up using layout-level CSS `zoom` instead of `transform: scale(zoom)`. Chromium rasterizes at the magnified device dimensions, downsampling from high-DPI sources. Adjust coordinates via `Tx = 960/zoom - cx` to maintain framing consistency with flat mode (see `PageCam.tsx:100-114`); missing this calculation shifts the camera focal point.
- **Implementation**: Pair 2× full-page screenshots (`deviceScaleFactor: 2`) with 4× element cutouts. Crossfade 4× cutouts over 6 frames during camera push-in to mask low-res textures (longer crossfades show double-image misalignment).
- **Troubleshooting Sequence**: Blurry text → check source resolution pipeline first (capture scale → rasterization path → zoom method); inspect camera last. DoF provides atmospheric mood, never image sharpness. Verify via cropped frame-by-frame inspection.

### Q3. Keep the camera steady: product promo videos default to zero handheld shake
**Rule**: Light-themed UI promo videos strictly forbid handheld camera shake. Camera noise is permitted with minimal amplitude only in dark-themed atmospheric videos deliberately pursuing documentary realism, and must be visually verified across rendered frames.
**Precedent**: User: "Camera angle is poor, and there's a weird jitter". Removing handheld shake and reframing eliminated all complaints. Another dark atmospheric promo retained `shake=0.02` without complaints — establishing this boundary.
**Self-Check**: Review rendered frames shot-by-shot: is there any non-narrative camera jitter?

### Q4. Highlights and sweeps: quality over quantity; never broadcast across batches, grant at most once to the hero, and clamp strictly within rounded borders
**Rule**: Never broadcast glints or bloom sweeps across batches of elements; bulk arrivals rely on motion itself rather than individual lights flashing. Any retained sheen must be clipped by the parent element's `border-radius` / `overflow: hidden`; light spilling over rounded corners is a hallmark of cheap templates. The visual technique itself is not banned: focused, single-instance sheen on hero elements with high execution polish is allowed, provided the rendered frames look genuinely refined.
**Precedent**: Two user rejections: "No need for every card to blink", "Remove the bloom sweep when cards appear, it looks cheap". Replaced card-by-card glints and removed sweeps, clamping remaining chip highlights inside border radii. Clarification (2026-07-13 user): Rejections targeted "poorly executed versions", "not that the technique/effect itself is invalid" — the ban on batch broadcasts and requirement for rounded clipping remain firm, but polished sheen effects may be attempted with higher standards.
**Self-Check**: Count glint/sweep occurrences across the video: does it exceed "once for the hero element"? Is every highlight clipped by rounded corners? Does every retained effect look premium at full playback speed?

### Q5. Dedicate the opening to a single hero: one subject + complete movement arc beats crowd choreography
**Rule**: Openings must be focused and minimal: one hero element, one complete movement arc (spotlight → push-in → hover → outline sheen → settle). A chorus of multiple elements moving together fails to create a strong first impression.
**Precedent**: User: "In the first shot, focus on a single card and give it higher texture quality". The opening was overhauled six times overnight; once the single-card structure was established, it remained unchanged through final delivery.
**Self-Check**: How many focal elements are competing for attention in the opening shot? Does the hero's movement arc have a complete narrative arc (anticipation, action, resolution)?

### Q6. Camera angle serves legibility: eye-level for dense information, horizontal profile for text close-ups, validate stylized tilts shot-by-shot
**Rule**: Determine stylized angles shot-by-shot. Narrative and emotional shots may tilt; information-dense shots like lists and grids must remain strictly front-facing (orthographic / eye-level). Close-ups of text-bearing cards should use lateral horizontal angles to prevent steep vertical angles from degrading legibility. Global one-size-fits-all camera tilts are forbidden.
**Precedent**: A uniform global tilt across the entire video was rejected: "It looks poor... the changes to content list pages are also bad, roll it back". The list page was reverted to front-facing. User: "Focus on one card... filmed from the left rather than below", switching to a left-side hero camera.
**Self-Check**: For each tilted shot: what is the specific narrative reason for the angle? Is the text still effortlessly readable at this angle?

### Q7. The 4-piece formula for object close-ups: lateral tilt + perceptible volume height + orbital rotation + high-contrast dark material background
**Rule**: Close-up asset shots need environmental depth: lateral tilted camera, visible volumetric stacking, orbital camera motion around the subject, set against a dark contrasting material (e.g. brushed metal), transitioning back to the primary scene via synchronized zoom-out.
**Precedent**: User: "The camera should tilt from the side, stacked items should have perceptible height, and the camera should rotate around the stack. The entire scene should have a dark metallic texture background, then zoom out while revealing the dashboard". Progressed from flat pile close-ups to the final version: dark brushed metal background + taller stack + orbital camera sweep.
**Self-Check**: Does the subject in close-up shots exhibit physical volume and environmental contrast? Is the camera static or dynamically orbiting/pulling back?

### Q8. Craft the finale as a keynote launch: elements fly in from all directions to frame the wordmark, pushing energy to peak
**Rule**: Conclude multi-feature product videos with a "group photo" ensemble: one representative element from each demonstrated feature flies in from multiple vectors to frame the wordmark. Production value must match the video's peak energy (crane move + stage lighting + particle dust). First drafts are almost always too conservative; default to dialing up one notch.
**Precedent**: User: "Core elements from various pages fly in from different directions... forming an ensemble group photo", "Add more visual effects, animations, camera work... like a product launch keynote". Elevated from a simple card grouping to keynote scale: crane move, stage lighting, gold dust.
**Self-Check**: Is the finale the unambiguous energy peak of the entire video? Does the ensemble include representative elements from every showcased feature?

### Q9. Element fly-in arrivals must snap into real layout slots; never hover detached above page surfaces
**Rule**: When elements fly into a page, they must integrate into the layout (snapping into real grid coordinates or extending the scroll flow). Floating statically above the page without settling looks artificial.
**Precedent**: User: "The research question list should fly in from the air and embed into the dashboard", "Don't let the 10 project cards float above; scroll down and arrange them below without overlapping". Handled by flying row elements directly into layout slots and extending the grid dynamically on scroll.
**Self-Check**: After flying in, does every element resolve to authentic coordinates within the page layout? Does any element hover permanently above the surface?

### Q10. Mock content in document shots must be publication-grade: native typography, fully populated body text, complete layout context
**Rule**: Viewers will read every word on the screen. Document and report shots must populate realistic text densities using the product's native typography; sidebars, comment panes, and header elements must be fully visible. "Placeholder card + slogan" mockups require complete shot rework.
**Precedent**: User: "Body text in the weekly report must match current styling and typography; keep content mocked but fully populated with text, and show the left sidebar and right comment pane completely". The initial placeholder mockup was completely rebuilt with authentic typography and full two-column layout.
**Self-Check**: Freeze any frame in a document shot: does the content read like an authentic product? Are structural elements (sidebars, comments, headers) fully realized?

### Q11. Readable text has minimum effective heights: captions ≥5% frame height, secondary text ≥3%; measure rendered pixels, not CSS fontSize
**Rule**: Calibrate legibility for mobile and embedded players on 1080p renders: narrative subtitles must have an **effective font height ≥56px (≥5.2% frame height, recommended: 60px tier)**; secondary text (subtitles, metrics, URLs) must be ≥32px (≥3%). Effective height = fontSize × cumulative ancestor scale × perspective foreshortening (estimate via `cos(rotY)` in 3D). Acceptance measures actual pixels on rendered frames, ignoring CSS `fontSize`. Text exists in only two states: **"Texture"** (decorative background text in screenshots, intentionally blurred or dimmed so viewers do not attempt to read) or **"To Be Read"** (compliant font size + sufficient contrast, paired with scrim or drop shadow over light backgrounds). There is no acceptable middle state of "rearranged but still unreadable" — if text cannot be read, delete it. The closing URL / CTA is the last line that should ever be undersized.
**Precedent**: User (2026-07-25): "In several shots, the text is tiny... you can't read it at all". In the gallery showcase video, S1/S2/S4 subtitles were 38–40px (~3.5% frame height), S6 secondary text was 30px, and the ending URL was 25px — all failing the threshold. In S2, a panel subtitle rearranged "for legibility" was only 19px — an exact counterexample of the unreadable middle state. All instances were updated to 60/40/34px tiers to pass review.
**Self-Check**: Crop a frame from each captioned shot down to 480px width (simulating mobile preview): is every sentence effortlessly readable? Measure actual rendered pixel heights: subtitles ≥56px, secondary text ≥32px? Does any text fall into the unreadable middle state?

---

## Sound (S)

### S1. Select music and SFX by video genre, not isolated events: driving electronic beat + cinematic SFX vocabulary, forbid video game sound packs (ban timbres, not actions)
**Rule**: Product promo SFX vocabulary = whoosh (camera motion) / impact (landing) / riser (anticipation) / sparkle (highlights) / transition (cuts); video game sound packs are strictly forbidden. Select driving, rhythm-heavy electronic music (tech-house tier) for BGM. Candidate tracks must be auditioned underneath rendered video — listening to isolated audio cannot judge fit.
**Precedent**: User: "The music and sound effects sound too much like a video game. Find something with strong beats and heavy rhythm, and use sound effects typical of product promo videos". All previously introduced Kenney CC0 game sound effects were replaced with Mixkit tech-house + cinematic whoosh/impact/riser/sparkle assets.
**Ban timbres, not actions**: This rule bans video game synthesizer plucks, cartoon boings, and 8-bit game-over scales; it does not ban foley for clicks or taps. If a click, toggle, or glass break occurs visually, provide authentic foley per S4. Distinguishing test: Does this sound like a **real physical object in the physical world** (camera shutter, mechanical switch, glass, paper), or like a **feedback chime in a video game engine**? Use the former; reject the latter.
- The reference template uses `click-camera.mp3` at peak SFX loudness (0.6) — a real mechanical shutter, not a UI beep.
- **`sfx/ui/` is not blanket-approved; it requires careful individual auditioning**: among its 18 files, some are physical foley (`switch-light`, `switch-tap`, `switch-click-quick`), while over half are synthetic UI notification chimes (`ui-confirm-bleep`, `ui-notify-tech`, `ui-success-soft`, etc.) — the latter embody the exact game-like timbre to avoid unless the narrative explicitly calls for system notifications.
- `sfx/glass/` contains authentic physical break foley and is fully approved.
**Self-Check**: Close your eyes and listen to the audio track: does it sound like a keynote product reveal, or a mobile casual game? Was the BGM auditioned directly beneath the final visuals? Does every UI sound effect possess physical texture rather than synthetic notification tones?

### S2. Manage SFX frame-by-frame on beat; burst sound effects require dual-sample alternation + volume stepping + accelerated spacing
**Rule**: Centrally manage SFX via declarative tables declaring `(frame, asset, volume)`, annotating each line with corresponding visual actions; never scatter audio intuitively. To eliminate machine-gun repetition during rapid bursts, apply three techniques: alternate dual samples, step volume down along the sequence (e.g. 0.40 → 0.25 across 6 steps), and accelerate spacing following the animation curve; if spacing becomes too tight, crossfade into a single swoosh (our pipeline uses no pitch-shifting `playbackRate`).
**Precedent**: User: "When weeks appear in the left sidebar, change the sound effect to match each week's arrival". Established a frame-locked SFX table, implemented dual-sample pluck alternation, accelerated spacing from 8f to 3f, and stepped per-week pop volume down across 0.40 → 0.25.
**Self-Check**: Is each SFX locked to a specific frame number with visual action annotations? Do burst sequences sound like articulated rhythm rather than mechanical machine-gun repetition?

### S3. Design sound after visuals are locked; when timelines change, re-anchor all SFX
**Rule**: Schedule BGM and SFX after visual timing is stabilized. Any change to shot duration or sequence must conclude with re-verifying the entire SFX keyframe schedule — audio/visual desync is a mandatory pre-delivery check.
**Precedent**: User: "After making these visual adjustments, readjust sound effect positions to match the new timeline". Re-anchored all SFX across the updated 1085-frame timeline. Two out of three re-anchoring passes were pure downstream costs of visual reworks.
**Self-Check**: Were shot durations or sequences modified in this round? If so, has every SFX keyframe been re-aligned against the updated timeline?

### S4. Physical foley takes precedence over decorative sound: match visual actions with authentic physical sounds, clipping audio strictly to action length
**Rule**: Pair physical screen actions with corresponding authentic sounds (typing uses keyboard strokes; sequential drops use individual pops); generic swooshes cannot ground distinct visual actions. Long audio samples must be clipped to visual action duration (via Sequence boundaries).
**Precedent**: User: "Add typing sound effects when weekly report content appears". Paired the document reveal with a typewriter track, clipping `keyboard.mp3` into distinct 24f and 44f segments.
**Operational Guidelines** (see `sound-design.md` §4.1):
- **Samples >5s (21 in library) must explicitly declare `durationInFrames`** to prevent audio trailing beyond action completion; impacts with long reverb decay are exceptions that should fade naturally.
- **Quiet assets with peaks <-12dB (7 in library)**: `volume` acts as a multiplier; setting volume to 1.0 merely plays original amplitude, remaining buried beneath BGM. Replace the asset, pre-normalize, or apply >1 gain, verifying peak levels on rendered output.
**Self-Check**: Does every distinct visual action (typing, clicking, landing) have authentic foley? Does audio trail past action completion? Are all sound effects distinctly audible in the rendered video?

### S5. Audio-visual alignment requires two compensations: measure output track offset per pipeline, measure peak latency per source file
**Rule**: Rendered video audio tracks exhibit fixed latency relative to video frames due to output encoding priming (AAC encoder priming typically adds 2048 samples ≈1.28f @30fps at 48kHz; Remotion tracking: `remotion-dev/remotion#7099`). This is not an artifact of `<Audio>` or `Sequence.from`. Measure and log the constant per pipeline (Remotion version + codec + sample rate + container) via normalized cross-correlation against sharp SFX files. Deduct this offset uniformly in the render layer `from` expression rather than altering storyboard frame numbers. Separately measure source peak latency (when peak amplitude is offset from file start). Unified formula: `from = target_peak_frame - source_peak_latency - output_pipeline_offset` (see `sound-design.md` §4.6).
**Precedent**: AiflPromo measured click latency at 2032 samples and impact latency at 2066 samples (~1.27–1.29f), matching AAC priming signatures. Without compensation, combined latency delayed impacts by 0.27s, creating obvious visual desync and making legitimate beat cuts feel like erratic jitter.
**Self-Check**: Has output audio track offset been measured for this pipeline? Is compensation applied uniformly in the `from` formula rather than scattered across keyframe schedules? Has source peak latency been verified for assets with sharp attack transients?

---

## Copy (C)

### C1. Rewrite copy against final visuals once locked; provide narrative captions even for purely animated segments
**Rule**: Initial draft copy serves solely as a placeholder. Once visuals are locked, rewrite copy line-by-line against rendered footage. Provide concise captions for animated shots to avoid voiceless voids (brand closing shots are excepted to maintain elegance).
**Precedent**: User: "Rewrite the copy based on my completed video content; current copy doesn't match the screen. Also, add captions explaining what's happening during animations". Rewrote headline copy and added explanatory captions across live shots.
**Self-Check**: Review each line: does the copy correspond directly to the visual action on screen? Are there voiceless animation sequences lasting longer than 3 seconds?

### C2. Write slogans as "Team + Feature Name + Concrete Benefit", replacing abstract metaphors with specifics
**Rule**: Slogans must be concrete and include product feature names (Paper Radar / Weekly Report), avoiding generic metaphorical slogans ("board" / "place" generalizations). Insert a lead-in title card before major feature reveals.
**Precedent**: User refined copy word-by-word: "Change 'All your research, one board' to 'All team's research, one place to go'... change 'The morning reading' to 'Paper Radar, tailored for your morning reading'"; "Add a text card before showing the final document page". Rewrote lines and added a lead-in title card before the document shot.
**Self-Check**: Does every slogan contain specific feature names and concrete benefits? Are any lines supported purely by vague metaphors?

### C3. Annotation text in 3D shots belongs in the same 3D coordinate space: page-space, matching perspective, angled camera, large serif typography + highlighter
**Rule**: When annotating subjects in 3D scenes, text must reside in that same 3D coordinate space (page coordinate system, matching camera perspective, `translateZ` elevation + drop shadow); flat 2D overlays detach from the scene. Style with large serif type and highlighter accents on keywords.
**Precedent**: User: "Text on the left, larger and bolder with highlights, floating in 3D space and filmed from an angle" (initial flat 2D card rejected). Moved hero-hover annotations into 3D page space with angled perspective and highlighter styling.
**Self-Check**: For all text in 3D scenes: does it move coherently with the scene camera, or is it pasted flatly against the screen glass?

---

## Process (P)

### P1. Render and inspect keyframes locally before delivery; never delegate first inspection to the user
**Rule**: Render keyframe screenshots after each revision pass and inspect locally (composition, jitter, text sharpness, render glitches), using pixel-level verification tools (cropped magnification, frame diffs) before presenting to the user.
**Precedent**: Upon receiving the first cut, the user asked: "Did you inspect screenshots yourself before sending? The camera angle is poor, and there's a weird jitter". Built crop/diff/measure self-check scripts and archived `out/qa/` static frames, transitioning to evidence-based frame reviews.
**Self-Check**: Which exact frames did I visually verify before delivering this cut? Do I have screenshot evidence for all critical shots?

### P2. Break down reference materials frame-by-frame into technique inventories; evaluate shot fit individually rather than applying globally
**Rule**: When given reference videos, extract frames to create a motion breakdown (implementations of animations, transitions, and effects) in the spec, evaluating project fit per shot. Reference images depict the mood of a specific shot type rather than a universal style mandate — evaluate applicability shot-by-shot.
**Precedent**: User: "Extract as many frames as possible from the reference video... reproduce and adapt what fits our project, without forcing what doesn't fit". In contrast, uniformly tilting all shots based on three reference images was rejected ("Done poorly... rollback").
**Self-Check**: Is there an explicit "adopt / reject" decision for every technique in the reference material? Was a single reference image mistakenly treated as a global style mandate?

### P3. Clarify ambiguous feedback before acting; revert incorrect changes cleanly via git rather than patching over errors
**Rule**: Clarify ambiguous feedback (e.g. "the first title") before coding; if changes target the wrong element, revert the entire commit cleanly and restart; maintain atomic commits for clean rollbacks.
**Precedent**: User: "Not the first title card, I mean the AI Field Lab animation at the opening and ending". Misunderstanding held card1; reverted cleanly within 8 minutes and redid on the correct target to pass review.
**Self-Check**: Am I completely certain of the target element in this feedback? If this change is wrong, can it be cleanly rolled back with one commit?

### P4. Map feature lists to shots upfront; each motion technique stars as hero only once; eliminate duplicate shots and copy
**Rule**: Compile product feature lists (dashboard, details, documents, reports, brand) and map them 1:1 to shots before animating; missing core features requires rework. Each motion technique (fly-in, stacking, card-flip) stars as hero only once. Audit the edit by asking "What new information does this shot provide?"; eliminate redundant footage and repetitive slogans.
**Precedent**: User: "The other animations feel homogeneous and don't showcase the full product", "Looks great, but where is the weekly report feature?" — prompting feature shot additions. User: "The second-to-last shot repeats the project cards, remove it" — removing redundant overview footage and deduplicating closing slogans.
**Self-Check**: Does every item in the feature list have a corresponding shot? Are two shots using the same technique as the hero or conveying duplicate information?
