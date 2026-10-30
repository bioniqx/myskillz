// Line boil (line-boil) — hand-drawn animation line boil texture: static line art micro-jitters
// along edges frame-by-frame during the "boil phase", mimicking hand-traced line trembling. SVG filter feTurbulence (baseFrequency
// 0.015, numOctaves 2, seed = Math.floor(f/3) stepped every 3 frames) + feDisplacementMap
// scale=8 (boosted from 3–6 for perceptibility) applied to title "ALIVE" and stroked card layer.
// Structure felt through contrast: static (clean) → boil → unmount back to static; criterion: feTurbulence
// filter must be entirely removed at end (no filter or SVG def rendered outside boil phase),
// perfectly identical frames from 105f onward, true static ≥35f.
// Keyframes: 0–35 fully static (boil off) → 35–105 boil (boil on, seed steps every 3 frames)
// → 105 unmount → 105–140 true static (boil off).
import React, { useId } from 'react';
import { useCurrentFrame, interpolate } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

const BOIL_START = 35;
const BOIL_END = 105;
const BOIL_SCALE = 8; // Boosted from original 3–6 for perceptibility; increase to 12 if QA cannot perceive

const CornerTag: React.FC<{ text: string; opacity: number }> = ({ text, opacity }) => (
  <div
    style={{
      position: 'absolute',
      right: 72,
      bottom: 56,
      padding: '10px 22px',
      border: `3px solid ${G.ink}`,
      borderRadius: 999,
      color: G.ink,
      background: G.bg,
      fontFamily: 'Helvetica, Arial, sans-serif',
      fontWeight: 700,
      fontSize: 30,
      letterSpacing: 2,
      opacity,
    }}
  >
    {text}
  </div>
);

export const LineBoil: React.FC = () => {
  const f = useCurrentFrame();
  // Filter ID generated per instance to prevent cross-referencing in multi-instance setups (sanitize «:» from useId which is invalid in url())
  const boilId = `boil-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  const boiling = f >= BOIL_START && f < BOIL_END;
  // Seed stepped every 3 frames → 8–10Hz hand-drawn jitter feel; frame-deterministic, no random sources
  const seed = Math.floor(f / 3);

  // Corner tag: boil on fades in/out only during boil phase; boil off is complementary.
  // All transitions finish before 105f → 105–140 frames are strictly identical
  const onOp = interpolate(f, [35, 40, 100, 105], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const offOp = 1 - onOp;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      {/* Filter definition only rendered during boil phase — unmounting removes entire SVG def, ensuring natural static ending */}
      {boiling && (
        <svg width={0} height={0} style={{ position: 'absolute' }}>
          <defs>
            <filter id={boilId} x="-15%" y="-15%" width="130%" height="130%">
              <feTurbulence
                type="fractalNoise"
                baseFrequency={0.015}
                numOctaves={2}
                seed={seed}
                result="noise"
              />
              <feDisplacementMap
                in="SourceGraphic"
                in2="noise"
                scale={BOIL_SCALE}
                xChannelSelector="R"
                yChannelSelector="G"
              />
            </filter>
          </defs>
        </svg>
      )}

      {/* Technique title tag: excluded from filter layer as a static visual reference */}
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <TitleBlock text="LINE BOIL" size={54} />
      </div>

      {/* Boiled layer: large title + stroked card */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 56,
          filter: boiling ? `url(#${boilId})` : undefined,
        }}
      >
        <div
          style={{
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: 170,
            color: G.ink,
            letterSpacing: 4,
            lineHeight: 1,
          }}
        >
          ALIVE
        </div>
        {/* Stroked card: transparent background, 3px ink stroke, 520×300 rounded box + gray lines */}
        <div
          style={{
            width: 520,
            height: 300,
            border: `3px solid ${G.ink}`,
            borderRadius: 20,
            boxSizing: 'border-box',
            padding: '36px 40px',
            display: 'flex',
            flexDirection: 'column',
            gap: 26,
          }}
        >
          <div style={{ height: 16, width: '62%', background: G.mid, borderRadius: 8 }} />
          <div style={{ height: 12, width: '88%', background: G.bar, borderRadius: 6 }} />
          <div style={{ height: 12, width: '74%', background: G.bar, borderRadius: 6 }} />
          <div style={{ height: 12, width: '81%', background: G.bar, borderRadius: 6 }} />
          <div style={{ marginTop: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
            <div style={{ width: 30, height: 30, borderRadius: 15, border: `3px solid ${G.ink}`, boxSizing: 'border-box' }} />
            <div style={{ height: 12, width: 120, background: G.mid, borderRadius: 6 }} />
          </div>
        </div>
      </div>

      {/* Status corner tag: boil on during boil phase, boil off during static phase */}
      <CornerTag text="boil on" opacity={onOp} />
      <CornerTag text="boil off" opacity={offOp} />
    </div>
  );
};
