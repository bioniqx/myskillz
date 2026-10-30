# music-beat-sync — BGM Rhythm Analysis & Beat-Sync Methodology

In promotional videos driven by strong rhythm, **all transitions and critical motion events must land squarely on the beat**. This document defines an end-to-end reproducible workflow from "receiving an audio track" to "post-render cut-point error ≤ 3 frames". Validated in production: a 70s, 18-shot, 131.97 BPM promotional video produced via this methodology achieved post-render retest errors ≤ 2.2f across all cut points (human perceptual threshold is ~3f).

## Table of Contents

- When to Activate
- Beat Grid Determination
- Transient Classification & Energy Structure
- Grid Acceptance Criteria & Artifacts
- Structuring Timelines via Beat Indices
- Post-Render Retesting
- Tooling Memo

## 0. When to Activate

In Stage 0, verify whether the user has designated a soundtrack:
- Music Selected → Follow this document: analyze rhythm first, then anchor storyboard cut points and motion cues to beat numbers.
- No Music Selected → Defer soundtrack selection to Stage 6 (see `pipeline.md`); pace the motion timeline to content semantics without forced beat syncing.

**Iron Law: Music Precedes Storyboard.** Do not storyboard until the beat grid passes acceptance. When durations conflict, adjust timing parameters; never mutate or delete user copy. Conduct all analysis in floating-point seconds; **conversion to discrete frames occurs solely at the final step entering Remotion** (premature rounding compounds errors throughout the pipeline).

## 1. Beat Grid Determination (Never Trust `beat_track` Tempo Scalars Alone)

Run a one-off script via `uv run --with librosa --with scipy --python 3.11`:

```python
import numpy as np, librosa

y, sr = librosa.load("bgm.mp3", sr=None, mono=True)
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, tightness=400, units="time")

# Key Step: Fit an equidistant grid to the beat sequence using ordinary least squares (OLS)
# to determine true BPM and phase. The scalar tempo returned by beat_track can deviate by 2%+
# (measured 129.2 vs true 131.97), but its timestamp sequence is solid.
# Fit a straight line: t_i = t0 + i * T
i = np.arange(len(beats))
A = np.vstack([i, np.ones_like(i)]).T
(T, t0), *_ = np.linalg.lstsq(A, beats, rcond=None)
bpm = 60.0 / T
residual = beats - (t0 + i * T)
print(f"BPM={bpm:.2f}  t0={t0:.4f}s  T={T:.5f}s  Residual ±{np.abs(residual).max()*1000:.0f}ms")
```

Acceptance Threshold: Residuals ≤ ±15ms (within half a frame at 30fps) indicate electronic/quantized percussion and a trustworthy grid. Large residuals suggest tempo variations requiring segmented piecewise fitting.

**Resolve Half-Time / Double-Time Ambiguity**: Beat tracking frequently oscillates between 0.5× and 2× (reporting 70 BPM as 140 BPM). Do not decide by subjective ear; evaluate drum data in §2. Under a correct grid, kicks land predominantly on integer beats; if kicks land half on integer beats and half on off-beats, the grid is likely running at double speed. Calculate candidate scores for 0.5×, 1×, and 2× per §3 metrics and select the highest coverage.

**Isolate Drum Stems for Dense Arrangements**: Thick vocals or bass obscure percussion attack transients, causing `beat_track` and onsets to drift. Use `librosa.effects.hpss` to isolate percussive components, or Demucs to isolate the drum stem completely (§6). Run all downstream detection on the isolated percussion stem.

## 2. Drum Classification and Energy Architecture (Deciding What Lands Where)

### 2a. Tri-Band Transient Detection

Different drum components drive distinct animation archetypes. Measure across separate frequency bands (on the drum stem or HPSS percussive component):

| Band | Frequency Range | Driven Motion Archetype |
|---|---|---|
| Kick | 40–160 Hz | Impact / Slam / Scale snap — moments where the canvas is "struck" |
| Snare | 150–500 Hz body + 1–3 kHz attack | Replacement / Flash cut / Framing cut — moments transitioning between ideas |
| Hi-Hat | 6–14 kHz | Micro-motion density — dense hi-hat patterns permit rapid micro-animations; sparse patterns demand restraint |

```python
from scipy.signal import butter, sosfilt

def band_env(y, sr, lo, hi):
    sos = butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    env = librosa.onset.onset_strength(y=sosfilt(sos, y), sr=sr)
    return env, librosa.times_like(env, sr=sr)

kick_env, times = band_env(y, sr, 40, 160)
# Extract energy at each integer beat to find peak hits:
for n in range(int((times[-1] - t0) / T)):
    t = t0 + n * T
    e = kick_env[np.argmin(np.abs(times - t))]
    # Log (beat n, energy e) to select top candidates for major slams
```

Save detections as a list of `{t: seconds, s: strength, k: category}` in project archives.

**Hit lists are candidate pools, not automated triggers.** Detected kicks do not require full-screen visual impacts. In driving electronic music, kicks occur on nearly every beat; firing full-screen slams on every kick causes visual fatigue and nausea (Aesthetic Rule R4). Map kick hits strictly to candidate pools for §2b's major slams (2–3 across the entire video); remaining kicks serve only as timing anchors for cuts and element-level animations without shaking the canvas.

### 2b. RMS Energy Curves & Sectional Architecture

Extract full-track RMS energy curves via `librosa.feature.rms` alongside transient density to isolate segment boundaries:

- **Musical Architecture Schedule**: Identifies when energy reaches full throttle and where breakdowns occur. Storyboard energy curves must track this structure (breakdowns naturally host brand breathing pauses); high-energy passages support concurrent multi-layer motion, while low-energy passages scale back to 1–2 layers.
- **Peak Hit Manifest**: Identify 2–3 peak slam beats (thematic reveal, climax, finale) to anchor critical moments.

**Common Failure Mode**: Placing a major slam on beat b52.5 (an off-beat) when the true kick transient lands on b52 causes post-render verification errors of +5.75f. In driving music, primary accents almost universally reside on integer beats; off-beat anchors require explicit envelope proof.

## 3. Grid Acceptance Criteria & Artifacts (Validate Before Storyboarding)

Align candidate grids (including 0.5×, 1×, 2×) against genuine transient onsets and evaluate four metrics:

| Metric | Meaning | Threshold |
|---|---|---|
| Match Ratio | Percentage of grid beats aligning with real transients | ≥ 98% |
| Mean Absolute Error | Average alignment deviation | < 10ms |
| Drift | Slope of linear regression of residuals over time | Cumulative < 5ms across entire track |
| Downbeat Validity | Beat 0 aligns with an authentic musical attack | Mandatory |

Select the winning grid based on metrics, documenting all candidates and selection rationale in the analysis archive. If uncertain, render a synthetic click track over the audio for auditory inspection, but let metrics decide.

Project Analysis Artifacts:

```text
analysis/
  beat_data.json    # bpm, t0, T, beats[], hits[{t,s,k}], rms[], sections[]
  grid_drift.json   # match ratio, errors, drift, and selection rationale for candidates
  click_*.wav       # candidate click tracks (optional, for auditory review)
```

Timestamps in `beat_data.json` remain floating-point seconds. Downstream tools depend on fields: `bpm`, `beats`, `hits`, `rms`, `sections`.

## 4. Structuring Timelines via Beat Indices

Store grid constants in the Remotion project and express shot boundaries and keyframes via `beatF()`:

```ts
export const FPS = 30;
export const SOURCE_BEAT0 = 0.2244;       // Source audio analysis t0 (seconds), matching beat_data.json
export const BEAT_INT = 0.45465;          // Interval T (seconds)
export const OUTPUT_AUDIO_OFFSET_SEC = 0; // Populated from post-render audio track offset (§5b)
export const beatT = (n: number) =>
  SOURCE_BEAT0 + OUTPUT_AUDIO_OFFSET_SEC + n * BEAT_INT;           // beat -> seconds
export const beatF = (n: number) => Math.round(beatT(n) * FPS);    // beat -> frames

export const SHOTS = {
  s0_open:  { from: 0,        to: beatF(8) },
  s1_slam:  { from: beatF(8), to: beatF(16) },
  // Each shot boundary is beatF(integer_beat); internal motion uses local beats:
};
export const localBeat = (shot: { from: number }, n: number) => beatF(n) - shot.from;
```

Advantages: Changing soundtracks requires modifying only two constants to re-sync the entire project; SFX keyframe tables also reference `beatF(n)`, sharing the single source of truth. Separate source analysis from rendering offset: `SOURCE_BEAT0` is the audited ground truth; encoding latencies enter only via `OUTPUT_AUDIO_OFFSET_SEC`.

**Anchor Binding Rules**:
- Dense regular cuts (every 1 or 2 beats) → Use winning grid `beatF(n)`.
- Sparse accents, isolated freezes → **Anchor to real transients**, not interpolated grid points.
- Finale freeze → Anchor to final true transient + RMS silence confirmation (avoids locking to reverb tails).
- Video assets and SFX align by **internal peak**, not file start: `asset_start = target_beat_time - (peak_time - trim_offset)`. Locate peaks via audio envelopes or FFmpeg frame differences.

Design Guidelines:
- Express shot durations in beats (4 or 8 beats per shot); accelerating passages may use half-beat or quarter-beat progressions (e.g. `CUT_BEATS = [48, 49.5, 50.5, 51, 51.25]`).
- Stepping shots (itemized lists, mosaic grids) map directly to beat numbers.
- When BGM drums are dense, practice SFX restraint: anchor only distinct visual actions, allow 2–3 major slams, and yield space to musical percussion.
- **Hard caps on full-frame impacts**: Impacts affecting full frame or camera (scale pumps, screen shakes, flash frames, negative inversions) are capped at ≤ 3 across the entire video, mapped 1:1 to §2b's peak hit manifest, separated by ≥ 16 beats. Beat-pump bursts are capped at ≤ 4 consecutive beats, ≤ 1 time per video, followed by a full resting hold.
  Count by set-piece technique application (one card use = one quota). Internal bursts within a card are governed by the card's documented limits.
- **Beat-synced animations default to the hero element layer** (cards, headings, counters); full frame and camera layers do not participate in per-beat pulsing.
- Structural motion (deformation, camera movement, transforms) uses continuous frame functions; impact events (appearances, cuts, flashes, snaps) trigger discretely on the designated frame. Multi-layer events hitting the same frame form an accent; deliberate offsets must be 1–2 frames and strictly intentional, never artifacts of rounding.

## 5. Post-Render Retesting (Mandatory Verification)

### 5a. Report Two Error Classes Independently

- **Audio Truth Error**: Distance between planned cut timestamp and true transient timestamp (seconds), validating the analysis pipeline. Thresholds: Mean < 5ms, 100% within ±33ms, 90% within ±15ms.
- **Visual Quantization Error**: Rounding error introduced when converting seconds to nearest renderable frame, validating frame-rate sufficiency. Recorded at each anchor point.

Rounding error limits are determined by FPS: ±16.7ms at 30fps, ±8.3ms at 60fps, ±4.2ms at 120fps. **Never claim < 5ms visual accuracy at 30fps.** If quantization error exceeds tolerance, increase frame rate rather than modifying audio analysis.

### 5b. Extract Audio from Rendered MP4 for Retesting

```bash
ffmpeg -i out/promo.mp4 -vn -acodec pcm_s16le /tmp/render-audio.wav
```

Rerun Step 1 grid fitting on the extracted audio track (measuring BGM from rendered video rather than raw source files to verify encoding and multiplexing latency), comparing:
**Designed Cut Frame vs. Nearest Measured Beat Frame**, generating an error table:

| Evaluation | Error |
|---|---|
| Pass | ≤ 3f (Perceptual Threshold) |
| Ideal | ≤ 1.5f |
| Must-Fix | Any cut > 3f |

Anchors exceeding tolerance must have beat numbers or frame offsets adjusted in Step 4, rerendering until all points pass.

**Systematic directional offsets indicate output audio track latency; do not adjust points manually.** If the error table displays a uniform directional shift across all points (+N frames everywhere), the root cause is output pipeline latency (AAC encoder priming typically introduces ~1.28f at 48kHz; see `sound-design.md` §4.6), not flawed beat detection. Diagnose via normalized cross-correlation between source BGM and rendered audio. Fix: **Declare output offset as a separate constant without modifying source analysis values**. Code structure:

```ts
export const SOURCE_BEAT0 = 0.2244;            // Source audio t0, matching beat_data.json, never contaminated by rendering offset
export const OUTPUT_AUDIO_OFFSET_SEC = 0.0427; // Output audio track offset measured empirically per pipeline (sound-design §4.6)
export const beatT = (n: number) => SOURCE_BEAT0 + OUTPUT_AUDIO_OFFSET_SEC + n * BEAT_INT;
```

All cuts shift uniformly via `beatT` without manual tweaking; SFX compensation references the same constant per `sound-design.md` §4.6. Visual desync of 2–3 frames causes impacts to detach from percussion, transforming deliberate sync into jarring camera jitter.

## 6. Tooling Memo

- librosa virtual environment: `uv run --with librosa --with scipy --python 3.11 script.py`
- When dense vocals/arrangements cause `beat_track` to drift: isolate percussive elements with `librosa.effects.hpss`, or separate drum stems using Demucs:
  `uvx --from demucs demucs --two-stems=drums -n htdemucs bgm.mp3 -o analysis/`, running §1 and §2 exclusively on `drums.wav`.
- Resolving ambiguous BPM across multiple methods: Cross-verify with madmom (RNN+DBN) or Essentia (RhythmExtractor2013). If discrepancies arise, resolve via transient coverage metrics (§3).
- Variable Tempo (DJ transitions, accelerando): Detect tempo inflection points via librosa local tempograms (~5s window), then fit piecewise grids per energy section with dedicated `t0` and `T` values.
