// bezier-source-converge-merge — Multi-source Bezier curve convergence & merge (ported from motion-lab to native Remotion)
// Four source nodes on the left connect via thin Bezier curves to a single convergence point on the right:
// curves draw on from left to right; nodes glide along their curves toward the convergence point, shrinking in
// three stages (as if swallowed); accent-colored data packets glide continuously along paths; after merging,
// curves erase backward from the left, leaving only the video-shotcraft mark and word-by-word deepened captions.
// Design canvas: 480x270 (DesignStage proportional scaling), 440x240 fixed-size canvas centered.
// Texture layer: soft light background + grain; source nodes rendered as lit white porcelain discs with grayscale linear icons (screenshot / shot card / code / audio);
// Curves use gray-to-ink gradient stroke; data packets are solid accent dots with comet trails; convergence point features video-shotcraft mark (light edition) + reception ripples;
// During erase phase, camera pans to center the emblem, settling into a balanced final composition.
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { Backdrop, EASE, FONT, softShadow } from '../../_fixtures/Polish';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const BEZIER_SOURCE_CONVERGE_MERGE_DURATION = 168; // 5600ms @30fps

// ---- Shared constants (light-gray Swiss minimalist palette, aligned with Phase 0 fixture tokens) ----
const SANS = FONT.sans;
const TXT = '#17181c'; // Primary text near-black (cool-toned)
const DIM = '#c4c6cc'; // Light gray placeholder text
const LINE = 'rgba(20,22,28,0.09)'; // Hairline border
const ACCENT = '#5b63d3'; // Sole accent color (matches fixture G.accent)
const ACCENT_HI = '#7d84ea';

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const h2r = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
// Color interpolation: mix(p, '#C9C9CE', '#111')
const mix = (p: number, a: string, b: string) => {
  const A = h2r(a), B = h2r(b), q = clamp01(p);
  return `rgb(${Math.round(A[0] + (B[0] - A[0]) * q)},${Math.round(A[1] + (B[1] - A[1]) * q)},${Math.round(A[2] + (B[2] - A[2]) * q)})`;
};

const XC = 332, YC = 120; // Convergence point

// Four media sources (grayscale tiered to distinguish tracks): screenshot / shot recipe card / code / audio — merging into a single reel
const SRCS = [
  { y: 36, icon: 'shot', c: '#2a2c33' },
  { y: 92, icon: 'card', c: '#4b4e57' },
  { y: 148, icon: 'code', c: '#6d7079' },
  { y: 204, icon: 'wave', c: '#8f929c' },
];

// Linear icons (24px viewBox)
const ICON: Record<string, React.ReactNode> = {
  // Screenshot: browser window
  shot: (
    <>
      <rect x="3.5" y="5" width="17" height="14" rx="2.4" />
      <path d="M3.5 9h17" />
      <path d="M6.2 7h.01M8.4 7h.01" />
    </>
  ),
  // Shot recipe card: stacked cards
  card: (
    <>
      <rect x="6.5" y="7.5" width="12" height="13" rx="2.2" />
      <path d="M9.5 4.5h7.8c1.2 0 2.2 1 2.2 2.2v9.8" />
      <path d="M9.3 12h6.4M9.3 15.5h4" />
    </>
  ),
  // Code
  code: (
    <>
      <path d="M8.5 7 3.8 12l4.7 5M15.5 7l4.7 5-4.7 5" />
      <path d="M13.2 5.5 10.8 18.5" />
    </>
  ),
  // Audio: sound wave
  wave: <path d="M4 12h.01M7.4 9.2v5.6M10.6 5.8v12.4M13.8 8.4v7.2M17 10.4v3.2M20 12h.01" />,
};

type Pt = { x: number; y: number };

// Cubic Bezier sampling: P0=(74,y0) P1=(186,y0) P2=(214,YC) P3=(XC,YC)
const cubic = (y0: number, u: number): Pt => {
  const v = 1 - u;
  return {
    x: v * v * v * 74 + 3 * v * v * u * 186 + 3 * v * u * u * 214 + u * u * u * XC,
    y: v * v * v * y0 + 3 * v * v * u * y0 + 3 * v * u * u * YC + u * u * u * YC,
  };
};

// Path geometry = straight segment M -22,y L 74,y (fixed length 96) + cubic above. Equivalent to getTotalLength /
// getPointAtLength: cumulative arc length table built for cubic segment (1600 polyline segments, error < 0.01px),
// binary search maps arc length -> parameter u; module-level precomputation, DOM-independent, deterministic rendering.
const SAMPLES = 1600;
const LINE_LEN = 96;
const mkPathGeom = (y0: number) => {
  const cum: number[] = [0];
  let px = 74, py = y0, acc = 0;
  for (let k = 1; k <= SAMPLES; k++) {
    const p = cubic(y0, k / SAMPLES);
    acc += Math.hypot(p.x - px, p.y - py);
    cum.push(acc);
    px = p.x; py = p.y;
  }
  const len = LINE_LEN + acc;
  const pointAt = (s: number): Pt => {
    const sc = Math.max(0, Math.min(len, s));
    if (sc <= LINE_LEN) return { x: -22 + sc, y: y0 };
    const target = sc - LINE_LEN;
    let lo = 0, hi = SAMPLES;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (cum[mid] < target) lo = mid + 1; else hi = mid;
    }
    const i = Math.max(1, lo);
    const s0 = cum[i - 1], s1 = cum[i];
    const u = (i - 1 + (s1 > s0 ? (target - s0) / (s1 - s0) : 0)) / SAMPLES;
    return cubic(y0, u);
  };
  // Node resting position x=74 is precisely the line segment endpoint (arc length 96), calibrated directly as f0 = 96/len —
  // original 40-step scan had 1/40 precision causing resting positions to drift 4-16px and misalign vertically.
  const f0 = LINE_LEN / len;
  return { len, pointAt, f0 };
};

const GEOMS = SRCS.map((s) => mkPathGeom(s.y));

// Ending caption (word-by-word deepening syntax, using show + inn states)
const CAP_WORDS = 'From screenshot to showreel'.split(' ');
const CAP_ST = 0.78 / CAP_WORDS.length;
const CAP_WIN = CAP_ST * 1.5;

// Convergence point: white porcelain disc + video-shotcraft mark (light edition)
const BADGE_SIZE = 46; // Convergence disc diameter (= starting ripple diameter), slightly larger than 44px source nodes
const MARK_SIZE = 34; // Mark viewBox 128 solid shape takes ~81%, 34 -> solid ~28, leaving adequate margin

// Packet comet trail: samples TAIL points backward along path at TAIL_GAP intervals (path ratio), decaying opacity and size
const TAIL = 9;
const TAIL_GAP = 0.0055;

// Final camera pan: shifts canvas left by SHIFT during erase, centering emblem in viewport (canvas left margin 20 + XC = 352 -> 240)
const SHIFT = 352 - 240;

export const BezierSourceConvergeMerge: React.FC = () => {
  const t = useT();
  const conv = seg(t, 0.34, 0.74, E.inOutCubic);            // Main convergence progress
  const erase = seg(t, 0.78, 0.9, E.outQuad);               // Erase from start
  const pkCycle = (seg(t, 0.1, 0.74, E.linear) * 2) % 1;    // Packet cycle (integer period at t=1)
  const pan = seg(t, 0.76, 0.93, EASE.smooth);              // Final centering pan (parallel with erase)

  // Emblem breathing: entrance fade-in + outBack punch and settle upon merge completion
  const bp = seg(t, 0.16, 0.26, E.outCubic);
  const badgeScale = lerp(bp, 0.7, 1) * (1 + seg(t, 0.7, 0.78, E.outBack) * 0.12 - seg(t, 0.78, 0.86, E.outQuad) * 0.12);
  // Reception ripple: single accent ring expands and fades at merge point (0.72)
  const ripple = seg(t, 0.72, 0.86, EASE.out);
  const capShow = seg(t, 0.84, 0.9, EASE.out);
  const capInn = seg(t, 0.84, 0.95);

  return (
    <AbsoluteFill>
      <Backdrop tone="light" light={{ x: 0.62, y: 0.3 }} accent={ACCENT} grain={0.05} vignette={0.12} />
      <DesignStage bg="transparent">
        {/* Page + 440x240 fixed-size canvas (centered) */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            overflow: 'hidden',
            fontFamily: SANS,
            WebkitFontSmoothing: 'antialiased',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              width: 440,
              height: 240,
              margin: '-120px 0 0 -220px',
              transform: `translateX(${(-pan * SHIFT).toFixed(2)}px)`,
            }}
          >
            {/* Four Bezier curves: forward draw-on via dashoffset, reverse erase during erase phase */}
            <svg width={440} height={240} viewBox="0 0 440 240" style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
              <defs>
                {/* Stroke gradient from light gray to near-black: light at source, heavy at convergence to convey flow direction */}
                <linearGradient id="bscm-stroke" gradientUnits="userSpaceOnUse" x1={-22} y1={0} x2={XC} y2={0}>
                  <stop offset="0" stopColor="#b8bac2" />
                  <stop offset="0.45" stopColor="#7c7f89" />
                  <stop offset="1" stopColor="#2a2c33" />
                </linearGradient>
              </defs>
              {SRCS.map((s, i) => {
                const { len } = GEOMS[i];
                const draw = seg(t, 0.04 + i * 0.045, 0.04 + i * 0.045 + 0.17, E.outQuad);
                const off = erase > 0 ? -erase * len : len * (1 - draw);
                return (
                  <path
                    key={i}
                    d={`M -22,${s.y} L 74,${s.y} C 186,${s.y} 214,${YC} ${XC},${YC}`}
                    fill="none"
                    stroke="url(#bscm-stroke)"
                    strokeWidth={0.9}
                    strokeLinecap="round"
                    strokeDasharray={len}
                    strokeDashoffset={off.toFixed(1)}
                    opacity={(draw * (1 - clamp01((erase - 0.85) / 0.15))).toFixed(3)}
                  />
                );
              })}
            </svg>

            {/* Source nodes + packet layer */}
            <div style={{ position: 'absolute', left: 0, top: 0, width: 440, height: 240 }}>
              {SRCS.map((s, i) => {
                const { len, pointAt, f0 } = GEOMS[i];
                // Nodes slide along path to convergence point, shrinking in three stages (44->15->0, as if swallowed)
                const tt = conv;
                const frac = f0 + (1 - f0) * tt;
                const pt = pointAt(len * frac);
                const size = tt < 0.75 ? lerp(tt / 0.75, 44, 15) : lerp((tt - 0.75) / 0.25, 15, 0);
                // Entrance: subtle overshoot pop (≈8%), providing a clean settling beat compared to plain outCubic
                const appear = seg(t, 0.02 + i * 0.04, 0.02 + i * 0.04 + 0.1, EASE.overshoot);
                const appearOp = seg(t, 0.02 + i * 0.04, 0.02 + i * 0.04 + 0.06, EASE.out);
                // Packet (phase-offset, constant size) + comet trail
                const ph = (pkCycle + i * 0.13) % 1;
                const pkOn = seg(t, 0.1, 0.16) * (1 - seg(t, 0.7, 0.76));
                const pkOp = pkOn * (1 - Math.abs(ph - 0.5) * 0.6);
                const k = size / 44; // Node inner elements scaled proportionally
                return (
                  <React.Fragment key={i}>
                    {/* Comet trail: drawn from tail to head, brightest at head */}
                    {pkOp > 0.01 &&
                      Array.from({ length: TAIL }, (_, j) => TAIL - j).map((j) => {
                        const pj = ph - j * TAIL_GAP;
                        if (pj < 0) return null;
                        const q = pointAt(len * (f0 + (1 - f0) * pj));
                        const r = 2.6 * (1 - j / (TAIL + 1));
                        return (
                          <div
                            key={`tail${j}`}
                            style={{
                              position: 'absolute',
                              left: 0,
                              top: 0,
                              width: r * 2,
                              height: r * 2,
                              borderRadius: '50%',
                              background: ACCENT,
                              transform: `translate(${(q.x - r).toFixed(2)}px,${(q.y - r).toFixed(2)}px)`,
                              opacity: (pkOp * 0.38 * (1 - j / (TAIL + 1))).toFixed(3),
                            }}
                          />
                        );
                      })}
                    {pkOp > 0.01 && (() => {
                      const q = pointAt(len * (f0 + (1 - f0) * ph));
                      return (
                        <div
                          style={{
                            position: 'absolute',
                            left: 0,
                            top: 0,
                            width: 6,
                            height: 6,
                            borderRadius: '50%',
                            background: `radial-gradient(circle at 35% 35%, ${ACCENT_HI}, ${ACCENT})`,
                            boxShadow: '0 0 0 1.5px rgba(91,99,211,0.16), 0 1px 3px rgba(91,99,211,0.45)',
                            transform: `translate(${(q.x - 3).toFixed(2)}px,${(q.y - 3).toFixed(2)}px)`,
                            opacity: pkOp.toFixed(3),
                          }}
                        />
                      );
                    })()}
                    {/* Source node: white porcelain disc (top-lit gradient + hairline + inner highlight + dual soft shadows) */}
                    <div
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: 0,
                        borderRadius: '50%',
                        background: 'linear-gradient(180deg, #ffffff 0%, #f6f6f4 100%)',
                        border: `0.5px solid ${LINE}`,
                        boxSizing: 'border-box',
                        boxShadow: `inset 0 0.5px 0 rgba(255,255,255,1), ${softShadow(2 + 4 * k, { strength: 0.8 })}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: s.c,
                        willChange: 'transform',
                        width: Math.max(0.1, size),
                        height: Math.max(0.1, size),
                        transform: `translate(${(pt.x - size / 2).toFixed(2)}px,${(pt.y - size / 2).toFixed(2)}px) scale(${appear.toFixed(3)})`,
                        opacity: (appearOp * (tt > 0.92 ? clamp01((1 - tt) / 0.08) : 1)).toFixed(3),
                      }}
                    >
                      <svg
                        width={Math.max(0.1, size * 0.46)}
                        height={Math.max(0.1, size * 0.46)}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={1.6}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        {ICON[s.icon]}
                      </svg>
                    </div>
                  </React.Fragment>
                );
              })}
            </div>

            {/* Reception ripple: thin accent ring expanding to 2.1x from badge edge and fading out */}
            <div
              style={{
                position: 'absolute',
                left: XC - BADGE_SIZE / 2,
                top: YC - BADGE_SIZE / 2,
                width: BADGE_SIZE,
                height: BADGE_SIZE,
                borderRadius: '50%',
                border: `0.75px solid ${ACCENT}`,
                boxSizing: 'border-box',
                transform: `scale(${lerp(ripple, 1, 2.1)})`,
                opacity: ripple > 0 && ripple < 1 ? (1 - ripple) * 0.55 : 0,
              }}
            />

            {/* Convergence point: white porcelain disc (same material as source nodes, covering curve and packet terminations)
                holding video-shotcraft mark (light edition, mark itself has no gradient/shadow); entrance and reception pulse share badge scale */}
            <div
              style={{
                position: 'absolute',
                width: BADGE_SIZE,
                height: BADGE_SIZE,
                left: XC - BADGE_SIZE / 2,
                top: YC - BADGE_SIZE / 2,
                borderRadius: '50%',
                background: 'linear-gradient(180deg, #ffffff 0%, #f6f6f4 100%)',
                border: `0.5px solid ${LINE}`,
                boxSizing: 'border-box',
                boxShadow: `inset 0 0.5px 0 rgba(255,255,255,1), ${softShadow(8, { strength: 1 })}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: bp,
                transform: `scale(${badgeScale})`,
              }}
            >
              <ShotcraftMark size={MARK_SIZE} tone="light" />
            </div>

            {/* Ending caption: word-by-word deepening (light gray placeholder -> near-black), centered below emblem, floating up with show fade */}
            <div
              style={{
                position: 'absolute',
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'center',
                whiteSpace: 'nowrap',
                left: XC - 120,
                width: 240,
                top: YC + 36,
                opacity: capShow,
                transform: `translateY(${((1 - capShow) * 4).toFixed(2)}px)`,
              }}
            >
              {CAP_WORDS.map((w, i) => {
                const q = clamp01((capInn - i * CAP_ST) / CAP_WIN);
                return (
                  <span
                    key={i}
                    style={{
                      font: `600 13px/1.25 ${SANS}`,
                      color: mix(q, DIM, TXT),
                      letterSpacing: (-0.012 - 0.02 * (1 - q)).toFixed(4) + 'em',
                      marginRight: i === CAP_WORDS.length - 1 ? 0 : 4,
                    }}
                  >
                    {w}
                  </span>
                );
              })}
            </div>
          </div>
        </div>
      </DesignStage>
    </AbsoluteFill>
  );
};
