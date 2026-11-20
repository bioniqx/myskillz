// grain-dissolve — Grain Dissolve -> Condense text granularization and convergence (motion-lab final spec ported to native Remotion)
// The clean text line "{ video-shotcraft. Now Live }" bursts into boiling granular noise (silhouette faintly discernible, white glow),
// accompanied by a selection box featuring 45° hatch lines and pixel-block corner handles; mid-boil, the selection box dismisses,
// and the noise cloud rapidly condenses into a larger granular short wordmark ("video-shotcraft", all lowercase),
// with displacement decaying to zero, glow peaking then settling, solidifying into a crisp luminous wordmark. Four-corner HUD brackets/dots and side tick marks persist throughout.
// Filter chain: feTurbulence frame-by-frame seed + bidirectional displacement scale animation, final wordmark shares filter before releasing.
// Polish upgrades: SVG rasterized at native 1920×1080 (viewBox 640×360, 1 unit = 3px),
// sharpening noise particles down to 2–3px instead of 4x blurred blobs; two-layer cool white bloom ("tight + wide") implemented inside filter chain;
// adds deterministic free-floating sand particles — scattered on granularization, accelerating back into wordmark on condense, extinguishing upon lock;
// wordmark contracts from 1.06 to 1 during condensation ("compressed"), accented by a one-off horizontal streak at the condensation peak.
import React, { useId } from 'react';
import { AbsoluteFill } from 'remotion';
import { E, rand, seg, useT } from '../../_fixtures/Motion';
import { Backdrop, FONT } from '../../_fixtures/Polish';
import { BRAND } from '../../_fixtures/Brand';

export const GRAIN_DISSOLVE_DURATION = 60; // 2000ms @30fps

// Selection box geometry (viewBox coordinates)
const BX = 128;
const BY = 148;
const BW = 384;
const BH = 62;

// 45° hatching: every 34 units starting from BX - BH, bottom-right -> top-left
const HATCH_XS: number[] = [];
for (let x = BX - BH; x < BX + BW; x += 34) HATCH_XS.push(x);

// Free sand particles: spawn across the full text ribbon, settle into short wordmark bounds (deterministic seed)
const SAND = Array.from({ length: 150 }, (_, i) => {
  const r = (k: number) => rand(i * 13.7 + k * 101.3);
  const hx = 140 + r(1) * 360; // Full text ribbon: x 140–500
  const hy = 168 + r(2) * 26; // y 168–194
  const ang = r(3) * Math.PI * 2;
  return {
    hx, hy,
    dx: Math.cos(ang) * (8 + r(4) * 26), // Displacement scattered during granularization
    dy: Math.sin(ang) * (5 + r(5) * 14),
    tx: 140 + r(6) * 360, // Short wordmark bounds (video-shotcraft 44px): x 140–500
    ty: 170 + r(7) * 28, // y 170–198
    size: 0.35 + r(8) * 0.75,
    alpha: 0.25 + r(9) * 0.6,
    lag: r(10) * 0.05, // Staggered attraction start (non-uniform)
    ph: r(11) * Math.PI * 2,
  };
});

// Four-corner pixel checkerboard handles (two 5×5 offset blocks)
const Handle: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g transform={`translate(${x - 5},${y - 5})`} fill="#d6d9e0">
    <rect width={5} height={5} />
    <rect x={5} y={5} width={5} height={5} />
  </g>
);

// HUD bracket corners + dots (sx/sy control orientation)
const Corner: React.FC<{ x: number; y: number; sx: number; sy: number }> = ({ x, y, sx, sy }) => (
  <>
    <path
      d={`M${x + 14 * sx} ${y}H${x}V${y + 14 * sy}`}
      fill="none"
      stroke="#474a55"
      strokeWidth={1.1}
      strokeLinecap="square"
    />
    <circle cx={x + 34 * sx} cy={y + 28 * sy} r={1.3} fill="#7d808b" />
  </>
);

export const GrainDissolve: React.FC = () => {
  const t = useT();
  // Filter / clipPath IDs generated per instance to avoid cross-referencing when multiple instances share a Composition
  // (colons in useId are invalid inside CSS url(), sanitized to alphanumeric)
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const fid = `gd-${uid}`;
  const cid = `gd-${uid}-clip`;
  const sid = `gd-${uid}-streak`;
  const burst = seg(t, 0.13, 0.28, E.outCubic); // Clean text -> granularization
  const cond = seg(t, 0.60, 0.71, E.inOutCubic); // Full noise cloud -> short wordmark cloud
  const lock = seg(t, 0.68, 0.90, E.outCubic); // Displacement decays to lock
  const settle = seg(t, 0.88, 1, E.outCubic); // Glow settles down
  // White glow: subtle during granularization, spikes during condensation, settles to soft glow after lock
  const glow = Math.max(0, burst * 0.3 + cond * 0.7 - settle * 0.45);
  // Selection box: expands horizontally from centerline with burst, dismisses 0.55–0.64 (before condensation finishes)
  const boxOut = seg(t, 0.55, 0.64, E.inCubic);
  const boxOpen = burst * (1 - boxOut * 0.35);
  const boxOp = Math.min(1, burst * 1.4) * (1 - boxOut);
  // Wordmark compaction: 1.06 -> 1 during condensation (converges via lock curve)
  const markScale = 1 + 0.06 * (1 - lock);
  // Horizontal streak: appears once at condensation peak (rises with cond, dims in latter half of lock)
  const streak = cond * (1 - seg(t, 0.74, 0.92, E.outCubic));
  const boil = Math.floor(t * 46); // Boiling rate synchronized with seed

  return (
    <AbsoluteFill style={{ background: '#0a0b0e' }}>
      <Backdrop tone="dark" light={{ x: 0.5, y: 0.47 }} grain={0.07} vignette={0.6} />
      <svg
        viewBox="0 0 640 360"
        width={1920}
        height={1080}
        style={{ position: 'absolute', inset: 0 }}
      >
        <defs>
          <filter id={fid} x="-40%" y="-150%" width="180%" height="400%" colorInterpolationFilters="sRGB">
            <feTurbulence
              type="fractalNoise"
              baseFrequency={0.9 + burst * 0.4}
              numOctaves={2}
              seed={boil}
              result="n"
            />
            <feDisplacementMap
              in="SourceGraphic"
              in2="n"
              scale={burst * 52 * (1 - lock)}
              xChannelSelector="R"
              yChannelSelector="G"
              result="d"
            />
            <feGaussianBlur in="d" stdDeviation={burst * 1.1 * (1 - lock)} result="core" />
            {/* Two-layer bloom: tight glow (edge highlight) + wide glow (air scatter), cool white, tracked by glow envelope */}
            <feGaussianBlur in="core" stdDeviation={1.2 + glow * 1.6} result="g1" />
            <feColorMatrix in="g1" type="matrix" result="g1c"
              values={`0 0 0 0 0.86  0 0 0 0 0.9  0 0 0 0 1  0 0 0 ${(0.15 + glow * 0.95).toFixed(3)} 0`} />
            <feGaussianBlur in="core" stdDeviation={5 + glow * 6} result="g2" />
            <feColorMatrix in="g2" type="matrix" result="g2c"
              values={`0 0 0 0 0.62  0 0 0 0 0.68  0 0 0 0 1  0 0 0 ${(glow * 0.75).toFixed(3)} 0`} />
            <feMerge>
              <feMergeNode in="g2c" />
              <feMergeNode in="g1c" />
              <feMergeNode in="core" />
            </feMerge>
          </filter>
          <linearGradient id={sid} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" stopColor="#9fb0ff" stopOpacity="0" />
            <stop offset="0.5" stopColor="#eef1ff" stopOpacity="1" />
            <stop offset="1" stopColor="#9fb0ff" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Four-corner HUD brackets + dots + side tick marks (persist throughout) */}
        <g>
          <Corner x={88} y={96} sx={1} sy={1} />
          <Corner x={552} y={96} sx={-1} sy={1} />
          <Corner x={88} y={264} sx={1} sy={-1} />
          <Corner x={552} y={264} sx={-1} sy={-1} />
          <line x1={52} y1={180} x2={76} y2={180} stroke="#4c4f5a" strokeWidth={1.1} strokeDasharray="4 3" />
          <line x1={564} y1={180} x2={588} y2={180} stroke="#4c4f5a" strokeWidth={1.1} strokeDasharray="4 3" />
        </g>
        {/* Selection box: unfolds horizontally from centerline during burst, retracts before condensation */}
        {boxOp > 0.002 && (
          <g opacity={boxOp} transform={`translate(320 0) scale(${(0.2 + 0.8 * boxOpen).toFixed(4)} 1) translate(-320 0)`}>
            <clipPath id={cid}>
              <rect x={BX} y={BY} width={BW} height={BH} />
            </clipPath>
            <rect x={BX} y={BY} width={BW} height={BH} fill="rgba(140,150,200,0.035)" />
            <g clipPath={`url(#${cid})`}>
              {HATCH_XS.map((x) => (
                <line key={x} x1={x} y1={BY + BH} x2={x + BH} y2={BY} stroke="#2f313a" strokeWidth={0.8} />
              ))}
            </g>
            <rect x={BX} y={BY} width={BW} height={BH} fill="none" stroke="#5d606c" strokeWidth={0.7} vectorEffect="non-scaling-stroke" />
            <Handle x={BX} y={BY} />
            <Handle x={BX + BW} y={BY} />
            <Handle x={BX} y={BY + BH} />
            <Handle x={BX + BW} y={BY + BH} />
          </g>
        )}
        {/* Horizontal streak: one-off pulse at condensation peak, thin core + wide halo */}
        {streak > 0.002 && (
          <g opacity={streak}>
            <ellipse cx={320} cy={182} rx={250} ry={7} fill={`url(#${sid})`} opacity={0.12} />
            <ellipse cx={320} cy={182} rx={230} ry={0.7} fill={`url(#${sid})`} opacity={0.7} />
          </g>
        )}
        {/* Free sand particles: scatter and boil during burst, accelerate back into wordmark during condensation, extinguish upon lock */}
        <g>
          {SAND.map((s, i) => {
            const pull = seg(t, 0.56 + s.lag, 0.71 + s.lag * 0.4, E.inQuart); // Accelerating pull-back
            const jitter = Math.sin(boil * 1.7 + s.ph) * 1.2 * burst * (1 - pull);
            const sx = s.hx + s.dx * burst;
            const sy = s.hy + s.dy * burst + jitter;
            const x = sx + (s.tx - sx) * pull;
            const y = sy + (s.ty - sy) * pull;
            const a = s.alpha * burst * (1 - seg(t, 0.66, 0.8, E.outCubic)) * (0.55 + 0.45 * Math.abs(Math.sin(boil * 0.9 + s.ph)));
            if (a < 0.01) return null;
            return <circle key={i} cx={x} cy={y} r={s.size * (1 - 0.4 * pull)} fill="#e9ecff" opacity={a} />;
          })}
        </g>
        {/* Text group: full line and final wordmark share filter chain (including bloom) */}
        <g filter={`url(#${fid})`}>
          <text
            x={320}
            y={191}
            textAnchor="middle"
            opacity={1 - cond}
            style={{
              fill: '#eceef3',
              font: `500 26px ${FONT.sans}`, // Brand name is longer than placeholder: size adjusted 33 -> 26 to fit selection box
              letterSpacing: '1.2px',
            }}
          >
            {`{ ${BRAND.name}. Now Live }`}
          </text>
          <text
            x={320}
            y={198}
            textAnchor="middle"
            opacity={cond}
            transform={`translate(320 180) scale(${markScale.toFixed(4)}) translate(-320 -180)`}
            style={{
              fill: '#ffffff',
              font: `750 44px ${BRAND.font}`, // 15-char wordmark: 54 -> 44px, stays within HUD brackets after locking
              letterSpacing: '1.5px',
            }}
          >
            {BRAND.name}
          </text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};
