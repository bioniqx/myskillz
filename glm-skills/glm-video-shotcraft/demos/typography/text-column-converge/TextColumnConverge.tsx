// text-column-converge — raycast-teams (measured source 28–36s) remake:
// Original footage measurements (1280w): NEW left edge fixed at x=412, feature words right edge fixed at x=867;
// Margins from both words to screen edges are equal (412 vs 413), gap does not shrink during cycling;
// Only once the word cycles to RAYCAST does the single convergence happen — ~1.2s ease-in-out continuous slide
// (left edge 412→554 / right edge 867→725), "NEW RAYCAST" settles centered on screen midline;
// ~0.6s after settling, italic "COMING 2026" appears below in a near-hard-cut.
// (Measurements from original footage; demo content updated to video-shotcraft: feature words cycle -> converge to "NEW video-shotcraft",
//  subtext is brand tagline ending "CRAFT THE SHOT."; convergence target recomputed for wordmark length.)
//
// Polish upgrades (tempo / fixed anchors / single convergence preserved):
// - Dark backdrop is no longer dead black #050506: cool deep base + subtle overhead spotlight above midline + vignette + soft-light grain.
// - 1-frame flash on word swap (typewriter carriage-return effect from original; >1f reads as a glitch so kept to 1f).
// - NEW starts as secondary gray during cycling (like an index tab), ramping to match feature word color during convergence — unifying into one sentence.
// - Convergence sliding gets horizontal motion blur based on real velocity (opposing directions), 0 at rest; soft background glow fades in after landing.
// - Italic subtext dropped to tertiary color for clear hierarchy; exported duration constant added (original workbench inferred 16f, keeping only 0.5s).
import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { FONT, Grain, SpeedBlur, Vignette, ramp, EASE } from '../../_fixtures/Polish';

// Word cycle table: variable hold frames (mechanical cadence), anchored to right edge throughout, no gap shrinking
// Content tailored for video-shotcraft: 8 feature words cycling, ending in lowercase wordmark video-shotcraft (brand spec: no all-caps)
const BRAND_WORD = 'video-shotcraft';
const STEPS: { word: string; dur: number }[] = [
  { word: 'SHOT RECIPE CARDS', dur: 16 },
  { word: 'PAGE CAPTURES', dur: 12 },
  { word: '2.5D CAMERA MOVES', dur: 9 },
  { word: 'BEAT-SYNCED CUTS', dur: 8 },
  { word: 'FILM-GRADE SFX', dur: 7 },
  { word: 'MOTION WORKBENCH', dur: 8 },
  { word: 'REMOTION RENDER', dur: 10 },
  { word: 'JIANYING EXPORT', dur: 12 },
  { word: BRAND_WORD, dur: 999 }, // Final word: triggers single convergence after settling
];

const START = 8; // Opening hold on black

// Original 1280w -> 1920w scaling (×1.5)
const NEW_LEFT_EDGE = 618; // 412×1.5: NEW left edge (= left screen margin)
const WORD_RIGHT_EDGE = 1302; // 868×1.5: feature word right edge (= right screen margin, 1920-1302=618 symmetric)

const FS = 42; // Original type scale is small (cap height ~20px @720p -> ~30px @1080p -> font size ~42)
const LSP = 3; // letterSpacing
// Convergence destination computed from actual font advance (monospaced: 0.6em + letterSpacing),
// ensuring "NEW video-shotcraft" meshes with exactly one space, centered at 960 without overlap
const ADV = 0.6 * FS + LSP; // Advance per character
const LINE_W = (4 + BRAND_WORD.length) * ADV; // "NEW " + wordmark, 19 characters total
const MERGED_LEFT = 960 - LINE_W / 2; // NEW left edge after convergence
const MERGED_RIGHT = 960 + LINE_W / 2; // Wordmark right edge after convergence
const CONVERGE_DUR = 36; // Convergence duration: original ~1.2s ≈ 36 frames
const CONVERGE_DELAY = 10; // Pause 10 frames after wordmark settles before converging (original 32.4→32.7s)
const SUB_DELAY = 18; // ~0.6s hold after convergence before italic subtext appears

// 8f black + 82f cycling + 10f settle + 36f converge + 18f hold + 4f subtext + 22f rest = 180f (6.0s)
export const TEXT_COLUMN_CONVERGE_DURATION = 180;

const INK = '#eeeef2';
const INK_NEW = '#8a8c96'; // Secondary gray for NEW during cycling
const INK_SUB = '#a3a5ae';

// Convergence progress (frame-dependent, for velocity calculation)
const LAST_START = START + STEPS.slice(0, -1).reduce((a, s) => a + s.dur, 0);
const cvAt = (frame: number) =>
  interpolate(frame - LAST_START - CONVERGE_DELAY, [0, CONVERGE_DUR], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

// Simple hex blend (NEW brightens from secondary gray to primary ink)
const mixHex = (a: string, b: string, t: number) => {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return `rgb(${pa.map((v, k) => Math.round(v + (pb[k] - v) * t)).join(',')})`;
};

export const TextColumnConverge: React.FC = () => {
  const f = useCurrentFrame();
  const t = f - START;

  // Locate current step
  let acc = 0;
  let idx = 0;
  let stepStart = 0;
  for (let i = 0; i < STEPS.length; i++) {
    if (t >= acc) { idx = i; stepStart = acc; }
    acc += STEPS[i].dur;
  }
  const cur = STEPS[idx];
  const isLast = idx === STEPS.length - 1;
  const local = t - stepStart;

  // Single convergence: ease-in-out continuous slide after wordmark settles for CONVERGE_DELAY frames
  const cvT = isLast ? local - CONVERGE_DELAY : -1;
  const cv = interpolate(cvT, [0, CONVERGE_DUR], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  // NEW left edge: 618 → 692; feature word right edge: 1302 → 1228
  const newLeft = interpolate(cv, [0, 1], [NEW_LEFT_EDGE, MERGED_LEFT]);
  const wordRight = interpolate(cv, [0, 1], [WORD_RIGHT_EDGE, MERGED_RIGHT]);

  const converged = cv >= 1;

  // Italic subtext: SUB_DELAY frames after convergence settles, near-hard-cut (4-frame quick fade, no shift)
  const subT = converged ? cvT - CONVERGE_DUR - SUB_DELAY : -1;
  const subOp = interpolate(subT, [0, 4], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const visible = t >= 0;

  const font: React.CSSProperties = {
    fontFamily: FONT.mono,
    fontWeight: 500,
    fontSize: FS,
    letterSpacing: LSP,
    color: INK,
    whiteSpace: 'nowrap',
    lineHeight: 1,
  };

  // 1-frame flash on word swap (first word does not flash)
  const flash = local === 0 && idx > 0 ? 1 : 0;
  const wordColor = flash ? '#ffffff' : INK;
  const wordGlow = flash ? '0 0 14px rgba(200,210,255,0.35)' : 'none';

  // Convergence velocity (px/frame) -> horizontal motion blur; opposing directions
  const span = MERGED_LEFT - NEW_LEFT_EDGE;
  const v = (cvAt(f + 0.5) - cvAt(f - 0.5)) * span;
  // Soft background glow after landing
  const glow = ramp(cvT, CONVERGE_DUR - 6, 24, EASE.out);

  return (
    <AbsoluteFill style={{ background: '#08090c', overflow: 'hidden' }}>
      {/* Cool deep base + subtle overhead spotlight above midline */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse 60% 55% at 50% 40%, rgba(120,130,170,0.10), rgba(120,130,170,0) 70%), ' +
            'linear-gradient(180deg, #0d0e12 0%, #08090c 60%, #060709 100%)',
        }}
      />
      {/* Soft background glow brightening after convergence */}
      <div
        style={{
          position: 'absolute', left: 960 - 520, top: 540 - 150, width: 1040, height: 300,
          background: 'radial-gradient(ellipse 50% 50% at 50% 50%, rgba(170,180,230,0.10), rgba(170,180,230,0) 70%)',
          opacity: glow,
        }}
      />
      {visible && (
        <div style={{ position: 'absolute', inset: 0 }}>
          {/* NEW: left-aligned (pinned at left screen margin during cycling); brightens from secondary gray during convergence */}
          <SpeedBlur vx={v} amount={0.35} max={4}>
            <div style={{
              ...font, position: 'absolute',
              left: newLeft, top: 519,
              color: mixHex(INK_NEW, INK, ramp(cvT, 0, CONVERGE_DUR * 0.8, EASE.smooth)),
            }}>
              NEW
            </div>
          </SpeedBlur>
          {/* Feature word: right-aligned (right edge remains fixed regardless of word length) */}
          <SpeedBlur vx={-v} amount={0.35} max={4}>
            <div style={{
              ...font, position: 'absolute',
              right: 1920 - wordRight, top: 519,
              color: wordColor, textShadow: wordGlow,
            }}>
              {cur.word}
            </div>
          </SpeedBlur>

          {/* Italic subtext: appears directly below the line after convergence, sharing left edge */}
          <div style={{
            ...font,
            fontStyle: 'italic',
            color: INK_SUB,
            position: 'absolute',
            left: MERGED_LEFT, top: 519 + FS + 14,
            opacity: subOp,
          }}>
            CRAFT THE SHOT.
          </div>
        </div>
      )}
      <Vignette strength={0.5} inner={0.45} color="#000000" />
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
