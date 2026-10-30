import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { FakeDashboard, Card, G } from '../../_fixtures/Fixtures';

// Dutch roll to level (dutch-roll-to-level): The entire frame hangs at a -10° Dutch angle during pain point presentation
// (layered with an ultra-slow sine drift to avoid reading as a static crooked image); on the beat of the solution at frame 70,
// the entire frame rolls back to level with a single overshoot (-10° -> +1.2° -> 0°), while warning banner fades out and clean card emerges —
// "the world is righted" landing right on the beat.
// Frames 0–70 tilted drift / 70–84 roll to level overshoot / 84–94 settle back to 0 / 94–140 true rest.

const ROLL = 70; // Roll-to-level start beat
const LEVEL = 94; // Fully leveled frame

export const DutchRollToLevel: React.FC = () => {
  const f = useCurrentFrame();

  // —— Slow drift during tilted phase (before frame 70): ±0.8° long-period sine + 2px vertical drift ——
  const driftT = Math.min(f, ROLL);
  const driftRot = Math.sin(driftT * 0.035) * 0.8;
  const driftY = Math.sin(driftT * 0.05) * 2;
  // Drift fades out as roll-to-level progresses
  const driftFade = interpolate(f, [ROLL, ROLL + 6], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // —— Roll to level: -10° overshoots 0 to +1.2° across 14f, then settles back to 0 over 10f (single overshoot without oscillation) ——
  const baseRot =
    f < ROLL
      ? -10
      : f < ROLL + 14
        ? interpolate(f, [ROLL, ROLL + 14], [-10, 1.2], {
            easing: Easing.out(Easing.cubic),
          })
        : interpolate(f, [ROLL + 14, LEVEL], [1.2, 0], {
            extrapolateRight: 'clamp',
            easing: Easing.inOut(Easing.quad),
          });

  const rot = baseRot + driftRot * driftFade;
  const y = driftY * driftFade;

  // scale 1.15 (prevents corner cut-off from rotation) -> scales down in sync to 1.08 upon leveling
  const scale = interpolate(f, [ROLL, LEVEL], [1.15, 1.08], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });

  // —— Warning banner (pain point): hangs above during tilt, fades out on leveling beat; clean card inversely fades in ——
  const alertOpacity = interpolate(f, [ROLL, ROLL + 12], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cleanOpacity = interpolate(f, [ROLL + 8, ROLL + 22], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ background: G.bg, overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `translateY(${y}px) rotate(${rot}deg) scale(${scale})`,
          transformOrigin: '50% 50%',
        }}
      >
        <FakeDashboard variant="B" />

        {/* Pain point alert banner: dark banner pinned to page top (accentuating tilt) */}
        <div
          style={{
            position: 'absolute',
            left: 560,
            top: 120,
            width: 800,
            height: 88,
            background: G.ink,
            borderRadius: 14,
            opacity: alertOpacity * 0.92,
            display: 'flex',
            alignItems: 'center',
            gap: 18,
            padding: '0 28px',
            boxSizing: 'border-box',
            boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
          }}
        >
          {/* Warning triangle */}
          <div
            style={{
              width: 0,
              height: 0,
              borderLeft: '18px solid transparent',
              borderRight: '18px solid transparent',
              borderBottom: '32px solid #f7f7f6',
            }}
          />
          <div style={{ height: 16, width: 420, background: G.mid, borderRadius: 8 }} />
        </div>

        {/* Solution: clean card surfaces at the same spot in sync with leveling */}
        <div style={{ position: 'absolute', left: 560, top: 96, opacity: cleanOpacity }}>
          <Card w={800} h={140} seed={2} style={{ boxShadow: '0 10px 30px rgba(0,0,0,0.12)' }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
