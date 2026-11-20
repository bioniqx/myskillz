// flip-grid-reflow — Grid FLIP reflow
// 6 Cards initially arranged in a single horizontal row (marquee style, centered above midline) holding for 30f, collective repositioning at beat:
// Each card flies along a straight line to its 3×2 grid target slot (precomputed coordinate tables), scale 1 -> 1.28,
// delay = cardIndex * 1.5f micro-stagger, 16f inOut(cubic) + 3f settle overshoot 1.02.
// After all cards land, an overall darken pulse concludes the motion. Holds completely static >= 40f at tail.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, TitleBlock } from '../../_fixtures/Fixtures';

const CARD_W = 280;
const CARD_H = 170;
const N = 6;

// ---- Coordinate Table A: Horizontal single row (24px card gap, above screen center) ----
// Total width 6*280 + 5*24 = 1800, x0 = 60; center y = 330
const ROW_Y = 330;
const ROW_CENTERS: Array<[number, number]> = Array.from({ length: N }, (_, i) => [
  60 + CARD_W / 2 + i * (CARD_W + 24),
  ROW_Y,
]); // x: 200, 504, 808, 1112, 1416, 1720

// ---- Coordinate Table B: 3×2 grid (cards scaled 1.28 -> 358.4×217.6, grid gap 30px) ----
// Grid total width 3*358.4 + 2*30 = 1135.2 -> x0 = 392.4; total height 2*217.6 + 30 = 465.2 -> y0 = 307.4
const GC = [571.6, 960, 1348.4]; // Column centers
const GR = [416.2, 663.8]; // Row centers
// Interleaved mapping: even indices go to top row, odd to bottom row (straight flight paths, no cross-collisions)
const GRID_CENTERS: Array<[number, number]> = [
  [GC[0], GR[0]], // card0 -> top-left
  [GC[0], GR[1]], // card1 -> bottom-left
  [GC[1], GR[0]], // card2 -> top-center
  [GC[1], GR[1]], // card3 -> bottom-center
  [GC[2], GR[0]], // card4 -> top-right
  [GC[2], GR[1]], // card5 -> bottom-right
];

const BEAT = 30; // Beat frame
const STAGGER = 1.5; // Per-card delay
const MOVE = 16; // Flight duration (frames)
const SETTLE = 3; // Settle overshoot duration (frames)
const SCALE_END = 1.28;
const OVERSHOOT = 1.02;
// Last card fully settles: 30 + 5*1.5 + 16 + 3 = 56.5
const ALL_SETTLED = BEAT + (N - 1) * STAGGER + MOVE + SETTLE; // 56.5

// Darken pulse: f58 -> f61 trough -> f64 recovery (trough brightness 0.78, spec 4f relaxed to 6f for perceptibility)
const PULSE_IN = 58;
const PULSE_MID = 61;
const PULSE_OUT = 64;

const moveEase = Easing.inOut(Easing.cubic);

const FlipCard: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const t0 = BEAT + i * STAGGER;
  const [x0, y0] = ROW_CENTERS[i];
  const [x1, y1] = GRID_CENTERS[i];

  const x = interpolate(frame, [t0, t0 + MOVE], [x0, x1], {
    easing: moveEase, extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const y = interpolate(frame, [t0, t0 + MOVE], [y0, y1], {
    easing: moveEase, extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // scale: ramps to 1.28*1.02 over 16f, then settles back to 1.28 over 3f
  const sUp = interpolate(frame, [t0, t0 + MOVE], [1, SCALE_END * OVERSHOOT], {
    easing: moveEase, extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const sBack = interpolate(frame, [t0 + MOVE, t0 + MOVE + SETTLE], [SCALE_END * OVERSHOOT, SCALE_END], {
    easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const s = frame < t0 + MOVE ? sUp : sBack;

  return (
    <div
      style={{
        position: 'absolute',
        left: x - CARD_W / 2,
        top: y - CARD_H / 2,
        width: CARD_W,
        height: CARD_H,
        transform: `scale(${s})`,
        transformOrigin: '50% 50%',
        zIndex: i,
      }}
    >
      <Card w={CARD_W} h={CARD_H} seed={i + 1} />
    </div>
  );
};

export const FlipGridReflow: React.FC = () => {
  const frame = useCurrentFrame();

  // Darken pulse: filter attached only inside pulse window, completely unmounted outside (zero overhead)
  const pulsing = frame >= PULSE_IN && frame <= PULSE_OUT;
  const bright = pulsing
    ? interpolate(frame, [PULSE_IN, PULSE_MID, PULSE_OUT], [1, 0.78, 1], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      })
    : 1;

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.bg,
        position: 'relative',
        overflow: 'hidden',
        ...(pulsing ? { filter: `brightness(${bright})` } : {}),
      }}
    >
      <div style={{ position: 'absolute', left: 70, top: 56 }}>
        <TitleBlock text="FLIP GRID REFLOW" size={44} />
      </div>
      {Array.from({ length: N }).map((_, i) => (
        <FlipCard key={i} i={i} frame={frame} />
      ))}
    </div>
  );
};
