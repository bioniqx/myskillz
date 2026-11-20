// Style E: Baseline whip-pan — authentic full-page frozen texture (demos/_textures/).
// World: projects-full top section (Scene A) and bottom section of the same page (Scene B) placed side-by-side horizontally
// — simulating "block handoff between functional sections"; camera whips 2880px across 8f (peak ~540px/f),
// with motion blur applied strictly to the whip segment. Timing: 0–35 A hold -> 35–43 whip (blurred) -> 43–120 B hold (true rest).
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';

export const WHIPPAN_DUR = 120;

const SWING = 2880; // 1.5 screens
// Viewport aligned to cards grid area (page space y≈247 onwards), viewport top at y=180
const VIEW_Y = -180;

const Scene: React.FC = () => {
  const frame = useCurrentFrame();
  const dx = interpolate(frame, [35, 43], [0, SWING], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.6, 0, 0.4, 1),
  });
  return (
    <AbsoluteFill style={{ backgroundColor: '#f9f6f1', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', transform: `translateX(${-dx}px)` }}>
        {/* Scene A: Full project board */}
        <Img
          src={staticFile('legacy-textures/projects-full.png')}
          style={{ position: 'absolute', left: 0, top: VIEW_Y, width: 1920 }}
        />
        {/* 960px paper-colored gap — flashes by mid-whip, completely blurred */}
        {/* Scene B: Bottom section of same page (PERCEPTION & SENSING section), identifiable scene change packed with content */}
        <Img
          src={staticFile('legacy-textures/projects-full.png')}
          style={{ position: 'absolute', left: SWING, top: -666, width: 1920 }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const WhipPanReal: React.FC = () => (
  // Peak ~540px/f: sampling calibrated to "echo interval ≤ text height", 20 samples yield continuous motion blur
  <CameraMotionBlur shutterAngle={200} samples={20}>
    <Scene />
  </CameraMotionBlur>
);
