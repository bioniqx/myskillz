// needle-sweep-selftest — full-arc needle sweep self-test
// Three side-by-side 270° dials within a card. After "ignition" at f12, needles sweep 0 to full arc staggered by 4f
// (outward stroke 12f ease-out), then settle back to their respective true values (return stroke ~20f: overshooting by 5–8° before rebounding),
// with numeric readouts popping up on the dial on the exact settle frame. Staggered timing creates a wave across the 3 gauges. True freeze for 80f after f60.
// Frame determinism: pure piecewise functions, clamped everywhere, outputting constants on every frame after settle.
//
// Polish upgrade: gauge context switched to dark theme (dark soft-light background + grain, dark card surface hairline + inner highlight); debug title replaced by card header
// "System health" + self-test status capsule (Running self-test… -> All systems nominal); dial faces gain subtle face and outer ring,
// 0–100 tick numbers; swept ticks light up sequentially on the outward stroke then settle back to baseline ("sweep range first"), with an amber arc trailing the needle;
// needle replaced by tapered luminous needle + metal hub cap, with angular motion ghosts during high-speed sweep; return stroke uses spring with damping derived from gauge travel,
// overshooting by 8° with single rebound and continuous velocity with no inflection points; numeric readout pops up with overshoot, metric label below.
// Brand pass: card header branded as video-shotcraft render node self-test (mark + "Render node health", switching to "Ready to render" once settled).
import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame } from 'remotion';
import { Backdrop, EASE, FONT, Grain, mix, ramp, softShadow, tracking } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const NEEDLE_SWEEP_SELFTEST_DURATION = 140; // True freeze for 80f after f60

const AMBER = '#f59e0b';
const AMBER_HI = '#fcd34d';
const RED = '#ef4444';
const INK1 = '#f3f4f7';
const INK3 = '#737885';

const CARD_W = 1500;
const CARD_H = 640;
const CARD_X = (1920 - CARD_W) / 2;
const CARD_Y = (1080 - CARD_H) / 2 + 10;

const GA_W = CARD_W / 3; // Slot width per gauge
const R = 148;
const CX = GA_W / 2;
const CY = 220;

// Dial angle d in [0, 270] -> SVG angle a = 135 + d (0 = right, clockwise, y downward)
const polar = (a: number, r: number): [number, number] => [
  CX + r * Math.cos((a * Math.PI) / 180),
  CY + r * Math.sin((a * Math.PI) / 180),
];

const arcPath = (d0: number, d1: number, r: number): string => {
  const [x0, y0] = polar(135 + d0, r);
  const [x1, y1] = polar(135 + Math.max(d0 + 0.01, d1), r);
  const large = d1 - d0 > 180 ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
};

// 3 gauges: ignition at f12, 4f stagger
const GAUGES = [
  { start: 12, target: 190, name: 'CPU' },
  { start: 16, target: 120, name: 'GPU' },
  { start: 20, target: 235, name: 'Network' },
];

// Return spring: damping ratio zeta derived from "8° overshoot" (overshoot ratio p = 8/travel, zeta = -ln p / sqrt(pi^2 + ln^2 p))
const STIFF = 120;
const dampingFor = (target: number) => {
  const p = Math.min(0.5, 8 / (270 - target));
  const lp = Math.log(p);
  const zeta = -lp / Math.sqrt(Math.PI * Math.PI + lp * lp);
  return 2 * zeta * Math.sqrt(STIFF);
};

const needleAngle = (frame: number, s: number, target: number): number => {
  if (frame <= s) return 0;
  if (frame <= s + 12) return 270 * ramp(frame, s, 12, (x) => 1 - Math.pow(1 - x, 3)); // Outward stroke: sweeps full arc with aggressive start
  if (frame >= s + 46) return target; // True freeze: locks to constant
  const k = spring({ frame: frame - (s + 12), fps: 30, config: { stiffness: STIFF, damping: dampingFor(target), mass: 1 } });
  return mix(270, target, k);
};

const Gauge: React.FC<{ start: number; target: number; name: string }> = ({ start, target, name }) => {
  const frame = useCurrentFrame();
  const d = needleAngle(frame, start, target);
  const dPrev = needleAngle(frame - 1, start, target);
  const settle = start + 32;
  const value = Math.round((target / 270) * 100);

  const pop = ramp(frame, settle, 9, EASE.overshoot);
  const popOp = ramp(frame, settle, 4, EASE.out);
  const nameOp = ramp(frame, settle + 3, 10, EASE.out);

  // Dial illuminate: dial face and outer ring light up at ignition
  const on = ramp(frame, start - 4, 10, EASE.out);
  // Swept ticks light up sequentially on outward stroke, settling back to normal brightness within 24f of full arc
  const swept = frame <= start + 12 ? d : 270;
  const calm = ramp(frame, start + 12, 24, EASE.smooth);

  const ticks: React.ReactNode[] = [];
  for (let k = 0; k <= 30; k++) {
    const dd = k * 9;
    const major = k % 3 === 0;
    const a = 135 + dd;
    const [x0, y0] = polar(a, R - 10);
    const [x1, y1] = polar(a, major ? R - 30 : R - 20);
    const lit = swept >= dd - 0.5 ? 1 - calm : 0;
    const red = dd >= 225;
    const base = red ? 0.55 : 0.22;
    ticks.push(
      <line
        key={k}
        x1={x0}
        y1={y0}
        x2={x1}
        y2={y1}
        stroke={red ? RED : '#ffffff'}
        strokeOpacity={(base + (red ? 0.4 : 0.6) * lit) * on}
        strokeWidth={major ? 3 : 1.6}
        strokeLinecap="round"
      />,
    );
    if (major) {
      const [lx, ly] = polar(a, R - 52);
      ticks.push(
        <text
          key={`l${k}`}
          x={lx}
          y={ly}
          textAnchor="middle"
          dominantBaseline="central"
          fontFamily={FONT.sans}
          fontSize={16}
          fontWeight={500}
          fill={red ? '#f87171' : '#ffffff'}
          fillOpacity={(red ? 0.7 : 0.38 + 0.4 * lit) * on}
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          {(k / 3) * 10}
        </text>,
      );
    }
  }

  // Tapered needle (local coordinates: points in 0° direction along +x, then rotated globally)
  const needle = (deg: number, opacity: number, key?: string) => {
    const [tx, ty] = polar(135, R - 13);
    const len = Math.hypot(tx - CX, ty - CY);
    return (
      <g key={key} transform={`rotate(${(135 + deg).toFixed(3)} ${CX} ${CY})`} opacity={opacity}>
        <path
          d={`M ${CX - 34} ${CY - 5} L ${CX + len} ${CY - 1.6} Q ${CX + len + 3.5} ${CY} ${CX + len} ${CY + 1.6} L ${CX - 34} ${CY + 5} Z`}
          fill="url(#nssNeedle)"
        />
      </g>
    );
  };
  const dv = d - dPrev;
  const ghosts = Math.abs(dv) > 4 ? [1, 2, 3, 4].map((g) => needle(d - (dv * g) / 4, 0.16 * (1 - g / 5), `gh${g}`)) : null;

  return (
    <div style={{ width: GA_W, height: 500, position: 'relative' }}>
      <svg width={GA_W} height={420} style={{ overflow: 'visible' }}>
        <defs>
          <linearGradient id="nssNeedle" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#b45309" />
            <stop offset="0.55" stopColor={AMBER} />
            <stop offset="1" stopColor={AMBER_HI} />
          </linearGradient>
          <radialGradient id="nssHub" cx="0.38" cy="0.32" r="0.7">
            <stop offset="0" stopColor="#6b7080" />
            <stop offset="1" stopColor="#1c1d23" />
          </radialGradient>
          <radialGradient id="nssFace" cx="0.5" cy="0.42" r="0.6">
            <stop offset="0" stopColor="#ffffff" stopOpacity={0.05} />
            <stop offset="1" stopColor="#ffffff" stopOpacity={0.01} />
          </radialGradient>
          <filter id="nssGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
        </defs>
        {/* Dial face: subtle radial gradient + hairline outer ring */}
        <circle cx={CX} cy={CY} r={R + 20} fill="url(#nssFace)" stroke="#ffffff" strokeOpacity={0.07 * on} strokeWidth={1} opacity={on} />
        {/* Arc track + redline zone */}
        <path d={arcPath(0, 270, R)} fill="none" stroke="#ffffff" strokeOpacity={0.07} strokeWidth={8} strokeLinecap="round" />
        <path d={arcPath(225, 270, R)} fill="none" stroke={RED} strokeOpacity={0.45 * on} strokeWidth={8} strokeLinecap="round" />
        {/* Glowing amber arc trailing the needle (soft glow layer + solid line layer) */}
        {d > 0.5 && (
          <>
            <path d={arcPath(0, d, R)} fill="none" stroke={AMBER} strokeOpacity={0.45} strokeWidth={10} strokeLinecap="round" filter="url(#nssGlow)" />
            <path d={arcPath(0, d, R)} fill="none" stroke={AMBER} strokeWidth={8} strokeLinecap="round" />
          </>
        )}
        {ticks}
        {/* Needle: angular ghost trail + glow + needle body */}
        {ghosts}
        <g filter="url(#nssGlow)" opacity={0.55}>
          {needle(d, 1)}
        </g>
        {needle(d, 1)}
        <circle cx={CX} cy={CY} r={19} fill="url(#nssHub)" stroke="#ffffff" strokeOpacity={0.12} strokeWidth={1} />
        <circle cx={CX} cy={CY} r={6} fill={AMBER} />
      </svg>
      {/* Readout value popping up on the settle frame + metric name */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 340,
          textAlign: 'center',
          opacity: popOp,
          transform: `scale(${mix(0.4, 1, pop).toFixed(4)})`,
          fontFamily: FONT.sans,
          whiteSpace: 'nowrap',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: 64, color: INK1, letterSpacing: tracking(64), fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        <span style={{ fontWeight: 600, fontSize: 30, color: INK3, marginLeft: 6 }}>%</span>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 424,
          textAlign: 'center',
          opacity: nameOp,
          transform: `translateY(${mix(6, 0, nameOp)}px)`,
          fontFamily: FONT.sans,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: tracking(22, true),
          textTransform: 'uppercase',
          color: INK3,
        }}
      >
        {name}
      </div>
    </div>
  );
};

export const NeedleSweepSelftest: React.FC = () => {
  const frame = useCurrentFrame();
  const inP = ramp(frame, 0, 12, EASE.snappy);
  const done = ramp(frame, 60, 8, EASE.out); // Status transition after all settle
  const pulse = 0.5 + 0.5 * Math.cos((frame / 14) * Math.PI);
  return (
    <AbsoluteFill style={{ background: '#0c0d11', overflow: 'hidden', fontFamily: FONT.sans }}>
      <Backdrop tone="dark" light={{ x: 0.5, y: 0.25 }} grain={0} />
      <div
        style={{
          position: 'absolute',
          left: CARD_X,
          top: CARD_Y,
          width: CARD_W,
          height: CARD_H,
          background: 'linear-gradient(180deg, #1a1c22 0%, #141519 100%)',
          border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 26,
          boxSizing: 'border-box',
          boxShadow: `inset 0 1px 0 rgba(255,255,255,0.06), ${softShadow(40, { color: '#000000', strength: 2.2 })}`,
          opacity: inP,
          transform: `translateY(${mix(18, 0, inP).toFixed(2)}px)`,
        }}
      >
        {/* Card header: title + self-test status capsule */}
        <ShotcraftMark size={62} tone="dark" style={{ position: 'absolute', left: 40, top: 30 }} />
        <div style={{ position: 'absolute', left: 122, top: 36 }}>
          <div style={{ fontSize: 32, fontWeight: 650, color: INK1, letterSpacing: tracking(32) }}>Render node health</div>
          <div style={{ marginTop: 7, fontSize: 19, fontWeight: 500, color: INK3 }}>
            <span style={{ fontFamily: BRAND.font, fontWeight: 600, color: '#a3a8b4' }}>{BRAND.name}</span> · render-node-02 · 3 sensors
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            right: 44,
            top: 42,
            height: 40,
            padding: '0 16px 0 13px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            borderRadius: 20,
            background: done > 0.5 ? 'rgba(52,211,153,0.10)' : 'rgba(245,158,11,0.10)',
            border: `1px solid ${done > 0.5 ? 'rgba(52,211,153,0.25)' : 'rgba(245,158,11,0.25)'}`,
            fontSize: 18,
            fontWeight: 600,
            color: done > 0.5 ? '#6ee7b7' : '#fbbf24',
            whiteSpace: 'nowrap',
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: 5,
              background: done > 0.5 ? '#34d399' : AMBER,
              opacity: done > 0.5 ? 1 : 0.45 + 0.55 * pulse,
            }}
          />
          {done > 0.5 ? 'Ready to render' : 'Running self-test…'}
        </div>
        {/* Divider hairline */}
        <div style={{ position: 'absolute', left: 44, right: 44, top: 122, height: 1, background: 'rgba(255,255,255,0.06)' }} />
        <div style={{ position: 'absolute', left: 0, top: 136, display: 'flex' }}>
          {GAUGES.map((g, i) => (
            <Gauge key={i} start={g.start} target={g.target} name={g.name} />
          ))}
        </div>
      </div>
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
