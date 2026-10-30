import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { Card, G } from '../../_fixtures/Fixtures';

// grid-wave-flip [entrance/exit]: 3x3 grey-back card wall flips 180° along diagonal wavefront via rotateX,
// turning grey backs into front content cards; wave sweeps screen in ~1 second, final card settles with subtle overshoot.
// Structure: hold 20f -> delay = (row+col)*6f, 14f per card bezier(0.35,0,0.25,1) -> final card overshoot rebound -> static settle.

const COLS = 3;
const ROWS = 3;
const CELL_W = 520;
const CELL_H = 280;
const GAP = 36;
const HOLD = 20; // Initial hold
const STAGGER = 6; // Diagonal wavefront step
const FLIP = 14; // Single card flip duration

const flipEase = Easing.bezier(0.35, 0, 0.25, 1);

// Per-card flip angle: standard cards 0->180; final card (wavefront tail) overshoots to ~190 before settling back to 180
const angleAt = (frame: number, row: number, col: number): number => {
  const delay = HOLD + (row + col) * STAGGER;
  const isLast = row === ROWS - 1 && col === COLS - 1;
  if (!isLast) {
    return interpolate(frame, [delay, delay + FLIP], [0, 180], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: flipEase,
    });
  }
  // Overshoot: 14f pushes to 190°, then 8f rebounds back to 180°
  const main = interpolate(frame, [delay, delay + FLIP], [0, 190], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: flipEase,
  });
  const settle = interpolate(frame, [delay + FLIP, delay + FLIP + 8], [0, -10], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  return main + settle;
};

export const GridWaveFlip: React.FC = () => {
  const frame = useCurrentFrame();
  const wallW = COLS * CELL_W + (COLS - 1) * GAP;
  const wallH = ROWS * CELL_H + (ROWS - 1) * GAP;

  return (
    <AbsoluteFill
      style={{
        background: G.bg,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {/* Card wall: shared perspective 1200px container, single vanishing point for full wall */}
      <div
        style={{
          width: wallW,
          height: wallH,
          perspective: 1200,
          perspectiveOrigin: '50% 50%',
          display: 'grid',
          gridTemplateColumns: `repeat(${COLS}, ${CELL_W}px)`,
          gridTemplateRows: `repeat(${ROWS}, ${CELL_H}px)`,
          gap: GAP,
        }}
      >
        {Array.from({ length: ROWS * COLS }).map((_, i) => {
          const row = Math.floor(i / COLS);
          const col = i % COLS;
          const angle = angleAt(frame, row, col);
          // Specular line: brightest when flipped edge-on at 90°, position sweeps from top to bottom with angle
          const glow = Math.max(0, 1 - Math.abs(angle - 90) / 45);
          const glowTop = interpolate(angle, [45, 135], [8, 92], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          // Shadow lifts during flip, retracts upon settling
          const lift = Math.sin(Math.min(Math.max(angle, 0), 180) * (Math.PI / 180));
          return (
            <div key={i} style={{ width: CELL_W, height: CELL_H, position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  transformStyle: 'preserve-3d',
                  transform: `rotateX(${angle}deg)`,
                  boxShadow: `0 ${4 + lift * 22}px ${10 + lift * 40}px rgba(0,0,0,${0.08 + lift * 0.16})`,
                  borderRadius: 14,
                }}
              >
                {/* Grey back face (initially facing out) */}
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    backfaceVisibility: 'hidden',
                    WebkitBackfaceVisibility: 'hidden',
                    background: '#c7c7c5',
                    border: `2px solid ${G.bar}`,
                    borderRadius: 14,
                    boxSizing: 'border-box',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  {/* Back face has only a matte dot mark to emphasize "grey back" */}
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 22,
                      background: G.mid,
                      opacity: 0.55,
                    }}
                  />
                </div>
                {/* Front content card (pre-rotated 180°, faces outward when flipped) */}
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    backfaceVisibility: 'hidden',
                    WebkitBackfaceVisibility: 'hidden',
                    transform: 'rotateX(180deg)',
                    borderRadius: 14,
                  }}
                >
                  <Card w={CELL_W} h={CELL_H} seed={i + 1} style={{ width: '100%', height: '100%' }} />
                </div>
              </div>
              {/* Edge-on specular highlight: fixed to grid slot, moves vertically with angle rather than rotating with card */}
              {glow > 0.01 && (
                <div
                  style={{
                    position: 'absolute',
                    left: '4%',
                    width: '92%',
                    top: `${glowTop}%`,
                    height: 4,
                    borderRadius: 2,
                    background:
                      'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.95) 50%, rgba(255,255,255,0) 100%)',
                    boxShadow: '0 0 14px rgba(255,255,255,0.8)',
                    opacity: glow,
                    pointerEvents: 'none',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
