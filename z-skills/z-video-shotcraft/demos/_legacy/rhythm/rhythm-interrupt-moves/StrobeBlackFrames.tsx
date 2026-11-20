// Strobe black frames (strobe-black-frames) — Rhythmic edit | VJ strobe / blackout flicker.
// FakeDashboard A slowly zooms in to build tension (scale 1.0 -> 1.05, Easing.in(quad),
// accelerating toward end). 40–80f strobe window: full-screen pure black #0c0c0c flashes on predetermined frames,
// 2f duration each, intervals tightening from 8f to 3f to build escalating tension. Final flash covers 79–80;
// at frame 81, view reveals a hard cut to scale 1.35 centered on row 2 middle card (zero-tween instantaneous cut),
// overlaid with 2f brightness 0.88 impact pulse.
// Keyframes: 0–78 zoom in 1.0 -> ~1.05 -> black strobes [40,48,55,61,66,70,73,76,79] (2f each) ->
// 79–80 pure black -> frame 81 hard cut scale 1.35 (81–82 darkening pulse) -> 83–134 completely static (52f >= 50f).
// Photosensitivity warning: recommended to pair with musical crescendo in production.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard, TitleBlock } from '../../_fixtures/Fixtures';

// Punch-in focal point: 3x2 grid row 2 center card midpoint (matching JumpCutPunchIn geometry)
// Sidebar 220 + padding 36; card width (1920-220-72-56)/3 ≈ 524.67, card height (1080-72-72-28)/2 = 454
const CARD_L = 220 + 36 + 524.67 + 28; // ≈808.67
const CARD_T = 72 + 36 + 454 + 28; // 590
const CARD_W = 524.67;
const CARD_H = 454;
const ORIGIN_X = CARD_L + CARD_W / 2; // ≈1071
const ORIGIN_Y = CARD_T + CARD_H / 2; // 817

// Black strobe frame table (hardcoded): intervals 8->7->6->5->4->3->3->3, 2f duration each (f0 and f0+1)
const FLASHES = [40, 48, 55, 61, 66, 70, 73, 76, 79];

const isBlack = (f: number): boolean =>
  FLASHES.some((f0) => f >= f0 && f <= f0 + 1);

// Slow zoom-in before frame 81 (Easing.in tension build), zero-tween hard cut to 1.35 freeze at 81
const scaleAt = (f: number): number =>
  f < 81
    ? interpolate(f, [0, 80], [1.0, 1.05], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.in(Easing.quad),
      })
    : 1.35;

// Impact gavel: 81–82 2-frame full-screen darkening pulse
const pulseAt = (f: number): number => (f >= 81 && f <= 82 ? 0.88 : 1);

export const StrobeBlackFrames: React.FC = () => {
  const frame = useCurrentFrame();
  const s = scaleAt(frame);
  const b = pulseAt(frame);
  const black = isBlack(frame);

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.bg,
        position: 'relative',
        overflow: 'hidden',
        filter: `brightness(${b})`,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${s})`,
          transformOrigin: `${ORIGIN_X}px ${ORIGIN_Y}px`,
        }}
      >
        <FakeDashboard variant="A" />
        {/* Target card marker: scales with composition to indicate focal card */}
        <div
          style={{
            position: 'absolute',
            left: CARD_L - 10,
            top: CARD_T - 10,
            width: CARD_W + 20,
            height: CARD_H + 20,
            border: `3px dashed ${G.mid}`,
            borderRadius: 20,
            boxSizing: 'border-box',
          }}
        />
      </div>
      {/* Label exempt from zoom, fixed in topbar */}
      <div style={{ position: 'absolute', left: 260, top: 20 }}>
        <TitleBlock text="STROBE BLACK FRAMES" size={54} />
      </div>
      {/* Fullscreen black strobe overlay: covers everything (including label), 2f each */}
      {black && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: '#0c0c0c',
            zIndex: 10,
          }}
        />
      )}
    </div>
  );
};
