// halation-bloom — Halation bloom
// Dark gray background with large white text "10x" crash-zooms to an abrupt stop (2.4 -> 1, 7f in-quad + 2f rebound).
// From impact frame: bottom duplicate text layer (blurred + brightened white bloom) surges outward (scale 1 -> 1.3, 6f out-cubic diffusion),
// then decays linearly over 20f to a 0.35 residual soft glow (diffusion/decay decoupled archetype), followed by a 15f ease to 0.22 steady state.
// Dark bg with white text: brightness boost invisible on pure white archetype. Settle phase true hold >=40f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';

const BG = '#2a2a28';
const WHITE = '#f7f7f5';
const MID = '#8f8f8d';

// —— Timeline (30fps) ——
const ZOOM_START = 8; // Entry start
const IMPACT = 15; // Impact frame (7f rapid zoom-in)
const REBOUND_END = 17; // 2f rebound
const POP_END = IMPACT + 6; // Bloom layer expansion 6f -> f21
const FALL_END = POP_END + 20; // 20f linear decay -> f41
const SETTLE_END = FALL_END + 15; // 15f ease settle -> f56, fully static thereafter
// Total duration 145f -> hold 89f >= 40f

const TextBlock: React.FC<{ color: string }> = ({ color }) => (
  <div
    style={{
      fontFamily: 'Helvetica, Arial, sans-serif',
      fontSize: 260,
      fontWeight: 800,
      color,
      letterSpacing: '-0.02em',
      lineHeight: 1,
      whiteSpace: 'nowrap',
    }}
  >
    10x
  </div>
);

export const HalationBloom: React.FC = () => {
  const frame = useCurrentFrame();

  // —— crash-zoom entry: scale 2.4 -> 0.94 (7f in-quad accelerated impact) -> 1 (2f rebound) ——
  const zoomIn = interpolate(frame, [ZOOM_START, IMPACT], [2.4, 0.94], {
    easing: Easing.in(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const rebound = interpolate(frame, [IMPACT, REBOUND_END], [0.94, 1], {
    easing: Easing.out(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const textScale = frame < IMPACT ? zoomIn : rebound;
  const textOpacity = interpolate(frame, [ZOOM_START, ZOOM_START + 3], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // —— Bloom layer: conditionally mounted from impact frame ——
  // Diffusion (scale): out-cubic, 6f surge 1 -> 1.3
  const bloomScale = interpolate(frame, [IMPACT, POP_END], [1, 1.3], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Decay (opacity): decoupled from diffusion — holds full brightness during surge, then decays linearly over 20f to 0.35
  const bloomFall = interpolate(frame, [POP_END, FALL_END], [1, 0.35], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Residual bloom eases over 15f to 0.22 steady state
  const bloomSettle = interpolate(frame, [FALL_END, SETTLE_END], [0.35, 0.22], {
    easing: Easing.out(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const bloomOpacity = frame < FALL_END ? bloomFall : bloomSettle;

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: BG,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Small badge, static throughout */}
      <div
        style={{
          position: 'absolute',
          top: 110,
          width: '100%',
          textAlign: 'center',
          fontFamily: 'Helvetica, Arial, sans-serif',
          fontSize: 30,
          fontWeight: 700,
          letterSpacing: '0.35em',
          color: MID,
        }}
      >
        HALATION BLOOM
      </div>

      {/* Bloom layer: text duplicate on bottom, blur + brightened, conditionally mounted from impact frame */}
      {frame >= IMPACT && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transform: `scale(${bloomScale})`,
            opacity: bloomOpacity,
            filter: 'blur(22px) brightness(1.8)',
          }}
        >
          <TextBlock color={WHITE} />
        </div>
      )}

      {/* Main text: crash-zoom abrupt stop */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scale(${textScale})`,
          opacity: textOpacity,
        }}
      >
        <TextBlock color={WHITE} />
      </div>
    </div>
  );
};
