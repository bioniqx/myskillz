// keycap-smash-cut | Keycap press trigger + smash cut punctuation (keycap-press-trigger × smash-cut)
// 0–25f Light background center 3D keycap (⌘⏎) floating breathing → 25–28f slammed down (3f sink 14px +
// base squashed 12→3px + key face darkens) + bottom bright ring (expansion out-cubic / dissipation linear decoupled)
// → Press immediately triggers rumble phase 28–58f: 5 cards + 1 panel rush in from all directions at high speed
// (ease-in full acceleration + scale 1.5→3 in-your-face zoom + velocity-gated blur), background overall
// ease-in push-in 1→1.3 + roll 1.5° — momentum peaks right before the cut point → 58f single-frame smash cut:
// FakeDashboard variant="A" orderly static panorama, keycap shrunk into a small element firmly embedded in
// the top bar corner (fuse echo), dead silence 82f (>50f). Total 140f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, FakeDashboard } from '../../_fixtures/Fixtures';

const T = {
  press: 25,      // Press starts (breathing cycle 25f, displacement reaches zero at this frame)
  pressEnd: 28,   // 3f bottomed out, triggers rumble phase on the same frame
  ringGrowEnd: 46, // Bright ring expansion ends (out-cubic)
  ringFadeEnd: 52, // Bright ring dissipation ends (linear, frame timing decoupled from expansion)
  cut: 58,        // Smash cut frame: fully static at >=58
  total: 140,     // Dead silence 82f
};

// —— Keycap (reuses keycap specs: multi-layer box-shadow for depth) ——
const Keycap: React.FC<{ size: number; thick: number; bright: number; label?: string }> = ({
  size, thick, bright, label = '⌘⏎',
}) => (
  <div style={{
    width: size, height: size, borderRadius: size * 0.117,
    background: 'linear-gradient(165deg, #ffffff 0%, #f2f2f0 45%, #e2e2e0 100%)',
    border: `2px solid ${G.border}`, boxSizing: 'border-box',
    boxShadow: [
      `0 ${thick}px 0 #6e6e6c`,
      `0 ${thick + 4}px 2px #565654`,
      `0 ${thick * 2 + 10}px ${thick * 2 + 14}px rgba(0,0,0,0.28)`,
      'inset 0 3px 0 rgba(255,255,255,0.9)',
      'inset 0 -6px 10px rgba(0,0,0,0.07)',
    ].join(', '),
    filter: `brightness(${bright})`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    <div style={{
      fontSize: size * 0.3, fontWeight: 700, color: G.ink,
      fontFamily: 'Helvetica, Arial, sans-serif',
    }}>
      {label}
    </div>
  </div>
);

// —— Rumble phase fly-ins: 5 cards + 1 panel rushing toward camera from all directions ——
type Fly = {
  from: [number, number];
  to: [number, number];
  rot: [number, number];
  seed: number;
  w: number;
  h: number;
  panel?: boolean;
};

const FLIES: Fly[] = [
  { from: [-1400, -140], to: [1400, 80], rot: [-6, 5], seed: 1, w: 440, h: 290 },
  { from: [1400, 200], to: [-1400, -120], rot: [7, -4], seed: 2, w: 400, h: 260 },
  { from: [-260, -900], to: [180, 900], rot: [-3, 8], seed: 3, w: 460, h: 300 },
  { from: [-1300, 820], to: [1300, -760], rot: [5, -7], seed: 4, w: 420, h: 280 },
  { from: [1350, -800], to: [-1350, 840], rot: [-8, 4], seed: 5, w: 480, h: 310 },
  // 6th item: Panel (larger and heavier, diagonal sweep)
  { from: [1500, 700], to: [-1500, -600], rot: [4, -6], seed: 6, w: 700, h: 430, panel: true },
];

// Card i round k: start = 28 + i*3 + k*16, duration 15 / 11 (round 2 faster = overall acceleration).
// i=3 k=1 (53–64f) is hard-cut truncated at cut point 58f — never slows down approaching the cut.
const passWindow = (i: number, k: number): [number, number] => {
  const start = T.pressEnd + i * 3 + k * 16;
  const dur = k === 0 ? 15 : 11;
  return [start, start + dur];
};

// Dummy panel fly-in: command palette-style grayscale block
const FlyPanel: React.FC<{ w: number; h: number }> = ({ w, h }) => (
  <div style={{
    width: w, height: h, background: G.card, border: `2px solid ${G.border}`,
    borderRadius: 20, padding: 26, boxSizing: 'border-box',
    display: 'flex', flexDirection: 'column', gap: 16,
    boxShadow: '0 16px 44px rgba(0,0,0,0.28)',
  }}>
    <div style={{ height: 52, border: `2px solid ${G.line}`, borderRadius: 12, background: G.panel }} />
    {Array.from({ length: 3 }).map((_, i) => (
      <div key={i} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: G.mid }} />
        <div style={{ height: 12, width: `${50 + ((i * 27) % 30)}%`, background: G.line, borderRadius: 6 }} />
      </div>
    ))}
  </div>
);

const FlyItem: React.FC<{ fly: Fly; i: number; frame: number }> = ({ fly, i, frame }) => {
  let active: [number, number] | null = null;
  for (let k = 0; k < 2; k++) {
    const [s, e] = passWindow(i, k);
    if (frame >= s && frame < e) { active = [s, e]; break; }
  }
  if (!active) return null;
  const [s, e] = active;
  // ease-in: Accelerates throughout, faster as it nears the endpoint
  const p = interpolate(frame, [s, e], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });
  const x = fly.from[0] + (fly.to[0] - fly.from[0]) * p;
  const y = fly.from[1] + (fly.to[1] - fly.from[1]) * p;
  const rot = fly.rot[0] + (fly.rot[1] - fly.rot[0]) * p;
  const scale = 1.5 + 1.5 * p; // In-your-face zoom
  const blur = 1 + 4 * p;      // Velocity-gated directional blur (velocity ∝ p under ease-in)
  return (
    <div style={{
      position: 'absolute', left: 960 - fly.w / 2, top: 540 - fly.h / 2,
      transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`,
      filter: `blur(${blur}px)`,
    }}>
      {fly.panel
        ? <FlyPanel w={fly.w} h={fly.h} />
        : <Card w={fly.w} h={fly.h} seed={fly.seed}
            style={{ boxShadow: '0 12px 40px rgba(0,0,0,0.25)' }} />}
    </div>
  );
};

export const KeycapSmashCut: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Dead silence phase: variant A orderly static panorama from 58f + keycap element nested in top bar corner,
  //    no frame-dependent properties ——
  if (frame >= T.cut) {
    return (
      <div style={{ width: 1920, height: 1080, position: 'relative' }}>
        <FakeDashboard variant="A" />
        {/* Keycap punctuation: firmly nested in the top bar (space right of title bar), echoing the fuse */}
        <div style={{ position: 'absolute', left: 464, top: 12 }}>
          <Keycap size={44} thick={4} bright={1} />
        </div>
      </div>
    );
  }

  // —— Fuse phase keycap motion ——
  // Breathing: full sine cycle over 0–25f (±5px), displacement zeroes at f25 into press
  const breathY = frame < T.press ? -5 * Math.sin((2 * Math.PI * frame) / T.press) : 0;
  // Press: 3f sink 14px, held down afterward
  const pressY = interpolate(frame, [T.press, T.pressEnd], [0, 14], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  // Base thickness squashes 12→3px (core touch), stays squashed during rumble phase
  const thick = interpolate(frame, [T.press, T.pressEnd], [12, 3], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const bright = interpolate(frame, [T.press, T.pressEnd], [1, 0.9], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // —— Bright ring: out-cubic expansion 90→640px, linear dissipation, decoupled frame timing, unmounted conditionally ——
  const ringOn = frame >= T.press && frame < T.ringFadeEnd;
  const ringD = interpolate(frame, [T.press, T.ringGrowEnd], [90, 640], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const ringA = interpolate(frame, [T.press, T.ringFadeEnd], [0.9, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const ringBorder = interpolate(frame, [T.press, T.ringGrowEnd], [14, 3], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // —— Rumble phase background momentum: overall ease-in push-in + roll, still accelerating before cut point ——
  const bgScale = interpolate(frame, [T.pressEnd, T.cut], [1, 1.3], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });
  const bgRot = interpolate(frame, [T.pressEnd, T.cut], [0, 1.5], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad),
  });

  return (
    <div style={{
      width: 1920, height: 1080, background: G.bg,
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Background layer (light background + keycap + bright ring), overall accelerated push-in during rumble phase */}
      <div style={{
        width: 1920, height: 1080, position: 'absolute',
        transform: `scale(${bgScale}) rotate(${bgRot}deg)`,
        transformOrigin: '50% 50%', background: G.bg,
      }}>
        {ringOn && (
          <div style={{
            position: 'absolute', left: 960 - ringD / 2, top: 540 + 120 + pressY - ringD / 2,
            width: ringD, height: ringD, borderRadius: '50%',
            border: `${ringBorder}px solid #4a4a48`, opacity: ringA,
            boxSizing: 'border-box',
          }} />
        )}
        <div style={{
          position: 'absolute', left: 960 - 120, top: 540 - 120,
          transform: `translateY(${breathY + pressY}px)`,
        }}>
          <Keycap size={240} thick={thick} bright={bright} />
        </div>
      </div>

      {/* Rumble phase fly-ins */}
      {frame >= T.pressEnd && FLIES.map((fly, i) => (
        <FlyItem key={i} fly={fly} i={i} frame={frame} />
      ))}
    </div>
  );
};
