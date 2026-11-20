// Slow push-in tension (slow-push-in) — StudioBinder camera movements.
// Shot A (frames 0–120): Dark background + large white text "10x", scale uses Easing.in(Easing.quad)
// uniformly accelerating from 1.00 to 1.14 — barely perceptible in first 2s, distinctly felt in latter half; simultaneously, 4-corner radial
// vignette deepens opacity 0 -> 0.5 in sync, establishing secondary source of tension.
// Frame 120 hard-cuts directly to Shot B with zero transition: fullscreen bright FakeDashboard(A) completely static for 30f —
// large dark-to-bright contrast delivers a punchy cut on the beat.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';

const CUT = 120; // Hard cut frame

export const SlowPushIn: React.FC = () => {
  const frame = useCurrentFrame();

  // ---- Shot B: From frame 120, fullscreen bright panel, completely static ----
  if (frame >= CUT) {
    return <FakeDashboard variant="A" />;
  }

  // ---- Shot A: 0–120f slow push-in ----
  // Uniformly accelerated push-in: Easing.in(quad) — imperceptible early on, noticeable late
  const scale = interpolate(frame, [0, CUT], [1.0, 1.14], {
    easing: Easing.in(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Vignette darkens synchronously: secondary source of tension
  const vignette = interpolate(frame, [0, CUT], [0, 0.5], {
    easing: Easing.in(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.side,
        position: 'relative',
        overflow: 'hidden',
        fontFamily: 'Helvetica, Arial, sans-serif',
      }}
    >
      {/* Pushed content layer: scaled globally */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scale(${scale})`,
          transformOrigin: '50% 50%',
        }}
      >
        <div
          style={{
            fontSize: 300,
            fontWeight: 800,
            color: '#ffffff',
            letterSpacing: -6,
            lineHeight: 1,
          }}
        >
          10x
        </div>
        <div
          style={{
            marginTop: 36,
            fontSize: 40,
            fontWeight: 500,
            color: '#b8b8b6',
            letterSpacing: 6,
          }}
        >
          FASTER THAN BASELINE
        </div>
      </div>

      {/* Vignette layer: 4-corner radial gradient, darkens in sync with push-in */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          opacity: vignette,
          background:
            'radial-gradient(ellipse 62% 55% at 50% 50%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.95) 100%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
};
