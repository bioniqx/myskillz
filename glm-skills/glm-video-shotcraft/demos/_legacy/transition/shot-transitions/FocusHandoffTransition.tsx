// Style C: Focus Handoff transition — Foreground slides out of the focal plane (blur deepening) while background brings
// reverse rack-focus into sharpness, using the focal point as the edit point. Section-to-section / long document page exploration transition.
// Reference implementation (authentic texture): Both A/B are sourced from the **same** projects-full long page — Scene A aligns
// to the upper card grid (cards, y≈180 onwards), Scene B aligns to the **lower half of the same page** (Perception &
// Sensing / Research Infra sections, y≈900 onwards), simulating "exploring the same long page with section relay".
// Timing: 0–24 A hold -> 24–40 A fade out + blur 0->8px sliding out, while 26–42 B sharpens 8px->0
// focus rack + fade in + slide in from opposite side (staggered 2f launch — launching on same frame feels like whole screen blurs);
// both scenes exchange focus within the overlap window -> 42–120 B hold (true rest). Shallow depth-of-field language established before use.
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';

export const FOCUSHANDOFF_DUR = 120;

const PAGE_H = 1746; // CSS height of projects-full (layout.projects.pageH)
// Scene A viewport: aligned to upper card grid (viewport top at page y=180)
const A_VIEW_Y = -180;
// Scene B viewport: lower half of the same page (viewport top at page y=900, showing
// Perception & Sensing / Research Infra sections), viewport bottom does not exceed page bottom
const B_VIEW_Y = -900;

const Scene: React.FC = () => {
  const frame = useCurrentFrame();

  // Scene A: 24->40 fade out + deepening blur + slight slide-out (foreground exits focal plane)
  const aOut = interpolate(frame, [24, 40], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.3, 1),
  });
  const aBlur = aOut * 8;
  const aDrift = aOut * 60; // Slight left drift, read as "sliding out" rather than fading in place

  // Scene B: 26->42 rack focus entrance (staggered 2f launch), 8px->0 + fade in + reverse slide-in
  const bIn = interpolate(frame, [26, 42], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const bBlur = (1 - bIn) * 8;
  const bDrift = (1 - bIn) * -50; // Reverse direction (sliding in from right)

  return (
    <AbsoluteFill style={{ backgroundColor: '#faf7f2', overflow: 'hidden' }}>
      {/* Scene A: Upper half of the same page (grid area) */}
      <div style={{ position: 'absolute', opacity: 1 - aOut, filter: `blur(${aBlur}px)`, transform: `translateX(${-aDrift}px)` }}>
        <Img
          src={staticFile('legacy-textures/projects-full.png')}
          style={{ position: 'absolute', left: 0, top: A_VIEW_Y, width: 1920, height: PAGE_H }}
        />
      </div>

      {/* Scene B (upper layer): Lower half of the same page (sections area), racking focus within overlap window */}
      <div style={{ position: 'absolute', opacity: bIn, filter: `blur(${bBlur}px)`, transform: `translateX(${bDrift}px)` }}>
        <Img
          src={staticFile('legacy-textures/projects-full.png')}
          style={{ position: 'absolute', left: 0, top: B_VIEW_Y, width: 1920, height: PAGE_H }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const FocusHandoffTransition: React.FC = () => (
  <Scene />
);
