// deck-deal-flyin —— Deck closeup orbit → Anticipation → Stack deals into grid with hard acceleration → Camera rises tracking deals → Full-board freeze (Round 2 redesign)
// Core motif retained: physical deck (authentic card slices) closeup orbit opener, followed by anticipation beat where 26 cards deal into the page grid in reading order with hard acceleration;
// camera tracks the deals, locking in after the board is filled.
//
// Design decisions
// - look = graphite (near-monochrome dark field · white accents · touch of champagne gold). The entire shot takes place on a dark brushed graphite tabletop:
//   the deck sits on the desk to the right of the page board (real projects screenshot, Q1 texture retained), illuminated by a single top spotlight;
//   as the camera pulls out, the spotlight expands from the deck to the page board (soft-edged circle of light revealing the board from dark to bright);
//   the page board appears as a white display board set on the desk, surrounded continuously by a dark field—
//   no longer snapping the full screen to white paper; dark/bright contrast sustains through the final frame.
// - Camera: single continuous monotonic Hermite spline (continuous velocity at keyframes, zero hitching) — low-angle oblique orbit around deck → zoom-out facing top of board →
//   tracking accelerating cards down the board while elevating and pitching back → landing on a "runway" bird's-eye view: the board stretches diagonally into the distance,
//   all 26 cards framed in perspective (scale of full board instantly readable). Bird's-eye position maintains a subtle 1.5% push-in.
// - Depth of field: distant end in bird's-eye view (top of board) dimmed + reduced contrast, foreground brightest — light follows final cards into the foreground.
// - Typography: after board fills, lower-left reveals two-line headline "Your product, / in motion." (video-shotcraft tagline, 120px 800/300 weight contrast) + mono counter
//   "video-shotcraft mark · 26 REAL PAGE CAPTURES" — counter increments with landed cards during dealing (26 cards = 26).
//
// Timeline (30fps, 150f total)
//   0–28    orbit: low-angle oblique orbit around deck (rotY −30°→+26°), top spotlight on deck only, board dark
//   26–36   Anticipation: entire deck depresses 48px, top card pulls back 30px against deal direction (surpasses perceptual threshold)
//   36–~101 Dealing: card k cue = 36 + 4k − 0.0792·k(k−1) (interval 4f → 0.2f hard acceleration),
//           per card 8f dive (z-arc apex + peak 1.06x) + 4f overshoot landing + 2f press; flight motion blur
//   34–62   Zoom out: board light circle illuminates, camera faces top of board
//   62–108  Track + Rise: camera tracks down board, ascends, tilts back, banks → runway bird's-eye perspective
//   100–126 Headline rises word-by-word, counter freezes
//   108–150 Hold: full-board rest (> 0.5s), very slow push-in + light breathing
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { EASE, FONT, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import layout from '../../_textures/live-layout.json';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const DECK_DEAL_FLYIN_DURATION = 150;

const L = LOOKS.graphite;
const cards = layout.projects.cards;
const PAGE_H = layout.projects.pageH;
const PAPER = '#f9f6f1';

// Page board: content area only (margins left/right), paper extended below to fit 16 overflow cards
const BOARD = { x: 352, w: 1216 };
const COLS = [408, 781.328125, 1154.65625];
const CARD_W = 357.328125;
const EXTRA_ROWS = [1795, 2188, 2581, 2974, 3367];
const BOARD_H = PAGE_H + 2036;

const extras = Array.from({ length: 16 }, (_, i) => ({
  file: `card${((i * 3 + 2) % 10) + 1}.png`,
  x: i === 0 ? COLS[2] : COLS[(i - 1) % 3],
  y: i === 0 ? 1402 : EXTRA_ROWS[Math.floor((i - 1) / 3)],
  w: CARD_W,
  h: 312,
}));

// Deck: placed on tabletop to the right of board (page coordinates)
const PILE = { x: 1640, y: 250 };
const N_CARDS = 26;
const DEAL_START = 36;
const STACK_STEP = 3;
const PILE_CX = PILE.x + CARD_W / 2;
const PILE_CY = PILE.y + 156;

const grid = [...cards.map((c) => ({ file: c.file, x: c.x, y: c.y, w: c.w, h: c.h })), ...extras]
  .sort((a, b) => a.y - b.y || a.x - b.x)
  .map((c, k) => ({
    ...c,
    cue: DEAL_START + 4 * k - 0.0792 * k * (k - 1),
    px: PILE.x + (((k * 7) % 9) - 4) * 2,
    py: PILE.y + (((k * 5) % 7) - 3) * 2,
    protZ: ((k * 11) % 7) - 3,
    pz: (N_CARDS - k) * STACK_STEP,
  }));

const HOVER_H = 40;
const SETTLE_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);
const DIVE_EASE = Easing.bezier(0.3, 0, 0.2, 1);
const ANTICIPATE = { from: 26, to: 36, pileDown: 48, topPull: 30 };

// ───────────── Camera: Monotonic cubic Hermite spline (parameters interpolate anchors with continuous velocity) ─────────────
type Cam = { cx: number; cy: number; zoom: number; rotX: number; rotY: number; rotZ: number; persp: number; sx: number };
type Key = Cam & { frame: number };
const ANCHORS: Key[] = [
  { frame: 0, cx: PILE_CX - 40, cy: PILE_CY + 60, zoom: 1.9, rotX: 48, rotY: -30, rotZ: 9, persp: 1100, sx: 0 },
  { frame: 30, cx: PILE_CX + 20, cy: PILE_CY + 40, zoom: 1.8, rotX: 42, rotY: 24, rotZ: -6, persp: 1100, sx: 0 },
  { frame: 62, cx: 1080, cy: 760, zoom: 0.8, rotX: 22, rotY: 0, rotZ: 2, persp: 1700, sx: 0 },
  { frame: 86, cx: 980, cy: 1720, zoom: 0.56, rotX: 38, rotY: -4, rotZ: -10, persp: 2500, sx: 120 },
  { frame: 110, cx: 960, cy: 2150, zoom: 0.5, rotX: 52, rotY: -6, rotZ: -26, persp: 3300, sx: 300 },
  { frame: 150, cx: 960, cy: 2160, zoom: 0.508, rotX: 52, rotY: -6, rotZ: -26, persp: 3300, sx: 300 },
];
const PARAMS: (keyof Cam)[] = ['cx', 'cy', 'zoom', 'rotX', 'rotY', 'rotZ', 'persp', 'sx'];
const hermite = (xs: number[], ys: number[]) => {
  const n = xs.length;
  const d = xs.slice(0, -1).map((x, i) => (ys[i + 1] - ys[i]) / (xs[i + 1] - x));
  const m = xs.map((_, i) => (i === 0 ? d[0] : i === n - 1 ? 0 : d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2));
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); m[i] = k * a * d[i]; m[i + 1] = k * b * d[i]; }
  }
  return (x: number) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = 0;
    while (i < n - 2 && x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i];
    const t = (x - xs[i]) / h;
    const t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1];
  };
};
const CURVES = Object.fromEntries(PARAMS.map((p) => [p, hermite(ANCHORS.map((k) => k.frame), ANCHORS.map((k) => k[p]))])) as Record<keyof Cam, (x: number) => number>;
const camAt = (f: number): Cam => Object.fromEntries(PARAMS.map((p) => [p, CURVES[p](f)])) as Cam;

// ------------- Brushed graphite desk texture (deterministic feTurbulence: x low-freq / y high-freq = horizontal brush) -------------
const BRUSH_TILE = (() => {
  const svg =
    `<svg xmlns='http://www.w3.org/2000/svg' width='640' height='640'>` +
    `<filter id='b' x='0' y='0' width='100%' height='100%' color-interpolation-filters='sRGB'>` +
    `<feTurbulence type='fractalNoise' baseFrequency='0.0018 0.62' numOctaves='3' seed='11' stitchTiles='stitch'/>` +
    `<feColorMatrix type='matrix' values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0.4 0.4 0.4 0 -0.5'/>` +
    `</filter><rect width='100%' height='100%' filter='url(#b)'/></svg>`;
  return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}")`;
})();

const T = 4000; // Desk plane margin (page coordinates) preventing edge visibility at oblique angles

export const DeckDealFlyin: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(frame);

  // Board illumination: f34->64 soft radial vignette centered at deck illuminates board
  const lightUp = interpolate(frame, [34, 64], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.5, 0, 0.6, 1) });
  const holeR = 4200 * lightUp;
  const feather = 600 + 1000 * lightUp;
  // Overhead depth of field: far edge darkened
  const fog = ramp(frame, 80, 34, EASE.smooth);

  // Anticipation beat
  const antT = interpolate(frame, [ANTICIPATE.from, ANTICIPATE.to], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad) });

  // Counter: number of landed cards
  const landed = grid.filter((c) => frame >= c.cue + 8).length;
  const statIn = ramp(frame, 90, 12, EASE.out);

  const tableBg = [
    // Top light: focuses on deck initially, expands as camera pulls back to light entire board
    `radial-gradient(${1100 + 1400 * lightUp}px ${800 + 1600 * lightUp}px at ${T + PILE_CX - 600 * lightUp}px ${T + PILE_CY + 900 * lightUp}px, rgba(235,232,224,${0.2 - 0.08 * lightUp}), rgba(220,216,206,0.05) 45%, transparent 70%)`,
    // Wide specular highlight streak
    `linear-gradient(104deg, transparent ${T + PILE_CX - 1600}px, rgba(220,226,236,0.07) ${T + PILE_CX - 500}px, rgba(240,244,252,0.11) ${T + PILE_CX}px, rgba(220,226,236,0.05) ${T + PILE_CX + 600}px, transparent ${T + PILE_CX + 1800}px)`,
    `${BRUSH_TILE} 0 0 / 640px 640px repeat`,
    'linear-gradient(115deg, #1b1c1f 0%, #24262a 30%, #18191c 56%, #202226 80%, #141518 100%)',
  ].join(', ');

  const persp = cam.persp * cam.zoom;

  return (
    <AbsoluteFill style={{ fontFamily: FONT.sans, overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.6, y: 0.2 }} fill={null} intensity={0.5} grain={0} vignette={0} />

      {/* 3D Camera (PageCam2D coordinate math: CSS zoom for magnification, native text rasterization) */}
      <AbsoluteFill style={{ transform: `translateX(${cam.sx.toFixed(2)}px)` }}>
        <div style={{ position: 'absolute', inset: 0, perspective: `${persp.toFixed(2)}px`, perspectiveOrigin: '960px 540px' }}>
          <div
            style={{
              position: 'absolute', width: 1920, height: BOARD_H, zoom: cam.zoom,
              transform: `translate(${(960 / cam.zoom - cam.cx).toFixed(3)}px, ${(540 / cam.zoom - cam.cy).toFixed(3)}px) rotateY(${cam.rotY.toFixed(3)}deg) rotateX(${cam.rotX.toFixed(3)}deg) rotateZ(${cam.rotZ.toFixed(3)}deg)`,
              transformOrigin: `${cam.cx.toFixed(2)}px ${cam.cy.toFixed(2)}px`,
              transformStyle: 'preserve-3d',
            }}
          >
            {/* Graphite desk: distant soft edges fade into dark field */}
            <div
              style={{
                position: 'absolute', left: -T, top: -T, width: 1920 + 2 * T, height: BOARD_H + 2 * T, background: tableBg,
                WebkitMaskImage: `radial-gradient(ellipse ${2600}px ${3600}px at ${T + 960}px ${T + BOARD_H / 2}px, #000 40%, transparent 100%)`,
                maskImage: `radial-gradient(ellipse ${2600}px ${3600}px at ${T + 960}px ${T + BOARD_H / 2}px, #000 40%, transparent 100%)`,
              }}
            />

            {/* Page board: screenshot + paper extension; deep drop shadow on desk + top edge highlight */}
            <div
              style={{
                position: 'absolute', left: BOARD.x, top: 0, width: BOARD.w, height: BOARD_H, overflow: 'hidden', borderRadius: 18,
                background: PAPER,
                boxShadow: '0 0 0 1px rgba(255,255,255,0.08), 0 60px 160px rgba(0,0,0,0.7), 0 12px 40px rgba(0,0,0,0.5)',
              }}
            >
              <Img src={staticFile('textures/live/projects-empty.png')} style={{ position: 'absolute', left: -BOARD.x, top: 0, width: 1920, height: PAGE_H }} />
              {/* Section label on extended paper (uppercase tracking + count) */}
              <div style={{ position: 'absolute', left: 408 - BOARD.x, top: PAGE_H + 6, width: 1104, height: 1, background: 'rgba(60,45,30,0.08)' }} />
              {/* Board dark layer: board starts in dark, radial light illuminates outward from deck */}
              {lightUp < 1 && (
                <div
                  style={{
                    position: 'absolute', inset: 0, background: 'rgba(14,14,16,0.88)',
                    WebkitMaskImage: lightUp > 0 ? `radial-gradient(circle at ${PILE_CX - BOARD.x}px ${PILE_CY}px, transparent ${holeR.toFixed(0)}px, #000 ${(holeR + feather).toFixed(0)}px)` : undefined,
                    maskImage: lightUp > 0 ? `radial-gradient(circle at ${PILE_CX - BOARD.x}px ${PILE_CY}px, transparent ${holeR.toFixed(0)}px, #000 ${(holeR + feather).toFixed(0)}px)` : undefined,
                  }}
                />
              )}
            </div>

            {/* 26 Cards: deck on right desk surface, dealt sequentially into grid with accelerated rhythm */}
            {grid.map((c, i) => {
              const { cue } = c;
              const diveT = interpolate(frame, [cue, cue + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: DIVE_EASE });
              const settleT = interpolate(frame, [cue + 8, cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SETTLE_EASE });
              const dx = (c.px - c.x) * (1 - diveT);
              const dy = (c.py - c.y) * (1 - diveT);
              const rotFlight = c.protZ * (1 - diveT);
              const arc = Math.sin(diveT * Math.PI) * 110;
              const zDive = interpolate(diveT, [0, 1], [c.pz, HOVER_H]) + arc;
              const z = frame < cue ? c.pz : zDive * (1 - settleT);
              const dealScale = 1 + Math.sin(diveT * Math.PI) * 0.06;
              const press = interpolate(frame, [cue + 10, cue + 11, cue + 12], [1, 0.996, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
              const scale = dealScale * press;
              const isLanded = frame >= cue + 12;
              const inPile = frame < cue;
              const antDy = inPile ? ANTICIPATE.pileDown * antT * (frame < ANTICIPATE.to + 2 ? 1 : 0) : 0;
              const antPull = i === 0 && inPile ? ANTICIPATE.topPull * antT : 0;
              const transform = isLanded
                ? 'translate3d(0px, 0px, 0px)'
                : inPile
                  ? `translate3d(${c.px - c.x - antPull}px, ${c.py - c.y + antDy}px, ${c.pz}px) rotateZ(${c.protZ}deg)`
                  : `translate3d(${dx}px, ${dy}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`;
              // Shadow: deep shadow at rest on desk; tall and diffuse during flight; converges to resting shadow on landing (~3f lag)
              const shadowLag = interpolate(frame, [cue + 8, cue + 15], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASE.out });
              const shadow = isLanded
                ? `0 ${(2 + 14 * (1 - shadowLag)).toFixed(1)}px ${(6 + 30 * (1 - shadowLag)).toFixed(1)}px rgba(40,30,20,${(0.1 + 0.12 * (1 - shadowLag)).toFixed(3)})`
                : inPile
                  ? i === N_CARDS - 1
                    ? '0 1px 3px rgba(0,0,0,.4), 0 26px 60px rgba(0,0,0,0.75)'
                    : '0 1px 2px rgba(0,0,0,.35)'
                  : `0 ${36 - 24 * settleT}px ${70 - 50 * settleT}px rgba(0,0,0,${(0.45 - 0.25 * settleT).toFixed(3)})`;
              const showGhost = diveT > 0.02 && diveT < 0.98;
              const gx = (c.px - c.x) * 0.06;
              const gy = (c.py - c.y) * 0.06;
              // Deck cards have subtle shadow in stack, recovers as light expands
              // Cards landing in unlit board areas remain in shadow (matching board illumination formula)
              const dist = Math.hypot(c.x + c.w / 2 - PILE_CX, c.y + c.h / 2 - PILE_CY);
              const dark = Math.min(1, Math.max(0, (dist - holeR) / feather)) * 0.88 * (lightUp < 1 ? 1 : 0);
              const pileShade = inPile ? 0.08 * (1 - lightUp) : diveT > 0.6 ? dark * Math.min(1, (diveT - 0.6) / 0.4) : 0;
              return (
                <div key={`${c.file}-${i}`} style={{ transformStyle: 'preserve-3d' }}>
                  {showGhost ? (
                    <div
                      style={{
                        position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h,
                        transform: `translate3d(${dx + gx}px, ${dy + gy}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`,
                        opacity: 0.28 * (1 - diveT), filter: 'blur(7px)', borderRadius: 16, overflow: 'hidden',
                      }}
                    >
                      <Img src={staticFile(`textures/live/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
                    </div>
                  ) : null}
                  <div
                    style={{
                      position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h,
                      transform, boxShadow: shadow, borderRadius: 16, overflow: 'hidden',
                    }}
                  >
                    <Img src={staticFile(`textures/live/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
                    {pileShade > 0.005 && <div style={{ position: 'absolute', inset: 0, background: `rgba(10,10,12,${pileShade.toFixed(3)})` }} />}
                  </div>
                </div>
              );
            })}

            {fog > 0 && (
              <div
                style={{
                  position: 'absolute', left: BOARD.x - 2, top: -2, width: BOARD.w + 4, height: BOARD_H + 4, pointerEvents: 'none', borderRadius: 18,
                  transform: 'translateZ(1px)',
                  background: `linear-gradient(180deg, rgba(12,12,14,${(0.62 * fog).toFixed(3)}) 0%, rgba(12,12,14,${(0.3 * fog).toFixed(3)}) 35%, rgba(12,12,14,0) 70%)`,
                }}
              />
            )}
          </div>
        </div>
      </AbsoluteFill>

      {/* Vignette + grain (screen space, full duration) */}
      <AbsoluteFill style={{ pointerEvents: 'none', background: `radial-gradient(ellipse 75% 75% at 58% 46%, transparent 45%, ${alpha('#050506', 0.55)} 100%)` }} />

      {/* Bottom-left: title + counter row */}
      <div style={{ position: 'absolute', left: 120, top: 664, color: L.ink }}>
        <div style={{ ...type(120, 800) }}>
          <TextReveal text="Your product," by="word" variant="rise" start={100} each={16} gap={4} />
        </div>
        <div style={{ ...type(120, 300), color: L.ink2, marginTop: 4 }}>
          <TextReveal text="in motion." by="word" variant="rise" start={106} each={16} gap={4} />
        </div>
      </div>
      <div
        style={{
          position: 'absolute', left: 124, top: 610, display: 'flex', alignItems: 'center', gap: 16, opacity: statIn,
          ...type(30, 600, { mono: true }), letterSpacing: '0.14em', color: L.ink2,
        }}
      >
        {/* video-shotcraft logo (reversed white on dark, no bloom) */}
        <ShotcraftMark size={34} tone="dark" style={{ margin: '-6px 0' }} />
        <span style={{ color: L.ink, fontVariantNumeric: 'tabular-nums', minWidth: '2.2ch' }}>{String(landed).padStart(2, '0')}</span>
        REAL PAGE CAPTURES
      </div>
    </AbsoluteFill>
  );
};
