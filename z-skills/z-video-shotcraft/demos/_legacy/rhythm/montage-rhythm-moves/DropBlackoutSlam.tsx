// Drop blackout slam (drop-blackout-slam) — EDM concert blackout rhythmic technique:
// Frames 0–49: faux dashboard "plays" normally (scale breathing 1.0 <-> 1.02) + lower-right beat dot flashes every 12f;
// Frames 50–61: hard cut to pure black #0c0c0c for 12f dead silence, screen completely empty (anticipation built via silence);
// Frame 62: large white title "DROP" slams from scale 1.35 to 1.0 (5f cubic out), simultaneous 10px full-screen
// exponential shake (tau ≈ 2.5f, settles in ~12f), background turns to G.ink with an expanding bright ring
// rapidly dissipating from center; frame ~80 to 130 completely static, >= 40f true static hold at finish.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard, G } from '../../_fixtures/Fixtures';

// Frame-deterministic pseudorandom (strict rule: no Math.random)
const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

const BLACK_IN = 50; // Cut to black frame
const SLAM = 62; // Slam frame

export const DropBlackoutSlam: React.FC = () => {
  const f = useCurrentFrame();

  // ===== Phase 1: frames 0–49 normal playback =====
  if (f < BLACK_IN) {
    // Scale breathing 1.0 <-> 1.02, 48f period
    const breathe = 1.01 + 0.01 * Math.sin((f / 48) * Math.PI * 2);
    // Beat indicator: flashes every 12f (4f decay)
    const beatPhase = f % 12;
    const beatOn = interpolate(beatPhase, [0, 1, 5], [0.25, 1, 0.25], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    const beatScale = interpolate(beatPhase, [0, 1, 5], [1, 1.5, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    return (
      <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
        <div style={{ width: 1920, height: 1080, transform: `scale(${breathe})`, transformOrigin: '50% 50%' }}>
          <FakeDashboard variant="B" />
        </div>
        {/* Lower-right beat indicator */}
        <div
          style={{
            position: 'absolute',
            right: 56,
            bottom: 48,
            width: 36,
            height: 36,
            borderRadius: 18,
            background: G.ink,
            opacity: beatOn,
            transform: `scale(${beatScale})`,
          }}
        />
      </div>
    );
  }

  // ===== Phase 2: frames 50–61 pure black silence, screen completely empty =====
  if (f < SLAM) {
    return <div style={{ width: 1920, height: 1080, background: '#0c0c0c' }} />;
  }

  // ===== Phase 3: frame 62 onward slam =====
  const t = f - SLAM;

  // Title: scale 1.35 -> 1.0, 5f cubic out
  const slamScale = interpolate(t, [0, 5], [1.35, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Screen shake: 10px exponential decay, tau ≈ 2.5f, settles in ~12f; clamped to 0 at t >= 14 for true static hold
  const amp = t >= 14 ? 0 : 10 * Math.exp(-t / 2.5);
  const shakeX = amp === 0 ? 0 : (h(f * 3.7 + 1) - 0.5) * 2 * amp;
  const shakeY = amp === 0 ? 0 : (h(f * 7.1 + 2) - 0.5) * 2 * amp;

  // Shockwave ring: expands from center and dissipates, completes in ~16f (opacity = 0 and unrendered for t >= 16)
  const ringR = interpolate(t, [0, 16], [80, 900], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const ringOpacity = interpolate(t, [0, 3, 16], [0.85, 0.55, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.ink, overflow: 'hidden', position: 'relative' }}>
      <div
        style={{
          width: 1920,
          height: 1080,
          transform: `translate(${shakeX}px, ${shakeY}px)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
        }}
      >
        {/* Shockwave ring: rapid expansion and dissipation */}
        {t < 16 && (
          <div
            style={{
              position: 'absolute',
              left: 960 - ringR,
              top: 540 - ringR,
              width: ringR * 2,
              height: ringR * 2,
              borderRadius: '50%',
              border: '10px solid #ffffff',
              opacity: ringOpacity,
            }}
          />
        )}
        <div
          style={{
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: 340,
            color: '#ffffff',
            letterSpacing: -6,
            transform: `scale(${slamScale})`,
            lineHeight: 1,
          }}
        >
          DROP
        </div>
      </div>
    </div>
  );
};
