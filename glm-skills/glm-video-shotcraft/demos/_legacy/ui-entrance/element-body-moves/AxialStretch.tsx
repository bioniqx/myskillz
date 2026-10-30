// axial-stretch — Axial stretch motion feel
// Three cards fly in horizontally from off-screen right into place, stretching along the motion axis driven by velocity
// (scaleX peak ~2.2 / scaleY ~0.72, taffy-like elongation), settling with a Back.out rebound.
// Velocity driven by finite position difference p(f)-p(f-1); no stretch below threshold. True hold >=35f at tail.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, TitleBlock } from '../../_fixtures/Fixtures';

const W = 1920;
const CARD_W = 380;
const CARD_H = 230;
const GAP = 60;
const ROW_W = 3 * CARD_W + 2 * GAP; // 1260
const ROW_X0 = (W - ROW_W) / 2; // 330
const ROW_Y = (1080 - CARD_H) / 2; // 425

const START_X = 1980; // Completely off-screen right
const FLIGHT = 36; // Flight frames
const STAGGER = 12; // Stagger interval
const FIRST = 10; // First card launch frame
const SQUASH = 8; // Landing rebound frames

const VEL_MIN = 2; // px/frame, no stretch below this
const VEL_REF = 140; // px/frame, maximum stretch reached at this velocity
const STRETCH_X = 1.2; // scaleX peak 1 + 1.2 = 2.2
const SQUISH_Y = 0.28; // scaleY trough 1 - 0.28 = 0.72

// poly(4) in-out: mid-flight peak velocity ~4x average velocity for punchy speed
const flightEase = Easing.inOut(Easing.poly(4));

const posAt = (f: number, start: number, targetX: number): number =>
  interpolate(f, [start, start + FLIGHT], [START_X, targetX], {
    easing: flightEase,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

const FlyCard: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const start = FIRST + i * STAGGER;
  const targetX = ROW_X0 + i * (CARD_W + GAP);
  const land = start + FLIGHT;

  const x = posAt(frame, start, targetX);
  // Velocity = position difference (frame-time decoupled, purely determined by position function)
  const v = Math.abs(posAt(frame, start, targetX) - posAt(frame - 1, start, targetX));
  const s = Math.min(Math.max((v - VEL_MIN) / (VEL_REF - VEL_MIN), 0), 1);

  const stretchX = 1 + STRETCH_X * s;
  const stretchY = 1 - SQUISH_Y * s;

  // Landing rebound: scaleX overshoots to 0.85 then returns to 1 (horizontal squash on impact), 8f
  const sqX = interpolate(frame, [land, land + SQUASH / 2, land + SQUASH], [1, 0.85, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const sqY = interpolate(frame, [land, land + SQUASH / 2, land + SQUASH], [1, 1.1, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: ROW_Y,
        // Order: translate first then scale; transformOrigin at trailing motion edge (flying left -> right edge)
        transform: `translateX(${x}px) scaleX(${stretchX * sqX}) scaleY(${stretchY * sqY})`,
        transformOrigin: '100% 50%',
      }}
    >
      <Card w={CARD_W} h={CARD_H} seed={i + 1} />
    </div>
  );
};

export const AxialStretch: React.FC = () => {
  const frame = useCurrentFrame();
  const titleOp = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 120, width: '100%', textAlign: 'center', opacity: titleOp }}>
        <TitleBlock text="AXIAL STRETCH" size={72} />
      </div>
      {/* Dashed landing slot markers indicate target positions */}
      {[0, 1, 2].map((i) => (
        <div
          key={`slot-${i}`}
          style={{
            position: 'absolute',
            left: ROW_X0 + i * (CARD_W + GAP),
            top: ROW_Y,
            width: CARD_W,
            height: CARD_H,
            border: `2px dashed ${G.bar}`,
            borderRadius: 14,
            boxSizing: 'border-box',
          }}
        />
      ))}
      {[0, 1, 2].map((i) => (
        <FlyCard key={i} i={i} frame={frame} />
      ))}
    </div>
  );
};
