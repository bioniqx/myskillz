// flyline-arc — glowing flyline trajectory connection
// Dark-field FakeDashboard A as background; bezier curve launches from top-left card to bottom-right card (22f out-cubic growth),
// bright leading beacon with comet trail; destination card stroke pulses on arrival. Second line relays to top-mid card.
// Static hold at finish: all animations conclude before f86, freezing completely.
//
// Polish pass: dark-field dashboard dimmed to 0.65 + vignette; flyline becomes hero foreground;
// line updated to white core + dual indigo glow layers;
// butt-end segments eliminate overlap beads; beacon head features comet tail + indigo halo; start anchor and destination node;
// card pulse illuminates with accent stroke + outer glow + shockwave ring on arrival; grain overlay.
import React, { useId } from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';
import { Grain, Vignette } from '../../_fixtures/Polish';

export const FLYLINE_ARC_DURATION = 140; // ~4.7s: animation ends before f86, last 54f static hold

type Pt = { x: number; y: number };

// Cubic bezier path sampling
const bez = (p0: Pt, p1: Pt, p2: Pt, p3: Pt, t: number): Pt => {
  const u = 1 - t;
  return {
    x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
    y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y,
  };
};

const N = 100; // Number of sampling segments
const GLOW = '128,138,255'; // Flyline glow color (indigo palette)

// Card layout geometry (FakeDashboard variant A grid)
const CARD_LT = { x: 256, y: 108, w: 524, h: 454, cx: 518, cy: 335 }; // Top-left
const CARD_RB = { x: 1360, y: 590, w: 524, h: 454, cx: 1622, cy: 817 }; // Bottom-right
const CARD_TM = { x: 808, y: 108, w: 524, h: 454, cx: 1070, cy: 335 }; // Top-middle

const clampX = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

// Single flyline: indigo glow base + segmented white core with comet tail + leading beacon (conditionally mounted)
const Flyline: React.FC<{
  frame: number;
  start: number; // Growth start frame
  haloId: string; // Beacon radial gradient ID
  p0: Pt; p1: Pt; p2: Pt; p3: Pt;
}> = ({ frame, start, haloId, p0, p1, p2, p3 }) => {
  const DUR = 22;
  if (frame < start) return null;
  const e = interpolate(frame, [start, start + DUR], [0, 1], { easing: Easing.out(Easing.cubic), ...clampX });
  const growing = frame < start + DUR;
  // Tail brightness homogenizes over 10f post-arrival (ease-out) -> static hold
  const settle = interpolate(frame, [start + DUR, start + DUR + 10], [0, 1], { easing: Easing.out(Easing.quad), ...clampX });
  // Start anchor: illuminates 6f before launch
  const anchor = interpolate(frame, [start, start + 6], [0, 1], { easing: Easing.out(Easing.cubic), ...clampX });

  const pts: Pt[] = [];
  const nDrawn = Math.max(2, Math.ceil(e * N) + 1);
  for (let i = 0; i < nDrawn; i++) {
    const t = Math.min(i / N, e);
    pts.push(bez(p0, p1, p2, p3, t));
  }
  const head = bez(p0, p1, p2, p3, e);
  pts[pts.length - 1] = head;

  const poly = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  // Segment opacity based on distance from head; settles to 1 on arrival without segment overlap beads
  const segs = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const tSeg = Math.min(i / N, e) / Math.max(e, 0.001); // 0 tail -> 1 head
    const grad = 0.3 + 0.7 * tSeg * tSeg;
    const op = grad + (1 - grad) * settle;
    segs.push(
      <line
        key={i}
        x1={pts[i].x} y1={pts[i].y} x2={pts[i + 1].x} y2={pts[i + 1].y}
        stroke="#f6f6ff" strokeWidth={3.5} strokeLinecap="butt" strokeOpacity={op}
      />
    );
  }
  const comet = pts.slice(Math.max(0, pts.length - 9)).map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  return (
    <g>
      {/* Start anchor dot */}
      <circle cx={p0.x} cy={p0.y} r={9 * anchor} fill={`rgba(${GLOW},0.25)`} />
      <circle cx={p0.x} cy={p0.y} r={4.5 * anchor} fill="#ffffff" />
      {/* Glow backing: dual broad and medium glow layers */}
      <polyline points={poly} fill="none" stroke={`rgb(${GLOW})`} strokeWidth={18} strokeLinecap="round" strokeLinejoin="round" strokeOpacity={0.1 + 0.04 * settle} />
      <polyline points={poly} fill="none" stroke="rgb(150,160,255)" strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" strokeOpacity={0.24} />
      {segs}
      {/* Beacon head + comet tail: mounted only during growth phase */}
      {growing && (
        <g>
          <polyline points={comet} fill="none" stroke="#ffffff" strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" strokeOpacity={0.55} />
          <circle cx={head.x} cy={head.y} r={40} fill={`url(#${haloId})`} />
          <circle cx={head.x} cy={head.y} r={7} fill="#ffffff" />
        </g>
      )}
      {/* Destination node: persists post-arrival */}
      {!growing && (
        <g>
          <circle cx={p3.x} cy={p3.y} r={11} fill={`rgba(${GLOW},0.22)`} />
          <circle cx={p3.x} cy={p3.y} r={5} fill="#ffffff" />
        </g>
      )}
    </g>
  );
};

// Destination card pulse: accent stroke + outer glow + shockwave ring on arrival (conditionally mounted)
const CardPulse: React.FC<{
  frame: number;
  at: number; // Trigger frame
  rect: { x: number; y: number; w: number; h: number; cx: number; cy: number };
}> = ({ frame, at, rect }) => {
  if (frame < at) return null;
  // Rise over 6f out-cubic, decay over 12f to 0.25 residual stroke indicating connection
  const amp =
    frame <= at + 6
      ? interpolate(frame, [at, at + 6], [0, 1], { easing: Easing.out(Easing.cubic), ...clampX })
      : interpolate(frame, [at + 6, at + 18], [1, 0.25], { easing: Easing.out(Easing.quad), ...clampX });
  const ring = interpolate(frame, [at, at + 14], [0, 1], { easing: Easing.out(Easing.cubic), ...clampX });
  return (
    <g>
      <defs>
        <filter id={`pulse-glow-${at}`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={10} />
        </filter>
      </defs>
      <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={14} fill="none" stroke={`rgb(${GLOW})`} strokeWidth={8}
        strokeOpacity={0.5 * amp} filter={`url(#pulse-glow-${at})`} />
      <rect x={rect.x} y={rect.y} width={rect.w} height={rect.h} rx={14} fill={`rgba(200,206,255,${(0.05 * amp).toFixed(3)})`} />
      <rect x={rect.x + 0.75} y={rect.y + 0.75} width={rect.w - 1.5} height={rect.h - 1.5} rx={13.5} fill="none"
        stroke="#c9ceff" strokeWidth={1.5} strokeOpacity={0.9 * amp} />
      {ring < 1 && (
        <circle cx={rect.cx} cy={rect.cy} r={12 + 80 * ring} fill="none" stroke="#c9ceff"
          strokeWidth={2.5 * (1 - ring) + 0.5} strokeOpacity={0.75 * (1 - ring)} />
      )}
    </g>
  );
};

export const FlylineArc: React.FC = () => {
  const frame = useCurrentFrame();
  // Instance-unique gradient IDs (sanitized for url() syntax)
  const haloId = `headHalo-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;

  // Timeline: Line 1 grows 10-32f -> Card RB pulses 32-50f; Line 2 grows 46-68f -> Card TM pulses 68-86f
  // Complete static hold after f86 (54f hold)
  const L1 = { p0: { x: CARD_LT.cx, y: CARD_LT.cy }, p1: { x: 818, y: 60 }, p2: { x: 1322, y: 380 }, p3: { x: CARD_RB.cx, y: CARD_RB.cy } };
  const L2 = { p0: { x: CARD_RB.cx, y: CARD_RB.cy }, p1: { x: 1760, y: 560 }, p2: { x: 1360, y: 150 }, p3: { x: CARD_TM.cx, y: CARD_TM.cy } };

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', background: '#0b0c10', overflow: 'hidden' }}>
      {/* Background: dark dashboard dimmed to 0.65, static */}
      <div style={{ filter: 'brightness(0.65) saturate(0.9)' }}>
        <FakeDashboard variant="A" tone="dark" />
      </div>
      <Vignette strength={0.5} inner={0.45} color="#030408" />
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
        <defs>
          <radialGradient id={haloId}>
            <stop offset="0%" stopColor="rgba(255,255,255,0.6)" />
            <stop offset="30%" stopColor="rgba(170,178,255,0.3)" />
            <stop offset="100%" stopColor="rgba(128,138,255,0)" />
          </radialGradient>
        </defs>
        <CardPulse frame={frame} at={32} rect={CARD_RB} />
        <CardPulse frame={frame} at={68} rect={CARD_TM} />
        <Flyline frame={frame} start={10} haloId={haloId} {...L1} />
        <Flyline frame={frame} start={46} haloId={haloId} {...L2} />
      </svg>
      <Grain opacity={0.07} blend="soft-light" />
    </div>
  );
};
