// dolly-zoom: hero card (card4-hires) locked at center,
// background card flock + full page expand inward (scale + blur),
// "world pushes in" while subject stays motionless. Pseudo dolly-zoom via layered inverse compensation.
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import layout from '../../_textures/live-layout.json';

export const DOLLYZOOM_DUR = 135;

const BG_CARDS = layout.projects.cards.filter((_, i) => i !== 3);

export const DollyZoomReal: React.FC = () => {
  const frame = useCurrentFrame();
  const t = interpolate(frame, [15, 110], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.4, 0, 0.3, 1),
  });
  const bgScale = 1 + t * 1.25;
  const bgBlur = t * 3.5;
  return (
    <AbsoluteFill style={{ backgroundColor: '#efece6', overflow: 'hidden' }}>
      {/* Background: full page + card flock expanding inward from screen center */}
      <div
        style={{
          position: 'absolute', inset: 0,
          transform: `scale(${bgScale})`, transformOrigin: '960px 540px',
          filter: `blur(${bgBlur}px) saturate(0.9)`,
        }}
      >
        <Img src={staticFile('legacy-textures/projects-full.png')} style={{ position: 'absolute', left: 0, top: -400, width: 1920, opacity: 0.55 }} />
        {BG_CARDS.slice(0, 8).map((c, k) => (
          <Img
            key={c.file + k}
            src={staticFile(`legacy-textures/${c.file}`)}
            style={{
              position: 'absolute',
              left: [180, 1280, 240, 1220, 700, 760, 60, 1500][k],
              top: [140, 120, 700, 720, 60, 840, 420, 430][k],
              width: 320, borderRadius: 12, opacity: 0.9,
              boxShadow: '0 6px 20px rgba(31,28,23,0.12)',
            }}
          />
        ))}
      </div>
      {/* Subject: hero card pinned at center, deepening shadow emphasizes motionless subject */}
      <Img
        src={staticFile('legacy-textures/card4-hires.png')}
        style={{
          position: 'absolute', left: 960 - 260, top: 540 - 228, width: 520,
          borderRadius: 14,
          boxShadow: `0 ${12 + t * 16}px ${40 + t * 28}px rgba(31,28,23,${0.16 + t * 0.10})`,
        }}
      />
    </AbsoluteFill>
  );
};
