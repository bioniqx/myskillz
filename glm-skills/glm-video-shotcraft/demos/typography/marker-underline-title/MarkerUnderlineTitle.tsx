// marker-underline-title — after large title settles, marker underline draws from left to right
// beneath italic keyword (variable width / rounded caps / organic slant / textured edge).
// Reference: notion-ai.mp4 2.3-3.6s. Emphasizes organic felt-tip marker texture.
// Polish pass: total 75f (line finishes at f42, holds 33f >= 1s); two title lines blur-slide staggered
// (snappy, row 2 lags 4f); dry marker texture via feTurbulence displacement edge + cutout,
// warm near-black ink multiplying onto paper base; warm white paper + key light + grain;
// row 2 = video-shotcraft brand mark + lowercase name; slow continuous push 1->1.015.
import React, { useId } from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { Backdrop, EASE, FONT, ramp } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const MARKER_UNDERLINE_TITLE_DURATION = 75; // Title settles 22f -> underline draws f32-42 -> static hold 33f

const mulberry32 = (a: number) => () => {
  let t = (a += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// Marker stroke: slightly slanted spine + variable-width polygon outline
const buildStroke = (len: number, seed: number) => {
  const rand = mulberry32(seed);
  const N = 40;
  const top: string[] = [];
  const bot: string[] = [];
  // Precomputed organic offset (low freq) and roughness (high freq)
  const wob = Array.from({ length: N + 1 }, () => rand() - 0.5);
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const x = t * len;
    // Spine: follows italic slant upward (low left, high right) + subtle undulation
    const mid = 19 - t * 9 + Math.sin(t * Math.PI * 1.6 + 0.4) * 2.6 + wob[i] * 1.6;
    // Stroke width: tapered start -> full middle -> tapered end + roughness
    const wBase = 14 + Math.sin(t * Math.PI) * 6 - Math.max(0, t - 0.86) * 46 - Math.max(0, 0.06 - t) * 70; // Tapered stroke entrance
    const w = Math.max(2.2, wBase + wob[i] * 3);
    top.push(`${x.toFixed(1)},${(mid - w / 2).toFixed(1)}`);
    bot.push(`${x.toFixed(1)},${(mid + w / 2).toFixed(1)}`);
  }
  return `M${top.join('L')}L${bot.reverse().join('L')}Z`;
};

const LEN = 252;
const PATH = buildStroke(LEN, 77);
const MARKER_INK = '#1b1916'; // Warm near-black marker ink

export const MarkerUnderlineTitle: React.FC = () => {
  const frame = useCurrentFrame();
  // Unique instance SVG IDs (sanitizing colons for url())
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const revealId = `reveal-${uid}`;
  const dryId = `dry-${uid}`;

  // Two-line staggered title entrance: shared snappy progress driving y / blur / opacity
  const line = (delay: number): React.CSSProperties => {
    const e = ramp(frame, delay, 22, EASE.snappy);
    return {
      opacity: Math.min(1, e * 1.4),
      transform: `translateY(${(1 - e) * 36}px)`,
      filter: e < 0.999 ? `blur(${((1 - e) * 8).toFixed(2)}px)` : undefined,
    };
  };

  // Underline: draws after title settles, 10 frames left to right, ease-out
  const draw = interpolate(frame, [32, 42], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const drawE = 1 - Math.pow(1 - draw, 2.2);
  // Slow continuous camera push (smooth)
  const push = 1 + 0.015 * ramp(frame, 0, 74, EASE.smooth);

  return (
    <AbsoluteFill>
      <Backdrop tone="light" light={{ x: 0.42, y: 0.3 }} vignette={0.12} grain={0.05} />
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', transform: `scale(${push})` }}>
        <div style={{
          fontFamily: FONT.sans,
          fontWeight: 700, fontSize: 118, color: '#17181c',
          textAlign: 'center', lineHeight: 1.12, letterSpacing: '-0.028em',
        }}>
          <div style={line(0)}>
            Meet the{' '}
            <span style={{ fontStyle: 'italic', position: 'relative', display: 'inline-block' }}>
              new
              {/* Marker underline: clip reveals left to right, preserving stroke width variation */}
              <svg
                width={LEN} height={44} viewBox={`0 0 ${LEN} 44`}
                style={{ position: 'absolute', left: -12, bottom: -20, overflow: 'visible', mixBlendMode: 'multiply' }}
              >
                <defs>
                  <clipPath id={revealId}>
                    <rect x={0} y={-20} width={drawE * (LEN + 6)} height={60} />
                  </clipPath>
                  {/* Dry marker texture: low-freq displacement edge + high-freq noise threshold cutout */}
                  <filter id={dryId} x="-5%" y="-40%" width="110%" height="180%" colorInterpolationFilters="sRGB">
                    <feTurbulence type="fractalNoise" baseFrequency="0.09 0.5" numOctaves={2} seed={7} result="warp" />
                    <feDisplacementMap in="SourceGraphic" in2="warp" scale={1.8} xChannelSelector="R" yChannelSelector="G" result="rough" />
                    <feTurbulence type="fractalNoise" baseFrequency="0.035 0.9" numOctaves={2} seed={19} result="grain" />
                    <feColorMatrix in="grain" type="matrix"
                      values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -16 11.4" result="holes" />
                    <feComposite in="rough" in2="holes" operator="in" />
                  </filter>
                </defs>
                {draw > 0 && (
                  <g clipPath={`url(#${revealId})`}>
                    <path d={PATH} fill={MARKER_INK} fillOpacity={0.94} filter={`url(#${dryId})`} />
                  </g>
                )}
              </svg>
            </span>
          </div>
          <div style={{ ...line(4), display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18 }}>
            <ShotcraftMark size={112} tone="light" />
            <span>{BRAND.name}</span>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
