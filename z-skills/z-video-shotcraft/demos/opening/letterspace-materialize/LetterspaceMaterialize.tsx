// letterspace-materialize v3 — Refined per reference (superhuman screenshots):
// 1. Wider glyph proportions: v3 redraws skeleton glyphs within 78x64 viewbox (58x54 optical), slightly square + thin strokes + wide letter-spacing;
// 2. Synchronous stroke animation: all letters start and complete together (normalized pathLength guarantees uniform completion across differing stroke lengths).
// v4 polish: background redesigned as dusk lake landscape — layered sky gradient + dual procedural mountain ridges (atmospheric depth)
//    + wide horizon twilight glow + water surface with sky reflection and gentle shimmering wavelets + wordmark reflection;
//    film grain prevents banding; background slowly dollies in 3% (subtle parallax), wordmark remains anchored.
// Brand identity: SUPERHUMAN -> video-shotcraft (lowercase logotype) using 13 geometric lowercase skeleton glyphs (see GLYPHS),
//    maintaining rhythm, synchronous finish, landscape backdrop, and timing.
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { bezier, ramp, EASE, Grain, Vignette } from '../../_fixtures/Polish';

// Brand identity: Wordmark updated to video-shotcraft (lowercase per brand guidelines), skeleton glyphs redrawn as geometric monoline.
// Standard 64-height viewbox: baseline y=59, x-height y=22, ascender y=5, each glyph carries its own width w;
// Rendered scaled by GLYPH_SCALE (compensating for lowercase optical weight to match visual prominence),
// stroke width scales inversely to maintain a crisp 5.5px hairline on screen. Sub-stroke order = draw order.
const GLYPHS: Record<string, { w: number; d: string }> = {
  v: { w: 42, d: 'M 4 22 L 21 59 L 38 22' },
  i: { w: 14, d: 'M 7 22 L 7 59 M 7 9.5 L 7 10' },
  d: { w: 46, d: 'M 41.5 40.5 A 18.5 18.5 0 0 0 4.5 40.5 A 18.5 18.5 0 0 0 41.5 40.5 M 41.5 5 L 41.5 59' },
  e: { w: 46, d: 'M 4.5 40.5 L 41.5 40.5 A 18.5 18.5 0 1 0 37.2 52.4' },
  o: { w: 46, d: 'M 23 22 A 18.5 18.5 0 0 0 23 59 A 18.5 18.5 0 0 0 23 22' },
  '-': { w: 28, d: 'M 5 41 L 23 41' },
  s: { w: 39, d: 'M 32.6 27.5 C 26.4 21.3, 7.9 20.6, 6.2 28.9 C 4.6 36.4, 14.1 38.4, 19.7 39.8 C 25.8 41.2, 34.8 43.9, 33.1 51.5 C 31.4 59, 9.6 60.4, 4 52.8' },
  h: { w: 41, d: 'M 5 5 L 5 59 M 5 38 C 5 27, 12 22, 20.5 22 C 30 22, 36 27, 36 37 L 36 59' },
  t: { w: 26, d: 'M 12 8 L 12 59 M 3 22 L 23 22' },
  c: { w: 42, d: 'M 37.2 28.6 A 18.5 18.5 0 1 0 37.2 52.4' },
  r: { w: 28, d: 'M 5 22 L 5 59 M 5 38 C 5 27, 13 22, 24 23' },
  a: { w: 46, d: 'M 41.5 40.5 A 18.5 18.5 0 0 0 4.5 40.5 A 18.5 18.5 0 0 0 41.5 40.5 M 41.5 22 L 41.5 59' },
  f: { w: 26, d: 'M 23 7 C 17 4, 11 6, 11 14 L 11 59 M 3 22 L 22 22' },
};

const WORD = 'video-shotcraft';
const GLYPH_SCALE = 1.3; // Viewbox -> screen scale multiplier
const GLYPH_H = 64 * GLYPH_SCALE; // Line height (screen px)
const TRACK = 30; // Letter spacing (screen px): wide spacing defines this card
const START = 16;   // Synchronized draw start frame (no stagger)
const DUR = 52;     // Synchronized draw duration (normalized pathLength -> simultaneous finish)
export const LETTERSPACE_MATERIALIZE_DURATION = 105; // Rest 16f + draw 52f + final hold 37f (>1s, R1)

const HORIZON = 640; // Horizon / shoreline y
const MARK_Y = 470; // Wordmark center y (within twilight glow above horizon)
// Draw curve: soft attack, brisk mid-stroke, gentle release (calligraphic pen cadence)
const strokeEase = bezier(0.5, 0, 0.3, 1);

// Procedural mountain ridge: deterministic silhouette via superimposed sine waves
const ridge = (seed: number, base: number, amp: number) => {
  const pts: string[] = [];
  for (let x = -60; x <= 1980; x += 20) {
    const y =
      base -
      amp * (0.55 * Math.sin(x / 233 + seed) + 0.3 * Math.sin(x / 97 + seed * 2.1) + 0.15 * Math.sin(x / 41 + seed * 3.7) + 0.6);
    pts.push(`${x},${y.toFixed(1)}`);
  }
  return `M -60 ${HORIZON + 2} L ${pts.join(' L ')} L 1980 ${HORIZON + 2} Z`;
};
const FAR_RIDGE = ridge(1.3, HORIZON, 70);
const NEAR_RIDGE = ridge(4.1, HORIZON + 2, 34);

// Water wavelets: deterministic horizontal specular dashes gently drifting horizontally
const GLINTS = Array.from({ length: 22 }, (_, i) => {
  const s = Math.sin(i * 91.7) * 43758.5453;
  const r = s - Math.floor(s);
  const s2 = Math.sin(i * 47.3 + 5) * 24634.6345;
  const r2 = s2 - Math.floor(s2);
  const depth = (i + 0.5) / 22; // 0 = horizon, 1 = bottom of frame
  return {
    y: HORIZON + 8 + depth * depth * 400,
    x: 960 + (r - 0.5) * (500 + depth * 1100),
    w: 40 + r2 * 120 + depth * 160,
    a: 0.05 + (1 - depth) * 0.12,
    ph: r * 6.28,
  };
});

const Word: React.FC<{ e: number; glowAmt: number }> = ({ e, glowAmt }) => (
  <div style={{ display: 'flex', gap: TRACK, alignItems: 'center' }}>
    {WORD.split('').map((ch, li) => {
      const g = GLYPHS[ch];
      return (
        <svg key={li} width={g.w * GLYPH_SCALE} height={GLYPH_H} viewBox={`0 0 ${g.w} 64`} style={{ overflow: 'visible', display: 'block' }}>
          {e > 0 && (
            <path
              d={g.d}
              fill="none"
              stroke="#f6f3fa"
              strokeWidth={5.5 / GLYPH_SCALE}
              strokeLinecap="round"
              strokeLinejoin="round"
              pathLength={1}
              strokeDasharray={1}
              strokeDashoffset={1 - e}
              style={{
                filter: `drop-shadow(0 0 ${(5 + glowAmt * 10) / GLYPH_SCALE}px rgba(245,225,240,${0.3 + glowAmt * 0.38}))`,
              }}
            />
          )}
        </svg>
      );
    })}
  </div>
);

export const LetterspaceMaterialize: React.FC = () => {
  const frame = useCurrentFrame();

  // All glyphs share identical progress: synchronized start and finish
  const e = ramp(frame, START, DUR, strokeEase);
  // Completion crystallization flash: brief luminance bloom on stroke close; builds over final 30%
  const rise = ramp(frame, START + DUR * 0.7, DUR * 0.3, EASE.swift);
  const fall = 1 - ramp(frame, START + DUR, 14, EASE.out);
  const glowAmt = e >= 1 ? fall : rise;

  // Subtle background push: distant mountains 1->1.02, foreground/water 1->1.035 (micro-parallax); wordmark stays anchored
  const push = ramp(frame, 0, LETTERSPACE_MATERIALIZE_DURATION, EASE.smooth);
  const sFar = 1 + 0.02 * push;
  const sNear = 1 + 0.035 * push;
  // Twilight glow brightens subtly on crystallization ("lighting up" the horizon)
  const dawn = 0.85 + 0.15 * ramp(frame, START + DUR * 0.5, DUR, EASE.out);

  return (
    <AbsoluteFill style={{ background: '#120f24', overflow: 'hidden' }}>
      {/* Sky + distant mountains (far layer) */}
      <AbsoluteFill style={{ transform: `scale(${sFar})`, transformOrigin: `50% ${HORIZON}px` }}>
        <AbsoluteFill
          style={{
            background:
              `linear-gradient(180deg, #17153a 0%, #24204f 24%, #3a2f63 42%, #5f4270 53%, #8a5878 ${((HORIZON - 14) / 1080) * 100}%, #1c1838 ${(HORIZON / 1080) * 100}%, #0b0a17 100%)`,
          }}
        />
        {/* Wide horizon glow: ellipse bleeds off-screen without clipped edges */}
        <div
          style={{
            position: 'absolute', left: -480, right: -480, top: HORIZON - 260, height: 520, opacity: dawn,
            background: 'radial-gradient(ellipse 50% 50% at 54% 50%, rgba(246,168,170,0.42) 0%, rgba(214,130,160,0.2) 35%, rgba(140,100,170,0.06) 65%, rgba(0,0,0,0) 80%)',
          }}
        />
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <linearGradient id="lm-far" x1="0" y1={HORIZON - 120} x2="0" y2={HORIZON} gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor="#5a4473" />
              <stop offset="1" stopColor="#3e3260" />
            </linearGradient>
          </defs>
          {/* Distant mountains: lighter, tinted with twilight (atmospheric haze) */}
          <path d={FAR_RIDGE} fill="url(#lm-far)" opacity={0.75} style={{ filter: 'blur(1.2px)' }} />
        </svg>
      </AbsoluteFill>

      {/* Near mountains + water (near layer, faster parallax push) */}
      <AbsoluteFill style={{ transform: `scale(${sNear})`, transformOrigin: `50% ${HORIZON}px` }}>
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
          <path d={NEAR_RIDGE} fill="#271f43" />
        </svg>
        {/* Water surface: sky reflection (glow stretches and dims) + deepens toward bottom */}
        <div
          style={{
            position: 'absolute', left: 0, right: 0, top: HORIZON, bottom: 0,
            background:
              'radial-gradient(ellipse 46% 40% at 54% 0%, rgba(230,150,165,0.22) 0%, rgba(150,105,160,0.08) 50%, rgba(0,0,0,0) 80%), ' +
              'linear-gradient(180deg, #2a2346 0%, #18142e 30%, #0d0b1a 100%)',
          }}
        />
        {/* Hairline specular edge along horizon */}
        <div
          style={{
            position: 'absolute', left: 0, right: 0, top: HORIZON - 1, height: 2,
            background: 'linear-gradient(90deg, rgba(255,200,210,0) 8%, rgba(255,200,210,0.35) 54%, rgba(255,200,210,0) 92%)',
          }}
        />
        {/* Gentle drifting specular wavelets */}
        {GLINTS.map((g, i) => (
          <div
            key={i}
            style={{
              position: 'absolute', top: g.y, height: 1.5, borderRadius: 1, width: g.w,
              left: g.x - g.w / 2 + Math.sin(frame / 38 + g.ph) * 14,
              background: `linear-gradient(90deg, rgba(255,215,225,0), rgba(255,215,225,${(g.a * (0.75 + 0.25 * Math.sin(frame / 23 + g.ph))).toFixed(3)}), rgba(255,215,225,0))`,
            }}
          />
        ))}
      </AbsoluteFill>

      {/* Wordmark reflection: mirrored across horizon, low opacity + soft blur + downward falloff */}
      <div
        style={{
          position: 'absolute', left: 0, right: 0, top: 2 * HORIZON - MARK_Y - GLYPH_H / 2, height: GLYPH_H,
          display: 'flex', justifyContent: 'center',
          transform: 'scaleY(-1)', opacity: 0.12, filter: 'blur(2.4px)',
          WebkitMaskImage: 'linear-gradient(0deg, rgba(0,0,0,1) 0%, rgba(0,0,0,0.2) 100%)',
          maskImage: 'linear-gradient(0deg, rgba(0,0,0,1) 0%, rgba(0,0,0,0.2) 100%)',
        }}
      >
        <Word e={e} glowAmt={glowAmt * 0.5} />
      </div>

      {/* Wide-tracked wordmark: parallel continuous stroke draw-on */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: MARK_Y - GLYPH_H / 2, height: GLYPH_H, display: 'flex', justifyContent: 'center' }}>
        <Word e={e} glowAmt={glowAmt} />
      </div>

      <Vignette strength={0.45} inner={0.5} color="#05040c" cy={0.5} />
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
