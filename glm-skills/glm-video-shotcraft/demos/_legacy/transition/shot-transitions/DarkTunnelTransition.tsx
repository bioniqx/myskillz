// Variant B dark-tunnel transition — camera pushes out foreground along movement direction → glides through dark tunnel for a few frames →
// background approaches and scales up from depth of field in a single continuous take without cuts. Primary transition for high energy → high energy scene jumps.
// Reference implementation (real textures): Scene A = projects-full board (tail of previous shot),
// push-out 10f camera right (foreground slides left out of frame in screen space); dark tunnel retains subtle gradient dust particles to keep
// "still moving" perceptible, avoiding pitch-black dead frames; Scene B = wbr-full weekly report page starting from scale ~0.6 + blur,
// scaling up and focusing in over 10f. Exit and entrance share the same direction (camera pushes right → Scene B enters from right edge,
// moving left in screen space), with continuous velocity curves.
// Beat: 0–26 A hold → 26–36 push-out (foreground shifts left off-screen, dark tunnel fades in from 32f suppressing the tail,
// avoiding pitch-black dead frames) → 40–42 dark tunnel full → 42–52 B scales in → 52–120 B hold (true static).
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';

export const DARKTUNNEL_DUR = 120;

// Both scenes use cards grid area as viewport; Scene A top aligns to y=180, Scene B (wbr) top aligns to y=0
const A_VIEW_Y = -180;
const A_W = 1920;

const Scene: React.FC = () => {
  const frame = useCurrentFrame();

  // Scene A push-out: 26→36, camera pushes right = foreground translates left out of frame in screen space.
  // Screen space direction must match Scene B (both leftward): previously written as 0→+1920 (content rightward)
  // which collided with Scene B's +960→0 (leftward), reading like two separate clips spliced together.
  const pushX = interpolate(frame, [26, 36], [0, -A_W], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.2, 1),
  });

  // Dark tunnel: 32→40 ramps 0→1 (entering dark tunnel), 42→50 ramps 1→0 (revealing Scene B incoming).
  // Fade-in must overlap the tail of Scene A push-out (at f34–35 Scene A is mostly off-screen) — starting at f36
  // would leak 2f of pitch-black dead frames; not pitch black — subtle gradient + dust particles keep "still moving" perceptible
  const tunnelVis = interpolate(frame, [32, 40, 42, 50], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.6, 1),
  });

  // Scene B approaches and scales in: 42→52, brings into focus from scale 0.6 + blur, while continuing along
  // the same motion axis as A (X rightward) — entry and exit share direction and continuous speed,
  // reading as "straight voyage through the dark tunnel" rather than two scenes moving independently.
  const bIn = interpolate(frame, [42, 52], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const bScale = 0.6 + 0.4 * bIn;
  const bBlur = (1 - bIn) * 12;
  // Slides in from right edge (+960→0), moving left in screen space — same direction as Scene A exiting left,
  // forming a single take where the camera moves right continuously.
  const bShiftX = (1 - bIn) * 960;

  // Dust particles: deterministic index derivation (render must be reproducible). Camera moves right continuously,
  // world-fixed dust drifts left in screen space — drift direction must match both scenes
  const DUST = Array.from({ length: 4 }, (_, i) => ({
    x: 780 + i * 320,
    y: 300 + ((i * 137) % 480),
    drift: 6 + (i % 3) * 4, // px/frame, slow drift conveying "still moving"
  }));

  return (
    <AbsoluteFill style={{ backgroundColor: '#0d0d10', overflow: 'hidden' }}>
      {/* Scene A (push-out phase) */}
      {frame < 42 ? (
        <div style={{ position: 'absolute', transform: `translateX(${pushX}px)` }}>
          <Img
            src={staticFile('legacy-textures/projects-full.png')}
            style={{ position: 'absolute', left: 0, top: A_VIEW_Y, width: A_W }}
          />
        </div>
      ) : null}

      {/* Dark tunnel: subtle gradient + dust particles, not a pitch-black dead field */}
      {frame >= 32 && frame < 50 ? (
        <AbsoluteFill style={{ opacity: tunnelVis, pointerEvents: 'none' }}>
          <div
            style={{
              position: 'absolute', inset: 0,
              background: 'radial-gradient(900px 500px at 50% 45%, rgba(40,42,50,0.9), rgba(12,12,16,1) 70%)',
            }}
          />
          {DUST.map((d, i) => (
            <div
              key={i}
              style={{
                position: 'absolute', left: d.x - frame * d.drift, top: d.y,
                width: 2, height: 2, borderRadius: '50%',
                background: 'rgba(120,125,140,0.35)',
              }}
            />
          ))}
        </AbsoluteFill>
      ) : null}

      {/* Scene B: continues sliding along A's motion axis + scales up head-on + focuses */}
      {frame >= 42 ? (
        <div
          style={{
            position: 'absolute', left: 0, top: 0, width: 1920, height: 1080,
            transform: `translateX(${bShiftX}px) scale(${bScale})`, filter: `blur(${bBlur}px)`,
            transformOrigin: '50% 45%',
          }}
        >
          <Img
            src={staticFile('legacy-textures/wbr-full.png')}
            style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080 }}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const DarkTunnelTransition: React.FC = () => (
  <Scene />
);
