// beat-step-list-theme-cycle (bear 22.3–24.6s) — Three-channel metronome: adjective list steps up one row per beat,
// fixed center capsule "catches" new word and shifts color, overall canvas background color shifts on the same beat; line, color, and scene lock to the same beat.
//
// Redesign (look = custom "5-theme dark skin cycle" · video-shotcraft theme preset teaser):
// - Sentence layout: static light "Make it" (132px / 300) on left + adjective in capsule on right (132px),
//   reading "Make it modern -> playful -> expressive -> BOLD -> yours.", with final beat landing on the tagline.
// - Each theme = capsule color + background color + capsule text color + active word typography (sans / rounded / serif italic /
//   all-caps Futura), jumping synchronously per beat — skins express multiple product personalities rather than just color swaps.
// - Capsule functions as a "lens": outside the capsule is a unified dim white sans list; inside is a clipped duplicate (dark text + theme font).
//   A word changes color/typography only as it crosses the capsule edge, avoiding glitches like darkening before entering. Capsule width tracks
//   measured word width (interpolated via the same tInBeat clock), avoiding an awkward half-empty pill.
// - Background is layered: base color + large halo matching capsule hue (synced to clock) + top-left cool white key light + vignette + grain;
//   list fades opacity, size, and blur based on distance from viewport center (scroll wheel depth of field); jumps carry vertical motion blur.
// - Fourth visual echo: top-right "THEME 03 / 05" counter and bottom-left 5 swatches all transition on the same integer beat.
//
// Timeline (30fps, 140f total):
//   0–16    Intro: "Make it" and list float in from blur, capsule expands horizontally (snappy)
//   16–30   Establishing pause (slow push-in 1.0->1.03 throughout), allowing viewer to parse list
//   30/48/66/84  Four beats (BEAT_LEN 18f ~ 100 BPM): 6f sharp ease-out jump + squash at beat onset, 12f rest
//   84–96   Final beat aftermath: tagline row "Your product, in motion." rises word-by-word
//   96–140  Hold: settles on "Make it yours." yellow / deep navy final poster
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { FONT, Grain, SpeedBlur, Vignette, mix, ramp, velocity, EASE } from '../../_fixtures/Polish';
import { SERIF, TextReveal, alpha } from '../../_fixtures/Look';
import { PITCH, ShotcraftWordmark } from '../../_fixtures/Brand';

export const BEAT_STEP_LIST_THEME_CYCLE_DURATION = 140; // Intro 30f + 4 beats x 18f + post-final hold 38f

const ROW_H = 176;
const FS = 132; // Adjective font size
const CY = 520; // Viewport center row (slightly above center to leave room for bottom swatches / tagline)
// Pad two unselected words above and below: 'modern' starts centered, final beat stops at 'yours.' with words still padded below
const WORDS = ['minimal', 'clean', 'modern', 'playful', 'expressive', 'bold', 'yours.', 'timeless', 'quiet'];
const START_IDX = 2; // modern

// Beat points: ~0.6s per beat = 18 frames
const BEAT_LEN = 18;
const FIRST_BEAT = 30;
const N_BEATS = 4;
const JUMP = 6; // Jump window: 6f at beat onset, remaining 12f completely resting

// Layout: "Make it" + capsule horizontally centered using median pill width; capsule width tracks selected word (interpolated via same clock)
const PILL_H = 156;
const PAD_L = 64; // Capsule inner left padding
const PAD_R = 76; // Slightly larger right padding (optical centering: lowercase words have right whitespace)
const LEAD_W = 470; // "Make it" placeholder width
const GAP = 34;
const MID_PILL = 560;
const LEFT = (1920 - (LEAD_W + GAP + MID_PILL)) / 2; // 428
const PILL_X = LEFT + LEAD_W + GAP; // 932
const WORD_X = PILL_X + PAD_L; // Left alignment origin inside capsule
const MARGIN = 128; // Corner safe area margin

// Word layout box: full row height, left-aligned, vertically centered (shared by outer list and lens capsule for pixel-perfect alignment)
const wordBox: React.CSSProperties = {
  position: 'absolute', top: 0, height: ROW_H, display: 'flex', alignItems: 'center',
  fontSize: FS, lineHeight: 1, letterSpacing: '-0.035em', whiteSpace: 'nowrap', transformOrigin: '0% 50%',
};

// Theme fonts (system font stack; ui-rounded unsupported in Chrome so Arial Rounded is used; falls back to sans)
const ROUNDED = `"Arial Rounded MT Bold", "SF Pro Rounded", ${FONT.sans}`;
const GEOMETRIC = `Futura, "Avenir Next", ${FONT.sans}`;

// ink = measured word width (measured on 1080p render frame at 132px), capsule width = ink + left/right padding
type Theme = { name: string; pill: string; bg: string; ink: string; inkW: number; font: React.CSSProperties };
// Initial state + four beats; adjacent background colors share lightness across hues (all ~ L6–9 dark field); capsule and background form paired contrast tones
const THEMES: Theme[] = [
  { name: 'Bone', pill: '#ece6da', bg: '#15120f', ink: '#17130f', inkW: 425, font: { fontFamily: FONT.sans, fontWeight: 700 } },
  { name: 'Tangerine', pill: '#ff8a3d', bg: '#1d0e17', ink: '#260e03', inkW: 384, font: { fontFamily: ROUNDED, fontWeight: 700, letterSpacing: '-0.03em' } },
  { name: 'Iris', pill: '#9d8aff', bg: '#0f0d25', ink: '#120b36', inkW: 540, font: { fontFamily: SERIF, fontWeight: 600, fontStyle: 'italic', letterSpacing: '-0.02em' } },
  { name: 'Mint', pill: '#38d690', bg: '#06181a', ink: '#03150d', inkW: 376, font: { fontFamily: GEOMETRIC, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.01em' } },
  { name: 'Sun', pill: '#ffd43b', bg: '#0f1834', ink: '#1a1404', inkW: 352, font: { fontFamily: FONT.sans, fontWeight: 800 } },
];

// In-beat step: steep ease-out (exponent 3.2), completes within 6 frames
const snap = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3.2);

const hex = (a: string) => [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
const mixRgb = (a: string, b: string, t: number) => {
  const pa = hex(a);
  const pb = hex(b);
  return pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
};
const css = (c: number[], a = 1) => (a >= 1 ? `rgb(${c.join(',')})` : `rgba(${c.join(',')},${a.toFixed(3)})`);
const lighten = (c: number[], k: number) => c.map((v) => Math.round(v + (255 - v) * k));
const darken = (c: number[], k: number) => c.map((v) => Math.round(v * (1 - k)));

// Unified clock: triggered beats + in-beat progress (step only occupies beat onset JUMP frames) — all three channels sample from here
const clock = (frame: number) => {
  const raw = (frame - FIRST_BEAT) / BEAT_LEN;
  const beat = Math.min(N_BEATS, Math.max(0, Math.floor(raw) + 1));
  const beatStart = FIRST_BEAT + (beat - 1) * BEAT_LEN;
  const tInBeat = beat === 0 ? 1 : snap((frame - beatStart) / JUMP);
  const step = beat === 0 ? 0 : beat - 1 + tInBeat; // Continuous step amount
  return { beat, tInBeat, step, sinceBeat: beat === 0 ? 99 : frame - beatStart };
};

export const BeatStepListThemeCycle: React.FC = () => {
  const frame = useCurrentFrame();
  const { beat, tInBeat, step, sinceBeat } = clock(frame);

  // Three channels — 1) List shifts up one row
  const listY = -step * ROW_H;
  const vy = velocity((f) => -clock(f).step * ROW_H, frame); // px/frame for motion blur

  // 2) Capsule / 3) Background color: cross-mixed per channel using the same tInBeat
  const prev = THEMES[Math.max(0, beat - 1)];
  const now = THEMES[beat];
  const mixT = beat === 0 ? 1 : tInBeat;
  const pill = mixRgb(prev.pill, now.pill, mixT);
  const bg = mixRgb(prev.bg, now.bg, mixT);
  const bgColor = css(bg);
  const pillW = mix(prev.inkW, now.inkW, mixT) + PAD_L + PAD_R;

  // Capsule landing squash: vertical 1.14->0.96->1, horizontal inverted 0.97->1.01->1 (volume conservation), completes over beat onset 6f
  const sy = beat === 0 ? 1 : interpolate(tInBeat, [0, 0.6, 1], [1.14, 0.96, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const sx = beat === 0 ? 1 : interpolate(tInBeat, [0, 0.6, 1], [0.97, 1.01, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  // Flash highlight + glow expansion on catch, decaying exponentially over 8f
  const hit = beat === 0 ? 0 : Math.exp(-sinceBeat / 3.2);

  // Intro (0–16f): capsule unfolds horizontally, text emerges from blur
  const open = ramp(frame, 2, 16, EASE.snappy);
  const listIn = ramp(frame, 4, 18, EASE.out);

  // Continuous subtle push-in (1.0->1.03, smooth start/stop without velocity spikes)
  const cam = mix(1, 1.03, ramp(frame, 0, BEAT_STEP_LIST_THEME_CYCLE_DURATION, EASE.smooth));

  const listPos = START_IDX + step; // Continuous row index corresponding to viewport center

  // Final beat aftermath: tagline rises word by word
  const LAST = FIRST_BEAT + (N_BEATS - 1) * BEAT_LEN;

  return (
    <AbsoluteFill style={{ background: bgColor, overflow: 'hidden', fontFamily: FONT.sans }}>
      {/* Scene: top-left cool white key light + large halo matching capsule hue (synced to clock) */}
      <AbsoluteFill style={{
        background:
          `radial-gradient(ellipse 60% 70% at 62% ${(CY / 1080) * 100}%, ${css(pill, 0.2 + 0.06 * hit)} 0%, ${css(pill, 0.06)} 45%, ${css(pill, 0)} 75%),` +
          `radial-gradient(ellipse 55% 55% at 18% 0%, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0) 70%)`,
      }} />

      <AbsoluteFill style={{ transform: `scale(${cam})`, transformOrigin: `${PILL_X}px ${CY}px` }}>
        {/* Word list (outer layer): unified dim white sans, fading with distance; vertical motion blur at beat jumps, filter disabled on resting frames */}
        <SpeedBlur vx={0} vy={vy} amount={0.16} max={9}>
          <div style={{
            position: 'absolute', left: 0, right: 0, top: CY - ROW_H / 2 - START_IDX * ROW_H,
            transform: `translateY(${(listY + (1 - listIn) * 40).toFixed(2)}px)`,
          }}>
            {WORDS.map((w, i) => {
              const d = Math.abs(i - listPos); // Distance from viewport center in rows (continuous)
              const op = Math.max(0, 0.42 - 0.15 * Math.max(0, d - 1)) * listIn;
              const sc = 1 - Math.min(0.14, 0.05 * Math.max(0, d - 0.5));
              const blur = Math.max(0, d - 1.2) * 3.5 + (1 - listIn) * 10;
              return (
                <div key={w} style={{ height: ROW_H, position: 'relative' }}>
                  <span style={{
                    ...wordBox, left: WORD_X, fontFamily: FONT.sans, fontWeight: 700,
                    color: `rgba(255,255,255,${op.toFixed(3)})`,
                    transform: `scale(${sc.toFixed(4)})`,
                    filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : undefined,
                  }}>{w}</span>
                </div>
              );
            })}
          </div>
        </SpeedBlur>

        {/* Fixed center capsule = lens: list scrolls beneath it, capsule holds clipped duplicate (dark text + theme font);
            text changes color/font only upon crossing the capsule boundary — visually "capsule jumps to next row and catches new word" */}
        <div style={{
          position: 'absolute', left: PILL_X, top: CY - PILL_H / 2, width: pillW, height: PILL_H,
          transformOrigin: '0% 50%', transform: `scale(${(sx * mix(0.55, 1, open)).toFixed(4)}, ${sy.toFixed(4)})`,
          opacity: Math.min(1, open * 2.5), borderRadius: PILL_H / 2, overflow: 'hidden',
          background: `linear-gradient(180deg, ${css(lighten(pill, 0.16 + 0.07 * hit))} 0%, ${css(lighten(pill, 0.03 * hit))} 50%, ${css(darken(pill, 0.1))} 100%)`,
          boxShadow: [
            'inset 0 2px 0 rgba(255,255,255,0.5)',
            'inset 0 -3px 8px rgba(0,0,0,0.12)',
            '0 3px 6px rgba(0,0,0,0.35)',
            `0 30px 90px -20px ${css(pill, 0.5 + 0.25 * hit)}`,
            `0 0 ${(40 + 60 * hit).toFixed(1)}px ${css(pill, 0.18 + 0.2 * hit)}`,
          ].join(', '),
        }}>
          <SpeedBlur vx={0} vy={vy} amount={0.16} max={9}>
            <div style={{
              position: 'absolute', left: 0, right: 0, top: PILL_H / 2 - ROW_H / 2 - START_IDX * ROW_H,
              transform: `translateY(${listY.toFixed(2)}px)`,
            }}>
              {WORDS.map((w, i) => {
                const k = i - START_IDX;
                const th = k >= 0 && k < THEMES.length ? THEMES[k] : null;
                return (
                  <div key={w} style={{ height: ROW_H, position: 'relative' }}>
                    <span style={{
                      ...wordBox, left: PAD_L, fontFamily: FONT.sans, fontWeight: 700, ...(th ? th.font : null),
                      color: th ? th.ink : THEMES[0].ink, opacity: Math.min(1, open * 2),
                    }}>{w}</span>
                  </div>
                );
              })}
            </div>
          </SpeedBlur>
          {/* Capsule top rim light: soft highlight along upper edge overlaying text to seat it inside capsule */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: PILL_H * 0.45, background: 'linear-gradient(rgba(255,255,255,0.18), rgba(255,255,255,0))', pointerEvents: 'none' }} />
        </div>

        {/* "Make it": static anchor, light weight + right-aligned against capsule */}
        <div style={{
          position: 'absolute', left: LEFT, width: LEAD_W, top: CY - FS * 0.62, textAlign: 'right',
          fontSize: FS, fontWeight: 300, letterSpacing: '-0.035em', lineHeight: 1.2, color: 'rgba(255,255,255,0.94)',
          whiteSpace: 'nowrap',
        }}>
          <TextReveal text="Make it" by="word" variant="blur" start={2} each={16} gap={4} />
        </div>
      </AbsoluteFill>

      {/* Top/bottom viewport fade: synchronized with bgColor to avoid edge artifacts */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 300, background: `linear-gradient(${bgColor} 34%, ${css(bg, 0)})` }} />
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 330, background: `linear-gradient(${css(bg, 0)}, ${bgColor} 62%)` }} />

      {/* Header: brand + theme counter (tied to same integer beat, scrolls vertically over 6f at onset) */}
      <div style={{ position: 'absolute', left: MARGIN, top: 96, opacity: ramp(frame, 0, 12, EASE.out) }}>
        <ShotcraftWordmark size={30} markScale={1.6} gap={14} tone="dark" />
      </div>
      <div style={{
        position: 'absolute', right: MARGIN, top: 98, display: 'flex', alignItems: 'baseline', gap: 18,
        opacity: ramp(frame, 0, 12, EASE.out), fontVariantNumeric: 'tabular-nums',
      }}>
        <span style={{ fontSize: 24, fontWeight: 600, letterSpacing: '0.16em', color: 'rgba(255,255,255,0.5)' }}>THEME</span>
        <span style={{ display: 'inline-block', height: 38, overflow: 'hidden', fontFamily: FONT.mono, fontSize: 32, fontWeight: 500, color: '#fff' }}>
          <span style={{ display: 'block', transform: `translateY(${(-(beat - 1 + (beat === 0 ? 1 : tInBeat)) * 38).toFixed(2)}px)` }}>
            {THEMES.map((_, k) => <span key={k} style={{ display: 'block', height: 38, lineHeight: '38px' }}>{String(k + 1).padStart(2, '0')}</span>)}
          </span>
        </span>
        <span style={{ fontFamily: FONT.mono, fontSize: 32, color: 'rgba(255,255,255,0.4)' }}>/ 05</span>
      </div>

      {/* Bottom-left: 5 color swatches, active theme enlarged + ringed (state switches on integer beat, springs in 6f) */}
      <div style={{ position: 'absolute', left: MARGIN, top: 900, display: 'flex', alignItems: 'center', gap: 22 }}>
        {THEMES.map((t, k) => {
          const cur = k === beat;
          const pop = cur ? (beat === 0 ? 1 : interpolate(tInBeat, [0, 0.6, 1], [0.7, 1.12, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })) : 1;
          const appear = ramp(frame, 6 + k * 2, 12, EASE.overshoot);
          return (
            <div key={t.name} style={{
              width: 46, height: 46, borderRadius: 23, background: t.pill,
              transform: `scale(${((cur ? 1 : 0.62) * pop * appear).toFixed(4)})`, opacity: cur ? 1 : k < beat ? 0.55 : 0.32,
              boxShadow: cur ? `0 0 0 5px ${bgColor}, 0 0 0 7px rgba(255,255,255,0.85), 0 0 30px ${alpha(t.pill, 0.6)}` : 'none',
            }} />
          );
        })}
        <span style={{
          marginLeft: 18, fontSize: 32, fontWeight: 600, color: 'rgba(255,255,255,0.88)', letterSpacing: '-0.01em',
          opacity: ramp(frame, 8, 12, EASE.out),
        }}>{now.name}</span>
      </div>

      {/* Final beat aftermath: tagline rises word-by-word, aligned bottom-right to capsule edge */}
      <div style={{
        position: 'absolute', right: MARGIN, top: 896, fontSize: 40, fontWeight: 500,
        color: 'rgba(255,255,255,0.72)', letterSpacing: '-0.015em', whiteSpace: 'nowrap',
      }}>
        <TextReveal text={PITCH.en.taglines[5]} by="word" variant="rise" start={LAST + 6} each={16} gap={3} />
      </div>

      <Vignette strength={0.5} inner={0.42} color="#020306" />
      <Grain opacity={0.09} blend="soft-light" />
    </AbsoluteFill>
  );
};
