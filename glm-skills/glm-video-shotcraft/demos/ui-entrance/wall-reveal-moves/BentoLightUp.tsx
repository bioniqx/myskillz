import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { Card } from '../../_fixtures/Fixtures';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';
import { Backdrop, FONT, Grain } from '../../_fixtures/Polish';

// bento-light-up: In a dark field, a 3×2 bento wall stands dimmed and ready, lighting up cell-by-cell on beat:
// border light traces a perimeter loop first (amber), then inner cell content brightens, floats up, and pops in;
// once all six cells are lit, the entire layout gently pushes forward and settles.
// Timing: 0–20 establish (hold) → cells activate sequentially with 12f interval (8f border trace + 8f content pop)
//       → ~96f fully lit → 96–121 gentle scale push 1→1.04 → 121–150 static hold outro.
// Aesthetic revisions:
// - Authentic bento: complementary wide/narrow pairs across two rows (600/420/420 ↔ 420/420/600), no longer equal-sized grids;
// - Card surface uses dark editorial Card (tone="dark"); avoids glare in dark-field brand sections; lighting reads as power-on rather than a color switch;
// - Border tracer redesigned as a "comet": bright head + fading tail traces one lap then settles into a steady hairline border; glow stays strictly on stroke;
// - Typography upgraded to eyebrow header + main title hierarchy; soft dark-field base (warm ambient glow) + vignette + grain.
// Brand: Eyebrow = video-shotcraft logo + lowercase wordmark (amber); Main title = PITCH tagline "Every shot, tuned in one place.".
export const BENTO_LIGHT_UP_DURATION = 150;

const AMBER = '#e8b45e';
const FIRST = 20; // First cell activation frame
const GAP = 12; // Inter-cell beat interval
const CELL_H = 330;
const GUT = 44;
const U = 480; // Base unit for wide/narrow cells: wide 1.25U=600, narrow 0.875U=420; row = 1440 + 2 gutters (wider variance causes noticeable font scale discrepancies)
const ROW_W = U * 3 + GUT * 2;
const LEFT = (1920 - ROW_W) / 2;
const TOP = (1080 - (CELL_H * 2 + GUT)) / 2 + 44;
const WIDTHS = [
  [1.25, 0.875, 0.875],
  [0.875, 0.875, 1.25],
];
const CELLS = WIDTHS.flatMap((row, r) => {
  let x = LEFT;
  return row.map((k) => {
    const w = k * U;
    const c = { x, y: TOP + r * (CELL_H + GUT), w };
    x += w + GUT;
    return c;
  });
});

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

const Cell: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const start = FIRST + i * GAP;
  const { x, y, w } = CELLS[i];

  // 1. Border tracer: comet segment (length: 22% perimeter) travels one loop along pathLength=100 in 8f; followed by a continuous fine border
  const draw = interpolate(frame, [start, start + 8], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  // Trace annealing after completion: amber bright edge → softens into a steady fine border
  const strokeFade = interpolate(frame, [start + 12, start + 26], [1, 0.4], { ...clamp, easing: Easing.out(Easing.quad) });
  const ring = interpolate(frame, [start + 2, start + 10], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });

  // 2. Content brightness + float pop: handed over halfway through tracing, 8f pop-in (back-out with slight overshoot)
  const lit = interpolate(frame, [start + 6, start + 14], [0, 1], { ...clamp, easing: Easing.out(Easing.cubic) });
  const rise = interpolate(frame, [start + 6, start + 14], [0, 1], { ...clamp, easing: Easing.bezier(0.3, 1.4, 0.5, 1) });
  const opacity = 0.18 + 0.82 * lit;
  const ty = 20 * (1 - rise);
  // Seed sine-hash for per-cell subtle variance (adds organic randomness to ignite flash glow)
  const jitter = Math.abs((Math.sin(i * 127.3) * 43758.5453) % 1);
  const pulse = lit * (1 - lit) * 4; // Peak glow pulse at midpoint of illumination
  const head = 100 * draw; // Comet head position (perimeter percentage)
  const TAIL = 22;

  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: CELL_H }}>
      {/* Dim card + lit content (same card, brightens and floats up via opacity/translateY) */}
      <div style={{ opacity, transform: `translateY(${ty.toFixed(2)}px)`, borderRadius: 14 }}>
        <Card w={w} h={CELL_H} seed={i + 1} tone="dark" />
        {/* Warm flash within card on ignition (clipped to border radius, decays to zero after pulse) */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 14, pointerEvents: 'none',
          background: `radial-gradient(90% 70% at 50% 0%, rgba(232,180,94,${(0.16 * pulse * (0.8 + jitter * 0.4)).toFixed(3)}), rgba(232,180,94,0) 70%)`,
        }} />
      </div>
      {/* Border tracer: SVG rect stroke */}
      {draw > 0 && (
        <svg width={w} height={CELL_H} viewBox={`0 0 ${w} ${CELL_H}`} style={{ position: 'absolute', left: 0, top: ty, overflow: 'visible' }}>
          <defs>
            <filter id={`blu-glow-${i}`} x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur stdDeviation={4 + jitter * 2} />
            </filter>
          </defs>
          {/* Steady fine border: reveals segmentally as comet passes, persists after annealing */}
          <rect
            x={0.75} y={0.75} width={w - 1.5} height={CELL_H - 1.5} rx={14} fill="none"
            stroke={AMBER} strokeWidth={1.5} pathLength={100} strokeDasharray={100} strokeDashoffset={100 * (1 - draw)}
            opacity={ring * strokeFade}
          />
          {/* Comet: glow layer + bright core layer, fades after completing loop and annealing */}
          {[0, 1].map((k) => (
            <rect
              key={k}
              x={1.5} y={1.5} width={w - 3} height={CELL_H - 3} rx={14} fill="none"
              stroke={k ? '#ffe3ae' : AMBER}
              strokeWidth={k ? 2.5 : 6}
              strokeLinecap="round"
              pathLength={100}
              strokeDasharray={`${TAIL} ${100 - TAIL}`}
              strokeDashoffset={TAIL - head}
              opacity={(1 - interpolate(frame, [start + 8, start + 16], [0, 1], clamp)) * (k ? 1 : 0.8)}
              filter={k ? undefined : `url(#blu-glow-${i})`}
            />
          ))}
        </svg>
      )}
    </div>
  );
};

export const BentoLightUp: React.FC = () => {
  const frame = useCurrentFrame();

  // 3. Once all six cells are lit (~96f), gentle scale push 1→1.04 across 25f, settling into complete rest
  const push = interpolate(frame, [96, 121], [1, 1.04], { ...clamp, easing: Easing.bezier(0.33, 0, 0.2, 1) });

  // Title gently brightens as first cell lights up to establish scene context
  const titleLit = interpolate(frame, [FIRST, FIRST + 20], [0.25, 1], { ...clamp, easing: Easing.out(Easing.quad) });
  // Ambient floor glow rises slightly once all cells are lit
  const allLit = interpolate(frame, [FIRST + 5 * GAP + 6, FIRST + 5 * GAP + 30], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Backdrop tone="dark" light={{ x: 0.5, y: 0.1 }} accent={AMBER} grain={0} vignette={0.55} />
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse 50% 40% at 50% 62%, rgba(232,180,94,0.10), rgba(232,180,94,0) 70%)',
        opacity: 0.3 + 0.7 * allLit,
      }} />
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push.toFixed(5)})`, transformOrigin: '960px 540px' }}>
        <div style={{ position: 'absolute', left: LEFT, top: TOP - 132, fontFamily: FONT.sans, opacity: titleLit }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, height: 18 }}>
            <ShotcraftMark size={24} tone="dark" />
            <span style={{ fontFamily: BRAND.font, fontSize: 17, fontWeight: 700, letterSpacing: '0.03em', color: AMBER, opacity: 0.9, lineHeight: 1 }}>{BRAND.name}</span>
          </div>
          <div style={{ marginTop: 10, fontSize: 56, fontWeight: 700, letterSpacing: '-0.03em', color: '#f1efe9', lineHeight: 1 }}>
            {PITCH.en.taglines[2]}
          </div>
        </div>
        {CELLS.map((_, i) => (
          <Cell key={i} i={i} frame={frame} />
        ))}
      </div>
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
