// speed-ramp — Real card stream frame remap: fast (slope 2.2) ->
// 0.2x slow-motion showcase window -> fast. Target card (card4-hires) slides clearly across screen center during slow window.
// Motion blur velocity-linked: blurred during fast phase, sharp during slow phase; contrast creates "gaze" feel.
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';
import layout from '../../_textures/live-layout.json';

export const SPEEDRAMP_DUR = 135;

const CARD_W = 460;
const GAP = 60;
const RAIL = layout.projects.cards.slice(0, 9);
const TARGET_I = 5;

const Scene: React.FC = () => {
  const frame = useCurrentFrame();
  // remap: 0–40f covers 88 source frames (fast), 40–85f covers 9 source frames (0.2x), 85–135f covers 110 (fast)
  const src = interpolate(frame, [0, 40, 85, 135], [0, 88, 97, 207], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const dx = src * 28;
  return (
    <AbsoluteFill style={{ backgroundColor: '#f9f6f1', overflow: 'hidden' }}>
      {/* Offset 717: centers target card k=5 on screen at midpoint of slow window (src≈92.4, dx≈2587) */}
      <div style={{ position: 'absolute', top: 360, transform: `translateX(${-dx + 717}px)` }}>
        {Array.from({ length: 16 }).map((_, k) => {
          const c = RAIL[k % RAIL.length];
          const isTarget = k === TARGET_I;
          return (
            <Img
              key={k}
              src={staticFile(`legacy-textures/${isTarget ? 'card4-hires.png' : c.file}`)}
              style={{
                position: 'absolute', left: k * (CARD_W + GAP), top: isTarget ? -16 : 0,
                width: CARD_W, borderRadius: 12,
                boxShadow: isTarget
                  ? '0 10px 32px rgba(31,28,23,0.18)'
                  : '0 4px 16px rgba(31,28,23,0.10)',
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const SpeedRampReal: React.FC = () => {
  const frame = useCurrentFrame();
  const fast = frame < 42 || frame > 83;
  return fast ? (
    <CameraMotionBlur shutterAngle={200} samples={20}>
      <Scene />
    </CameraMotionBlur>
  ) : (
    <Scene />
  );
};
