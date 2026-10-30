// card-footage-cadence — Title card intercut cadence
// UI shots <-> black title cards exchange beats like dialogue: 0–14f UI A slow push -> hard cut 8f title card SHIP ->
// hard cut 12f UI B 1.6x crop slow pan -> 8f title card FASTER -> 10f UI A 2x crop ->
// 10f title card TODAY (underlined) -> 62f hard cut concluding panorama freeze.
// All UI segments feature micro-motion (push/pan); title cards stay completely static aside from a subtle settle scale-down (1.05 -> 1, out-cubic);
// motion <-> stillness contrast is the core device. All transitions use zero crossfade (conditional mount, no crossfade).
// Concluding 62–105f finishes with gentle push, 105–150f completely static 45f >= 40f. Deterministic, zero randomness.
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';

const CLAMP = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// White text on black title card: settle scale-down 1.05 -> 1 (out-cubic, completed in first 5f of segment), otherwise completely static
const TitleCard: React.FC<{ text: string; local: number; underline?: boolean }> = ({
  text,
  local,
  underline = false,
}) => {
  const scale = interpolate(local, [0, 5], [1.05, 1], {
    ...CLAMP,
    easing: Easing.out(Easing.cubic),
  });
  return (
    <AbsoluteFill
      style={{ background: '#0d0d0d', alignItems: 'center', justifyContent: 'center' }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 26,
        }}
      >
        <div
          style={{
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: 170,
            color: '#ffffff',
            letterSpacing: 2,
            lineHeight: 1,
          }}
        >
          {text}
        </div>
        {underline && (
          <div style={{ width: 560, height: 14, background: '#ffffff', borderRadius: 7 }} />
        )}
      </div>
    </AbsoluteFill>
  );
};

// UI shot: wrapped in transform layer for slow push/pan; hard cuts guaranteed via outer conditional mounting
const UiShot: React.FC<{
  variant: 'A' | 'B';
  transform: string;
  origin?: string;
}> = ({ variant, transform, origin = '50% 50%' }) => (
  <AbsoluteFill style={{ overflow: 'hidden', background: '#ececea' }}>
    <div style={{ width: 1920, height: 1080, transform, transformOrigin: origin }}>
      <FakeDashboard variant={variant} />
    </div>
  </AbsoluteFill>
);

export const CardFootageCadence: React.FC = () => {
  const frame = useCurrentFrame();

  // ---- Segments: cut points 14 / 22 / 34 / 42 / 52 / 62, total length 150 ----

  // Seg 1 0–14f: UI A full view slow push 1.0 -> 1.08
  if (frame < 14) {
    const s = interpolate(frame, [0, 14], [1, 1.08], CLAMP);
    return <UiShot variant="A" transform={`scale(${s})`} />;
  }

  // Seg 2 14–22f: Title card SHIP
  if (frame < 22) {
    return <TitleCard text="SHIP" local={frame - 14} />;
  }

  // Seg 3 22–34f: UI B 1.6x crop + horizontal slow pan (120px content displacement, ~192px on screen).
  // origin shifted left to bring list item icons into view, ensuring readable UI context (QA adjustment: 50% -> 35%)
  if (frame < 34) {
    const tx = interpolate(frame - 22, [0, 12], [60, -60], CLAMP);
    return (
      <UiShot variant="B" transform={`scale(1.6) translateX(${tx}px)`} origin="35% 50%" />
    );
  }

  // Seg 4 34–42f: Title card FASTER
  if (frame < 42) {
    return <TitleCard text="FASTER" local={frame - 34} />;
  }

  // Seg 5 42–52f: UI A alternative 2x crop (top-left card area) + continued slow push 2.0 -> 2.14
  if (frame < 52) {
    const s = interpolate(frame - 42, [0, 10], [2, 2.14], CLAMP);
    return <UiShot variant="A" transform={`scale(${s})`} origin="32% 30%" />;
  }

  // Seg 6 52–62f: Title card TODAY + underline
  if (frame < 62) {
    return <TitleCard text="TODAY" local={frame - 52} underline />;
  }

  // Seg 7 62–150f: Concluding panorama UI freeze. 62–105f ultra-slow push settles (out-cubic),
  // transform constant at 1.02 after 105f, completely static 45f from 105–150f.
  const s = interpolate(frame, [62, 105], [1, 1.02], {
    ...CLAMP,
    easing: Easing.out(Easing.cubic),
  });
  return <UiShot variant="B" transform={`scale(${s})`} />;
};
