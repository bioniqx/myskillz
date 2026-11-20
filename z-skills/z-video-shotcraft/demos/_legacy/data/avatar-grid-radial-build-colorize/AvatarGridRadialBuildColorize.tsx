// avatar-grid-radial-build-colorize — Avatar Grid radial build with random colorization (ported from motion-lab final to native Remotion)
// 8×7 small card grid expands radially outward ring by ring from center (expands 1 ring every 4 frames, filling canvas in 1.2s); card contents mix three placeholders:
// initials / icon glyph / color swatch thumbnail, animating opacity + scale 0.8 -> 1 without displacement; once populated, ~15% of cards
// tint their background pale red and status dot red at random moments within 1s, creating a breathing sensation of "anomalies gradually surfacing".
// Center 3×6 area reserved with visibility:hidden for title and legend; title layer remains 100% opaque throughout.
// Design canvas 480×270 (DesignStage proportional scale); parameter values calibrated in this coordinate space.
import React from 'react';
import { DesignStage, E, lerp, rand, seg, useT } from '../../_fixtures/Motion';

export const AVATAR_GRID_RADIAL_BUILD_COLORIZE_DURATION = 168; // 5600ms @30fps

const PAPER = '#F3F3F1';
const INK = '#111113';
const MID = '#8A8A8F';
const CARD_WHITE = '#ffffff';
const FLAG_BG = '#FDECEC';

// Color interpolation (mix from effect.js; hex2rgb originally from lab page global, inlined here)
const hex2rgb = (hex: string): [number, number, number] => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
];
const mix = (a: string, b: string, t: number) => {
  const A = hex2rgb(a);
  const B = hex2rgb(b);
  return `rgb(${Math.round(A[0] + (B[0] - A[0]) * t)},${Math.round(A[1] + (B[1] - A[1]) * t)},${Math.round(
    A[2] + (B[2] - A[2]) * t,
  )})`;
};

const COLS = 8;
const ROWS = 7;
const TOTAL = 5.6 * 30; // Total frames (used for delay conversion)

// Grid geometry: equivalent to effect.js inset:16px + gap:10px CSS grid, but manually placed via absolute positioning.
// CSS grid under 480×270 design coordinates rounds tracks to whole pixels (alternating 140/144 pitch when scaled 4x),
// departing from reference uniform distribution at full resolution; fractional design coords + absolute positioning preserve subpixel pitch.
const GAP = 10;
const CELL_W = (480 - 32 - (COLS - 1) * GAP) / COLS; // 47.25
const CELL_H = (270 - 32 - (ROWS - 1) * GAP) / ROWS; // ≈25.43

// Three placeholder types for card content: initials (logo slot) / icon glyph / color swatch thumbnail (image slot), replaceable with project assets
const INI = ['VS', 'KJ', 'EM', 'AL', 'TR', 'MN', 'BQ', 'DW', 'RC', 'SF', 'PL', 'GH'];
const ICONS = ['◆', '▲', '●', '■', '✦', '◐', '❖', '▣'];

// Static parameters per cell (seeds correspond 1:1 with effect.js, deterministic across frames)
const CELLS = Array.from({ length: ROWS * COLS }, (_, i) => {
  const r = Math.floor(i / COLS);
  const c = i % COLS;
  const hidden = r >= 2 && r <= 4 && c >= 1 && c <= 6; // Center void reserved for title + legend (placeholder preserves grid)
  const kind = Math.floor(rand(i * 9.1) * 3); // 0=initials 1=icon 2=image thumbnail
  const ini = INI[Math.floor(rand(i * 3.7) * INI.length)];
  const icon = ICONS[Math.floor(rand(i * 5.3) * ICONS.length)];
  const h = Math.floor(rand(i * 7.7) * 360); // Thumbnail gradient hue
  const ring = Math.round(Math.hypot((c - 3.5) / 1.0, (r - 3) / 0.85)); // "Ring index" from center
  const delay = (ring * 4 + rand(i + 40) * 3) / TOTAL; // Expands 1 ring every 4 frames + frame jitter
  const flagged = rand(i + 900) < 0.15; // ~15% anomalous cards
  const at = 0.3 + rand(i + 1600) * 0.3; // Random moment for color tint
  return { hidden, kind, ini, icon, h, delay, flagged, at };
});

const LEGEND: Array<[string, string]> = [
  ['Active', '#37C46B'],
  ['Pending', '#F5A524'],
  ['Inactive', '#F0453A'],
];

export const AvatarGridRadialBuildColorize: React.FC = () => {
  const t = useT();
  // Title fades in + subtle scale; legend emerges thereafter
  const tIn = seg(t, 0.02, 0.1, E.outQuad);
  const legendIn = seg(t, 0.26, 0.36, E.outQuad);
  return (
    <DesignStage bg={PAPER} raster="zoom">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
          fontFamily: "-apple-system,'Helvetica Neue',Helvetica,Arial,sans-serif",
        }}
      >
        <div style={{ position: 'absolute', inset: 16 }}>
          {CELLS.map((cl, i) => {
            const r = Math.floor(i / COLS);
            const c = i % COLS;
            const f = 0.09 + cl.delay;
            const o = seg(t, f, f + 0.018, E.linear);
            const sc = seg(t, f, f + 0.03, E.outQuad);
            // Anomalous card: background tinted pale red, border tinted pink, status dot turns red
            const cT = cl.flagged ? seg(t, cl.at, cl.at + 0.036, E.outQuad) : 0;
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: c * (CELL_W + GAP),
                  top: r * (CELL_H + GAP),
                  width: CELL_W,
                  height: CELL_H,
                  boxSizing: 'border-box', // Equivalent to grid stretch: border included in track size
                  borderRadius: 8,
                  background: cl.flagged ? mix(CARD_WHITE, FLAG_BG, cT) : CARD_WHITE,
                  border: `1px solid ${cl.flagged ? mix('#E7E7E4', '#F6CFCF', cT) : '#E7E7E4'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  overflow: 'hidden',
                  fontWeight: 700,
                  fontSize: cl.kind === 1 ? 13 : 11,
                  lineHeight: 1,
                  fontFamily: '-apple-system,Helvetica,sans-serif', // Remotion headless browser lacks -apple-system; fallback Helvetica aligns with reference SF glyphs
                  color: cl.kind === 1 ? '#6a6f7c' : '#3A3A3E',
                  opacity: o,
                  boxShadow: '0 1px 2px rgba(0,0,0,.04)',
                  visibility: cl.hidden ? 'hidden' : 'visible',
                  transform: `scale(${lerp(sc, 0.8, 1)})`,
                }}
              >
                {cl.kind === 0 ? cl.ini : cl.kind === 1 ? cl.icon : null}
                {cl.kind === 2 && (
                  <div
                    style={{
                      position: 'absolute',
                      inset: 0,
                      borderRadius: 7,
                      background: `linear-gradient(${45 + (cl.h % 90)}deg, hsl(${cl.h},18%,78%), hsl(${
                        (cl.h + 40) % 360
                      },22%,62%))`,
                    }}
                  />
                )}
                <div
                  style={{
                    position: 'absolute',
                    right: 4,
                    top: 4,
                    width: 5,
                    height: 5,
                    borderRadius: '50%',
                    background: cl.flagged ? mix('#37C46B', '#F0453A', cT) : '#37C46B',
                  }}
                />
              </div>
            );
          })}
        </div>
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '45%',
            transform: `translate(-50%,-50%) scale(${lerp(tIn, 0.98, 1)})`,
            fontWeight: 800,
            fontSize: 30,
            lineHeight: 1.2,
            fontFamily: "-apple-system,'Helvetica Neue',sans-serif",
            letterSpacing: -1.2,
            color: INK,
            textAlign: 'center',
            zIndex: 5,
            whiteSpace: 'nowrap',
            opacity: tIn,
          }}
        >
          Let's bring them back in
        </div>
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '56%',
            transform: 'translateX(-50%)',
            display: 'flex',
            gap: 14,
            alignItems: 'center',
            zIndex: 5,
            padding: '4px 10px',
            opacity: legendIn,
            whiteSpace: 'nowrap',
          }}
        >
          {LEGEND.map(([txt, col]) => (
            <div
              key={txt}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                fontWeight: 600,
                fontSize: 11,
                lineHeight: 1,
                fontFamily: '-apple-system,Helvetica,sans-serif', // Remotion headless browser lacks -apple-system; fallback Helvetica aligns with reference SF glyphs
                color: MID,
              }}
            >
              <span
                style={{ width: 6, height: 6, borderRadius: '50%', background: col, display: 'inline-block' }}
              />
              <span>{txt}</span>
            </div>
          ))}
        </div>
      </div>
    </DesignStage>
  );
};
