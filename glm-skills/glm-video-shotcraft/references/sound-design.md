# sound-design — Sound Design Methodology

Origin: Empirical sound design practices from the template promotional video (`template/`). For codified rules S1–S4, refer to `references/aesthetic-rules.md`.

In the reference template, all audio is centrally managed in a single file (`template/src/aifl/Main.tsx`: `SFX[]` keyframe table); scene components contain zero audio code. Sound is a timeline-level asset, not a shot-level asset.

## Table of Contents

- Methodology
- BGM Selection
- SFX Vocabulary
- Alignment Techniques

---

## 1. Methodology

**Order: Visual structure locked → Lay BGM to set energy skeleton → Frame-lock SFX.**

1. **BGM Precedes SFX to Establish Energy Structure.** A single BGM track beds the entire video, with volume envelopes shaped via `interpolate` for head/tail fades (template video: `[0, 30, TOTAL-50, TOTAL] -> [0, 0.34, 0.34, 0]`, i.e. 1s fade-in, 1.7s fade-out). BGM volume is held around 0.34 to preserve headroom for SFX. The soundtrack's energy curve must mirror the storyboard's arc (low opening → mid-section progression → peak outro). Candidate tracks must be auditioned underneath rendered video — listening to isolated audio cannot judge fit (S1). Wrap the BGM `<Audio>` tag with a boolean inputProp (e.g. `bgm`, default `true`); SFX remain unaffected by this switch. Any project with BGM delivers two final cuts rendered from the identical timeline: a full mix and a no-BGM mix (SFX preserved): `npx remotion render … --props=props-nobgm.json` (content: `{"bgm":false}`).
2. **Select Vocabulary by Video Genre, Not Isolated Events (S1).** Product promo SFX vocabulary = whoosh (camera motion) / impact (landing) / riser (anticipation) / sparkle (highlights, stored in `light/`) / transition (scene cuts); video game sound pack **timbres** (synth plucks, bloops, cartoon boings) are strictly forbidden. The template's first cut selected sounds by UI event semantics (click/drop/confirmation) and was rejected immediately: "It sounds too much like a video game".
   **Ban timbres, not actions**: If real clicking, toggling, or glass breaking occurs on screen, provide authentic foley (the template uses `click-camera.mp3` at peak SFX volume 0.6). However, `sfx/ui/` requires individual auditioning — it contains both authentic mechanical switches and synthetic notification chimes; the latter embody the exact game-like timbre to avoid (§3.3); `sfx/glass/` contains authentic physical break foley. Distinguishing test: see Aesthetic Rule S1.
3. **Manage SFX via Frame-Locked Declarative Tables (S2).** SFX is an array of `{ from, src, volume }[]`, annotating each entry with corresponding visual actions ("hero card: whoosh up on the pop"); during rendering, wrap each entry with `<Sequence from={s.from}>`. Never scatter audio intuitively.
4. **Reserve Slots for Custom Screen Foley Beyond Generic SFX.** Beyond core vocabulary, distinct screen actions require dedicated foley (typing reveals use keyboard clicks; sequential drops use pops) — generic swooshes cannot ground distinct visual actions (S4).

Timing Lessons: Audio work in the reference template began only after ~30 rounds of visual revisions (in the final wrap-up passes). Swapping BGM and overhauling visuals in the same pass resulted in scrapped audio schedules when visuals changed again. **Audio always follows visual lock** (S3); details in Section 4.

---

## 2. BGM Selection

### Evolution: Three Iterations Across 34 Minutes

| Version | Track | Source / License | Reason for Replacement |
|---|---|---|---|
| v1 | Kevin MacLeod – *Inspired* (warm ambient piano); *Deliberate Thought* downloaded as backup, never referenced | incompetech, CC-BY | User: "Change BGM to something more rhythmic, exciting, and upbeat" — ambient piano lacked punch |
| v2 | Kevin MacLeod – *Life of Riley* (upbeat folk-pop) | incompetech, CC-BY | User: "The music and sound effects sound too much like a video game. Find something with strong beats, heavy rhythm" — cheerful ≠ promotional tech polish |
| v3 (Final) | Mixkit tech-house percussion bed (`bgm-tech-house.mp3`), volume raised to 0.34 | Mixkit license | Retained through final delivery |

v1 to v2 were separated by only 22 minutes before rejection — proving candidate tracks were never tested beneath actual video. **Always audition candidate tracks beneath rendered footage** (S1 check).

### Selection Criteria (Derived from User Feedback)

- **Driving beat, heavy rhythm**, prioritizing electronic beds (tech-house tier); pleasant/upbeat is not the primary criteria.
- Baseline mood is a "typical product promotional launch" — closing your eyes, the audio should feel like a keynote reveal, not a casual mobile game (S1).
- Energy arc anchors full video structure: steady drum beds provide room for multi-layered SFX; overly melodic tracks clash with foley.

### Free License Sources

| Source | License | Scope | Notes |
|---|---|---|---|
| [Mixkit](https://mixkit.co/) | Mixkit License (free commercial use, no attribution required) | BGM + cinematic SFX (whoosh/impact/riser/sparkle) + diverse foley | Primary source for template video; record track title and URL upon download to preserve audit trail |
| [incompetech](https://incompetech.com/) (Kevin MacLeod) | CC-BY 4.0 (requires attribution) | BGM, extensive library filtered by mood | Source for template v1/v2; note CC-BY attribution requirements |
| [Kenney](https://kenney.nl/assets) (Game packs) | CC0 | Gaming projects | **Strictly forbidden for product promos** (S1) — purged entirely from template after initial trial |

---

## 3. SFX Vocabulary

### 3.0 Directory Structure & Discovery Paths

```
assets/audio/
  bgm/                5 files  BGM candidates (tech-house beds + house/hip-hop)
  sfx/<category>/   149 files  16 categories split by scene/material
```

**Pick category first, then select timbre** — identify visual action, consult table below, and audition within the corresponding directory.

Mapping the 5 S1 vocabulary words to directory names (**`sparkle` resides in `light/`; there is no `sparkle/` directory**):

| Vocabulary | whoosh | impact | riser | sparkle | transition |
|---|---|---|---|---|---|
| Directory | `transition/` | `impact/` | `riser/` | **`light/`** | `transition/` |

Both whoosh and transition live in `transition/` (camera motion and transition timbres overlap); remaining 11 categories serve as the **foley layer** (S4 custom screen slots).

| Category | Count | Contents | When to Browse |
|---|---|---|---|
| `transition/` | 23 | whoosh / sweep / swoosh / wind | Camera motion, scene transitions, element fly-ins/outs |
| `impact/` | 14 | impact / thud / stomp / bass hit | Landing anchors, downbeats, slams |
| `riser/` | 1 | Risers | Buildup into finale or major hero shots |
| `camera/` | 10 | Shutter, lens clicks, zooms | Photographic moments, crash zooms, focus, iris |
| `ui/` | 18 | Clicks, switches, notifications, pops | UI feedback, theme toggles, list arrivals |
| `text/` | 13 | Typewriters, keyboards, handwriting | Typing reveals, stroke draws, underlines |
| `paper/` | 10 | Paper shuffles, page turns, print | Page flip transitions, tears, papercraft, riso |
| `film/` | 8 | Projectors, film reels, tape, vinyl | Trailer grammar, film strips, tape rewinds |
| `light/` | 10 | Sparkles, light sweeps | Light sweeps, illuminate reveals, shimmering accents |
| `data/` | 13 | Glitches, static, telemetry | HUD, streaming output, skeletons, glitch effects |
| `scifi/` | 5 | Sci-fi hums, space, room tone | Space moves, systemic background hums |
| `mech/` | 8 | Mechanical gears, industrial locks | Component assembly, locks, morphs |
| `glass/` | 4 | Glass breaks, shatter impacts | Shatter transitions, hard-cut impacts |
| `fluid/` | 5 | Ink, water, fluids, bubbles | Ink reveals, particle fill, bubbles |
| `crowd/` | 3 | Crowds, applause, breathing, heartbeats | Group photo finales, keynote atmosphere, tension |
| `counter/` | 4 | Counters, meters, clocks, countdowns | Number rolls, readouts, timelines |

For file-by-file duration, peak latency, and suggested anchors, refer to `assets/audio/AUDITION-2026-07-27.md`. For licensing details, see `assets/audio/ATTRIBUTION.md`.

Note: Category names serve as **discovery indexes, not licensing mandates**. Follow genre discipline from Section 2: physical materials (`glass/`, `crowd/`, `fluid/`) are custom foley slots (S4); general transitions prioritize `transition/` and `impact/`.

### 3.1 Base Layer: 14 Assets Used in the Reference Template

The table below lists assets used in the reference template. **"Typical Anchor Keyframe" represents battle-tested frame anchors** (30fps, 1085f total); reuse relative semantics rather than absolute values. Durations verified via ffprobe.

| File | Directory | Duration | Usage | Typical Anchor (Template) | Source & License |
|---|---|---|---|---|---|
| `bgm-tech-house.mp3` | `bgm/` | 288.7s | Full-video tech-house percussion BGM bed | Bed track, envelope 0 -> 0.34 -> 0.34 -> 0 | Mixkit |
| `transition-soft.mp3` | `sfx/transition/` | 1.27s | Soft transition: brand settle, scene entrances | f12 / f277 / f475 / f623 / f779 (once per new scene) | Mixkit |
| `whoosh-fast.mp3` | `sfx/transition/` | 1.76s | Fast camera move, batch elements exiting | f78 brand->dashboard, f340/356 deal acceleration, f435 filter grid fly-out | Mixkit |
| `whoosh-big.mp3` | `sfx/transition/` | 2.32s | Sweeping camera move: pop up, pull back, pan back | f127 hero pop up, f308 orbit pull-back, f388 swoosh back to search | Mixkit |
| `sparkle.mp3` | `sfx/light/` | 4.55s | Light reveal: scan beam, ending sparkle | f141 hero light beam, f1005 outro rule sparkle | Mixkit |
| `transition-snap.mp3` | `sfx/transition/` | 0.57s | Crisp landing/reseating snap | f204 hero impact reseat | Mixkit |
| `swoosh-quick.mp3` | `sfx/transition/` | 0.78s | Title card entrance, subtle push-in | f220/565/725/885 four title cards, f455 post-click push-in | Mixkit |
| `keyboard.mp3` | `sfx/text/` | 19.6s | Authentic typing foley (long sample, clipped to section) | f401 search bar input (24f cut), f781 report typing (44f cut) | Mixkit |
| `click-camera.mp3` | `sfx/camera/` | 0.35s | Click confirm / shutter snap (loudest SFX: vol 0.6) | f451 click card to detail, f648 paper counter settle | Mixkit |
| `riser-cine.mp3` | `sfx/riser/` | 4.81s | Cinematic riser into finale | f945 outro group assembly starts | Mixkit |
| `impact-cine.mp3` | **Deleted from library** | 4.06s | Cinematic heavy impact (vol 0.55 peak SFX) | f980 wordmark stamp landing | Mixkit |
| `pop.mp3` | `sfx/ui/` | 0.48s | Short pop for sequential item arrivals | f840–865 weekly report 6-item burst, 5f apart, volume stepped 0.40 -> 0.25 | Source unknown |
| `impact-transition.mp3` | `sfx/impact/` | 4.87s | Unused asset: downloaded backup impact | None | Mixkit |
| `typewriter.mp3` | **Deleted from library** | 0.22s | Unused asset: typing reveal used `keyboard.mp3` | None | Source unknown |

Summary: 12/14 active in template; 2 dead assets (`impact-transition.mp3` retained in library, `typewriter.mp3` deleted).

**Handling Deleted Files (2026-07-27 Filter)**:
- `impact-cine.mp3` was removed from `assets/audio/`, but **the template renders normally** via its standalone copy in `template/public/audio/`. In new projects reproducing the outro 3-beat phrase, use `sfx/impact/impact-deep-whoosh.mp3`: it is **byte-for-byte identical** (MD5 `ce27fd2f`, see §3.2) to Mixkit's "Cinematic whoosh deep impact".
- `typewriter.mp3` was removed (unused dead asset). For single typewriter hits, use `sfx/text/typewriter-hit-single.mp3` or `typewriter-hit-hard.mp3`.

### 3.2 Duplicate Assets Under Different Names: 4 Identical Pairs

An MD5 audit on 2026-07-27 revealed 4 pairs of **identical Mixkit assets downloaded twice under different filenames**:

| Pair | Identical Material | Current Status |
|---|---|---|
| `transition/transition-soft` = `transition/air-zoom-vacuum` | Air zoom vacuum | Both present |
| `transition/swoosh-quick` = `transition/sweep-fast-small` | Fast small sweep transition | Both present |
| `impact/impact-transition` = `impact/impact-epic-trailer` | Movie trailer epic impact | Both present |
| `impact/impact-cine` = `impact/impact-deep-whoosh` | Cinematic whoosh deep impact | `impact-cine` removed, `impact-deep-whoosh` preserved |

**These duplicate pairs cannot be used for §4.2 dual-sample alternation** — identical bytes produce zero variation, preserving machine-gun repetition. Choose distinctly recorded files with similar timbres instead (e.g. `text/typewriter-hit-hard` + `text/typewriter-hit-soft`).

Deduplication command for new assets:
```bash
find assets/audio -name '*.mp3' -exec md5 -r {} \; | sort | awk '{print $1}' | uniq -d
```

### 3.3 Auditioning the `ui/` Directory Individually

`ui/` is the only category with **internal textural divergence**: it mixes authentic physical foley with synthetic UI notification tones — the latter being what S1 bans. Mixkit original titles reveal nature (`tone`, `bleep`, `alert`, `notification` signal synthetic tones):

| File | Mixkit Title | Quality |
|---|---|---|
| `switch-light` | Light switch sound | Pass: authentic physical light switch |
| `switch-tap` | On or off light switch tap | Pass: authentic physical switch |
| `switch-click-quick` | Quick switch click | Pass: authentic physical switch |
| `pop` | (Source unknown) | Pass: tested in template (weekly report burst) |
| `hitech-touch-magnet` | Hi-tech touch with magnet | Caution: magnetic texture, slightly synthetic but physical; evaluate in context |
| `chime-crystal` | Crystal chime | Caution: crystal wind chime, decorative/light accent rather than UI feedback |
| `pop-electric` | Electric pop | Caution: electronic pop; viable for bursts, slightly synthetic alone |
| `ui-select-click` | Select click | Caution: interface click, cleaner than below |
| `ui-click-tone` | Cool interface click tone | Ban: synthetic tone |
| `ui-confirm-bleep` | High tech bleep confirmation | Ban: synthetic bleep |
| `ui-confirm-tone` | Confirmation tone | Ban: synthetic tone |
| `ui-tone-quick` | Digital quick tone | Ban: synthetic tone |
| `ui-success-soft` | Success software tone | Ban: synthetic tone (matches S1 rejection archetype) |
| `ui-notify-tech` | Technology notification | Ban: notification chime |
| `ui-message-pop` | Message pop alert | Ban: notification chime |
| `ui-popup-dry` | Dry pop up notification alert | Ban: notification chime |
| `ui-option-select` | Interface option select | Ban: synthetic interface tone |
| `ui-select-modern` | Modern technology select | Ban: synthetic interface tone |

Usage:
- **Pass** assets can be used directly for interaction foley (e.g. `theme-switch-moves`, `segmented-thumb-hero`).
- **Caution** assets **must be auditioned beneath rendered video**.
- **Ban** assets default to excluded from promotional videos. **Exception**: deliberate narratives depicting system feedback (HUD readouts, AI confirmations, error states), which must be documented in project specs per aesthetic rules.

Similar scrutiny applies to `data/` and `scifi/`, though their stated purpose is digital/sci-fi textures.

---

## 4. Alignment Techniques

### 4.1 Keyframing Methods

- **Centralized Declarative Registry**: `SFX: { from, src, volume }[]`, annotating each entry with corresponding screen actions; render layer iterates the array, wrapping each entry in `<Sequence from={s.from}>`. Co-locate keyframe tables with shot schedules (`AIFL_SHOTS`) for direct comparison (S2).
- **Sequence Truncation for Long Samples**: Use `durationInFrames` (e.g. 24f or 44f for `keyboard.mp3`) rather than destructive audio file cuts; default to 90f for samples ≤3s to fade naturally. Audio durations must match visual actions (S4). **21 files in library exceed 5s and require explicit `durationInFrames`** to avoid trailing audio.
- **Volume Layering**: BGM 0.34 bed; SFX normal range 0.2–0.6 (click confirm 0.6 loudest, sequential pop tail 0.25 softest) to express hierarchical accent weight. **This range assumes assets peak near 0dB**: `volume` is a multiplier; quiet assets peaking <-12dB remain buried beneath BGM even at `volume=1.0`. Replace assets, pre-normalize, or apply >1 gain, verifying peak amplitude on rendered output.

#### Long Samples Requiring Explicit Truncation (>5s, 21 files)

| File | Duration | Usage |
|---|---|---|
| `scifi/scifi-computer-ambience` | 23.5s | Room tone / bed across full shot |
| `film/projector-spin-antique` | 21.7s | Room tone / loop, truncated to section |
| `text/keyboard` | 19.6s | Typing section (template cuts at 24f / 44f) |
| `text/write-blackboard` | 13.9s | Line drawing section, cut to stroke duration |
| `mech/mech-robotic-futuristic` | 9.6s | Assembly / morph sequence |
| `camera/camera-autofocus` | 9.6s | Autofocus, typically uses initial 10–20f |
| `paper/paper-book-browse-fast` | 9.3s | Rapid page turn, cut to page count |
| `scifi/space-intro-futuristic` | 8.1s | Opening atmosphere |
| `light/light-spell` | 8.0s | Illumination duration |
| `impact/impact-cine-big` | 7.9s | Landing with long reverb tail; do not clip abruptly |
| `scifi/tech-hum-futuristic` | 6.0s | Ambient room hum |
| `transition/wing-flutter` `swoosh-slow` `wind-pass-vibrate` | 5.0–5.7s | Camera moves, cut to move duration |
| `paper/paper-wind-blow` | 5.5s | Paper scatter sequence |
| `mech/metal-drop-scifi-small` | 5.5s | Landing with resonant tail |
| `light/light-aura` `light-transition-magic` | 5.1–5.5s | Light shimmer aftermath |
| `impact/impact-movie-epic` | 5.1s | Landing with long tail |
| `data/power-up-electronic` | 5.0s | Power-up / illumination sequence |
| `crowd/applause-rhythmic-loop` | 5.0s | Loopable applause |

Rule: **Ambience / Loops** span the entire shot; **Action foley** clips to action duration; **Impacts with reverb tails** decay naturally.

#### Soft-Recorded Assets (Peak < -12dB, 7 files)

`volume` is a multiplier, not target loudness. `volume={1}` merely plays the file at its original amplitude. If an asset is recorded at -24.6dB, `volume={1}` remains at -24.6dB. With BGM at 0.34 (~-9.4dB), `data-load-os` at 1.0 is 15dB softer than the music and completely masked.

| File | Peak | Below BGM (-9.4dB) | Multiplier to Overcome BGM (~-6dB) |
|---|---|---|---|
| `data/data-load-os` | -24.6dB | -15.2dB | ~8.5x |
| `text/pencil-write-short` | -22.7dB | -13.3dB | ~6.8x |
| `text/write-fast` | -20.0dB | -10.6dB | ~5.0x |
| `transition/wing-flutter` | -17.9dB | -8.5dB | ~3.9x |
| `camera/ui-zoom-in` | -14.3dB | -4.9dB | ~2.6x |
| `counter/clock-knob-spin` | -14.0dB | -4.6dB | ~2.5x |
| `counter/clock-tick-single` | -13.9dB | -4.5dB | ~2.5x |

Remedies in order of priority:
1. **Swap Asset (Preferred)**. Choose an alternative from the same category peaking near 0dB. Boosting quiet assets amplifies noise floors.
2. **Pre-Normalize**. Normalize with FFmpeg before importing:
   ```bash
   ffmpeg -i in.mp3 -af "loudnorm=I=-16:TP=-1.5" out.mp3
   ```
3. **Apply Gain > 1 via `volume`**. Remotion permits `volume > 1`: setting `volume={4}` yields ~+12dB. Note that **browser previews clamp to 1.0**; judge final loudness on rendered video. Verify that `max_volume` on output does not clip:
   ```bash
   ffmpeg -hide_banner -i out.mp4 -af volumedetect -f null /dev/null 2>&1 | grep max_volume
   ```

### 4.2 Eliminating Machine-Gun Repetition

Our pipeline uses no pitch-shifting `playbackRate` modulations. Burst sequences eliminate machine-gun repetition via three combined techniques (S2):

1. **Dual-Sample Alternation**: Alternate between two closely matched audio files (e.g. `pluck_002` / `pluck_001`).
2. **Stepped Volume Attenuation**: Linearly attenuate volume across the sequence (e.g. 0.40 -> 0.25 across 6 steps).
3. **Accelerate Spacing Along Animation Curve**: Compress intervals matching visual acceleration (8f -> 3f); when spacing becomes excessively tight, **fade into a single swoosh** rather than triggering discrete clicks.

### 4.3 The Riser → Impact → Sparkle Outro Phrase

Large hero moments (especially the outro) use a 3-beat cadence:

```
riser-cine (assembly starts) -> ~35f later impact-deep-whoosh (wordmark stamp, peak volume) -> 25f later sparkle (highlight shimmer)
```

In the template video (f945 -> f980 -> f1005), this sequence remained untouched through all visual passes. Other reusable cadences: Scene Entrance = `transition-soft`; Title Card Entrance = `swoosh-quick`; Click Confirmation = `click-camera` (highest SFX volume).

### 4.4 Rework Lessons: Sequence Accounting

The template video re-anchored SFX three times; two instances were collateral costs of visual adjustments (S3):

| Pass | Cause | Nature |
|---|---|---|
| 1 | Timbre misaligned (gaming pack -> cinematic vocabulary) | Necessary audio rework |
| 2 | Visual timeline updated (1020 -> 1085 frames), shifting all `from` values | **Cost of anchoring audio before visual lock** |
| 3 | Added animations in report section, rewriting local SFX | Same as above (local) |

**Rule: Design sound after visual timing is locked. Any change to shot duration or sequence must conclude with re-verifying the full SFX keyframe schedule** (S3).

### 4.5 Anchor Keyframes Relative to Shot Starts (Hard Rule)

Do not anchor SFX to absolute frame numbers across the video. Use relative offsets: `SHOTS.<shot>.from + offset` (or `beatF(n)` for rhythm cuts; see `music-beat-sync.md`). If an earlier shot changes duration, subsequent SFX automatically shift with their parent shot, eliminating manual re-anchoring.

### 4.6 Compensating for Audio-Visual Pipeline Offsets (Hard Rule)

Two physical latencies separate planned keyframes from rendered output:

```
Sequence.from = target_peak_frame - source_peak_latency_frames - output_audio_offset_frames
```

**Offset 1: Output Audio Track Latency (Empirically Measured per Pipeline).**
Rendered MP4 audio tracks exhibit fixed latency relative to video frames due to encoder priming (AAC priming typically adds 2048 samples = 1.28f @30fps at 48kHz; Remotion issue `#7099`). In AiflPromo, click latency measured 2032 samples and impact latency measured 2066 samples (~1.27–1.29f).
- **Log per Pipeline**: Determined by Remotion version + codec + sample rate + container; measure once per pipeline combination and document in specs.
- Measure via normalized cross-correlation: extract rendered audio via `ffmpeg -i out/promo.mp4 -vn -acodec pcm_s16le /tmp/render-audio.wav` and cross-correlate against 2–3 sharp source SFX files.

**Offset 2: Source Audio Peak Latency (Measured per File).**
Many assets peak after file start (gradual attack transients). For example: `brush-write` peaks at 2f, `paper-slide` at 10f, `ink-char` at 24f. Record internal peak offsets alongside `max_volume` in file catalogs.

Render Layer Implementation: Maintain `{ from, src, volume }` records, applying compensation dynamically in the calculation expression:

```tsx
// Pipeline benchmark: Remotion 4.x + AAC 48kHz MP4, measured via cross-correlation
const OUTPUT_AUDIO_OFFSET_F = 1.28;
const PEAK_F: Record<string, number> = { 'impact-deep-whoosh.mp3': 2 };
const sfxFrom = (targetPeakF: number, src: string) =>
  Math.max(0, Math.round(targetPeakF - (PEAK_F[src] ?? 0) - OUTPUT_AUDIO_OFFSET_F));
```

Boundary considerations:
- **Do not add offset to `durationInFrames`**: Moving the window shifts both start and end points identically.
- `Math.max(0, ...)` limits compensation for events within the first 2 frames of the video; avoid placing major impacts within frames 0–2.
- Soundtrack handling follows the same principle: keep `SOURCE_BEAT0` untouched as ground truth, applying output offset via `OUTPUT_AUDIO_OFFSET_SEC` (see `music-beat-sync.md` §5b).

Acceptance: Retest 2–3 probes via cross-correlation on rendered output; residuals ≤ 0.5f pass review.
