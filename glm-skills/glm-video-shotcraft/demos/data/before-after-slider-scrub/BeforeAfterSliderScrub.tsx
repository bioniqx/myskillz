// before-after-slider-scrub — before/after comparison slider
// FakeDashboard stacked in two versions: before = low-contrast hazy version ("pre-processed"), after = normal crisp version.
// Vertical divider bar with round handle: flicks quickly from 8% on the left to 70% (overshooting to 76% before bouncing back),
// then slowly sweeps back to 40% and halts. The after version is revealed as the bar sweeps across (clip-path inset tracks bar x).
// The speed contrast between the quick fling and slow sweep is the key to rhythm. Full freeze after f=110 (40f).
//
// Polish upgrade: "before" state updated from crude grayscale overlay to a believable raw state (subtle defocus + desaturation + low-contrast matte);
// corner badges upgraded to proper Before/After capsules, each embedded in its respective layer and clipped together with the divider line; divider bar updated to 2px white line +
// hairline stroke + soft shadows on both sides; handle is a white circular button with inner highlight + vector double arrows; 4f anticipation pull-back before the fling;
// handle stretches horizontally with directional motion blur proportional to speed during fling, returning to rest upon landing.
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';
import { EASE, FONT, Grain, SpeedBlur, mix, ramp, softShadow, tracking, velocity } from '../../_fixtures/Polish';

export const BEFORE_AFTER_SLIDER_SCRUB_DURATION = 150; // 110f animation + 40f true freeze

// Timeline (bar position expressed as a percentage of screen width)
const PRE = 10; // Anticipation: 10->14 pulls back 1.5% leftward ("wind-up" before fling)
const T0 = 14; // Start of fast fling
const FLING = 26; // Fast fling: 14->26 (12f dash to 76%)
const BOUNCE = 38; // Bounce back: 26->38 settles to 70%
const HOLD = 56; // Pause for readability
const SCRUB = 104; // Slow sweep: 56->104 (48f return to 40%) - speed is roughly 1/5 of the fling

const posAt = (f: number): number => {
  if (f < T0) return mix(8, 6.5, ramp(f, PRE, T0 - PRE, EASE.smooth));
  if (f < FLING) return mix(6.5, 76, ramp(f, T0, FLING - T0, EASE.out));
  if (f < BOUNCE) return mix(76, 70, ramp(f, FLING, BOUNCE - FLING, EASE.smooth));
  if (f < HOLD) return 70;
  return mix(70, 40, ramp(f, HOLD, SCRUB - HOLD, EASE.smooth));
};

const W = 1920;
const H = 1080;

// Badge capsule: placed in empty space of top bar (avoids overlapping card titles/sidebar); before has white background with dark text, after has dark background with white text + accent dot
const Tag: React.FC<{ label: string; x: number; accent?: boolean; muted?: boolean }> = ({ label, x, accent, muted }) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: 15,
      height: 42,
      padding: '0 18px 0 15px',
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      borderRadius: 21,
      background: accent ? G.ink1 : 'rgba(255,255,255,0.88)',
      border: accent ? '1px solid rgba(255,255,255,0.08)' : `1px solid ${G.hairlineStrong}`,
      boxShadow: `inset 0 1px 0 rgba(255,255,255,${accent ? 0.12 : 0.9}), ${softShadow(accent ? 10 : 4)}`,
      fontFamily: FONT.sans,
      fontSize: 20,
      fontWeight: 600,
      letterSpacing: tracking(20, false),
      color: accent ? '#ffffff' : muted ? G.ink2 : G.ink1,
      whiteSpace: 'nowrap',
    }}
  >
    <span
      style={{
        width: 9,
        height: 9,
        borderRadius: 5,
        background: accent ? '#8f96f0' : G.ink3,
        boxShadow: accent ? '0 0 0 3px rgba(143,150,240,0.22)' : 'none',
      }}
    />
    {label}
  </div>
);

export const BeforeAfterSliderScrub: React.FC = () => {
  const frame = useCurrentFrame();
  const p = posAt(frame); // Bar position %
  const x = (p / 100) * W;

  // Velocity (px/frame): drives handle stretching and motion blur, 0 when stationary
  const vx = velocity((f) => (posAt(f) / 100) * W, frame);
  const speed = Math.abs(vx);
  const squish = 1 + Math.min(speed / 110, 1) * 0.18; // Peak 1.18
  const press = 1 - 0.06 * Math.sin(Math.PI * ramp(frame, PRE, FLING - PRE, EASE.linear)); // Handle slightly pinches/shrinks during fling

  return (
    <AbsoluteFill style={{ background: G.bg, overflow: 'hidden' }}>
      {/* before: believable "raw" state — subtle blur + desaturation + low contrast, overlaid with warm gray haze */}
      <div style={{ position: 'absolute', inset: 0, filter: 'blur(1.6px) saturate(0.18) contrast(0.72) brightness(1.04)' }}>
        <FakeDashboard variant="A" />
      </div>
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(214,212,206,0.30), rgba(196,194,188,0.38))' }} />
      <Tag label="Before" x={1372} muted />

      {/* after: normal crisp version, revealed to the left of the bar; After badge belongs to this layer and is clipped by the divider line */}
      <div style={{ position: 'absolute', inset: 0, clipPath: `inset(0 ${W - x}px 0 0)` }}>
        <FakeDashboard variant="A" />
        {/* x shifted right to accommodate the longer branded breadcrumb (video-shotcraft > Overview), leaving ~20px clearance on both sides (time toggle / divider bar at hold) */}
        <Tag label="After" x={646} accent />
      </div>

      {/* Reveal edge: faint 24px contact shadow on the after side to establish depth separation between layers (clipped within after) */}
      <div
        style={{
          position: 'absolute',
          left: x - 24,
          top: 0,
          width: 24,
          height: H,
          background: 'linear-gradient(90deg, rgba(16,18,26,0), rgba(16,18,26,0.07))',
        }}
      />

      {/* Divider bar + round handle: handle stretches horizontally with speed during fast fling; bar and handle blur together directionally */}
      <SpeedBlur vx={vx} amount={0.12} max={14}>
        {/* Divider bar: 2px white line + hairline border + soft shadows on both sides */}
        <div
          style={{
            position: 'absolute',
            left: x - 1,
            top: 0,
            width: 2,
            height: H,
            background: '#ffffff',
            boxShadow: '0 0 0 1px rgba(16,18,26,0.10), 0 0 22px rgba(16,18,26,0.22)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: x - 38,
            top: H / 2 - 38,
            width: 76,
            height: 76,
            borderRadius: 38,
            background: 'linear-gradient(180deg, #ffffff, #f4f4f2)',
            border: `1px solid ${G.hairlineStrong}`,
            boxShadow: `inset 0 1px 0 #ffffff, ${softShadow(14 + Math.min(speed / 8, 18))}`,
            transform: `scale(${press * squish}, ${press})`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxSizing: 'border-box',
          }}
        >
          <svg width={36} height={20} viewBox="0 0 36 20" style={{ display: 'block' }}>
            <path d="M11 3 L4 10 L11 17" fill="none" stroke={G.ink2} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
            <path d="M25 3 L32 10 L25 17" fill="none" stroke={G.ink2} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </SpeedBlur>

      <Grain opacity={0.04} />
    </AbsoluteFill>
  );
};
