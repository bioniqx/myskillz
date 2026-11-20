# JianYing / CapCut Project Export: Final Video → Editable NLE Draft

Exports a Remotion timeline into a JianYing / CapCut project draft file, allowing users to fine-tune captions (content, size, color), retime/reorder/color-grade individual shots, or replace SFX and BGM directly within JianYing. Complex internal shot motion (procedural per-frame rendering) exceeds JianYing's asset + keyframe model and is baked into the video plate.

**Trigger condition**: After delivering the final video in any mode, inform the user once as item 3 of the delivery wrap-up steps — that the final video can be exported as an editable JianYing draft (to modify captions, retime shots, swap audio). Execute this workflow when requested; if the user explicitly specifies "export JianYing project", execute immediately without re-confirmation.

**Platform Prerequisites**: Verified on macOS JianYing Pro 11.2 (`jianying-export/mac_draft.py`); Windows version implemented per upstream spec but unverified on bare metal (`windows_draft.py`) — run a smoke test before first use (§6). Opening plaintext drafts in JianYing encrypts and saves them upon close (**one-way conversion**). If modifications are required, edit the export script and reinstall idempotently; never attempt to parse encrypted JianYing drafts backwards.

## 1. Layering Principles: What Is Editable vs. Baked

| Layer | Representation in JianYing | Editability |
|---|---|---|
| Internal shot motion (camera moves, particles, 3D, choreography) | Baked into plate video | Section retiming and color grading only |
| Shot boundaries | Plate split per shot (same file, distinct `source_timerange`) | Retime, reorder, cut |
| Screen-space subtitles / voiceover captions | Native JianYing text tracks | Content, font size, colors fully open |
| SFX / BGM | Native JianYing audio tracks (with volume) | Fully open |
| User-specified isolated overlays (logos, counters) | Optional Picture-in-Picture (PiP) layer | Position, scale, opacity |

Brand motion moments (custom title positioning, logo lockups) are baked by default — converting them to native JianYing text loses carefully tuned entrance curves. Only split them into text tracks upon explicit user request, explaining trade-offs.

## 2. Clean Plate Video Rendering

Add a `plate` inputProp to the Remotion project to render a clean plate **without subtitles, SFX, or BGM**. Captions use a `getInputProps()` gateway (avoiding prop drilling):

```tsx
// Top of caption component
import { getInputProps } from 'remotion';
const { plate } = getInputProps() as { plate?: boolean };
if (plate) return null;
```

```tsx
// Unified audio gating in Root
{bgm && !plate && <Audio src={staticFile('audio/bgm.mp3')} volume={0.72} />}
{!plate && SFX.map(...)}
```

```bash
npx remotion render src/index.ts <CompId> out/plate.mp4 \
  --props='{"bgm":false,"plate":true}'
```

After rendering, compare sample frames against the full video (via `ffmpeg -ss`): verify subtitles are stripped and remaining visual elements match frame-for-frame.

## 3. Extracting Timeline Data

Extract three schedules from Remotion project constants (`SHOTS` in `theme.ts`, `CAPTIONS` & `SFX` in `Main.tsx`). **Recalculate beat grids with float precision in Python** rather than rounding from comments:

```python
FPS = 30
BEAT0, BEAT_T = 0.0538, 0.47609        # Exactly matching theme.ts
def beatF(n): return round((BEAT0 + n * BEAT_T) * FPS)
def f2us(f): return round(f * 1_000_000 / FPS)   # frames -> microseconds
```

- **Shot Schedule** `(name, from_frame, to_frame)`: Copy `SHOTS` definitions (including non-integer beat boundaries locked to visual transients).
- **Caption Schedule** `(chinese, english, from_frame, to_frame)`: Copy arguments from shot caption components; **merge adjacent identical text into a single segment** (cross-shot continuity).
- **SFX Schedule** `(file, target_beat, peak_sec, volume)`: Copy keyframe tables from Root. JianYing plays audio from placement timestamps; **do not include Remotion-side output audio track offset compensation** (which compensates for Remotion render pipeline encoding offsets, see sound-design §4.6, irrelevant to JianYing playback): `start_f = beatF(beat) - round(peak_sec * FPS)`.
  Preserve explicit duration cuts for long samples (e.g. impact reverb tails).

**Microsecond Boundary Rule**: Adjacent segment Timeranges must calculate start and end independently before subtracting (`Timerange(f2us(f0), f2us(f1) - f2us(f0))`). Rounding start and duration separately can introduce 1µs gaps/overlaps, triggering `SegmentOverlap` exceptions in `pyJianYingDraft`.

## 4. Track Construction (pyJianYingDraft 0.3.x)

Environment: `python3.11 -m venv .venv && pip install pyJianYingDraft`; thumbnail extraction requires ffmpeg. Track layout skeleton:

```python
import pyJianYingDraft as draft

folder = draft.DraftFolder(STAGING)          # Build in staging directory first
script = folder.create_draft(NAME, 1920, 1080, fps=FPS, allow_replace=True)
script.append_track(draft.TrackSpec(draft.TrackType.video, name="Plate"))
script.append_track(draft.TrackSpec(draft.TrackType.audio, name="BGM"))
script.append_track(draft.TrackSpec(draft.TrackType.text, name="CaptionsEN"))
script.append_track(draft.TrackSpec(draft.TrackType.text, name="CaptionsZH"))

# Plate slicing: source=target identical intervals -> each slice independently retimable
plate = draft.VideoMaterial(PLATE)
for _name, f0, f1 in SHOTS:
    rng = draft.Timerange(f2us(f0), f2us(f1) - f2us(f0))
    script.add_segment(draft.VideoSegment(plate, rng, source_timerange=rng),
                       "Plate")

# SFX: Remotion auto-mixes overlapping audio, but JianYing forbids overlapping segments on the same track -> greedy lane allocation
sfx_segs = []
for file, beat, peak_sec, volume in SFX:
    mat = draft.AudioMaterial(os.path.join(SFX_DIR, file))
    start_f = max(0, beatF(beat) - round(peak_sec * FPS))
    dur_us = min(f2us(cut_frames), mat.duration, f2us(TOTAL_F - start_f))
    sfx_segs.append((f2us(start_f), dur_us, mat, volume))
lanes, placed = [], []
for start, dur, mat, volume in sorted(sfx_segs):
    lane = next((i for i, end in enumerate(lanes) if end <= start), len(lanes))
    if lane == len(lanes): lanes.append(0)
    lanes[lane] = start + dur
    placed.append((lane, start, dur, mat, volume))
for i in range(len(lanes)):
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name=f"SFX{i+1}"))
for lane, start, dur, mat, volume in placed:
    script.add_segment(draft.AudioSegment(mat, draft.Timerange(start, dur),
                                          volume=volume), f"SFX{lane+1}")

# BGM segment (volume matching Root)
bgm = draft.AudioMaterial(BGM)
script.add_segment(draft.AudioSegment(
    bgm, draft.Timerange(0, min(bgm.duration, f2us(TOTAL_F))), volume=0.72),
    "BGM")

# Bilingual subtitles split across two tracks: a text segment supports only one font size
for zh, en, f0, f1 in CAPTIONS:
    rng = draft.Timerange(f2us(f0), f2us(f1) - f2us(f0))
    script.add_segment(draft.TextSegment(zh, rng, **ZH_STYLE), "CaptionsZH")
    script.add_segment(draft.TextSegment(en, rng, **EN_STYLE), "CaptionsEN")
script.save()
```

**Caption Style Conversion** (Empirically calibrated on macOS 11.2):

- JianYing `TextStyle(size=...)` units ≈ **percentage of canvas height**: size 15 renders at ≈150px @1080p. CSS pixel size / 10.8 ≈ JianYing size (64px → 6.0).
- `ClipSettings(transform_y=t)` normalized to half-height: `screen_y = 540 * (1 - t)`:
  bottom subtitle zone t ≈ -0.70 (y≈915) / -0.825 (y≈985).
- Scrim background uses `TextBackground(color="#FFFFFF", alpha=0.82, round_radius=0.35)`; colors are 0–1 float triplets (`#2C2C2C` → `(0.173,)*3`).
- Unspecified fonts fall back to JianYing defaults; inform user they can adjust typography in JianYing.

## 5. Installing into JianYing Drafts Library

```python
import mac_draft                      # macOS; use windows_draft on Windows
info = mac_draft.macify(draft_dir, DRAFT_NAME)   # macOS adaptations + asset packaging
bak = mac_draft.install(draft_dir, DRAFT_NAME, info)
```

Three macOS gotchas handled by `mac_draft.py`: entry file named `draft_info.json`; meta `draft_materials(type 0)` must register all media assets (otherwise "Media Missing" triggers); sandboxed apps can only access `~/Movies`, requiring media to be bundled into draft `Resources/` (otherwise permission errors occur).

macOS requires device fingerprints (device_id, etc.), which the module automatically extracts from existing unencrypted drafts. **A fresh machine without plaintext drafts will cause `macify` to halt with an error**. Provide `donor_draft` or pass `allow_missing_fingerprint=True` experimentally.

Windows: `windows_draft.install(draft_dir, DRAFT_NAME)`, no registry required; restart JianYing if drafts list does not refresh.

**Ensure user fully quits JianYing before installation** (Cmd+Q; osascript quit is ignored by JianYing; do not force kill). Uninstall via `mac_draft.uninstall(name)`.

## 6. Verification and Acceptance

1. Script self-check: reads installed `draft_info.json` to verify track count, segment count, duration; verifies media registration via `os.path.exists` within draft directory.
2. User verification: smooth full playback, SFX aligned to beats; double-click captions to modify text/size/color; retime any plate segment.
3. First-time use on new machine or version: run `jianying-export/smoke_test.py` first (minimal 3-track draft injection) to confirm draft loads cleanly.
4. Delivery clarification: JianYing encrypts drafts upon save (one-way); to alter caption setups or shot cuts, modify parameters in export script and reinstall.
5. **Privacy**: macOS draft platform fields contain machine identifiers (device_id, hard_disk_id, mac_address). **Do not distribute self-contained draft folders to third parties**; deliver rendered MP4s publicly. If editable drafts are required on another machine, re-export locally on that machine.
