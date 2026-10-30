// Karaoke fill sync (karaoke-fill-sync) — as voiceover reads each word, it fills from left to right with highlight color.
// Two centered tagline lines "FRAME MOTION / CRAFT SHOTS" (four-word version of the video-shotcraft phrase "Frame motion. Craft the shot."),
// each word stacked with dual identical text layers: bottom layer is low-opacity ink for unread text,
// top layer is revealed linearly via mask based on word progress (per-word independent stacking; reveal percentage equals word progress without measuring text width;
// reveal leading edge is a +/-4% soft feather rather than a hard cut). Currently spoken word fills with accent color, fading to primary ink within 10f once read —
// accent color strictly belongs to "the present moment". Word-level schedule mimics speech pacing: FRAME 20-38, MOTION 42-75 (longer word read slower),
// CRAFT 85-103, SHOTS 107-130, with breath pauses between words.
// Reading indicator: 8px rounded accent underline beneath current word, right edge tracking fill progress; retracts left-to-right (6f) once read, leaving no line behind.
// Bottom voiceover waveform acts as a silent reference: rises during speech, drops on breath pauses, colored for played portion.
// 0-19f hold; 130-149f true freeze (final color fade / line retraction finishes before f140).
import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, ramp, tracking } from '../../_fixtures/Polish';

export const KARAOKE_FILL_SYNC_DURATION = 150;

type Word = { text: string; start: number; end: number };

const LINES: Word[][] = [
  [
    { text: 'FRAME', start: 20, end: 38 },
    { text: 'MOTION', start: 42, end: 75 },
  ],
  [
    { text: 'CRAFT', start: 85, end: 103 },
    { text: 'SHOTS', start: 107, end: 130 },
  ],
];
const ALL = LINES.flat();
const SIZE = 150;
const FEATHER = 4; // Reveal leading edge feather (%)
const ACC = [91, 99, 211]; // G.accent
const INK = [23, 24, 28]; // G.ink1

const rgbMix = (a: number[], b: number[], k: number) =>
  `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(',')})`;

const KaraokeWord: React.FC<{ word: Word; frame: number }> = ({ word, frame }) => {
  // Linear fill progress within word; clamp maintains state after completion (follows speech rate without easing)
  const p = interpolate(frame, [word.start, word.end], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const edge = p * (100 + FEATHER * 2) - FEATHER; // Feather center (%), fully hidden at p=0 and fully revealed at p=1
  const mask = `linear-gradient(90deg, #000 ${(edge - FEATHER).toFixed(2)}%, transparent ${(edge + FEATHER).toFixed(2)}%)`;
  const settle = ramp(frame, word.end, 10, EASE.out); // Settles to primary ink color after reading
  const fillColor = rgbMix(ACC, INK, settle);
  // Reading indicator: tracks leading edge while reading, retracts left-to-right over 6f when done
  const retract = ramp(frame, word.end, 6, EASE.swift);
  const showLine = frame >= word.start && retract < 1;
  return (
    <span style={{ position: 'relative', display: 'inline-block' }}>
      {/* Bottom layer: low-opacity ink for unread text */}
      <span style={{ color: 'rgba(23,24,28,0.13)' }}>{word.text}</span>
      {/* Top layer: soft-feather reveal from left to right tracking progress */}
      {p > 0 && (
        <span style={{
          position: 'absolute', inset: 0, color: fillColor,
          WebkitMaskImage: mask, maskImage: mask,
        }}>
          {word.text}
        </span>
      )}
      {/* Reading indicator underline: right edge follows fill progress, retracts from left when finished */}
      {showLine && (
        <span style={{
          position: 'absolute', bottom: -6, height: 8, borderRadius: 4,
          left: `${(retract * p * 100).toFixed(2)}%`,
          width: `${(Math.max(0, p - retract * p) * 100).toFixed(2)}%`,
          background: G.accent, boxShadow: '0 2px 10px rgba(91,99,211,0.35)',
        }} />
      )}
    </span>
  );
};

// Voiceover waveform: 48 vertical bars, enveloped by whether a word is currently being spoken, undulating via deterministic hash
const BARS = 48;
const WAVE_W = 560;
const WAVE_T0 = 14;
const WAVE_T1 = 136;
const h = (n: number) => {
  const s = Math.sin(n * 91.7 + 13.1) * 43758.5453;
  return s - Math.floor(s);
};
const speechAt = (f: number) => {
  let e = 0.06;
  for (const w of ALL) {
    const fadeIn = ramp(f, w.start - 2, 3, EASE.out);
    const fadeOut = 1 - ramp(f, w.end - 2, 4, EASE.out);
    e = Math.max(e, fadeIn * fadeOut);
  }
  return e;
};

export const KaraokeFillSync: React.FC = () => {
  const frame = useCurrentFrame();
  const playhead = (frame - WAVE_T0) / (WAVE_T1 - WAVE_T0);
  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden', fontFamily: FONT.sans }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.22 }} accent="#5b63d3" />

      {/* Tagline: two lines centered */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 0, bottom: 60,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        fontSize: SIZE, fontWeight: 800, letterSpacing: tracking(SIZE, true), lineHeight: 1.18,
      }}>
        {LINES.map((words, li) => (
          <div key={li} style={{ display: 'flex', gap: 56 }}>
            {words.map((w) => (
              <KaraokeWord key={w.text} word={w} frame={frame} />
            ))}
          </div>
        ))}
      </div>

      {/* Voiceover waveform: accent color for played portion, faint ink for unplayed portion */}
      <div style={{
        position: 'absolute', left: 960 - WAVE_W / 2, top: 860, width: WAVE_W, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {Array.from({ length: BARS }, (_, i) => {
          const u = i / (BARS - 1);
          const at = WAVE_T0 + u * (WAVE_T1 - WAVE_T0); // Timestamp corresponding to this bar
          const env = speechAt(at);
          const amp = 0.12 + env * (0.35 + 0.65 * h(i * 3 + 1));
          const played = u <= playhead;
          return (
            <div key={i} style={{
              width: 4, height: `${(amp * 100).toFixed(1)}%`, borderRadius: 2,
              background: played ? G.accent : 'rgba(23,24,28,0.16)',
              opacity: played ? 0.9 : 1,
            }} />
          );
        })}
      </div>
    </div>
  );
};
