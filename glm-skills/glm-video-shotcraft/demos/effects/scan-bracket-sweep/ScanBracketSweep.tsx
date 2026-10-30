// scan-bracket-sweep — Scan Bracket Viewfinder Bracket Scanning Band (motion-lab native Remotion port)
// Document springs into screen center, four corners drop L-shaped viewfinder brackets (displacing inward 8px),
// then a scanning light band with directional gradient trail sweeps back and forth across document for 5 passes,
// slow at ends and fast at center, document itself remains completely static.
// Design coordinates 480×270 (DesignStage raster="zoom": small document text rasterized at delivery resolution, crisp).
//
// Polish upgrade: Skeleton grey bars replaced with publication-grade manifest — video-shotcraft launch film storyboard breakdown (title / metadata / 4 cols x 7 rows / total);
// Light band upgraded from "black rule + grey sludge trail" to indigo scanning beam — fine hot core + soft bloom + multiply-blended tint trail,
// trail length dynamically scales with sweep speed (contracts to 0 during terminal turnaround pause, eliminating abrupt direction snapping);
// Table rows illuminated as light band crosses (light reads while document stays motionless); brackets styled with rounded caps and gentle overshoot landing;
// Backdrop features soft vignette + subtle grain, document casts dual drop shadows tightening with landing.
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { Backdrop, EASE, FONT, Grain, softShadow } from '../../_fixtures/Polish';
import { BRAND } from '../../_fixtures/Brand';

export const SCAN_BRACKET_SWEEP_DURATION = 150; // 5000ms @30fps

// —— Colors: INK handles brackets and typography, SCAN is the sole light color (shared across beam core / glow / trail, reskin touches only these two) ——
const INK = '#16171c'; // Cool near-black (replaces pure black)
const SCAN = '91,99,211'; // Indigo scanning beam (rgb components for easy alpha blending)
const INK2 = '#5d5f66';
const INK3 = '#9b9da3';
const HAIR = 'rgba(20,22,28,0.09)';

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const inOutSin = (x: number) => 0.5 - Math.cos(Math.PI * clamp01(x)) / 2;

// Document geometry: 300×178 document centered within 440×240 fixed viewport canvas
const DW = 300;
const DH = 178;
const DX = (440 - DW) / 2;
const DY = (240 - DH) / 2;

// Table columns: 4-column layout adhering to skeleton grid (14px horizontal padding, 10px gutter)
const COLS = 4;
const COL_W = (DW - 28 - (COLS - 1) * 10) / COLS;
const colX = (c: number) => 14 + c * (COL_W + 10);
// Storyboard breakdown: Shot / recipe card / in-point / frame count (in-point = cumulative preceding frames @30fps, total 828f = 27.6 s)
const HEAD = ['Shot', 'Recipe', 'Cue', 'Frames'];
const ROWS: [string, string, string, string][] = [
  ['Cold open', 'Text mask', '0:00', '96 f'],
  ['Hero reveal', 'Spotlight', '0:03', '120 f'],
  ['Feature tour', 'Graze tour', '0:07', '150 f'],
  ['Data beat', 'Riso hit', '0:12', '120 f'],
  ['Workbench', 'Crash zoom', '0:16', '90 f'],
  ['Gallery pass', 'Flyover', '0:19', '144 f'],
  ['Logo sting', 'Brand snap', '0:24', '108 f'],
];
const ROW_TOP = 58; // Row 1 top (consistent with original skeleton 13px line spacing)
const ROW_H = 13;

// Four-corner viewfinder brackets: Outer margin −7, arm length 34 (36 including stroke), 1.6px round-cap L-shapes
const CS = 36;
const CORNERS = [
  { left: -8, top: -8, d: 'M1 35V1h34', dx: 1, dy: 1 },
  { left: DW + 8 - CS, top: -8, d: 'M1 1h34v34', dx: -1, dy: 1 },
  { left: DW + 8 - CS, top: DH + 8 - CS, d: 'M35 1v34H1', dx: -1, dy: -1 },
  { left: -8, top: DH + 8 - CS, d: 'M35 35H1V1', dx: 1, dy: -1 },
];

const PASSES = 5;
const TAIL = 82; // Maximum trail length (at peak velocity)

// Scan position (document y, 0->DH) and direction: Pure function of t, enabling velocity differentiation
const scanAt = (t: number) => {
  const sp = seg(t, 0.17, 0.95, E.linear);
  const raw = sp * PASSES;
  const pi = Math.min(PASSES - 1, Math.floor(raw));
  const local = clamp01((raw - pi) / 0.88); // 12% complete pause at end of each pass
  const dir = pi % 2 === 0 ? 1 : -1;
  const prog = inOutSin(local);
  return { y: dir > 0 ? prog * DH : DH - prog * DH, dir };
};

export const ScanBracketSweep: React.FC = () => {
  const t = useT();
  const dt = 1 / (SCAN_BRACKET_SWEEP_DURATION - 1); // Single frame delta t

  // Document spring-in: scale 0.86->1 (snappy), opacity dp*3 reaches full early — "present" before "settled"
  const dp = seg(t, 0, 0.11, EASE.snappy);
  const elev = lerp(dp, 22, 6);

  // Scan: Position + velocity (trail length tracks speed, collapses to 0 at turnaround pauses)
  const { y, dir } = scanAt(t);
  const speed = Math.abs(scanAt(t + dt / 2).y - scanAt(t - dt / 2).y); // Design px/frame
  const PEAK = (DH * Math.PI) / 2 / (((0.78 * SCAN_BRACKET_SWEEP_DURATION) / PASSES) * 0.88);
  const sNorm = clamp01(speed / PEAK);
  const tail = TAIL * Math.pow(sNorm, 0.75);
  // Light band global fade-in (0.16–0.20) and fade-out (0.93–0.99)
  const clipOp = seg(t, 0.16, 0.2) * (1 - seg(t, 0.93, 0.99));

  // Row illumination: Brightness scales inversely with distance to light core (pure spatial function, document remains stationary)
  const lit = (cy: number) => clipOp * Math.exp(-Math.pow((y - cy) / 7, 2));

  const cell = (txt: string, c: number, top: number, style: React.CSSProperties) => (
    <div
      style={{
        position: 'absolute',
        top,
        left: colX(c),
        width: COL_W,
        textAlign: c === 3 ? 'right' : 'left',
        whiteSpace: 'nowrap',
        lineHeight: 1,
        ...style,
      }}
    >
      {txt}
    </div>
  );

  return (
    <AbsoluteFill>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.3 }} accent="#5b63d3" grain={0} vignette={0.16} />
      <DesignStage bg="transparent" raster="zoom">
        {/* 440×240 fixed canvas, centered in 480×270 design coordinates */}
        <div style={{ position: 'absolute', left: '50%', top: '50%', width: 440, height: 240, margin: '-120px 0 0 -220px' }}>
          {/* holder: Unified positioning container for document + light band + brackets */}
          <div style={{ position: 'absolute', left: DX, top: DY, width: DW, height: DH }}>
            {/* Document card: Hairline stroke + top interior highlight + dual drop shadows tightening with landing */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(180deg, #ffffff 0%, #fcfcfb 100%)',
                borderRadius: 10,
                boxShadow: `inset 0 0 0 0.3px ${HAIR}, inset 0 0.4px 0 rgba(255,255,255,0.9), ${softShadow(elev / 4, { strength: 1.1 })}`,
                overflow: 'hidden',
                transformOrigin: '50% 50%',
                transform: `scale(${lerp(dp, 0.86, 1)})`,
                opacity: clamp01(dp * 3),
                fontFamily: FONT.sans,
                color: INK,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {/* Header: Document icon + title + page count chip */}
              <svg style={{ position: 'absolute', left: 14, top: 10.5 }} width={9} height={11} viewBox="0 0 9 11">
                <path d="M1 .5h4.6L8.5 3.4V10a.5.5 0 0 1-.5.5H1A.5.5 0 0 1 .5 10V1A.5.5 0 0 1 1 .5z" fill="#eef0fb" stroke={`rgb(${SCAN})`} strokeWidth={0.6} />
                <path d="M5.5.6v2.9h2.9" fill="none" stroke={`rgb(${SCAN})`} strokeWidth={0.6} />
              </svg>
              <div style={{ position: 'absolute', left: 27, top: 11, fontSize: 8.6, fontWeight: 650, letterSpacing: '-0.01em', lineHeight: 1 }}>
                Launch Film — Shot List
              </div>
              <div style={{ position: 'absolute', left: 27, top: 23, fontSize: 5.4, color: INK2, lineHeight: 1, letterSpacing: '-0.01em' }}>
                {BRAND.name} · Storyboard v3 · 1080p · 30 fps
              </div>
              <div
                style={{
                  position: 'absolute',
                  right: 14,
                  top: 12,
                  padding: '2px 4.5px',
                  borderRadius: 4,
                  background: '#f3f3f1',
                  boxShadow: `inset 0 0 0 0.3px ${HAIR}`,
                  fontFamily: FONT.mono,
                  fontSize: 4.6,
                  color: INK2,
                  letterSpacing: '0.04em',
                  lineHeight: 1,
                }}
              >
                7 SHOTS · 0:28
              </div>
              <div style={{ position: 'absolute', left: 14, right: 14, top: 36, height: 0.3, background: HAIR }} />

              {/* Table header */}
              {HEAD.map((h, c) =>
                cell(h.toUpperCase(), c, 44, { fontSize: 4.5, fontWeight: 600, color: INK3, letterSpacing: '0.07em' }),
              )}
              <div style={{ position: 'absolute', left: 14, right: 14, top: 52.5, height: 0.3, background: HAIR }} />

              {/* Manifest row: Row subtly illuminates as light core traverses */}
              {ROWS.map((row, r) => {
                const top = ROW_TOP + r * ROW_H;
                const L = lit(top + 3);
                return (
                  <React.Fragment key={r}>
                    <div
                      style={{
                        position: 'absolute',
                        left: 8,
                        right: 8,
                        top: top - 3.5,
                        height: ROW_H - 1,
                        borderRadius: 3,
                        background: `rgba(${SCAN},${(L * 0.09).toFixed(3)})`,
                      }}
                    />
                    {row.map((v, c) =>
                      cell(v, c, top, {
                        fontSize: 5.6,
                        letterSpacing: '-0.012em',
                        fontWeight: c === 0 || c === 3 ? 520 : 420,
                        color: c === 0 || c === 3 ? INK : INK2,
                      }),
                    )}
                  </React.Fragment>
                );
              })}

              {/* Total summary */}
              <div style={{ position: 'absolute', left: 14, right: 14, top: 151, height: 0.3, background: HAIR }} />
              {cell('Runtime', 0, 158, { fontSize: 5.6, fontWeight: 600 })}
              {cell('30 fps', 2, 158, { fontSize: 5.6, color: INK2 })}
              {cell('828 f · 27.6 s', 3, 157.2, { fontSize: 7, fontWeight: 680, letterSpacing: '-0.01em' })}
            </div>

            {/* Scanning light band (clipped inside matching 10px document radius): Fine hot core + soft bloom + directional tint trail */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: 10,
                overflow: 'hidden',
                pointerEvents: 'none',
                opacity: clipOp,
              }}
            >
              <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 0, transform: `translateY(${y.toFixed(3)}px)` }}>
                {/* Trail: Multiply blend tints table beneath; length scales with speed, attached above on downward sweep, below on upward sweep */}
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    height: tail,
                    top: dir > 0 ? -tail : 0,
                    mixBlendMode: 'multiply',
                    background:
                      dir > 0
                        ? `linear-gradient(180deg, rgba(${SCAN},0) 0%, rgba(${SCAN},0.06) 55%, rgba(${SCAN},0.2) 100%)`
                        : `linear-gradient(0deg, rgba(${SCAN},0) 0%, rgba(${SCAN},0.06) 55%, rgba(${SCAN},0.2) 100%)`,
                  }}
                />
                {/* Soft bloom: Symmetrical narrow halo flanking light core */}
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    top: -5,
                    height: 10,
                    background: `linear-gradient(180deg, rgba(${SCAN},0) 0%, rgba(${SCAN},0.22) 50%, rgba(${SCAN},0) 100%)`,
                  }}
                />
                {/* Light core: 1.2px indigo line, boosted to white-hot at center */}
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    right: 0,
                    top: -0.6,
                    height: 1.2,
                    background: `linear-gradient(90deg, rgba(${SCAN},0.55) 0%, rgb(${SCAN}) 18%, #8f95ff 50%, rgb(${SCAN}) 82%, rgba(${SCAN},0.55) 100%)`,
                    boxShadow: `0 0 2.5px rgba(${SCAN},0.75)`,
                  }}
                />
              </div>
            </div>

            {/* Four-corner viewfinder brackets: Staggered entrance, collapsing inward from 8px offset with gentle overshoot */}
            {CORNERS.map((c, i) => {
              const t0 = 0.08 + i * 0.022;
              const a = seg(t, t0, t0 + 0.03); // Opacity arrives first
              const p = EASE.overshoot(clamp01((t - t0) / 0.055)); // Displacement with ~8% overshoot
              const off = (1 - p) * 8;
              return (
                <svg
                  key={i}
                  width={CS}
                  height={CS}
                  viewBox={`0 0 ${CS} ${CS}`}
                  style={{
                    position: 'absolute',
                    left: c.left,
                    top: c.top,
                    overflow: 'visible',
                    opacity: a,
                    transform: `translate(${(-off * c.dx).toFixed(3)}px,${(-off * c.dy).toFixed(3)}px)`,
                  }}
                >
                  <path d={c.d} fill="none" stroke={INK} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              );
            })}
          </div>
        </div>
      </DesignStage>
      <Grain opacity={0.045} />
    </AbsoluteFill>
  );
};
