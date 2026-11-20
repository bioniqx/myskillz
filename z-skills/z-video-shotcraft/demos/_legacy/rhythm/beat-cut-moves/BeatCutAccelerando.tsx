import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { FakeDashboard, G } from '../../_fixtures/Fixtures';

// beat-cut-accelerando: Six different compositions hard-cut fullscreen at decreasing intervals of 16→12→8→6→4 frames,
// accelerating forward, culminating in a sudden freeze-frame back to the main view with a 1→1.06 slow push-in hold.
// True hard cut: whichever interval frame falls into renders that view directly, without any transition.

// A view = FakeDashboard variant + scale + focal point (point on canvas pushed to screen center)
type View = { variant: 'A' | 'B'; scale: number; cx: number; cy: number };

const VIEWS: View[] = [
  { variant: 'A', scale: 1, cx: 960, cy: 540 },    // v0 Full view (establishing)
  { variant: 'A', scale: 1.8, cx: 1070, cy: 576 }, // v1 Cards area
  { variant: 'A', scale: 2.6, cx: 600, cy: 340 },  // v2 Single card close-up
  { variant: 'B', scale: 1, cx: 960, cy: 540 },    // v3 List page full view
  { variant: 'B', scale: 1.9, cx: 1070, cy: 500 }, // v4 List rows area
  { variant: 'B', scale: 2.8, cx: 1070, cy: 290 }, // v5 Single row close-up
];

// Start frame per segment: establishing 49f, then intervals 16→12→8→6→4, final segment (return to main view) hold 35f
// 0–48 v0 | 49–64 v1 | 65–76 v2 | 77–84 v3 | 85–90 v4 | 91–94 v5 | 95–129 freeze
const CUTS = [0, 49, 65, 77, 85, 91, 95];
const FINAL = 95; // Final cut: sudden freeze back to main view

const ViewShot: React.FC<{ view: View; extraScale?: number }> = ({ view, extraScale = 1 }) => {
  const s = view.scale * extraScale;
  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        transformOrigin: `${view.cx}px ${view.cy}px`,
        transform: `translate(${960 - view.cx}px, ${540 - view.cy}px) scale(${s})`,
      }}
    >
      <FakeDashboard variant={view.variant} />
    </div>
  );
};

export const BeatCutAccelerando: React.FC = () => {
  const frame = useCurrentFrame();

  // Which interval current frame falls into (final segment = main view v0)
  let seg = 0;
  for (let i = 0; i < CUTS.length; i++) {
    if (frame >= CUTS[i]) seg = i;
  }
  const isFinal = seg === CUTS.length - 1;
  const view = isFinal ? VIEWS[0] : VIEWS[seg];

  // Final slow push-in: scale 1 → 1.06, ease-out, pushes 22f then static (ending static ≥15f)
  const push = isFinal
    ? interpolate(frame, [FINAL, FINAL + 20], [1, 1.06], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.out(Easing.cubic),
      })
    : 1;

  // 1f brightness jump (~+5%) on each hard cut to simulate shutter
  const isCutFrame = CUTS.some((c, i) => i > 0 && frame === c);
  const flash = isCutFrame ? 1.05 : 1;

  return (
    <AbsoluteFill style={{ background: G.bg, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, filter: `brightness(${flash})` }}>
        <ViewShot view={view} extraScale={push} />
      </div>
      {/* Super thin white flash on cut frame to ensure human perceptibility */}
      {isCutFrame && (
        <AbsoluteFill style={{ background: '#ffffff', opacity: 0.06 }} />
      )}
    </AbsoluteFill>
  );
};
