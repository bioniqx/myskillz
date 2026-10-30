// smash-cut — Smash cut (chaos -> dead silence)
// 0–41f crescendo phase: 5 cards rush past camera at high speed from multiple directions (cross-screen translate + scale 1.5 -> 3
// zoom-in + slight rotate, cards run two staggered passes, second pass faster = overall acceleration), background
// FakeDashboard A accelerates push-in 1 -> 1.55 with ease-in and rolls rotate 1.8 degrees —
// momentum peaks right before the cut. At 42f, hard cut snaps to variant B static wide shot, completely still,
// holding for 93f (>50f). The contrast is the technique itself. Total 135f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, FakeDashboard } from '../../_fixtures/Fixtures';

const CUT = 42; // Hard-cut frame: >=42 fully static

// Each flying card: two passes, second pass shorter (faster), ease-in keeps accelerating each pass.
// from/to are off-screen start/end points (center-relative coordinates), scale 1.5 -> 3 in-flight rush.
type Fly = {
  from: [number, number];
  to: [number, number];
  rot: [number, number]; // Slight rotation start -> end
  seed: number;
  w: number;
  h: number;
};

const FLIES: Fly[] = [
  { from: [-1400, -120], to: [1400, 60], rot: [-6, 5], seed: 1, w: 440, h: 290 },
  { from: [1400, 180], to: [-1400, -100], rot: [7, -4], seed: 2, w: 400, h: 260 },
  { from: [-300, -900], to: [200, 900], rot: [-3, 8], seed: 3, w: 460, h: 300 },
  { from: [-1300, 800], to: [1300, -750], rot: [5, -7], seed: 4, w: 420, h: 280 },
  { from: [1350, -780], to: [-1350, 820], rot: [-8, 4], seed: 5, w: 480, h: 310 },
];

// Card i pass k: start = i*4 + k*20, duration 16 / 12 (second pass faster).
// card4 second pass 36–48f is truncated at cut frame 42f — precisely "never decelerate into the cut".
const passWindow = (i: number, k: number): [number, number] => {
  const start = i * 4 + k * 20;
  const dur = k === 0 ? 16 : 12;
  return [start, start + dur];
};

const FlyCard: React.FC<{ fly: Fly; i: number; frame: number }> = ({ fly, i, frame }) => {
  // Find currently active pass (2 passes)
  let active: [number, number] | null = null;
  for (let k = 0; k < 2; k++) {
    const [s, e] = passWindow(i, k);
    if (frame >= s && frame < e) { active = [s, e]; break; }
  }
  if (!active) return null;
  const [s, e] = active;
  // ease-in: accelerates throughout, faster toward end
  const p = interpolate(frame, [s, e], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });
  const x = fly.from[0] + (fly.to[0] - fly.from[0]) * p;
  const y = fly.from[1] + (fly.to[1] - fly.from[1]) * p;
  const rot = fly.rot[0] + (fly.rot[1] - fly.rot[0]) * p;
  const scale = 1.5 + 1.5 * p; // 1.5 -> 3 camera rush
  // Velocity-gated directional blur feel: instantaneous speed proportional to p under ease-in, faster = blurrier
  const blur = 1 + 4 * p;
  return (
    <div style={{
      position: 'absolute', left: 960 - fly.w / 2, top: 540 - fly.h / 2,
      transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`,
      filter: `blur(${blur}px)`,
    }}>
      <Card w={fly.w} h={fly.h} seed={fly.seed}
        style={{ boxShadow: '0 12px 40px rgba(0,0,0,0.25)' }} />
    </div>
  );
};

export const SmashCut: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Dead silence phase: variant B static wide shot from 42f, zero animated properties ——
  if (frame >= CUT) {
    return <FakeDashboard variant="B" />;
  }

  // —— Crescendo phase: background ease-in accelerated push-in + roll, still accelerating 3f before cut ——
  const bgScale = interpolate(frame, [0, CUT], [1, 1.55], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });
  const bgRot = interpolate(frame, [0, CUT], [0, 1.8], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
      <div style={{
        width: 1920, height: 1080,
        transform: `scale(${bgScale}) rotate(${bgRot}deg)`,
        transformOrigin: '50% 50%',
        filter: 'blur(1.5px)', // Slight background blur to highlight foreground flying cards
      }}>
        <FakeDashboard variant="A" />
      </div>
      {FLIES.map((fly, i) => (
        <FlyCard key={i} fly={fly} i={i} frame={frame} />
      ))}
    </div>
  );
};
