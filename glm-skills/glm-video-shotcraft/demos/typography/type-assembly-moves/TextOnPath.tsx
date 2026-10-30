// text-on-path — characters stream along rising growth curve, rotating tangentially along path;
// characters then elevate and orient into a horizontal headline. Curve evolves with lead character.
//
// Redesign (midnight: dark-field data launch keynote):
// - look = midnight (dark blue night, electric blue, cyan accent). Hero is a revenue growth curve filling screen: 5px round stroke +
//   gradient fill area + glow, with leading cyan beacon; background of 4 grid hairlines + mono ticks.
// - Headline "UP AND TO THE RIGHT" 92px / 800 all-caps — literal expression of trajectory aligning typography with data.
//   Progresses along arc length (lead char in front, tangential rotation), with velocity motion blur.
// - Orientation transition: each char follows curved trajectory (snappy y lift, swift x translate)
//   to top-left headline slot, staggered 1.1f with subtle overshoot.
// - Aftermath: beacon reaches apex -> metric badge "$48.6M ARR" + "▲ 312%" springs up, kicker and subtitle rise;
//   slow 1.5% push-in during hold.
//
// Timeline (30fps, total 160f):
//   0-16    Grid lines wipe in from left, ticks fade in; stage light present from frame 0
//   4-64    String advances along curve 60f (gentle start, long ease-out), curve grows with lead char
//   64-72   Pause 8f: full sentence legible along curve
//   72-110  Characters elevate and orient into title (18f/char, 1.1f stagger), curve finishes
//   92-110  Subtitle / kicker rise; 98 metric badge springs up; 100+ quarter markers ignite
//   108-160 Hold (slow 1.5% push)
import React, { useLayoutEffect, useRef, useState } from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, bezier, mix, ramp, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, glow, springAt, type } from '../../_fixtures/Look';

export const TEXT_ON_PATH_DURATION = 160;

const L = LOOKS.midnight;

// Growth curve: bottom-left -> top-right with radius accommodating 92px font
const P0 = { x: 150, y: 930 };
const P1 = { x: 860, y: 920 };
const P2 = { x: 1300, y: 780 };
const P3 = { x: 1700, y: 400 };

const bez = (t: number) => {
  const u = 1 - t;
  return {
    x: u * u * u * P0.x + 3 * u * u * t * P1.x + 3 * u * t * t * P2.x + t * t * t * P3.x,
    y: u * u * u * P0.y + 3 * u * u * t * P1.y + 3 * u * t * t * P2.y + t * t * t * P3.y,
  };
};
const tangent = (t: number) => {
  const u = 1 - t;
  const dx = 3 * u * u * (P1.x - P0.x) + 6 * u * t * (P2.x - P1.x) + 3 * t * t * (P3.x - P2.x);
  const dy = 3 * u * u * (P1.y - P0.y) + 6 * u * t * (P2.y - P1.y) + 3 * t * t * (P3.y - P2.y);
  return (Math.atan2(dy, dx) * 180) / Math.PI;
};

// Arc-length table: s(t) sampling and inverse lookup t(s)
const SAMPLES = 300;
const ARC: number[] = (() => {
  const a = [0];
  let prev = bez(0);
  for (let k = 1; k <= SAMPLES; k++) {
    const p = bez(k / SAMPLES);
    a.push(a[k - 1] + Math.hypot(p.x - prev.x, p.y - prev.y));
    prev = p;
  }
  return a;
})();
const LEN = ARC[SAMPLES];
const tAtS = (s: number) => {
  const v = Math.max(0, Math.min(LEN, s));
  let lo = 0;
  let hi = SAMPLES;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (ARC[mid] < v) lo = mid;
    else hi = mid;
  }
  const seg = ARC[hi] - ARC[lo] || 1;
  return (lo + (v - ARC[lo]) / seg) / SAMPLES;
};

const TEXT = 'UP AND TO THE RIGHT';
const N = TEXT.length;
const FS = 92;
const TRACK = '-0.01em';
const CHAR_W = 60; // Fallback character width
const FINAL = { x: 150, y: 250 }; // Final title slot: left x, baseline center y
const T0 = 4; // Launch frame
const TRAVEL = 60; // Path travel duration
const HOLD = 8; // On-curve pause duration
const SETTLE = 18; // Per-char orientation duration
const SETTLE_STAG = 1.1;
const END_S = LEN * 0.94; // Lead char center lands at 94% arc length
const TRAVEL_EASE = bezier(0.42, 0, 0.12, 1); // Gentle start, long ease-out
const LIFT_EASE = bezier(0.3, 1.22, 0.6, 1); // Lift: rapid arrival with ~4% overshoot settle

// Grid (y) and ticks
const GRID = [400, 577, 753, 930];
const TICKS = ['$60M', '$40M', '$20M', '$0'];
const QUARTERS: [number, string][] = [[0.42, 'Q2 · $11M'], [0.66, 'Q3 · $24M'], [0.85, 'Q4 · $37M']];
const MONTHS = ['JAN', 'MAR', 'MAY', 'JUL', 'SEP', 'NOV'];

export const TextOnPath: React.FC = () => {
  const frame = useCurrentFrame();

  // Measured character centers relative to string start
  const measRef = useRef<HTMLDivElement>(null);
  const [centers, setCenters] = useState<number[]>(() => TEXT.split('').map((_, i) => i * CHAR_W + CHAR_W / 2));
  useLayoutEffect(() => {
    const el = measRef.current;
    if (!el) return;
    const kids = Array.from(el.children) as HTMLElement[];
    const c = kids.map((k) => k.offsetLeft + k.offsetWidth / 2);
    if (el.offsetWidth > 0) setCenters(c);
  }, []);
  const lastC = centers[N - 1];

  // Lead character advances along arc length
  const headAt = (f: number) => -24 + (END_S + 24) * ramp(f, T0, TRAVEL, TRAVEL_EASE);
  const headS = headAt(frame);
  const headV = Math.abs(velocity(headAt, frame)); // px/frame
  // Curve evolution: tracks lead character, completes remaining segment on arrival
  const tail = ramp(frame, T0 + TRAVEL - 4, 30, EASE.out);
  const evolveS = Math.min(LEN, Math.max(headS + FS * 0.45, 0) * (1 - tail) + LEN * tail);
  const tip = bez(tAtS(evolveS));
  const evolveFrac = evolveS / LEN;

  const pathD = `M ${P0.x} ${P0.y} C ${P1.x} ${P1.y}, ${P2.x} ${P2.y}, ${P3.x} ${P3.y}`;
  const areaD = `${pathD} L ${P3.x} ${GRID[3]} L ${P0.x} ${GRID[3]} Z`;
  const areaFull = ramp(frame, 70, 34, EASE.out);

  // Slow push toward curve apex during hold
  const push = 1 + 0.015 * ramp(frame, 100, 60, EASE.swift);
  // Metric badge
  const badge = springAt(frame, 98, { damping: 15, stiffness: 190 });
  const badgeIn = ramp(frame, 98, 8, EASE.out);
  const pulse = ramp(frame, T0 + TRAVEL + 2, 24, EASE.out); // Pulse ring on apex arrival

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.78, y: 0.28 }} fill={{ x: 0.12, y: 0.95 }} breathe={0.6} />
      {/* Hidden measurement row */} 
      <div ref={measRef} style={{ position: 'absolute', visibility: 'hidden', whiteSpace: 'pre', display: 'flex', ...type(FS, 800, { caps: true }), letterSpacing: TRACK }}>
        {TEXT.split('').map((ch, i) => <span key={i}>{ch === ' ' ? ' ' : ch}</span>)}
      </div>

      <AbsoluteFill style={{ transform: `scale(${push.toFixed(5)})`, transformOrigin: '70% 40%' }}>
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <linearGradient id="top-area" x1="0" y1={400} x2="0" y2={930} gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor={L.accent} stopOpacity={0.34} />
              <stop offset="0.6" stopColor={L.accent} stopOpacity={0.08} />
              <stop offset="1" stopColor={L.accent} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="top-line" x1={P0.x} y1="0" x2={P3.x} y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor={alpha(L.accent, 0.35)} />
              <stop offset="0.55" stopColor={L.accent} />
              <stop offset="1" stopColor="#9fc0ff" />
            </linearGradient>
            <clipPath id="top-reveal"><rect x={0} y={0} width={tip.x} height={1080} /></clipPath>
            <filter id="top-glow" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="10" /></filter>
          </defs>
          {/* Hairline grid + ticks */} 
          {GRID.map((y, k) => {
            const g = ramp(frame, k * 3, 18, EASE.out);
            return (
              <g key={y} opacity={0.4 + 0.6 * g}>
                <line x1={150} x2={150 + 1560 * g} y1={y} y2={y} stroke={k === 3 ? alpha(L.ink, 0.22) : L.line} strokeWidth={1.5} strokeDasharray={k === 3 ? undefined : '2 10'} />
                <text x={1740} y={y + 8} fontFamily={FONT.mono} fontSize={22} fill={L.ink3} opacity={g}>{TICKS[k]}</text>
              </g>
            );
          })}
          {MONTHS.map((m, k) => (
            <text key={m} x={150 + k * 300} y={980} fontFamily={FONT.mono} fontSize={22} letterSpacing="0.12em" fill={L.ink3} opacity={ramp(frame, 6 + k * 2, 16, EASE.out)}>{m}</text>
          ))}
          {/* Area under curve: reveals with curve, fills completely at top */} 
          <path d={areaD} fill="url(#top-area)" clipPath="url(#top-reveal)" opacity={0.55 + 0.45 * areaFull} />
          {/* Outer glow + hero curve */} 
          <path d={pathD} fill="none" stroke={L.accent} strokeWidth={14} strokeLinecap="round" opacity={0.55} filter="url(#top-glow)"
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - evolveFrac} />
          <path d={pathD} fill="none" stroke="url(#top-line)" strokeWidth={5} strokeLinecap="round"
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - evolveFrac} />
          {/* Quarter markers: light up sequentially after curve passes */} 
          {QUARTERS.map(([tq, lab], k) => {
            const q = bez(tq);
            const on = ramp(frame, 100 + k * 4, 12, EASE.overshoot);
            if (evolveFrac < tq || on <= 0) return null;
            return (
              <g key={lab} opacity={Math.min(1, on)}>
                <line x1={q.x} x2={q.x} y1={q.y + 14} y2={GRID[3]} stroke={alpha(L.accent, 0.25)} strokeWidth={1.5} strokeDasharray="2 6" />
                <circle cx={q.x} cy={q.y} r={7 * on} fill={L.bg[1]} stroke={L.accent} strokeWidth={3} />
                <text x={q.x + 16} y={q.y + 34} fontFamily={FONT.mono} fontSize={22} fill={L.ink2}>{lab}</text>
              </g>
            );
          })}
          {/* Lead beacon + apex pulse */} 
          {evolveFrac > 0.002 && (
            <g>
              {pulse > 0 && pulse < 1 && <circle cx={tip.x} cy={tip.y} r={12 + 60 * pulse} fill="none" stroke={L.accent2} strokeWidth={2} opacity={1 - pulse} />}
              <circle cx={tip.x} cy={tip.y} r={22} fill={L.accent2} opacity={0.18} />
              <circle cx={tip.x} cy={tip.y} r={9} fill={L.ink} stroke={L.accent2} strokeWidth={4} />
            </g>
          )}
        </svg>

        {/* Metric badge anchored below apex */} 
        <div style={{
          position: 'absolute', left: P3.x - 56, top: P3.y - 168, transform: `translateX(-100%) translateY(${((1 - badge) * 30).toFixed(2)}px) scale(${(0.9 + 0.1 * badge).toFixed(4)})`,
          transformOrigin: '100% 100%', opacity: badgeIn, textAlign: 'right',
        }}>
          <div style={{ ...type(84, 760), color: L.ink, textShadow: glow(L.accent, 0.35) }}>$48.6M</div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 18, marginTop: 10, alignItems: 'baseline' }}>
            <span style={{ ...type(32, 500), color: L.ink2 }}>ARR</span>
            <span style={{ ...type(32, 700), color: L.accent2 }}>▲ 312%</span>
          </div>
        </div>

        {/* Kicker + subtitle */} 
        <div style={{ position: 'absolute', left: FINAL.x + 4, top: FINAL.y - 112, ...type(26, 700, { caps: true, mono: true }), letterSpacing: '0.18em', color: L.accent }}>
          <TextReveal text="FY2026 · Annual report" start={96} by="word" variant="rise" each={14} gap={3} />
        </div>
        <div style={{ position: 'absolute', left: FINAL.x + 4, top: FINAL.y + 70, ...type(40, 450), color: L.ink2 }}>
          <TextReveal text="Every quarter beat the last one." start={92} by="word" variant="blur" each={16} gap={2.5} />
        </div>

        {/* Characters: advance along curve -> lift and orient */} 
        {TEXT.split('').map((ch, i) => {
          if (ch === ' ') return null;
          const s = headS - (lastC - centers[i]);
          const onPath = bez(tAtS(s));
          const pre = Math.min(0, s); // Pre-curve characters held along start tangent
          const ang0 = tangent(0) * (Math.PI / 180);
          const px = onPath.x + Math.cos(ang0) * pre;
          const py = onPath.y + Math.sin(ang0) * pre;
          const angOnCurve = tangent(tAtS(s));
          const st = T0 + TRAVEL + HOLD + i * SETTLE_STAG;
          const sx = ramp(frame, st, SETTLE, EASE.swift); // Horizontal translation (in-out)
          const sy = ramp(frame, st, SETTLE, LIFT_EASE); // Vertical lift with ~4% overshoot
          const sr = ramp(frame, st + 2, SETTLE, EASE.out); // Rotation converges 2f later
          const x = mix(px, FINAL.x + centers[i], sx);
          const y = mix(py, FINAL.y, sy);
          const ang = angOnCurve * (1 - sr);
          const lift = -0.4 * FS * (1 - Math.min(1, sy)); // Character baseline to center
          const op = ramp(s, -FS * 0.9, FS * 0.9, EASE.linear);
          // Horizontal motion blur during rapid motion
          const moving = frame < st ? Math.min(6, headV * 0.12) : 0;
          return (
            <div key={i} style={{
              position: 'absolute', left: x, top: y, opacity: op,
              transform: `translate(-50%, -50%) rotate(${ang.toFixed(3)}deg) translateY(${lift.toFixed(2)}px)`,
              ...type(FS, 800, { caps: true }), letterSpacing: TRACK, lineHeight: 1, color: L.ink, whiteSpace: 'pre',
              textShadow: `${(-moving * 1.4).toFixed(1)}px 0 ${(moving * 2).toFixed(1)}px ${alpha(L.accent, 0.5)}, 0 0 24px ${alpha(L.accent, 0.25)}`,
            }}>
              {ch}
            </div>
          );
        })}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
