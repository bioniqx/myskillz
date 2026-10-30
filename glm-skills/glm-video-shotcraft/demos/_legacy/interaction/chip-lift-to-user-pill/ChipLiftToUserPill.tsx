// chip-lift-to-user-pill — Selected chip grows into user pill (ported from motion-lab to native Remotion)
// Target chip in grid hard-cuts to inverted black background with white text over 3 frames,
// while remaining chips stagger fade out and scale to 0.9 based on distance from target;
// Black chip anchors its left edge and expands rightward into a pill, revealing the name letter-by-letter
// and lighting up a green dot, then draws a 1px connector line to a circular badge, ending with progressive caption darkening.
// Design space 480x270 (DesignStage proportional scaling), 440x240 fixed canvas centered.
import React from 'react';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';

export const CHIP_LIFT_TO_USER_PILL_DURATION = 150; // 5000ms @30fps

// ---- Shared constants (Swiss minimal light gray palette / typography; BG/DIM/h2r from motion-lab/fx/b09.js) ----
const SANS = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif';
const BG = '#F1F1F3'; // Page light gray
const INK = '#0B0B0C'; // Pure black
const TXT = '#111111'; // Body text black
const DIM = '#C9C9CE'; // Light gray placeholder text
const LINE = '#E6E6EA'; // Stroke / border

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const h2r = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
// Color interpolation: mix(p,'#C9C9CE','#111')
const mix = (p: number, a: string, b: string) => {
  const A = h2r(a), B = h2r(b), q = clamp01(p);
  return `rgb(${Math.round(A[0] + (B[0] - A[0]) * q)},${Math.round(A[1] + (B[1] - A[1]) * q)},${Math.round(A[2] + (B[2] - A[2]) * q)})`;
};

// ---- Grid parameters (matches effect.js) ----
const COLS = 4, ROWS = 3, CW = 40, CH = 24, GX = 10, GY = 9, GX0 = 8, GY0 = 70;
const TC = 1, TR = 1; // Target chip column/row
const LABELS = ['JD', 'MK', 'CD', 'RL', 'AV', 'TP', 'KN', 'BW', 'CE', 'HR', 'LM', 'DQ'];
// Target chip top-left coordinates (left edge anchored, stays fixed during growth)
const TX = GX0 + TC * (CW + GX); // 58
const TY = GY0 + TR * (CH + GY); // 103
// Remaining chips: position + Manhattan distance to target (for staggered fade-out)
const OTHERS = Array.from({ length: ROWS * COLS }, (_, i) => {
  const r = Math.floor(i / COLS), c = i % COLS;
  return {
    x: GX0 + c * (CW + GX),
    y: GY0 + r * (CH + GY),
    label: LABELS[i],
    dist: Math.abs(c - TC) + Math.abs(r - TR),
    isT: c === TC && r === TR,
  };
}).filter((o) => !o.isT);

const PW0 = CW, PW1 = 190; // Start and end width for pill expansion
const NAME_CHARS = 'Casey Doe'.split(''); // Name typed character-by-character inside the pill

// Ending caption (progressive word darkening syntax, only uses show + inn states)
const CAP_WORDS = 'Starting with Casey'.split(' ');
const CAP_ST = 0.78 / CAP_WORDS.length;
const CAP_WIN = CAP_ST * 1.5;

// Badge size (white circular base + four-point star)
const BADGE_SIZE = 26;
const BADGE_SVG = Number((BADGE_SIZE * 0.52).toFixed(1)); // 13.5

export const ChipLiftToUserPill: React.FC = () => {
  const t = useT();

  // A Invert hard-cut (3-frame feel): stepped progress to 0 / 0.5 / 1 -> hard-cut feel
  const a = seg(t, 0.04, 0.085, E.linear);
  const aq = a < 0.34 ? 0 : a < 0.67 ? 0.5 : 1;

  // C Pill expands from left edge + character stagger + green dot
  const g = seg(t, 0.26, 0.44, E.outCubic);
  const w = lerp(g, PW0, PW1);
  const dq = seg(g, 0.85, 1, E.outBack);

  // D Connector line -> badge -> caption
  const cw = seg(t, 0.47, 0.57, E.outQuad);
  const bp = seg(t, 0.56, 0.63, E.outCubic);
  const capShow = seg(t, 0.6, 0.66);
  const capInn = seg(t, 0.6, 0.92);

  return (
    <DesignStage bg={BG}>
      {/* Page + 440x240 fixed canvas (centered) */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: BG,
          overflow: 'hidden',
          fontFamily: SANS,
          WebkitFontSmoothing: 'antialiased',
        }}
      >
        <div style={{ position: 'absolute', left: '50%', top: '50%', width: 440, height: 240, margin: '-120px 0 0 -220px' }}>
          {/* B Remaining chips: staggered fade-out by Manhattan distance to target + scale 0.9 */}
          {OTHERS.map((o, i) => {
            const d0 = 0.10 + o.dist * 0.022;
            const p = seg(t, d0, d0 + 0.075, E.outQuad);
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: o.x,
                  top: o.y,
                  width: CW,
                  height: CH,
                  borderRadius: CH / 2,
                  background: '#fff',
                  border: `1px solid ${LINE}`,
                  display: 'flex',
                  alignItems: 'center',
                  boxSizing: 'border-box',
                  overflow: 'hidden',
                  boxShadow: '0 1px 3px rgba(0,0,0,.04)',
                  opacity: 1 - p,
                  transform: `scale(${lerp(p, 1, 0.9)})`,
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    width: CW,
                    height: CH,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    font: `600 10.5px/1 ${SANS}`,
                    letterSpacing: '.6px',
                    color: TXT,
                  }}
                >
                  {o.label}
                </div>
              </div>
            );
          })}

          {/* Target chip (top layer): hard-cut inversion -> left-edge anchored growth to pill */}
          <div
            style={{
              position: 'absolute',
              left: TX,
              top: TY,
              width: w,
              height: CH,
              borderRadius: CH / 2,
              background: mix(aq, '#ffffff', INK),
              border: `1px solid ${mix(aq, LINE, INK)}`,
              display: 'flex',
              alignItems: 'center',
              boxSizing: 'border-box',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,.04)',
            }}
          >
            {/* Original abbreviated label: fades out as pill expands after inversion */}
            <div
              style={{
                position: 'absolute',
                left: 0,
                top: 0,
                width: CW,
                height: CH,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                font: `600 10.5px/1 ${SANS}`,
                letterSpacing: '.6px',
                color: mix(aq, TXT, '#ffffff'),
                opacity: 1 - clamp01(g * 5),
              }}
            >
              CD
            </div>
            {/* Name typed character-by-character (staggered on growth progress g) */}
            <div
              style={{
                position: 'absolute',
                left: 13,
                top: 0,
                height: CH,
                display: 'flex',
                alignItems: 'center',
                whiteSpace: 'nowrap',
              }}
            >
              {NAME_CHARS.map((ch, i) => {
                const p = seg(g, 0.18 + i * 0.062, 0.18 + i * 0.062 + 0.05, E.outQuad);
                return (
                  <span
                    key={i}
                    style={{
                      font: `600 11px/1 ${SANS}`,
                      color: '#fff',
                      opacity: p,
                      whiteSpace: 'pre',
                      letterSpacing: '.2px',
                      transform: `translateY(${lerp(p, 2, 0)}px)`,
                      display: 'inline-block',
                    }}
                  >
                    {ch}
                  </span>
                );
              })}
            </div>
            {/* Online green indicator: pops out with outBack, pinned inside the right edge of the pill */}
            <div
              style={{
                position: 'absolute',
                top: (CH - 7) / 2,
                left: w - 15,
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#35D07F',
                boxShadow: '0 0 8px rgba(53,208,127,.6)',
                opacity: clamp01(dq * 2),
                transform: `scale(${dq})`,
              }}
            />
          </div>

          {/* 1px connector line: runs from pill's right edge to badge */}
          <div
            style={{
              position: 'absolute',
              left: TX + PW1,
              top: TY + CH / 2,
              height: 1,
              width: `${(cw * 90).toFixed(1)}px`,
              background: TXT,
            }}
          />

          {/* AI badge (white circular base + four-point star) */}
          <div
            style={{
              position: 'absolute',
              width: BADGE_SIZE,
              height: BADGE_SIZE,
              borderRadius: '50%',
              background: '#fff',
              border: `1px solid ${LINE}`,
              boxSizing: 'border-box',
              boxShadow: '0 2px 10px rgba(0,0,0,.07)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              left: TX + PW1 + 90 - 2,
              top: TY + CH / 2 - 13,
              opacity: bp,
              transform: `scale(${lerp(bp, 0.8, 1)})`,
            }}
          >
            <svg width={BADGE_SVG} height={BADGE_SVG} viewBox="0 0 24 24">
              <path d="M12 0.8 L14.3 9.7 L23.2 12 L14.3 14.3 L12 23.2 L9.7 14.3 L0.8 12 L9.7 9.7 Z" fill={TXT} />
            </svg>
          </div>

          {/* Ending caption: word-by-word darkening (light gray placeholder -> black), line opacity fades in with show */}
          <div
            style={{
              position: 'absolute',
              display: 'flex',
              alignItems: 'baseline',
              whiteSpace: 'nowrap',
              left: TX + PW1 - 18,
              top: TY + CH + 34,
              opacity: capShow,
            }}
          >
            {CAP_WORDS.map((wd, i) => {
              const q = clamp01((capInn - i * CAP_ST) / CAP_WIN);
              return (
                <span
                  key={i}
                  style={{
                    font: `600 13px/1.25 ${SANS}`,
                    color: mix(q, DIM, TXT),
                    letterSpacing: (-0.03 * (1 - q)).toFixed(4) + 'em',
                    marginRight: i === CAP_WORDS.length - 1 ? 0 : 4.5,
                  }}
                >
                  {wd}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </DesignStage>
  );
};
