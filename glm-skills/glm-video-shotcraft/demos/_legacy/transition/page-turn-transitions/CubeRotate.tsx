// Spatial cube rotation (cube-rotate) — custom cube transition implementation.
// FakeDashboard A / B each scaled by 0.82 centered, acting as adjacent cube faces: perspective 1400px,
// face width W=1920*0.82, each face rotateY(face angle) translateZ(W/2), scene overall first
// translateZ(-W/2) then rotateY(θ) (pulling front face back to z=0, ensuring exact 0.82 scale during hold).
// Old face A rotates out darkening brightness 1→0.55, new face B rotates in from +90° side brightening 0.55→1;
// vertical gradient shadows along both sides of seam deepen with sin(pπ) then fade out; mid-rotation adds blur(1.5px),
// removed upon settling (conditionally applied filter ensures frame-identical ending).
// Keyframes: 0–30 static display A → 30–68 θ 0→-90° (inOut cubic) rotation → 68–140 B true static 72f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard, TitleBlock } from '../../_fixtures/Fixtures';

const S = 0.82;
const W = 1920 * S; // Face width = cube edge length
const H = 1080 * S;

// Single cube face: entire dashboard scaled to 0.82 within W×H viewport
const Face: React.FC<{
  variant: 'A' | 'B';
  rot: number; // Face's own rotateY (A=0, B=90)
  brightness: number;
  seam: number; // Seam shadow opacity 0–1
  seamSide: 'right' | 'left'; // Which vertical edge shadow attaches to (shared edge side)
}> = ({ variant, rot, brightness, seam, seamSide }) => (
  <div
    style={{
      position: 'absolute',
      width: W,
      height: H,
      overflow: 'hidden',
      backfaceVisibility: 'hidden',
      transform: `rotateY(${rot}deg) translateZ(${W / 2}px)`,
      filter: `brightness(${brightness})`,
      background: G.bg,
    }}
  >
    <div style={{ transform: `scale(${S})`, transformOrigin: '0 0' }}>
      <FakeDashboard variant={variant} />
    </div>
    {seam > 0.01 && (
      <div
        style={{
          position: 'absolute',
          top: 0,
          [seamSide]: 0,
          width: 150,
          height: H,
          opacity: seam,
          background:
            seamSide === 'right'
              ? 'linear-gradient(to right, rgba(0,0,0,0), rgba(0,0,0,0.55))'
              : 'linear-gradient(to left, rgba(0,0,0,0), rgba(0,0,0,0.55))',
        }}
      />
    )}
  </div>
);

export const CubeRotate: React.FC = () => {
  const frame = useCurrentFrame();
  // Rotation progress: 30–68f, inOut cubic; clamped both ends to guarantee constant frames during hold
  const p = interpolate(frame, [30, 68], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const theta = -90 * p;
  const brightA = 1 - 0.45 * p; // Old face rotates out darkening 1→0.55
  const brightB = 0.55 + 0.45 * p; // New face rotates in brightening 0.55→1
  const mid = Math.sin(p * Math.PI); // 0→1→0, deepest at 45°
  const seam = mid * 0.9;
  const blur = mid * 1.5;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      {/* Blur outer wrapper: only applies filter when >0.02, ensuring final frames are completely identical */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          filter: blur > 0.02 ? `blur(${blur}px)` : undefined,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: (1920 - W) / 2,
            top: (1080 - H) / 2,
            width: W,
            height: H,
            perspective: 1400,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              transformStyle: 'preserve-3d',
              transform: `translateZ(${-W / 2}px) rotateY(${theta}deg)`,
            }}
          >
            {/* Face A: starts at front, swings leftward; seam edge on its right */}
            <Face variant="A" rot={0} brightness={brightA} seam={seam} seamSide="right" />
            {/* Face B: rotates in from +90° side; seam edge on its left */}
            <Face variant="B" rot={90} brightness={brightB} seam={seam} seamSide="left" />
          </div>
        </div>
      </div>
      <div style={{ position: 'absolute', left: 120, top: 60 }}>
        <TitleBlock text="CUBE ROTATE" size={54} />
      </div>
    </div>
  );
};
