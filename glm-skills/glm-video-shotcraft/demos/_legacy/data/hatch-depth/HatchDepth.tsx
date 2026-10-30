// hatch-depth — Hatch -> Depth Chart hatching bar materialization (ported from motion-lab final to native Remotion)
// Hatched bars under labels wipe and extend one by one (preserving 45° hatched placeholder texture); hatched layer then fades out while accent-colored
// solid layer fades in, morphing into horizontal data bar chart — zero geometric jump, switching only texture and color, metaphor of "placeholder becoming real data".
// Design canvas 480×270 (DesignStage proportional scale); parameter values calibrated in this coordinate space.
import React from 'react';
import { DesignStage, E, seg, useT } from '../../_fixtures/Motion';

export const HATCH_DEPTH_DURATION = 132; // 4400ms @30fps

const ACCENT = '#5B8DEF'; // Template accent color, customizable per project
const ACCENT_HI = '#8FB2F7'; // Same-family highlight (value text)

const ROWS = [
  { label: 'SERIES_A', w: 0.85 },
  { label: 'SERIES_B', w: 0.55 },
  { label: 'GROUP_C', w: 0.95 },
  { label: 'GROUP_D', w: 0.4 },
  { label: 'OTHER_E', w: 0.7 },
];

// &nbsp;&nbsp; in header info bar (consecutive standard spaces get collapsed in JSX, must use non-breaking spaces)
const NBSP2 = '  ';

export const HatchDepth: React.FC = () => {
  const t = useT();
  // Header info bar: slides down into view
  const headIn = seg(t, 0.62, 0.78, E.outCubic);
  return (
    <DesignStage bg="#0a0a0c">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: '#0a0a0c',
          padding: '36px 60px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 13,
          // Original font stack SF Mono invisible in headless Chrome; real Chrome falls back to macOS default
          // monospace font Courier (serif typewriter style); explicit Courier fallback aligns with reference
          fontFamily: '"SF Mono",Courier,monospace',
        }}
      >
        {ROWS.map(({ label, w }, i) => {
          // Staggered wipe extension -> hatch fades out / solid fades in -> subtle wiggle at end
          const grow = seg(t, 0.06 + i * 0.05, 0.06 + i * 0.05 + 0.22, E.outCubic);
          const morph = seg(t, 0.5 + i * 0.03, 0.5 + i * 0.03 + 0.14);
          const wiggle = 1 + Math.sin(t * 30 + i * 2.1) * 0.02 * seg(t, 0.7, 0.85);
          const wPct = grow * w * 100 * wiggle;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, height: 26 }}>
              <span
                style={{
                  color: morph > 0.5 ? '#5c626f' : '#8b91a3',
                  fontSize: 11,
                  width: 70,
                  flex: 'none',
                  textAlign: 'right',
                }}
              >
                {label}
              </span>
              <div style={{ position: 'relative', height: '100%', flex: 1 }}>
                {/* Hatch placeholder layer */}
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${wPct}%`,
                    borderRadius: 3,
                    background: 'repeating-linear-gradient(45deg,#565860 0 4px,transparent 4px 9px)',
                    border: '1px solid #565860',
                    // Original render lacked global border-box: width/height represent content size, 1px border expands outward
                    // (hatch pattern phase shifts with element size; phase mismatches unless original box-sizing is preserved)
                    boxSizing: 'content-box',
                    opacity: 1 - morph,
                  }}
                />
                {/* Accent solid layer */}
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${wPct}%`,
                    borderRadius: 3,
                    background: `linear-gradient(90deg,${ACCENT},${ACCENT_HI})`,
                    opacity: morph,
                  }}
                />
                {/* Bar-end value */}
                <span
                  style={{
                    position: 'absolute',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: ACCENT_HI,
                    fontSize: 10,
                    left: `calc(${wPct}% + 8px)`,
                    opacity: morph,
                  }}
                >
                  {Math.round(w * 420 * grow)}K
                </span>
              </div>
            </div>
          );
        })}
        {/* Header info bar */}
        <div
          style={{
            position: 'absolute',
            top: 20,
            left: 60,
            fontWeight: 600,
            fontSize: 12,
            fontFamily: '"SF Mono",Courier,monospace', // As above: Courier fallback
            letterSpacing: 1,
            transform: `translateY(${-30 + headIn * 30}px)`,
            opacity: headIn,
          }}
        >
          <span style={{ color: '#e8eaf0', fontWeight: 700 }}>METRICS</span>
          {NBSP2}
          <span style={{ color: '#67d17c' }}>● LIVE</span>
          {NBSP2}
          <span style={{ color: '#8b91a3' }}>TOTAL 875K{NBSP2}AVG 1.02M</span>
        </div>
      </div>
    </DesignStage>
  );
};
