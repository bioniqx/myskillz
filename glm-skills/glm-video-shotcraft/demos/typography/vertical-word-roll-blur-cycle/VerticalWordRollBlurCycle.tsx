// vertical-word-roll-blur-cycle — Vertical word reel (ported from finalized motion-lab to native Remotion)
// The second half of tagline (video-shotcraft value prop "Crafted for ___") rotates through Launches->Demos->Promos->Every Shot on a vertical reel: center word sharp and tinted, adjacent rows light gray with
// vertical blur (simulating reel depth-of-field); each step uses outQuint (fast start, slow settle) with subtle overshoot; on settling, the center word transitions from gray to accent color.
// Rendering polish: blur uses true vertical Gaussian (SVG feGaussianBlur in y-axis only, keeping horizontal strokes crisp); reel rotation
// overlays an additional vertical motion blur proportional to velocity (0 when static); rows farther from center are slightly compressed along the cylinder surface; viewport edges fade softly at top and bottom,
// eliminating hard clipping; background features soft lighting + grain.
// Design canvas: 480x270 (DesignStage scales proportionally); values in parameter table are calibrated to this coordinate space.
import React from 'react';
import { DesignStage, E, seg, useT } from '../../_fixtures/Motion';
import { Backdrop, FONT, Grain } from '../../_fixtures/Polish';

export const VERTICAL_WORD_ROLL_BLUR_CYCLE_DURATION = 150; // 5000ms @30fps

const ROW = 44;
const WORDS = ['Launches', 'Demos', 'Promos', 'Every Shot'];
// 3 word transitions, each taking 0.11 (~0.55s)
const STEPS = [0.16, 0.36, 0.56];

const ACCENT = '#5b63d3';
const ACCENT_DIM = '#B9B9BE';
const INK = '#17181c';
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
// Mix two hex colors by factor k (equivalent to original mixHex in effect.js)
const mixHex = (a: string, b: string, k: number) => {
  k = clamp01(k);
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * k));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
};

// Reel progress p: 0.7 * outQuint + 0.3 * outBack per step (fast start, very slow finish + subtle overshoot settle)
const reelAt = (t: number) => {
  let p = 0;
  for (const s of STEPS) {
    const u = seg(t, s, s + 0.11);
    p += 0.7 * E.outQuint(u) + 0.3 * E.outBack(u);
  }
  return p;
};
const DT = 0.5 / (VERTICAL_WORD_ROLL_BLUR_CYCLE_DURATION - 1); // Normalized t corresponding to half a frame

export const VerticalWordRollBlurCycle: React.FC = () => {
  const t = useT();
  const p = reelAt(t);
  // Reel speed (rows/frame) -> vertical motion blur (design px), 0 when static
  const speed = Math.abs(reelAt(t + DT) - reelAt(t - DT));
  const motionBlur = Math.min(4, speed * ROW * 0.22);

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
    <DesignStage bg="#F4F4F2">
      <Backdrop tone="light" light={{ x: 0.5, y: 0.3 }} accent={ACCENT} vignette={0.12} grain={0} />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: FONT.sans,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            // Entire group fades out at the end
            opacity: 1 - seg(t, 0.9, 0.985) * 0.999,
          }}
        >
          <div
            style={{
              fontSize: 30,
              fontWeight: 800,
              color: INK,
              letterSpacing: -0.5,
            }}
          >
            Crafted for
          </div>
          {/* Three-row viewport containing the sliding word reel, center row = row 2; top and bottom edges fade softly */}
          <div
            style={{
              position: 'relative',
              height: ROW * 3,
              width: 190,
              overflow: 'hidden',
              WebkitMaskImage: 'linear-gradient(180deg, transparent 0%, #000 26%, #000 74%, transparent 100%)',
              maskImage: 'linear-gradient(180deg, transparent 0%, #000 26%, #000 74%, transparent 100%)',
            }}
          >
            <div
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                transform: `translateY(${ROW - p * ROW}px)`,
              }}
            >
              {WORDS.map((w, i) => {
                const d = Math.abs(i - p);
                // Vertical blur for adjacent rows: linear 0->3px within 1 row from center, 3->5px farther out; adds motion blur during rotation
                const blur = (d < 1 ? 3 * d : 3 + 2 * Math.min(d - 1, 1)) + motionBlur;
                const op = d < 1 ? 1 - 0.65 * d : Math.max(0.1, 0.35 - 0.23 * (d - 1));
                // Cylinder curvature: squashes more with distance from center (up to 14%)
                const squash = 1 - 0.14 * Math.min(1, d / 1.4);
                const fid = `vroll-${i}`;
                return (
                  <div key={w} style={{ position: 'relative', height: ROW }}>
                    <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
                      <filter id={fid} x="-10%" y="-120%" width="120%" height="340%" colorInterpolationFilters="sRGB">
                        <feGaussianBlur stdDeviation={`0 ${blur.toFixed(2)}`} />
                      </filter>
                    </svg>
                    <div
                      style={{
                        height: ROW,
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: 30,
                        fontWeight: 800,
                        letterSpacing: -0.5,
                        whiteSpace: 'nowrap', // Final item "Every Shot" contains space, prevent wrapping
                        filter: blur > 0.05 ? `url(#${fid})` : undefined,
                        opacity: op,
                        transform: `scaleY(${squash.toFixed(4)})`,
                        // Settling tint: center word transitions from gray to accent color (smaller d = more saturated)
                        color: mixHex(ACCENT_DIM, ACCENT, clamp01(1 - d * 2.4)),
                      }}
                    >
                      {w}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </DesignStage>
    {/* Grain sits outside the design coordinate container, sampled at output resolution so it doesn't scale up 4x */}
    <Grain opacity={0.05} />
    </div>
  );
};
