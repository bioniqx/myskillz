import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';
import { MARK_PATHS } from '../../_fixtures/Brand';
import { Grain, Vignette } from '../../_fixtures/Polish';

// wireframe-draw-on (entrance / exit): Interface forms via blueprint thin-line drawing (stroke-dashoffset
// staggered across groups), followed by a luminous vertical beam sweeping left-to-right, materializing wireframes into the actual UI.
// Timing: 0–20 empty hold -> 20–82 grouped line draw-on -> 88–118 beam scan materialization -> 118–150 hold.
// Texture improvements:
// - Wireframes meticulously aligned to Phase 0 updated FakeDashboard A geometry (sidebar logo/nav/projects/usage card, top bar breadcrumbs/
//   segmented controls/search/avatar, and 6 card headers/big numbers/chart shapes/footers) so the scan sweep no longer shifts position;
// - Blueprint styling: cool gray-blue lines (outer frame 1.6px, inner elements 1.25px) + pale blue dot matrix + crop marks, reading as an architectural blueprint rather than gray placeholders;
// - Scanning leading edge trails a fading warm afterglow (developing warmth of the materialized layer), driven by the same scan progress as the clip edge;
// - Added WIREFRAME_DRAW_ON_DURATION = 150.
// Brand: After updating FakeDashboard sidebar/breadcrumbs to video-shotcraft, wireframes re-aligned synchronously — logo square traces two-path mark,
// with sidebar title, breadcrumbs (shifted 30px right), segmented controls, and project name lengths matched to actual text widths.
export const WIREFRAME_DRAW_ON_DURATION = 150;

// FakeDashboard variant A geometry (1920x1080):
// Sidebar width 220; top bar x220-1920 h72; content area padding 36 gap 28, 3x2 cards
// Cards w524 h454, x = 256/808/1360, y = 108/590.
const CARD_W = 524;
const CARD_H = 454;
const CARD_X = [256, 808, 1360];
const CARD_Y = [108, 590];
const MARK_K = 26 / 128; // Sidebar ShotcraftMark 26px / viewBox 128
// Sidebar project names (Launch film / Feature tour / Release reel) and breadcrumb "video-shotcraft" aligned to measured rendered text widths
const PROJ_W = [72, 77, 76];
const INK = '#6c7894'; // Blueprint stroke color
const PAPER = '#eef0f2';

const seedFrac = (i: number) => {
  const v = Math.sin(i * 127.3) * 43758.5453;
  return v - Math.floor(v);
};
const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// Smooth polyline -> Bezier (Catmull-Rom)
const smoothPath = (pts: [number, number][]) => {
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    d += ` C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)},${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)},${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
};
const wave = (x0: number, x1: number, yTop: number, yBot: number, seed: number) =>
  smoothPath(
    Array.from({ length: 12 }, (_, i) => {
      const k = i / 11;
      const v = 0.45 * k + 0.2 * Math.sin(i * 0.9 + seed) + 0.12 * seedFrac(seed * 7 + i);
      return [x0 + (x1 - x0) * k, yBot - (yBot - yTop) * Math.min(1, Math.max(0, v + 0.15))] as [number, number];
    }),
  );

export const WireframeDrawOn: React.FC = () => {
  const frame = useCurrentFrame();

  // Line drawing progress: each group completes in 30f with staggered starts
  const draw = (start: number) =>
    interpolate(frame, [start, start + 30], [0, 1], { ...clamp, easing: Easing.bezier(0.4, 0, 0.3, 1) });

  const tSide = draw(20); // Sidebar
  const tTop = draw(30); // Top bar
  const tCards = Array.from({ length: 6 }, (_, i) => draw(40 + i * 3)); // Staggered cards
  const tChart = draw(52); // Charts

  // Materialization scan: 88–118 left to right
  const scan = interpolate(frame, [88, 118], [0, 1], { ...clamp, easing: Easing.bezier(0.55, 0, 0.25, 1) });
  const scanX = scan * 1920;
  const lineOpacity = interpolate(frame, [86, 92, 112, 120], [0, 1, 1, 0], clamp);
  const gridIn = interpolate(frame, [0, 18], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });

  // Stroke helper: pathLength=1 + dashoffset from 1 -> 0
  const stroke = (t: number, w = 1.25): React.SVGAttributes<SVGElement> => ({
    fill: 'none',
    stroke: INK,
    strokeWidth: w,
    pathLength: 1,
    strokeDasharray: 1,
    strokeDashoffset: 1 - t,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    opacity: t > 0 ? 1 : 0,
  });

  return (
    <AbsoluteFill style={{ background: PAPER, overflow: 'hidden' }}>
      {/* Blueprint dot matrix background */}
      <AbsoluteFill style={{
        opacity: gridIn * 0.9,
        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(108,120,148,0.28) 1px, rgba(0,0,0,0) 1.4px)',
        backgroundSize: '24px 24px',
      }} />
      {/* —— Wireframe layer (blueprint line drawing) —— */}
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute', inset: 0 }}>
        {/* Sidebar */}
        <rect x={1} y={1} width={219} height={1078} rx={2} {...stroke(tSide, 1.6)} />
        <rect x={22} y={28} width={40} height={40} rx={10} {...stroke(draw(24))} />
        {/* video-shotcraft mark (26px centered in logo box): viewfinder frame + diagonal slice drawn sequentially; stroke width scaled back to 1.25px */}
        <g transform={`translate(29 35) scale(${MARK_K})`}>
          <path d={MARK_PATHS.frame} {...stroke(draw(25), 1.25 / MARK_K)} />
          <path d={MARK_PATHS.cut} {...stroke(draw(28), 1.25 / MARK_K)} />
        </g>
        <line x1={73} y1={40} x2={188} y2={40} {...stroke(draw(25))} />
        <line x1={73} y1={58} x2={118} y2={58} {...stroke(draw(26))} />
        <rect x={22} y={96} width={176} height={34} rx={8} {...stroke(draw(26))} />
        {Array.from({ length: 7 }).map((_, i) => {
          const cy = 113 + i * 40;
          const w = 42 + ((i * 29) % 36);
          return (
            <g key={`s${i}`}>
              <rect x={33} y={cy - 7} width={14} height={14} rx={3} {...stroke(draw(26 + i * 2))} />
              <line x1={59} y1={cy} x2={59 + w} y2={cy} {...stroke(draw(27 + i * 2))} />
            </g>
          );
        })}
        <line x1={32} y1={409} x2={98} y2={409} {...stroke(draw(40))} />
        {[437, 475, 513].map((cy, i) => (
          <g key={`p${i}`}>
            <circle cx={40} cy={cy} r={4} {...stroke(draw(41 + i * 2))} />
            <line x1={59} y1={cy} x2={59 + PROJ_W[i]} y2={cy} {...stroke(draw(42 + i * 2))} />
          </g>
        ))}
        <rect x={22} y={1001} width={176} height={50} rx={10} {...stroke(draw(46))} />
        <line x1={34} y1={1038} x2={186} y2={1038} {...stroke(draw(48))} />

        {/* Top bar */}
        <line x1={220} y1={72} x2={1920} y2={72} {...stroke(tTop, 1.6)} />
        <line x1={252} y1={36} x2={358} y2={36} {...stroke(draw(33))} />
        <line x1={388} y1={36} x2={454} y2={36} {...stroke(draw(34))} />
        <rect x={486} y={20} width={136} height={32} rx={9} {...stroke(draw(35))} />
        <rect x={1512} y={18} width={320} height={36} rx={10} {...stroke(draw(36))} />
        <circle cx={1870} cy={36} r={18} {...stroke(draw(38))} />

        {/* 3x2 cards: outlines + headers / big numbers / footers + corner crop marks */}
        {tCards.map((t, i) => {
          const cx = CARD_X[i % 3];
          const cy = CARD_Y[Math.floor(i / 3)];
          const titleW = 80 + (((i + 1) * 37) % 50);
          const numW = 120 + (((i + 2) * 53) % 110);
          const td = (k: number) => draw(46 + i * 3 + k);
          return (
            <g key={`c${i}`}>
              <rect x={cx} y={cy} width={CARD_W} height={CARD_H} rx={14} {...stroke(t, 1.6)} />
              {/* Crop marks */}
              {[[cx - 10, cy - 10, 1, 1], [cx + CARD_W + 10, cy - 10, -1, 1], [cx - 10, cy + CARD_H + 10, 1, -1], [cx + CARD_W + 10, cy + CARD_H + 10, -1, -1]].map(([x, y, sx, sy], k) => (
                <path key={k} d={`M${x},${y + sy * 14} L${x},${y} L${x + sx * 14},${y}`} {...stroke(t, 1)} opacity={t > 0 ? 0.55 : 0} />
              ))}
              <rect x={cx + 20} y={cy + 20} width={28} height={28} rx={7} {...stroke(td(0))} />
              <line x1={cx + 58} y1={cy + 34} x2={cx + 58 + titleW} y2={cy + 34} {...stroke(td(1))} />
              <rect x={cx + CARD_W - 75} y={cy + 24} width={30} height={20} rx={5} {...stroke(td(1))} />
              <line x1={cx + 20} y1={cy + 84} x2={cx + 20 + numW} y2={cy + 84} {...stroke(td(2), 3)} />
              <line x1={cx + 20} y1={cy + 120} x2={cx + 20 + 110} y2={cy + 120} {...stroke(td(3))} />
              <line x1={cx + 20} y1={cy + 393} x2={cx + CARD_W - 20} y2={cy + 393} {...stroke(td(4))} />
              {[0, 1, 2].map((k) => (
                <circle key={k} cx={cx + 31 + k * 20} cy={cy + 421} r={10} {...stroke(td(5 + k))} />
              ))}
              <line x1={cx + 94} y1={cy + 421} x2={cx + 190} y2={cy + 421} {...stroke(td(6))} />
              <line x1={cx + CARD_W - 66} y1={cy + 421} x2={cx + CARD_W - 20} y2={cy + 421} {...stroke(td(7))} />
            </g>
          );
        })}

        {/* Chart representations for each card (isomorphic to concrete cards) */}
        {/* 0 Active users / 5 Sessions: area curve */}
        <path d={wave(CARD_X[0] + 20, CARD_X[0] + CARD_W - 24, CARD_Y[0] + 170, CARD_Y[0] + 355, 1)} {...stroke(tChart, 2)} />
        <path d={wave(CARD_X[2] + 20, CARD_X[2] + CARD_W - 24, CARD_Y[1] + 165, CARD_Y[1] + 350, 4)} {...stroke(draw(60), 2)} />
        {/* 1 Top pages: 6 row bars */}
        {Array.from({ length: 6 }).map((_, k) => {
          const y = CARD_Y[0] + 85 + k * 42;
          const w = [484, 320, 212, 140, 92, 180][k];
          return <rect key={`tp${k}`} x={CARD_X[1] + 20} y={y - 12} width={w} height={24} rx={5} {...stroke(draw(54 + k * 2))} />;
        })}
        {/* 2 Revenue: 14 bar columns */}
        {Array.from({ length: 14 }).map((_, k) => {
          const h = 30 + (0.25 + 0.75 * Math.min(1, k / 8)) * 150 * (0.75 + 0.25 * seedFrac(k + 9));
          const x = CARD_X[2] + 26 + k * 34.6;
          const base = CARD_Y[0] + 358;
          return <rect key={`rv${k}`} x={x} y={base - h} width={20} height={h} rx={3} {...stroke(draw(56 + k))} />;
        })}
        {/* 3 Quarterly goals: 5 progress bars */}
        {Array.from({ length: 5 }).map((_, k) => {
          const y = CARD_Y[1] + 178 + k * 46;
          return (
            <g key={`qg${k}`}>
              <line x1={CARD_X[0] + 20} y1={y - 18} x2={CARD_X[0] + 20 + 60 + k * 9} y2={y - 18} {...stroke(draw(58 + k * 2))} />
              <rect x={CARD_X[0] + 20} y={y - 3} width={CARD_W - 40} height={6} rx={3} {...stroke(draw(59 + k * 2))} />
            </g>
          );
        })}
        {/* 4 Deploys: heatmap grid (border + row lines) */}
        <rect x={CARD_X[1] + 20} y={CARD_Y[1] + 144} width={CARD_W - 46} height={156} rx={4} {...stroke(draw(60))} />
        {Array.from({ length: 6 }).map((_, k) => (
          <line key={`dp${k}`} x1={CARD_X[1] + 20} y1={CARD_Y[1] + 167 + k * 23} x2={CARD_X[1] + CARD_W - 26} y2={CARD_Y[1] + 167 + k * 23} {...stroke(draw(62 + k), 1)} />
        ))}
      </svg>

      {/* —— Concrete layer: clip-path inset unfolds left to right —— */}
      <div style={{ position: 'absolute', inset: 0, clipPath: `inset(0 ${((1 - scan) * 100).toFixed(3)}% 0 0)` }}>
        <FakeDashboard variant="A" />
        {/* Scan front afterglow: warm light trailing freshly revealed segment, fading to the left */}
        {scan > 0 && scan < 1 && (
          <div style={{
            position: 'absolute', top: 0, bottom: 0, left: scanX - 260, width: 260, pointerEvents: 'none',
            background: 'linear-gradient(90deg, rgba(255,196,107,0) 0%, rgba(255,196,107,0.10) 70%, rgba(255,196,107,0.22) 100%)',
            mixBlendMode: 'multiply',
          }} />
        )}
      </div>

      {/* —— 4px glowing vertical scan line (amber shimmer) —— */}
      <div
        style={{
          position: 'absolute', left: scanX - 2, top: 0, width: 4, height: 1080,
          background: 'linear-gradient(180deg, rgba(255,214,150,0.6), #ffc46b 20%, #ffd28a 50%, #ffc46b 80%, rgba(255,214,150,0.6))',
          opacity: lineOpacity,
          boxShadow: '0 0 18px 6px rgba(232, 163, 61, 0.55), 0 0 60px 18px rgba(232, 163, 61, 0.22)',
        }}
      />
      <Vignette strength={0.12} color="#2a3040" inner={0.55} />
      <Grain opacity={0.04} />
    </AbsoluteFill>
  );
};
