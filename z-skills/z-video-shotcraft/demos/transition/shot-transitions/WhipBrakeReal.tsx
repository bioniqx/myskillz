// whip-brake (hard-brake style) — horizontal gallery of project cards sweeps across 7 cards before target card (card4-hires)
// executes hard brake with long ease-out tail. Ideal for shots requiring legible text at landing.
//
// Redesign (warm paper: index gallery + mechanical counter):
// - look = paper (warm white paper, ink, vermilion). Features top-left mechanical counter "No 02 / 10",
//   150px serif roller wheel counter tracking gallery position with vertical velocity blur,
//   rapid spinning during whip and decelerating to sharp snap at 09 on shared motion curve.
// - Fixed vermilion playhead on screen midline (top indicator + hairline), scale ruler along gallery bottom
//   (major ticks per card + sub-ticks): blurs during whip, snaps playhead into slot 09 on brake.
// - Velocity: integrated curve v(u) = V0 * exp(-6u/60) * smoothstep(0,3,u) — 3f launch then monotonic decay
//   (first 70% travel in ~12f blur phase, remaining 30% over 48f tail), continuous velocity with directional motion blur.
// - Settle: target card elevates and scales to 1.2x (high-res texture, legible text), neighboring cards dim to 45% and recede;
//   section title "Efficient Models" rises beneath playhead.
//
// Timeline (30fps, total 130f):
//   0-24    Start hold: card 02 under playhead, counter reads 02
//   24-36   Whip phase (blur, peak ~300px/f, counter spins)
//   36-84   Brake phase: long tail slides into slot 09
//   80-98   Target card elevates 1->1.2, neighbors dim; section name rises 88f+
//   98-130  Static hold
import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import layout from '../../_textures/live-layout.json';
import { EASE, FONT, ramp, mix, velocity, softShadow, SpeedBlur } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, type, SERIF } from '../../_fixtures/Look';

export const WHIPBRAKE_DUR = 130;

const L = LOOKS.paper;
const cards = layout.projects.cards;
// Gallery order: target card card4 (hires) at index 9, followed by next card at 10
const RAIL = [cards[0], cards[1], cards[2], cards[4], cards[5], cards[6], cards[7], cards[8], null, cards[9]];
const TARGET_I = 8;
const START_I = 1;
const CARD_W = 460;
const GAP = 64;
const PITCH = CARD_W + GAP;
const RAIL_Y = 318;
const CARD_H = 402; // 460 × 312/357
const LEFT0 = 960 - CARD_W / 2 - START_I * PITCH; // Start: card 02 centered
const END = (TARGET_I - START_I) * PITCH;
const T0 = 24;

// Precomputed velocity integral table (step 0.05f): 3f smoothstep launch, exp(-6u/60) decay
const STEP = 0.05;
const TABLE = (() => {
  const n = Math.round(60 / STEP);
  const vel = (u: number) => {
    const r = Math.min(1, u / 3);
    return Math.exp((-6 * u) / 60) * r * r * (3 - 2 * r);
  };
  const out = new Float64Array(n + 1);
  for (let i = 1; i <= n; i++) out[i] = out[i - 1] + ((vel((i - 1) * STEP) + vel(i * STEP)) / 2) * STEP;
  const total = out[n];
  for (let i = 0; i <= n; i++) out[i] /= total;
  return out;
})();
const progress = (u: number) => {
  if (u <= 0) return 0;
  if (u >= 60) return 1;
  const x = u / STEP;
  const i = Math.floor(x);
  return TABLE[i] + (TABLE[i + 1] - TABLE[i]) * (x - i);
};
const dxAt = (f: number) => END * progress(f - T0);
// Counter value: card index currently under playhead (continuous, 1-based)
const indexAt = (f: number) => START_I + 1 + dxAt(f) / PITCH;

// Single mechanical roller digit: vertical number strip with velocity-based motion blur
const DIGIT = 150;
const Wheel: React.FC<{ pos: number; speed: number }> = ({ pos, speed }) => {
  const id = React.useId().replace(/[^a-zA-Z0-9]/g, '');
  const p = ((pos % 10) + 10) % 10;
  const blur = Math.min(14, speed * DIGIT * 0.2);
  return (
    <span style={{
      display: 'inline-block', width: '0.6em', height: '1em', overflow: 'hidden', position: 'relative', verticalAlign: 'top',
      // Drum aesthetic: top/bottom edge fade simulating cylindrical rotation
      WebkitMaskImage: 'linear-gradient(180deg, transparent 0%, #000 16%, #000 84%, transparent 100%)',
      maskImage: 'linear-gradient(180deg, transparent 0%, #000 16%, #000 84%, transparent 100%)',
    }}>
      {blur > 0.3 && (
        <svg width={0} height={0} style={{ position: 'absolute' }}>
          <filter id={`wb${id}`} x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation={`0 ${blur.toFixed(2)}`} /></filter>
        </svg>
      )}
      <span style={{
        position: 'absolute', left: 0, top: 0, display: 'flex', flexDirection: 'column', lineHeight: 1,
        transform: `translateY(${(-p).toFixed(4)}em)`, filter: blur > 0.3 ? `url(#wb${id})` : undefined,
      }}>
        {['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'].map((d, k) => <span key={k} style={{ height: '1em', textAlign: 'center' }}>{d}</span>)}
      </span>
    </span>
  );
};

export const WhipBrakeReal: React.FC = () => {
  const frame = useCurrentFrame();
  const dx = dxAt(frame);
  const v = velocity(dxAt, frame);

  // Counter: units digit spins continuously, tens digit advances on 9->0 wrap
  const idx = indexAt(frame);
  const ones = idx % 10;
  const tens = Math.floor(idx / 10) + Math.max(0, ones - 9);
  const iv = Math.abs(velocity(indexAt, frame));

  // Landing focus state
  const lift = ramp(frame, 80, 18, EASE.out);
  const dim = ramp(frame, 82, 16, EASE.out);
  const label = ramp(frame, 88, 16, EASE.snappy);
  const targetScale = mix(1, 1.2, lift);

  const cardStyle = (k: number): React.CSSProperties => ({
    position: 'absolute', left: LEFT0 + k * PITCH, top: RAIL_Y, width: CARD_W, borderRadius: 12,
    boxShadow: softShadow(8, { color: L.shadow, strength: 0.9 }),
    opacity: k === TARGET_I ? 1 : 1 - 0.55 * dim,
    transform: k !== TARGET_I && dim > 0 ? `scale(${(1 - 0.04 * dim).toFixed(4)})` : undefined,
  });

  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: L.bg[1] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.25 }} fill={null} />

      {/* Gallery world: cards + ruler translating with motion blur */}
      <SpeedBlur vx={-v} amount={0.085} max={64}>
        <div style={{ position: 'absolute', left: 0, top: 0, transform: `translateX(${(-dx).toFixed(2)}px)` }}>
          {RAIL.map((c, k) => (c ? (
            <Img key={c.file} src={staticFile(`textures/live/${c.file}`)} style={cardStyle(k)} />
          ) : (
            <Img key="target" src={staticFile('textures/live/card4-hires.png')} style={{
              ...cardStyle(k), top: RAIL_Y - 12 * lift, transform: lift > 0 ? `scale(${targetScale.toFixed(4)})` : undefined,
              boxShadow: softShadow(mix(8, 44, lift), { color: L.shadow, strength: 1.3 }), zIndex: 2,
            }} />
          )))}
          {/* Ruler: major ticks + labels per card with 4 intermediate ticks */}
          <svg width={LEFT0 + RAIL.length * PITCH + 400} height={200} style={{ position: 'absolute', left: 0, top: 812 }}>
            <line x1={LEFT0 - 300} x2={LEFT0 + RAIL.length * PITCH + 200} y1={0} y2={0} stroke={alpha(L.ink, 0.22)} strokeWidth={1.5} />
            {Array.from({ length: (RAIL.length + 1) * 5 + 6 }, (_, j) => {
              const x = LEFT0 + CARD_W / 2 + (j - 5) * (PITCH / 5);
              const major = j % 5 === 0;
              return <line key={j} x1={x} x2={x} y1={0} y2={major ? 26 : 12} stroke={alpha(L.ink, major ? 0.5 : 0.22)} strokeWidth={major ? 2 : 1.5} />;
            })}
          </svg>
          {RAIL.map((_, k) => (
            <div key={k} style={{
              position: 'absolute', left: LEFT0 + k * PITCH, width: CARD_W, top: 852, textAlign: 'center',
              fontFamily: FONT.mono, fontSize: 32, fontWeight: 500, color: k === TARGET_I ? L.ink : L.ink3,
              opacity: k === TARGET_I ? 1 : 1 - 0.5 * dim,
            }}>
              {String(k + 1).padStart(2, '0')}
            </div>
          ))}
        </div>
      </SpeedBlur>

      {/* Fixed playhead: vermilion marker triangle + vertical hairline across ruler */}
      <svg width={40} height={80} style={{ position: 'absolute', left: 940, top: 770 }}>
        <path d="M6 0 L34 0 L20 18 Z" fill={L.accent} />
        <line x1={20} x2={20} y1={16} y2={70} stroke={L.accent} strokeWidth={2} />
      </svg>
      {/* Section name reveals under playhead after landing */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 930, textAlign: 'center', ...type(32, 600, { caps: true }), letterSpacing: '0.16em',
        color: L.accent, opacity: label, transform: `translateY(${((1 - label) * 16).toFixed(2)}px)`,
      }}>
        Efficient Models
      </div>

      {/* Mechanical index counter */}
      <div style={{ position: 'absolute', left: 120, top: 70 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, ...type(30, 600, { caps: true }), color: L.ink2, letterSpacing: '0.18em' }}>
          <span style={{ width: 12, height: 12, borderRadius: 6, background: L.accent }} />Project index
        </div>
      </div>
      <div style={{ position: 'absolute', left: 1800, top: 64, transform: 'translateX(-100%)', display: 'flex', alignItems: 'flex-start', whiteSpace: 'nowrap' }}>
        <span style={{ fontFamily: SERIF, fontSize: 56, fontStyle: 'italic', color: L.ink3, marginRight: 18, marginTop: 30 }}>Nº</span>
        <span style={{ fontFamily: SERIF, fontSize: DIGIT, fontWeight: 600, color: L.ink, lineHeight: 1, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', height: '1em' }}>
          <Wheel pos={tens} speed={0} />
          <Wheel pos={ones} speed={iv} />
        </span>
        <span style={{ fontFamily: SERIF, fontSize: 56, color: L.ink3, marginLeft: 16, marginTop: 84 }}>/ 10</span>
      </div>
    </AbsoluteFill>
  );
};
