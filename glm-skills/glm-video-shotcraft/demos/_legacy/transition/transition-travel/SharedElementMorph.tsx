import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { FakeDashboard, Card, G } from '../../_fixtures/Fixtures';

// shared-element-morph [transition]: Fullscreen close-up panel contracts, translates, develops rounded corners,
// flying seamlessly into its designated card slot within the dashboard grid, landing with 3% overshoot.
// Creates the perception of the identical element being returned to place by the camera (FLIP shared-element transition).
//
// Target slot = FakeDashboard A center column, row 2 slot (seed 5), calculated precisely from fixtures layout:
//   Sidebar 220 + grid padding 36 -> column width (1920-220-72-56)/3 = 524
//   Header 72 + padding 36       -> row height (1008-72-28)/2   = 454
//   Center col x = 220+36+524+28 = 808; row 2 y = 72+36+454+28 = 590
const SLOT = { x: 808, y: 590, w: 524, h: 454, r: 14, seed: 5 };
const FULL = { x: 0, y: 0, w: 1920, h: 1080, r: 0 };

// Rhythm: 0–35 fullscreen close-up hold | 35–60 morph 25f (bezier 0.4,0,0.2,1 -> 1.03)
//         60–70 overshoot rebound into place | 70–130 static tail
const MORPH_START = 35;
const MORPH_END = 60;
const SETTLE_END = 70;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const SharedElementMorph: React.FC = () => {
  const frame = useCurrentFrame();

  // Position/size/border-radius share identical progress curve: ramps to 1.03 over 25f, bounces back to 1 over 10f
  const drive = interpolate(frame, [MORPH_START, MORPH_END], [0, 1.03], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.4, 0, 0.2, 1),
  });
  const settle = interpolate(frame, [MORPH_END, SETTLE_END], [1.03, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const p = frame <= MORPH_END ? drive : settle;

  const x = lerp(FULL.x, SLOT.x, p);
  const y = lerp(FULL.y, SLOT.y, p);
  const w = lerp(FULL.w, SLOT.w, p);
  const h = lerp(FULL.h, SLOT.h, p);
  const r = lerp(FULL.r, SLOT.r, p);

  // Content is the exact same card: rendered at target dimensions, scaled up proportionally to fill fullscreen (fullscreen = close-up of this card);
  // content shrinks along with container during contraction, reinforcing the "single continuous object" perception
  const contentScale = w / SLOT.w;

  // Shadow shrinks with size: large and deep while airborne, settling into fixtures card native shadow scale upon landing
  const ps = Math.min(Math.max(p, 0), 1);
  const shadowY = lerp(36, 2, ps);
  const shadowBlur = lerp(110, 8, ps);
  const shadowAlpha = lerp(0.32, 0.06, ps);

  // Background dashboard stays on standby at 0.9 opacity, snapping to 1 the instant of landing
  const bgOpacity = interpolate(frame, [MORPH_END - 2, MORPH_END + 3], [0.9, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

  return (
    <AbsoluteFill style={{ background: G.bg, overflow: 'hidden' }}>
      <div style={{ opacity: bgOpacity }}>
        <FakeDashboard variant="A" />
      </div>
      {/* Shared element: fullscreen close-up -> flies precisely into slot */}
      <div
        style={{
          position: 'absolute',
          left: x,
          top: y,
          width: w,
          height: h,
          borderRadius: r,
          overflow: 'hidden',
          background: G.card,
          boxShadow: `0 ${shadowY}px ${shadowBlur}px rgba(0,0,0,${shadowAlpha})`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            transform: `scale(${contentScale})`,
            transformOrigin: 'top left',
          }}
        >
          <Card
            w={SLOT.w}
            h={SLOT.h}
            seed={SLOT.seed}
            style={{ boxShadow: 'none', borderRadius: r / Math.max(contentScale, 0.0001) }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};
