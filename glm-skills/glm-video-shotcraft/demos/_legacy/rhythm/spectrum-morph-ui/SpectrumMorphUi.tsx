// spectrum-morph-ui — Spectrogram-style UI
// 8px ink underline (720px) beneath title "LAUNCH WEEK". At 25f splits into 28 vertical bars
// (20px wide, 6px gap); bar heights bounce via pseudo-FFT for 64f (envelope with high bass and lower treble),
// bottoms aligned with original line, growing upward. After two bars, collapses back to 8px line in 12f; true rest ≥35f after collapse.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

// Library-standard seed hash (frame-deterministic, no Math.random)
const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

const LINE_W = 720;
const LINE_H = 8;
const LINE_X = (1920 - LINE_W) / 2; // 600
const LINE_BOTTOM = 620; // Underline bottom y (bars grow upward from here)

const N_BARS = 28;
const GAP_MAX = 6;

const SPLIT = 25; // Split start frame
const SPLIT_DUR = 8; // Split & amplitude ramp-up
const DANCE = 64; // Dance for two measures
const COLLAPSE_START = SPLIT + DANCE; // 89
const COLLAPSE_DUR = 12;
const COLLAPSE_END = COLLAPSE_START + COLLAPSE_DUR; // 101 -> true rest 39f thereafter

const AMP = 92; // Theoretical peak 8 + 92 = 100px; wobble×jitter×env rarely maximize simultaneously, measured peak ~80px

// Envelope: higher on low frequencies, lower on high frequencies
const env = (i: number) => 0.4 + 0.6 * Math.pow(1 - i / (N_BARS - 1), 1.1);

export const SpectrumMorphUi: React.FC = () => {
  const frame = useCurrentFrame();

  const titleOp = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Amplitude ramp-up (spread -> out-cubic) and collapse (12f to zero)
  const rampIn = interpolate(frame, [SPLIT, SPLIT + SPLIT_DUR], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rampOut = interpolate(frame, [COLLAPSE_START, COLLAPSE_END], [1, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const amp = rampIn * rampOut;

  // Gap: 0->6 when splitting, 6->0 when collapsing (precisely merges into solid line at end of collapse)
  const gapIn = interpolate(frame, [SPLIT, SPLIT + SPLIT_DUR], [0, GAP_MAX], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const gapOut = interpolate(frame, [COLLAPSE_START, COLLAPSE_END], [GAP_MAX, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const gap = Math.min(gapIn, gapOut);
  const barW = (LINE_W - (N_BARS - 1) * gap) / N_BARS; // ≈20px when gap=6

  // Conditionally mount solid line outside bar phase (unmasking = conditional mount, ensuring pixel-perfect rest at end)
  const barsActive = frame >= SPLIT && frame < COLLAPSE_END;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          top: 330,
          width: '100%',
          textAlign: 'center',
          opacity: titleOp,
          fontFamily: 'Helvetica, Arial, sans-serif',
          fontWeight: 800,
          fontSize: 120,
          color: G.ink,
          letterSpacing: -1,
        }}
      >
        LAUNCH WEEK
      </div>

      {!barsActive && (
        <div
          style={{
            position: 'absolute',
            left: LINE_X,
            top: LINE_BOTTOM - LINE_H,
            width: LINE_W,
            height: LINE_H,
            background: G.ink,
            borderRadius: 4,
          }}
        />
      )}

      {barsActive &&
        Array.from({ length: N_BARS }).map((_, i) => {
          // Pseudo-FFT: |sin| oscillation × seed random shifted every 4 frames × frequency envelope × amplitude envelope
          const wobble = Math.abs(Math.sin(i * 0.7 + frame * 0.31));
          const jitter = 0.4 + 0.6 * h(i * 13 + Math.floor(frame / 4));
          const barH = LINE_H + AMP * wobble * jitter * env(i) * amp;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: LINE_X + i * (barW + gap),
                top: LINE_BOTTOM - barH, // Bottom aligned to original line, growing upward
                width: barW + (gap < 1 ? 0.5 : 0), // Add 0.5px when gap closes to 0 to prevent subpixel seams
                height: barH,
                background: G.ink,
                borderRadius: 3,
              }}
            />
          );
        })}
    </div>
  );
};
