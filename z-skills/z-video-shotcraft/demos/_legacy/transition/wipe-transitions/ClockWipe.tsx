// clock-wipe — Clock radar wipe transition
// FakeDashboard A -> B. 30–90f an invisible radar needle sweeps one full clockwise rotation from 12 o'clock,
// Page B on top layer reveals frame-by-frame via expanding fan clip-path polygon; leading edge carries bright sweep line (white core + dark border + soft glow).
// 90–96f sweep line fades out; mask dropped at 96f (Page B displays unclipped fullscreen, sweep line unmounted),
// 96–150f completely static 54f >= 40f. Deterministic, zero randomness.
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';

const CX = 960;
const CY = 540;
const R = 1400; // Greater than center-to-corner distance ~1101, fan fully covers corners
const SEGS = 72; // Fixed and dense vertex count to prevent jagged stepping

// 12 o'clock is 0°, clockwise (screen coordinates y points down)
const polar = (deg: number, r: number): [number, number] => {
  const a = (deg * Math.PI) / 180;
  return [CX + r * Math.sin(a), CY - r * Math.cos(a)];
};

const fanClip = (theta: number): string => {
  const pts: string[] = [`${CX}px ${CY}px`];
  for (let i = 0; i <= SEGS; i++) {
    const [x, y] = polar((theta * i) / SEGS, R);
    pts.push(`${x.toFixed(1)}px ${y.toFixed(1)}px`);
  }
  return `polygon(${pts.join(', ')})`;
};

export const ClockWipe: React.FC = () => {
  const frame = useCurrentFrame();

  // 30–90f needle 0 -> 360°, linear (clock sweep requires constant speed for radar feel)
  const theta = interpolate(frame, [30, 90], [0, 360], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const wipeDone = frame >= 90;

  // Sweep line: steady bright during sweep, fades linearly 90–96f, conditionally unmounted from 96f (unmasking case)
  const lineOpacity = interpolate(frame, [90, 96], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const lineMounted = frame >= 30 && frame < 96;

  const [x2, y2] = polar(theta, R);

  return (
    <AbsoluteFill style={{ background: '#ececea' }}>
      {/* Bottom layer: Page A. Unmounted once wipe finishes (Page B fully fullscreen) */}
      {!wipeDone && (
        <AbsoluteFill>
          <FakeDashboard variant="A" />
        </AbsoluteFill>
      )}

      {/* Top layer: Page B. Clipped via fan clip-path during sweep, rendered directly without mask once complete */}
      {frame >= 30 && (
        <AbsoluteFill style={wipeDone ? undefined : { clipPath: fanClip(theta) }}>
          <FakeDashboard variant="B" />
        </AbsoluteFill>
      )}

      {/* Sweep line: soft glow + dark stroke + white core, pointing from center to current angle */}
      {lineMounted && (
        <svg
          width={1920}
          height={1080}
          style={{ position: 'absolute', inset: 0, opacity: lineOpacity, pointerEvents: 'none' }}
        >
          {/* Soft glow strip (boosted 1.5x after QA: darkened + widened for visibility against light backgrounds) */}
          <line x1={CX} y1={CY} x2={x2} y2={y2} stroke="rgba(255,255,255,0.35)" strokeWidth={26} strokeLinecap="round" />
          <line x1={CX} y1={CY} x2={x2} y2={y2} stroke="rgba(255,255,255,0.60)" strokeWidth={13} strokeLinecap="round" />
          {/* Dark outline: highlighting is invisible on white backgrounds; darkening ensures needle legibility over light areas */}
          <line x1={CX} y1={CY} x2={x2} y2={y2} stroke="rgba(0,0,0,0.55)" strokeWidth={9} strokeLinecap="round" />
          {/* White core */}
          <line x1={CX} y1={CY} x2={x2} y2={y2} stroke="rgba(255,255,255,0.95)" strokeWidth={4} strokeLinecap="round" />
        </svg>
      )}
    </AbsoluteFill>
  );
};
