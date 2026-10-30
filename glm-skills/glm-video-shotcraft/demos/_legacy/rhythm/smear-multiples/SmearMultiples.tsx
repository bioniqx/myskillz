// smear-multiples — Multiple smear-frame afterimages
// When card translates at high speed, it trails 4 distinct translucent clones (each sampled at frame - k*2,
// evaluated from same interpolation function with frame offset, purely frame-deterministic), distinct from continuous motion blur.
// Clones visible only when body velocity >25px/f (velocity = adjacent frame position difference).
// Keyframes: 0–25 left slot hold -> 25–37 translates 900px (inOut cubic, 3% overshoot) ->
// 35–38 clones delay-collapse to 0 into body + opacity to zero -> 37–43 overshoot rebound -> 43–130 fully static.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, TitleBlock } from '../../_fixtures/Fixtures';

const X0 = 240; // Left slot card left edge
const X1 = 1140; // Right slot card left edge (900px translation)
const OVER = 27; // 3% overshoot
const Y = 380; // Card top edge (vertically centered 1080-320)

// Body position: 25–37 high-speed move to overshoot point, 37–43 rebound settle, constant thereafter -> frame deterministic
const posAt = (f: number): number =>
  f < 37
    ? interpolate(f, [25, 37], [X0, X1 + OVER], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      })
    : interpolate(f, [37, 43], [X1 + OVER, X1], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      });

const Slot: React.FC<{ x: number }> = ({ x }) => (
  <div
    style={{
      position: 'absolute',
      left: x - 20,
      top: Y - 20,
      width: 520,
      height: 360,
      border: `3px dashed ${G.bar}`,
      borderRadius: 20,
      boxSizing: 'border-box',
    }}
  />
);

export const SmearMultiples: React.FC = () => {
  const frame = useCurrentFrame();
  const bodyX = posAt(frame);
  // Body speed = adjacent frame position delta; clones render only when >25px/f
  const speed = Math.abs(posAt(frame) - posAt(frame - 1));
  const speedGate = interpolate(speed, [25, 60], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Landing convergence: clones collapse delay to 0 over 3 frames (35–38) sliding into body + opacity fades to zero
  const cv = interpolate(frame, [35, 38], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  const convergeFade = frame >= 35 ? 1 - cv : 0;

  const ghostOps = [0.45, 0.3, 0.18, 0.09];

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <TitleBlock text="SMEAR MULTIPLES" size={54} />
      </div>
      <Slot x={X0} />
      <Slot x={X1} />
      {/* 4 clones: k-th takes position at frame - k*2; during convergence, delay*(1-cv) shrinks to 0 */}
      {ghostOps.map((baseOp, i) => {
        const k = i + 1;
        const gx = posAt(frame - k * 2 * (1 - cv));
        const op = baseOp * Math.max(speedGate, convergeFade);
        if (op <= 0.001) return null;
        return (
          <div key={k} style={{ position: 'absolute', left: gx, top: Y, opacity: op }}>
            <Card w={480} h={320} seed={5} />
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: bodyX, top: Y }}>
        <Card w={480} h={320} seed={5} />
      </div>
    </div>
  );
};
