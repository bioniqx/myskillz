// neon-frame-forerun — Neon frame forerun: frame traces out both ways from left midpoint to define bounds -> page brightens from dark -> components land staggered from 3D space with soft shadows
// -> background neon echoes extinguish at the end to give way.
//
// Redesign v2 (Aurora - workspace dashboard inside neon tunnel):
// - look = aurora (violet-pink night). Neon frame is a violet-to-pink gradient "tube": 4-layer stroke stack builds glow (wide soft halo / mid halo / color core / hot white core);
//   two hot-white runner heads depart from left midpoint, accelerate-decelerate along top and bottom paths, colliding with a flash at the right midpoint.
// - Background is no longer random tilted frames: it consists of 7 depth echoes of the same frame (translateZ recession, scaling up per layer), forming a neon tunnel leading to the page —
//   once the frame closes, the tunnel ignites layer-by-layer near-to-far (deterministic fluorescent tube strike flicker); final phase extinguishes mid-tunnel first then outward, yielding brightness to the hero.
// - Page is a camera-tailored video-shotcraft dashboard: brand / 4 nav items / 64px greeting / 3 stat cards / 4 shot tasks, font size >= 30px.
//   Components truly hover in 3D (preserve-3d + translateZ 110-170px), casting matching soft shadows on the panel (higher = larger, blurrier, softer),
//   landing staggered from sidebar top-down -> main area top-down; landing progress syncs with page illumination, concluding ~20f later.
// - Camera: starts at high perspective tilt (rotateY -30°), softens to -12° as page lights up (EASE.out long deceleration), continuing a gentle 1.5° drift during hold.
//
// Timeline (30fps, 140f total):
//   0–2     Prep: dark field + bright dot at left midpoint
//   2–22    Frame trace 20f (swift: fast start, brake and collide at right midpoint), collision flash at 22
//   20–44   Tunnel echoes strike layer-by-layer near to far
//   24–84   Page brightens from dark (lit, smooth)
//   30–104  Component landing: each 24f accelerated drop + soft landing, landing frames 54->104 staggered (dense to sparse)
//   0–96    Camera settling (EASE.out); 96–140 gentle drift
//   92–124  Tunnel extinguishes from middle to ends; frame core narrows to hairline, frame glow merges into panel rim
//   124–140 hold
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, bezier, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const NEON_FRAME_FORERUN_DURATION = 140;

const L = LOOKS.aurora;
const NEON_A = '#b48cff'; // Tube violet
const NEON_B = '#ff6fb5'; // Tube pink

// In-page palette (light UI set against dark neon backdrop to maximize illumination contrast)
const INK = '#17141f', INK2 = '#5a5568', INK3 = '#9a95a8';
const HAIR = 'rgba(30,20,50,0.09)';
const ACC = '#7c5cf0';

const PW = 1440;
const PH = 840;
const PAD = 22; // Neon frame offset from panel
const PERSP = 1600;

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const easeFall = bezier(0.55, 0, 0.75, 0.95); // Accelerated fall with slight deceleration at end (soft landing)

// ───────────── Floating element: genuine 3D elevation + matching soft shadow on panel ─────────────
// h = height from panel (px, translateZ); lit = page brightness (brightness on leaf nodes to preserve parent 3D)
const Float: React.FC<{ x: number; y: number; w: number; h: number; lit: number; vis: number; children: React.ReactNode }> = ({ x, y, w, h, lit, vis, children }) => (
  <div style={{ position: 'absolute', left: x, top: y, width: w, transformStyle: 'preserve-3d' }}>
    {h > 0.5 && (
      <div style={{
        position: 'absolute', left: 0, top: 0, width: w,
        // Key light top-left: shadow offsets bottom-right; greater height yields further offset, larger blur, and lighter opacity
        transform: `translate3d(${(h * 0.34).toFixed(2)}px, ${(h * 0.5).toFixed(2)}px, 0.5px) scale(${(1 + h * 0.0011).toFixed(4)})`,
        filter: `brightness(0) blur(${(2 + h * 0.12).toFixed(2)}px)`,
        opacity: (0.42 - h * 0.0016) * lit * vis, pointerEvents: 'none',
      }}>{children}</div>
    )}
    <div style={{ transform: `translateZ(${(h + 1).toFixed(2)}px)`, opacity: vis, filter: lit < 0.995 ? `brightness(${Math.max(0.04, lit).toFixed(3)})` : undefined }}>
      {children}
    </div>
  </div>
);

// ───────────── Page components ─────────────
const Icon: React.FC<{ k: number; c: string; s?: number }> = ({ k, c, s = 30 }) => {
  const p = { fill: 'none', stroke: c, strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg width={s} height={s} viewBox="0 0 20 20">
      {k === 0 && <path d="M3.5 9 L10 3.5 L16.5 9 V16.5 H3.5 Z M8 16.5 V12 H12 V16.5" {...p} />}
      {k === 1 && <path d="M3 11 L5.2 4.5 H14.8 L17 11 V16 H3 Z M3 11 H7.2 L8.3 12.8 H11.7 L12.8 11 H17" {...p} />}
      {k === 2 && <><circle cx={10} cy={10} r={7} {...p} /><path d="M7 10.2 L9.2 12.4 L13.2 8" {...p} /></>}
      {k === 3 && <><circle cx={10} cy={10} r={7} {...p} /><circle cx={10} cy={10} r={3} {...p} /></>}
    </svg>
  );
};

const NAV = ['Home', 'Inbox', 'My shots', 'Renders'];
const STATS: [string, string, string][] = [['Shots today', '6', '2 to tune'], ['Rendering', '3', 'Avg. 4m'], ['Films this week', '24', '+38%']];
const TASKS: [string, string, string, string][] = [
  ['Add shot: crash zoom', '#e5484d', 'Today', 'DW'],
  ['Sync cuts to the beat', '#f5a524', 'In progress', 'MK'],
  ['Capture the pricing page', '#e5484d', 'Blocked', 'JS'],
  ['Render launch film', '#7c5cf0', 'Fri', 'AL'],
];

type Part = { key: string; x: number; y: number; w: number; land: number; H: number; node: React.ReactNode };

// Landing keyframe (0..1 normalized to landing window): sidebar top-down -> main area top-down, dense to sparse
const PARTS: Part[] = (() => {
  const parts: Part[] = [];
  parts.push({
    key: 'brand', x: 40, y: 44, w: 280, land: 0.0, H: 150, node: (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* Brand: mark (light edition) + video-shotcraft wordmark */}
        <ShotcraftMark size={48} tone="light" />
        <div style={{ fontFamily: BRAND.font, fontSize: 25, fontWeight: 700, color: INK, letterSpacing: '0.01em', whiteSpace: 'nowrap' }}>{BRAND.name}</div>
      </div>
    ),
  });
  NAV.forEach((n, i) => parts.push({
    key: `nav${i}`, x: 28, y: 160 + i * 76, w: 270, land: 0.08 + i * 0.06, H: 130, node: (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16, height: 62, padding: '0 18px', borderRadius: 14,
        background: i === 0 ? '#ffffff' : 'transparent', boxShadow: i === 0 ? `0 0 0 1px ${HAIR}, 0 2px 6px rgba(30,20,60,0.06)` : undefined,
      }}>
        <Icon k={i} c={i === 0 ? ACC : INK2} />
        <div style={{ fontSize: 31, fontWeight: i === 0 ? 650 : 500, color: i === 0 ? INK : INK2, letterSpacing: '-0.01em' }}>{n}</div>
        {i === 1 && <div style={{ marginLeft: 'auto', fontSize: 22, fontWeight: 700, color: '#fff', background: ACC, borderRadius: 13, padding: '3px 11px', fontVariantNumeric: 'tabular-nums' }}>4</div>}
      </div>
    ),
  }));
  parts.push({
    key: 'hello', x: 384, y: 52, w: 960, land: 0.04, H: 170, node: (
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 26 }}>
        <div style={{ fontSize: 66, fontWeight: 750, color: INK, letterSpacing: '-0.035em' }}>Good morning, Dana</div>
        <div style={{ fontSize: 30, color: INK3, fontWeight: 500 }}>Tue, Oct 14</div>
      </div>
    ),
  });
  STATS.forEach(([label, v, sub], i) => parts.push({
    key: `stat${i}`, x: 384 + i * 334, y: 176, w: 310, land: 0.2 + i * 0.07, H: 160, node: (
      <div style={{
        height: 188, borderRadius: 22, background: '#ffffff', padding: '24px 28px', boxSizing: 'border-box',
        boxShadow: `0 0 0 1px ${HAIR}, 0 1px 2px rgba(30,20,60,0.05), 0 10px 24px -14px rgba(30,20,60,0.18)`,
      }}>
        <div style={{ fontSize: 26, fontWeight: 550, color: INK2 }}>{label}</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 10 }}>
          <div style={{ fontSize: 84, fontWeight: 750, color: i === 2 ? ACC : INK, letterSpacing: '-0.04em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
          <div style={{ fontSize: 24, fontWeight: 600, color: i === 0 ? '#d93f44' : INK3 }}>{sub}</div>
        </div>
      </div>
    ),
  }));
  parts.push({
    key: 'today', x: 388, y: 404, w: 400, land: 0.42, H: 120, node: (
      <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: '0.14em', color: INK3 }}>TODAY</div>
    ),
  });
  TASKS.forEach(([t, c, status, who], i) => parts.push({
    key: `task${i}`, x: 384, y: 450 + i * 88, w: 978, land: 0.5 + i * 0.12, H: 140, node: (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 22, height: 74, padding: '0 24px', borderRadius: 16, background: '#ffffff',
        boxShadow: `0 0 0 1px ${HAIR}, 0 1px 2px rgba(30,20,60,0.05)`,
      }}>
        <div style={{ width: 26, height: 26, borderRadius: 13, boxShadow: `inset 0 0 0 3px ${c}`, flex: 'none' }} />
        <div style={{ fontSize: 32, fontWeight: 550, color: INK, letterSpacing: '-0.015em' }}>{t}</div>
        <div style={{
          marginLeft: 'auto', fontSize: 24, fontWeight: 650, borderRadius: 10, padding: '5px 14px',
          color: status === 'Blocked' ? '#c2353b' : status === 'Today' ? ACC : INK2,
          background: status === 'Blocked' ? '#fde8e8' : status === 'Today' ? '#efeaff' : '#f1eff4',
        }}>{status}</div>
        <div style={{ width: 44, height: 44, borderRadius: 22, background: ['#e9e3ff', '#ffe6f1', '#e3f0ff', '#fff0dc'][i], color: '#4b4560', fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{who}</div>
      </div>
    ),
  }));
  return parts;
})();

// ───────────── Neon frame geometry ─────────────
const FW = PW + PAD * 2;
const FH = PH + PAD * 2;
// Starts from left midpoint, moves upward clockwise full loop
const FRAME_D = `M 0 ${FH / 2} L 0 0 L ${FW} 0 L ${FW} ${FH} L 0 ${FH} Z`;
const PERIM = 2 * (FW + FH);
// Perimeter fraction u (clockwise from left midpoint) -> coordinates
const pointAt = (u: number): [number, number] => {
  let s = (((u % 1) + 1) % 1) * PERIM;
  const segs: [number, number, number, number][] = [[0, FH / 2, 0, 0], [0, 0, FW, 0], [FW, 0, FW, FH], [FW, FH, 0, FH], [0, FH, 0, FH / 2]];
  for (const [x1, y1, x2, y2] of segs) {
    const len = Math.hypot(x2 - x1, y2 - y1);
    if (s <= len) return [x1 + ((x2 - x1) * s) / len, y1 + ((y2 - y1) * s) / len];
    s -= len;
  }
  return [0, FH / 2];
};

// Deterministic fluorescent tube ignition / extinguish flicker: t = frames from trigger
const STRIKE = [0, 0.7, 0.15, 0.9, 0.35, 1];
const strike = (f: number, on: number) => (f < on ? 0 : f - on >= STRIKE.length ? 1 : STRIKE[Math.floor(f - on)]);
const FADE = [1, 0.3, 0.8, 0.12, 0.4, 0];
const quench = (f: number, off: number) => (f < off ? 1 : f - off >= FADE.length ? 0 : FADE[Math.floor(f - off)]);

// Tube: 4-layer stroke (wide soft halo / mid halo / color core / hot white core), avoids filters for cheap and crisp rendering
const Tube: React.FC<{ d: string; grad: string; dash?: string; offset?: number; a: number; core?: number; w?: number }> = ({ d, grad, dash, offset, a, core = 1, w = 1 }) => (
  <g fill="none" strokeLinejoin="miter" strokeDasharray={dash} strokeDashoffset={offset}>
    <path d={d} pathLength={dash ? 1000 : undefined} stroke={grad} strokeWidth={34 * w} opacity={0.07 * a} />
    <path d={d} pathLength={dash ? 1000 : undefined} stroke={grad} strokeWidth={14 * w} opacity={0.18 * a} />
    <path d={d} pathLength={dash ? 1000 : undefined} stroke={grad} strokeWidth={5 * w} opacity={0.9 * a} />
    <path d={d} pathLength={dash ? 1000 : undefined} stroke="#fff6fd" strokeWidth={1.6 * w} opacity={0.85 * a * core} />
  </g>
);

// Tunnel echoes: k=1..7, z-recession, scaling up per layer (screen projection shows concentric larger matching frames)
const ECHO = Array.from({ length: 5 }, (_, i) => {
  const k = i + 1;
  const z = 320 * k;
  const g = 1.13 + 0.2 * k; // Apparent on-screen size / panel
  return { k, z, s: (g * (PERSP + z)) / PERSP, on: 20 + i * 4, off: 94 + [2, 1, 0, 1, 2][i] * 7 + (i % 2) * 2 };
});

export const NeonFrameForerun: React.FC = () => {
  const frame = useCurrentFrame();
  const uid = React.useId().replace(/[^a-zA-Z0-9]/g, '');
  const gid = `nff${uid}`;

  // Frame trace: two bright runner heads depart left midpoint frames 2->22 top and bottom, colliding at right midpoint
  const trace = ramp(frame, 2, 20, EASE.swift);
  const half = trace * 500; // Distance drawn per branch (half of pathLength 1000)
  const meet = ramp(frame, 21, 14, EASE.out); // Collision flash decay (0->1)
  const flash = frame >= 21 ? (1 - meet) : 0;

  // Page illumination: page surfaces from black after frame closes (vis), then brightens from dark (lit)
  const vis = ramp(frame, 16, 14, EASE.out);
  const lit = ramp(frame, 24, 60, EASE.smooth);
  // Landing window 30–104: maps each item's land (0..1) to frame 54..104, dense to sparse
  const landFrame = (u: number) => 54 + EASE.out(u) * 50;
  const liftOf = (p: Part) => {
    const lf = landFrame(p.land);
    const q = clamp01((frame - (lf - 24)) / 24);
    return (1 - easeFall(q)) * p.H;
  };

  // Camera: strong perspective -> settled; gentle drift during hold
  const settle = ramp(frame, 0, 96, EASE.out);
  const drift = ramp(frame, 90, 50, EASE.smooth);
  const rotY = mix(-30, -12, settle) + 1.5 * drift;
  const rotX = mix(10, 5, settle);
  const rotZ = mix(-7, -2.5, settle);
  const scale = mix(0.8, 0.88, settle) + 0.01 * drift;

  // Frame core line: recedes to hairline after lighting; frame glow merges into panel rim
  const frameCore = mix(1, 0.35, ramp(frame, 60, 40, EASE.smooth));
  const frameA = 1 - 0.35 * ramp(frame, 96, 30, EASE.smooth);
  const rim = ramp(frame, 40, 40, EASE.out) * (1 + 0.25 * ramp(frame, 100, 30, EASE.smooth));
  const stageI = 0.55 + 0.45 * ramp(frame, 18, 30, EASE.out) - 0.3 * ramp(frame, 96, 30, EASE.smooth);

  const heads = trace < 1 ? [pointAt(trace * 0.5), pointAt(1 - trace * 0.5)] : [];

  return (
    <AbsoluteFill style={{ background: L.bg[2], overflow: 'hidden', fontFamily: FONT.sans }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.05 }} fill={{ x: 0.85, y: 0.95 }} intensity={stageI} vignette={0.7} />

      <div style={{ position: 'absolute', inset: 0, perspective: PERSP, perspectiveOrigin: '50% 45%' }}>
        <div style={{
          position: 'absolute', left: (1920 - PW) / 2, top: (1080 - PH) / 2, width: PW, height: PH,
          transform: `scale(${scale.toFixed(4)}) rotateY(${rotY.toFixed(3)}deg) rotateX(${rotX.toFixed(3)}deg) rotateZ(${rotZ.toFixed(3)}deg)`,
          transformStyle: 'preserve-3d',
        }}>
          {/* Tunnel echoes: matching neon frames receding in depth */}
          {ECHO.map((e) => {
            const a = strike(frame, e.on) * quench(frame, e.off) * (0.42 - e.k * 0.06) * (0.85 + 0.15 * Math.sin(frame / 7 + e.k));
            if (a <= 0.002) return null;
            return (
              <svg key={e.k} width={FW} height={FH} viewBox={`0 0 ${FW} ${FH}`} style={{
                position: 'absolute', left: -PAD, top: -PAD, overflow: 'visible',
                transform: `translateZ(${-e.z}px) scale(${e.s.toFixed(4)})`,
              }}>
                <Tube d={FRAME_D} grad={e.k % 2 ? NEON_A : NEON_B} a={a} core={0.5} w={1.2 + e.k * 0.3} />
              </svg>
            );
          })}

          {/* Panel drop shadow + rim glow (frame glow eventually merges here) */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: 18, transform: 'translateZ(-2px)',
            boxShadow: `0 40px 120px -10px rgba(4,1,12,0.85), -30px -10px 80px 6px ${alpha(NEON_A, 0.32 * rim)}, 30px 30px 90px 10px ${alpha(NEON_B, 0.26 * rim)}`,
            opacity: clamp01(trace * 2),
          }} />

          {/* Panel baseplate: dark to lit */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: 18, overflow: 'hidden', opacity: vis,
            background: 'linear-gradient(180deg, #faf9fc 0%, #f3f1f7 100%)',
            filter: lit < 0.995 ? `brightness(${Math.max(0.03, lit).toFixed(3)})` : undefined,
          }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 330, background: '#efecf4', boxShadow: `inset -1px 0 0 ${HAIR}` }} />
            {/* Neon illuminates page from left: cold violet dark veil receding left-to-right */}
            <div style={{
              position: 'absolute', inset: 0,
              background: `linear-gradient(90deg, rgba(40,20,90,0) ${mix(-40, 100, lit)}%, rgba(40,20,90,0.6) ${mix(0, 160, lit)}%)`,
            }} />
          </div>

          {/* Components: genuine 3D hover + matching soft shadow, staggered landing */}
          <div style={{ position: 'absolute', inset: 0, transformStyle: 'preserve-3d' }}>
            {PARTS.map((p) => (
              <Float key={p.key} x={p.x} y={p.y} w={p.w} h={liftOf(p)} lit={lit} vis={vis}>{p.node}</Float>
            ))}
          </div>

          {/* Main neon frame: bidirectional trace from left midpoint */}
          <svg width={FW} height={FH} viewBox={`0 0 ${FW} ${FH}`} style={{ position: 'absolute', left: -PAD, top: -PAD, overflow: 'visible', transform: 'translateZ(2px)' }}>
            <defs>
              <linearGradient id={gid} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={FW} y2={FH}>
                <stop offset="0" stopColor={NEON_A} />
                <stop offset="0.55" stopColor="#e07ae0" />
                <stop offset="1" stopColor={NEON_B} />
              </linearGradient>
              <radialGradient id={`${gid}h`}>
                <stop offset="0" stopColor="#ffffff" />
                <stop offset="0.25" stopColor="#ffe6fb" stopOpacity={0.9} />
                <stop offset="1" stopColor={NEON_B} stopOpacity={0} />
              </radialGradient>
            </defs>
            {trace > 0 && (
              <>
                <Tube d={FRAME_D} grad={`url(#${gid})`} dash={`${half} 1000`} offset={0} a={frameA} core={frameCore} />
                <Tube d={FRAME_D} grad={`url(#${gid})`} dash={`${half} 1000`} offset={-(1000 - half)} a={frameA} core={frameCore} />
              </>
            )}
            {/* Starting bright dot (present at frame 0) and runner heads */}
            {frame < 3 && <circle cx={0} cy={FH / 2} r={34} fill={`url(#${gid}h)`} />}
            {heads.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={46} fill={`url(#${gid}h)`} />)}
            {/* Collision flash at right midpoint */}
            {flash > 0.01 && <circle cx={FW} cy={FH / 2} r={60 + 160 * meet} fill={`url(#${gid}h)`} opacity={flash} />}
          </svg>
        </div>
      </div>
    </AbsoluteFill>
  );
};
