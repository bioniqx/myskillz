// integration-hub-map v5 — single-point rhythm refinement:
// Design intent: "The motion is right, but the flip needs to start fast and decelerate toward completion"
// -> rotateY 0->180 deg updated to fast flip + tail deceleration: strong ease-out (cubic), first ~40% duration
//   covers ~80% rotation, tail eases out smoothly into landing; continuous motion with no stepped pauses
//   (fast-flip deceleration curve).
//   90 deg edge-on point advances to ~f28 with white flash peak aligned. Rest preserved.
// --- v3 Architecture description (structure retained): ---
// 1. Initial motion flips page rotateY 180 deg to reveal back side,
//    revealing new page (double-sided card: front = close-up old page, back = new hub page),
//    reaching 90 deg edge-on triggers white flash wash over screen.
// 2. Five icon conduits connect with data flow: light pulses stream along pipelines (icon -> hub)
//    looping continuously through end.
// Motion structure: S1 close-up readable -> S2 flipping + zoom out + bloom rises ->
// S3/S4 edge-on flash + icons appear -> S5/S6 new page settles + conduits connect -> S7/S8 steady flow.
// --- Polish pass: ---
// - Camera push/pan converted to single continuous curve, smooth lead-in without pauses
// - Panel scale uses CSS zoom so text rasters at native resolution at both 2.05x and 1x
// - Tile popup has overshoot spring; conduits tint tiles on connect; 5 input icons represent video-shotcraft inputs
//   (Page Capture / Code Repo / Shot Recipe / BGM / SFX Library) line icons
// - Conduits: slender rainbow tube + white-hot core + leading sparks, comet flow pulses with ripple at connection
// - Background neon frames: subtle parallax with grain + vignette on dark background
import React, { useId } from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { Grain, Vignette, bezier } from '../../_fixtures/Polish';
import { ShotcraftWordmark } from '../../_fixtures/Brand';

export const INTEGRATION_HUB_MAP_DURATION = 150; // Lead-in 0.5s + fast flip 1.2s + 2-beat connect 0.7s + stream 2.6s

const mulberry32 = (a: number) => () => {
  let t = (a += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const rand = mulberry32(20260718);
const NOISE: number[] = Array.from({ length: 200 }, () => rand());

const FONT = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Inter, Arial, sans-serif';
const INK = '#1d1e25', INK2 = '#5f616b', INK3 = '#a0a2ab', HAIR = 'rgba(20,22,28,0.08)';
const ACC = '#5b55c8';

// Panel zoom uses CSS zoom for native text rasterization at all zoom levels
const PW = 820, PH = 520;

// ---------- Hub Panel (video-shotcraft workspace: layout matches design, content set in shots/renders domain) ----------
const LIST: { icon: string; title: string; sub: string }[] = [
  { icon: '#4a9fd8', title: 'Launch Film v3', sub: 'Storyboard · 12 shots · 0:45' },
  { icon: '#4a9fd8', title: 'Shot 04 · Crash Zoom Punch', sub: 'Recipe card · Camera · 36f' },
  { icon: '#34a853', title: 'Pricing Page Captures', sub: 'Page capture · 2x' },
  { icon: '#a259ff', title: 'Hero Frame Design', sub: 'Design File · Last Edited' },
  { icon: '#f2c744', title: 'Beat Grid · Soundtrack', sub: 'Audio · 120 BPM' },
  { icon: '#9a9a98', title: 'Render Archive', sub: 'Archived · In Launch Film' },
  { icon: '#c8c8c6', title: 'Render launch film - 1080p', sub: 'In Progress · In Render Queue · Yesterday' },
];

// Panel styling: hairline border + top lit edge + deep drop shadow + cool violet ambient light
const panelShell = (glow: number): React.CSSProperties => ({
  width: PW,
  height: PH,
  background: 'linear-gradient(180deg, #fdfdfc 0%, #f7f7f5 100%)',
  borderRadius: 14,
  boxSizing: 'border-box',
  fontFamily: FONT,
  overflow: 'hidden',
  boxShadow: [
    'inset 0 1px 0 rgba(255,255,255,1)',
    '0 0 0 1px rgba(255,255,255,0.55)',
    '0 2px 6px rgba(0,0,0,0.35)',
    '0 40px 90px -24px rgba(0,0,0,0.75)',
    `0 0 ${50 + glow * 90}px rgba(236,226,255,${(0.10 + glow * 0.45).toFixed(3)})`,
    `0 0 ${150 + glow * 120}px rgba(176,110,255,${(0.16 + glow * 0.28).toFixed(3)})`,
  ].join(', '),
});

const HubPanel: React.FC<{ glow: number }> = ({ glow }) => (
  <div style={{ ...panelShell(glow), padding: '26px 30px', display: 'flex', gap: 26 }}>
    <div style={{ flex: 2 }}>
      {/* Workspace header = product wordmark */}
      <ShotcraftWordmark size={25} tone="light" color={INK} markScale={1.3} gap={10} style={{ height: 32 }} />
      <div style={{ display: 'flex', gap: 16, marginTop: 12, borderBottom: `1px solid ${HAIR}`, paddingBottom: 8 }}>
        {['All', 'Shots', 'Cards', 'Storyboards', 'Renders', 'Audio', 'Captures', 'Exports'].map((t, i) => (
          <div key={t} style={{ fontSize: 12, color: i === 0 ? ACC : '#8e9099', fontWeight: i === 0 ? 650 : 450, position: 'relative' }}>
            {t}
            {i === 0 && <div style={{ position: 'absolute', left: 0, right: 0, bottom: -9, height: 2, borderRadius: 1, background: ACC }} />}
          </div>
        ))}
      </div>
      <div style={{ fontSize: 11, color: INK3, marginTop: 14, letterSpacing: '0.04em', fontWeight: 600 }}>RECENT</div>
      {LIST.map((it, i) => (
        <div key={i} style={{ display: 'flex', gap: 11, alignItems: 'center', marginTop: 12 }}>
          <div
            style={{
              width: 22, height: 22, borderRadius: 6,
              background: `linear-gradient(160deg, ${it.icon}, ${it.icon}cc)`,
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.35), 0 1px 2px rgba(16,18,24,0.12)',
            }}
          />
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: INK, letterSpacing: '-0.005em' }}>{it.title}</div>
            <div style={{ fontSize: 11, color: INK3, marginTop: 2 }}>{it.sub}</div>
          </div>
        </div>
      ))}
    </div>
    <div style={{ flex: 1, borderLeft: `1px solid ${HAIR}`, paddingLeft: 22 }}>
      <div
        style={{
          height: 30, width: 168, borderRadius: 8, marginTop: 4, fontSize: 12, color: INK2, fontWeight: 500,
          background: '#fff', boxShadow: `inset 0 0 0 1px rgba(20,22,28,0.14), 0 1px 2px rgba(16,18,24,0.05)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        + Add Shot Filter
      </div>
      <div style={{ fontSize: 10.5, color: INK3, marginTop: 24, letterSpacing: '0.08em', fontWeight: 600 }}>QUICK FILTERS</div>
      {['Assigned to Me', 'Created by Me'].map((t) => (
        <div key={t} style={{ fontSize: 13.5, color: INK2, marginTop: 11 }}>{t}</div>
      ))}
      <div style={{ fontSize: 10.5, color: INK3, marginTop: 24, letterSpacing: '0.08em', fontWeight: 600 }}>RENDER QUEUE</div>
      {[['Queued', 3], ['Rendered', 31], ['Archived', 7]].map(([t, n]) => (
        <div key={t} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5, color: INK2, marginTop: 11, width: 168 }}>
          <span>{t}</span>
          <span style={{ color: INK3, fontVariantNumeric: 'tabular-nums', fontSize: 12 }}>{n}</span>
        </div>
      ))}
    </div>
  </div>
);

// ---------- Pre-flip initial page (front face): previous page before flipping to hub ----------
const PARAS = [
  'A 45-second launch film for the new pricing page, cut from real page captures. video-shotcraft drafted the storyboard from twelve shot recipe cards; the beat grid is locked to the soundtrack.',
  'Camera moves are 2.5D push-ins with a crash zoom on the hero. Sound design lands a whoosh on every cut, and the first full render is already queued for review in the workbench.',
];
const FrontPanel: React.FC<{ glow: number }> = ({ glow }) => (
  <div style={{ ...panelShell(glow), padding: '30px 34px' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 26, height: 26, borderRadius: 7, background: 'linear-gradient(160deg, #5aaee6, #3d8fcc)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.35)' }} />
      <div style={{ fontSize: 26, fontWeight: 650, color: INK, letterSpacing: '-0.02em' }}>Launch Film v3</div>
      <div style={{ marginLeft: 'auto', fontSize: 11.5, color: INK3 }}>Edited 2h ago</div>
    </div>
    <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
      {['Storyboard', '12 shots', '0:45'].map((t) => (
        <div key={t} style={{ fontSize: 11.5, color: INK2, background: '#efeff1', borderRadius: 6, padding: '3px 10px', boxShadow: `inset 0 0 0 1px ${HAIR}` }}>
          {t}
        </div>
      ))}
    </div>
    <div style={{ height: 1, background: HAIR, marginTop: 18 }} />
    {/* Key fields */}
    <div style={{ display: 'flex', gap: 34, marginTop: 16 }}>
      {[['Duration', '0:45'], ['Stage', 'Rendering'], ['Ships', 'Sep 28'], ['Director', 'Dana Whitfield']].map(([k, v]) => (
        <div key={k}>
          <div style={{ fontSize: 10.5, color: INK3, letterSpacing: '0.06em', fontWeight: 600 }}>{k.toUpperCase()}</div>
          <div style={{ fontSize: 15, color: INK, fontWeight: 600, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{v}</div>
        </div>
      ))}
    </div>
    <div style={{ fontSize: 15, fontWeight: 650, color: INK, marginTop: 22 }}>Summary</div>
    {PARAS.map((p, i) => (
      <div key={i} style={{ fontSize: 13, lineHeight: 1.62, color: INK2, marginTop: 8, maxWidth: 720 }}>{p}</div>
    ))}
    <div style={{ fontSize: 15, fontWeight: 650, color: INK, marginTop: 18 }}>Next steps</div>
    {['Tune the crash zoom on the hero shot', 'Render the final cut at 1080p'].map((s, i) => (
      <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 9, marginTop: 9, fontSize: 13, color: INK2 }}>
        <div style={{ width: 13, height: 13, borderRadius: 4, boxShadow: `inset 0 0 0 1.2px ${i ? 'rgba(20,22,28,0.22)' : ACC}`, background: i ? '#fff' : 'rgba(91,85,200,0.1)' }} />
        {s}
      </div>
    ))}
  </div>
);

// ---------- Input source icon tiles (video-shotcraft native asset inputs) ----------
// Line icons: ink stroke + amber accent (primary brand accent); 48 viewBox, 54px display
const Tile: React.FC<{ kind: string; on: number; tint: string }> = ({ kind, on, tint }) => {
  const AMBER = '#D3923C';
  const ln = { fill: 'none', stroke: INK, strokeWidth: 3, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  const am = { ...ln, stroke: AMBER };
  const glyph = (() => {
    switch (kind) {
      case 'capture':
        // Page Capture: browser frame with viewfinder reticle
        return (
          <svg width={54} height={54} viewBox="0 0 48 48">
            <rect x={5} y={8} width={38} height={32} rx={5} {...ln} />
            <path d="M5 16 H43" {...ln} />
            <circle cx={10.5} cy={12} r={1.4} fill={INK} />
            <circle cx={15} cy={12} r={1.4} fill={INK} />
            <circle cx={19.5} cy={12} r={1.4} fill={INK} />
            <path d="M15 26 V22 H19 M29 22 H33 V26 M33 30 V34 H29 M19 34 H15 V30" {...am} strokeWidth={2.6} />
          </svg>
        );
      case 'code':
        // Code Repo: </> brackets
        return (
          <svg width={54} height={54} viewBox="0 0 48 48">
            <path d="M16 14 L6 24 L16 34" {...ln} strokeWidth={3.4} />
            <path d="M32 14 L42 24 L32 34" {...ln} strokeWidth={3.4} />
            <path d="M27.5 10 L20.5 38" {...am} strokeWidth={3.4} />
          </svg>
        );
      case 'recipe':
        // Shot Recipe: card + play triangle + recipe lines
        return (
          <svg width={54} height={54} viewBox="0 0 48 48">
            <rect x={8} y={5} width={32} height={38} rx={6} {...ln} />
            <path d="M20 13 L30 19 L20 25 Z" fill={AMBER} stroke={AMBER} strokeWidth={2} strokeLinejoin="round" />
            <path d="M15 32 H33 M15 37 H26" {...ln} strokeWidth={2.6} />
          </svg>
        );
      case 'music':
        // Music BGM: waveform
        return (
          <svg width={54} height={54} viewBox="0 0 48 48">
            {[6, 14, 24, 32, 18, 26, 10].map((h, k) => (
              <path key={k} d={`M${6 + k * 6} ${24 - h / 2} V${24 + h / 2}`} {...(k === 2 || k === 3 ? am : ln)} />
            ))}
          </svg>
        );
      default: // SFX: sound library — speaker + soundwaves
        return (
          <svg width={54} height={54} viewBox="0 0 48 48">
            <path d="M7 19 H14 L23 11 V37 L14 29 H7 Z" {...ln} />
            <path d="M29 19 A7 7 0 0 1 29 29" {...am} />
            <path d="M33.5 14 A13.5 13.5 0 0 1 33.5 34" {...am} />
          </svg>
        );
    }
  })();
  return (
    <div
      style={{
        width: 112,
        height: 112,
        borderRadius: 28,
        background: 'linear-gradient(180deg, #ffffff 0%, #f1f1f4 100%)',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        boxShadow: [
          'inset 0 1px 0 rgba(255,255,255,1)',
          'inset 0 -2px 4px rgba(20,22,40,0.08)',
          '0 0 0 1px rgba(255,255,255,0.4)',
          '0 18px 40px -12px rgba(0,0,0,0.7)',
          // Neon tint from conduit terminal after connection
          `0 0 ${18 + on * 40}px ${tint}${Math.round(Math.min(1, on) * 0x70).toString(16).padStart(2, '0')}`,
        ].join(', '),
      }}
    >
      {glyph}
    </div>
  );
};

// ---------- Conduits (rainbow gradient neon tubes) ----------
type Pipe = { kind: string; icon: [number, number]; path: string; len: number; tIcon: number; tPipe: number; tint: string };
const PIPES: Pipe[] = [
  { kind: 'capture', icon: [452, 262], path: 'M 452 322 L 452 440 Q 452 480 492 480 L 552 480', len: 300, tIcon: 52, tPipe: 62, tint: '#ffd44d' },
  { kind: 'code', icon: [252, 612], path: 'M 316 612 L 552 612', len: 240, tIcon: 52, tPipe: 62, tint: '#ffd44d' },
  { kind: 'recipe', icon: [992, 178], path: 'M 992 240 L 992 332', len: 92, tIcon: 52, tPipe: 62, tint: '#ffd44d' },
  { kind: 'music', icon: [1512, 272], path: 'M 1512 332 L 1512 440 Q 1512 480 1472 480 L 1372 480', len: 290, tIcon: 52, tPipe: 62, tint: '#ffd44d' },
  { kind: 'sfx', icon: [1702, 618], path: 'M 1640 618 L 1372 618', len: 270, tIcon: 52, tPipe: 62, tint: '#ffd44d' },
];
const GROW = 9; // 2-beat timing: 5 icons appear at frame 52 simultaneously, 5 conduits connect at frame 62 simultaneously
const FLOW_SPEED = 4.6; // Flow pulse velocity px/f
const FLOW_PERIOD = 74; // Pulse spacing (px)

// Arc-length point sampling on path for sparks
const pointAt = (path: string, dist: number): [number, number] => {
  const tok = path.match(/[MLQ]|-?[\d.]+/g)!;
  let i = 0, cx = 0, cy = 0, rest = dist;
  let last: [number, number] = [0, 0];
  while (i < tok.length) {
    const c = tok[i++];
    if (c === 'M') { cx = +tok[i++]; cy = +tok[i++]; last = [cx, cy]; continue; }
    if (c === 'L') {
      const x = +tok[i++], y = +tok[i++];
      const L = Math.hypot(x - cx, y - cy);
      if (rest <= L) { const k = rest / L; return [cx + (x - cx) * k, cy + (y - cy) * k]; }
      rest -= L; cx = x; cy = y; last = [cx, cy]; continue;
    }
    if (c === 'Q') {
      const qx = +tok[i++], qy = +tok[i++], x = +tok[i++], y = +tok[i++];
      const pts: [number, number][] = [];
      for (let s = 0; s <= 16; s++) {
        const u = s / 16;
        pts.push([(1 - u) * (1 - u) * cx + 2 * (1 - u) * u * qx + u * u * x, (1 - u) * (1 - u) * cy + 2 * (1 - u) * u * qy + u * u * y]);
      }
      for (let s = 1; s < pts.length; s++) {
        const L = Math.hypot(pts[s][0] - pts[s - 1][0], pts[s][1] - pts[s - 1][1]);
        if (rest <= L) { const k = rest / L; return [pts[s - 1][0] + (pts[s][0] - pts[s - 1][0]) * k, pts[s - 1][1] + (pts[s][1] - pts[s - 1][1]) * k]; }
        rest -= L;
      }
      cx = x; cy = y; last = [cx, cy]; continue;
    }
  }
  return last;
};

// ---------- Background neon rectangle outlines ----------
const RECTS = Array.from({ length: 9 }, (_, i) => ({
  x: [150, 660, 1740, 250, 1150, 700, 1660, 90, 1330][i],
  y: [255, 355, 545, 850, 935, 985, 830, 555, 760][i],
  w: 90 + NOISE[i * 3] * 160,
  h: 60 + NOISE[i * 3 + 1] * 70,
  hue: [265, 285, 300, 255, 275, 210, 320, 240, 40][i],
  ph: NOISE[i * 3 + 2] * Math.PI * 2,
}));

// Camera: continuous smooth trajectory without abrupt keyframe stops
const CAM = bezier(0.55, 0, 0.18, 1);

export const IntegrationHubMap: React.FC = () => {
  const frame = useCurrentFrame();
  // Instance-unique filter/gradient IDs (sanitized for url() syntax)
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');

  // --- Camera/panel path: close-up initial page -> 180 deg flip -> zoom out and settle ---
  const cam = CAM(Math.min(1, Math.max(0, frame / 96)));
  const zoom = 2.05 + (1.0 - 2.05) * cam;
  // Flip window: f14-49 (35 frames), fast flip with ease-out tail;
  // 90 deg edge-on at ~f21.2 (easeOut=0.5 -> t ~ 0.206).
  
  const rotY = interpolate(frame, [14, 49], [0, 180], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const panX = 130 + (0 - 130) * cam;
  const panY = 120 + (25 - 120) * cam;

  // Flash timing: at 90 deg edge-on (~f21) brief 2-frame pulse flash
  
  const bloom = interpolate(frame, [19, 21, 23, 27], [0, 1, 0.25, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const noise = NOISE[Math.min(frame, NOISE.length - 1)];

  // Ambient pulse after all connections established
  const allOn = Math.max(...PIPES.map((p) => p.tPipe)) + GROW;
  const breathe = frame > allOn ? 0.5 + 0.5 * Math.sin((frame - allOn) * 0.16) : 0;
  const panelGlow = bloom * 1.1 + breathe * 0.16;

  // Hub map overall visibility (icons, conduits, rects)
  const mapIn = interpolate(frame, [34, 60], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  // Background subtle parallax: 18% translation and 10% zoom tracking camera
  const bgPar = `translate(${(panX * 0.18).toFixed(2)}px, ${(panY * 0.18).toFixed(2)}px) scale(${(1 + (zoom - 1) * 0.1).toFixed(4)})`;

  return (
    <AbsoluteFill style={{ background: '#09080e' }}>
      {/* Deep violet base: center cold violet glow + bottom-left magenta rim light */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse 60% 55% at 50% 50%, rgba(98,58,160,0.28), transparent 70%), radial-gradient(ellipse 45% 40% at 16% 80%, rgba(150,56,128,0.13), transparent 70%), radial-gradient(ellipse 40% 35% at 86% 18%, rgba(70,90,190,0.10), transparent 70%)',
        }}
      />

      {/* Background neon rectangle outlines: thin, subtle, softly defocused */}
      <AbsoluteFill style={{ transform: bgPar, transformOrigin: '50% 50%' }}>
        {RECTS.map((r, i) => {
          const on = interpolate(frame, [36 + i * 4, 56 + i * 4], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          const settle = interpolate(frame, [90, 120], [1, 0.62], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          const a = on * settle;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: r.x,
                top: r.y,
                width: r.w,
                height: r.h,
                borderRadius: 12,
                border: `1.5px solid hsla(${r.hue} 85% 72% / ${(0.5 * a).toFixed(3)})`,
                boxShadow: `0 0 14px hsla(${r.hue} 90% 62% / ${(0.32 * a).toFixed(3)}), inset 0 0 12px hsla(${r.hue} 90% 62% / ${(0.14 * a).toFixed(3)})`,
                filter: 'blur(0.8px)',
              }}
            />
          );
        })}
      </AbsoluteFill>

      {/* Conduit layer */}
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, opacity: mapIn }}>
        <defs>
          {/* Each conduit uses userSpaceOnUse gradient along endpoints, expanding rainbow along pipeline.
              objectBoundingBox on pure horizontal/vertical lines has zero dimension disabling paint. */}
          {PIPES.map((p, i) => {
            const nums = p.path.match(/-?[\d.]+/g)!.map(Number);
            const [x1, y1] = [nums[0], nums[1]];
            const [x2, y2] = [nums[nums.length - 2], nums[nums.length - 1]];
            return (
              <linearGradient key={i} id={`rainbow-${uid}-${i}`} gradientUnits="userSpaceOnUse" x1={x1} y1={y1} x2={x2} y2={y2}>
                <stop offset="0%" stopColor="#ffe14d" />
                <stop offset="28%" stopColor="#ff8a5a" />
                <stop offset="52%" stopColor="#ff5ad0" />
                <stop offset="76%" stopColor="#b46bff" />
                <stop offset="100%" stopColor="#5ad0ff" />
              </linearGradient>
            );
          })}
          {/* userSpaceOnUse prevents filter collapse on straight horizontal/vertical pipes */}
              
          <filter id={`pipeGlow-${uid}`} filterUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
            <feGaussianBlur stdDeviation="9" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id={`soft-${uid}`} filterUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
            <feGaussianBlur stdDeviation="3.5" />
          </filter>
        </defs>
        {PIPES.map((p, i) => {
          const grow = interpolate(frame, [p.tPipe, p.tPipe + GROW], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.quad),
          });
          if (grow <= 0) return null;
          const dashOn = p.len * grow;
          const pulse = frame > allOn ? 0.84 + 0.16 * Math.sin((frame - allOn) * 0.16 + i) : 1;
          // Flow pulses: bright pulses loop along pipeline toward hub
          const flowOffset = -((frame - p.tPipe) * FLOW_SPEED + i * 37);
          const flowIn = interpolate(frame, [p.tPipe + GROW, p.tPipe + GROW + 8], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          const head = pointAt(p.path, dashOn);
          const growing = grow < 1;
          return (
            <g key={i}>
              <g filter={`url(#pipeGlow-${uid})`}>
                <path
                  d={p.path}
                  fill="none"
                  stroke={`url(#rainbow-${uid}-${i})`}
                  strokeWidth={12}
                  strokeLinecap="round"
                  strokeDasharray={`${dashOn} ${p.len + 60}`}
                  opacity={0.9 * pulse}
                />
              </g>
              {/* White-hot core: thin and luminous giving tube appearance */}
              <path
                d={p.path}
                fill="none"
                stroke="rgba(255,250,255,0.92)"
                strokeWidth={3}
                strokeLinecap="round"
                strokeDasharray={`${dashOn} ${p.len + 60}`}
                opacity={0.8 * pulse}
              />
              {/* Leading sparks: visible only during 9f growth window */}
              {growing && (
                <>
                  <circle cx={head[0]} cy={head[1]} r={16} fill="rgba(255,240,255,0.5)" filter={`url(#soft-${uid})`} />
                  <circle cx={head[0]} cy={head[1]} r={5.5} fill="#fff" />
                </>
              )}
              {grow >= 1 && flowIn > 0 && (
                <>
                  {/* Comet tail: elongated, soft fade */}
                  <path
                    d={p.path}
                    fill="none"
                    stroke="rgba(255,255,255,0.7)"
                    strokeWidth={8}
                    strokeLinecap="round"
                    strokeDasharray={`26 ${FLOW_PERIOD - 26}`}
                    strokeDashoffset={flowOffset}
                    opacity={0.38 * flowIn}
                    filter={`url(#soft-${uid})`}
                  />
                  {/* Comet head: leading bright point oriented toward hub */}
                  <path
                    d={p.path}
                    fill="none"
                    stroke="#ffffff"
                    strokeWidth={6}
                    strokeLinecap="round"
                    strokeDasharray={`7 ${FLOW_PERIOD - 7}`}
                    strokeDashoffset={flowOffset - 19}
                    opacity={0.95 * flowIn}
                  />
                </>
              )}
            </g>
          );
        })}
      </svg>

      {/* Icon tiles: pop up in same frame (overshoot spring), tinted after connection */}
      {PIPES.map((p, i) => {
        const appear = interpolate(frame, [p.tIcon, p.tIcon + 13], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        if (appear <= 0) return null;
        const pop = Easing.bezier(0.34, 1.5, 0.64, 1)(appear); // Overshoot ~8% then settle
        const on = interpolate(frame, [p.tPipe + GROW - 2, p.tPipe + GROW + 8], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.out(Easing.cubic),
        });
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: p.icon[0] - 56,
              top: p.icon[1] - 56,
              opacity: Math.min(1, appear * 2.2),
              transform: `translateY(${((1 - pop) * 22).toFixed(2)}px) scale(${(0.72 + 0.28 * pop).toFixed(4)})`,
            }}
          >
            <Tile kind={p.kind} tint={p.tint} on={on * (frame > allOn ? 0.82 + 0.18 * breathe : 1)} />
          </div>
        );
      })}

      {/* Hub panel: double-sided card 180 deg flip (front initial page -> back hub page) */}
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', perspective: 1500 }}>
        <div
          style={{
            transform: `translate(${panX.toFixed(2)}px, ${panY.toFixed(2)}px) rotateY(${rotY.toFixed(3)}deg)`,
            position: 'relative',
            transformStyle: 'preserve-3d',
            width: PW * zoom,
            height: PH * zoom,
            flexShrink: 0,
          }}
        >
          {/* Front: initial page before flip */}
          <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden' }}>
            <div style={{ zoom }}>
              <FrontPanel glow={panelGlow} />
            </div>
          </div>
          {/* Back: new hub page (pre-rotated 180 deg so face forward when flipped) */}
          <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}>
            <div style={{ zoom }}>
              <HubPanel glow={panelGlow} />
            </div>
          </div>
          {/* White flash overlay during burst peak */}
          <div
            style={{
              position: 'absolute',
              inset: -6 * zoom,
              borderRadius: 18 * zoom,
              background: '#ffffff',
              opacity: Math.min(0.96, bloom * 1.05),
              filter: `blur(${5 * zoom}px)`,
              pointerEvents: 'none',
              transform: rotY > 90 ? 'rotateY(180deg) translateZ(1px)' : 'translateZ(1px)',
              backfaceVisibility: 'hidden',
            }}
          />
        </div>
      </AbsoluteFill>

      {/* Port ripples: ripple rings emit as all five pipes reach hub edge */}
      {PIPES.map((p, i) => {
        const nums = p.path.match(/-?[\d.]+/g)!.map(Number);
        const [ex, ey] = [nums[nums.length - 2], nums[nums.length - 1]];
        const k = interpolate(frame, [p.tPipe + GROW - 1, p.tPipe + GROW + 13], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        if (k <= 0 || k >= 1) return null;
        const r = 6 + Easing.out(Easing.cubic)(k) * 26;
        return (
          <div
            key={`port-${i}`}
            style={{
              position: 'absolute', left: ex - r, top: ey - r, width: r * 2, height: r * 2, borderRadius: '50%',
              border: '2px solid rgba(255,255,255,0.9)', opacity: (1 - k) * 0.85,
              boxShadow: '0 0 12px rgba(255,200,255,0.6)',
            }}
          />
        );
      })}

      {/* Full-screen white-hot glare: white core + magenta wings + cyan flare */}
      {bloom > 0.02 && (
        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          <div
            style={{
              position: 'absolute',
              left: 300,
              top: 60,
              width: 1100,
              height: 900,
              background:
                'radial-gradient(closest-side, rgba(255,255,255,0.98), rgba(255,235,255,0.75) 42%, rgba(255,120,230,0.4) 68%, transparent 88%)',
              filter: 'blur(26px)',
              opacity: Math.min(1, bloom * (0.94 + 0.06 * noise)),
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: 1150,
              top: 150,
              width: 700,
              height: 620,
              background: 'radial-gradient(closest-side, rgba(255,90,208,0.85), rgba(200,70,255,0.4) 60%, transparent 85%)',
              filter: 'blur(34px)',
              opacity: bloom * 0.9,
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: 40,
              top: 480,
              width: 620,
              height: 520,
              background: 'radial-gradient(closest-side, rgba(140,210,255,0.8), rgba(90,120,255,0.35) 60%, transparent 85%)',
              filter: 'blur(30px)',
              opacity: bloom * 0.85,
            }}
          />
          {/* Horizontal violet-white streak on edge-on flash */}
          <div
            style={{
              position: 'absolute',
              left: 30,
              top: 700,
              width: 420,
              height: 40,
              borderRadius: 20,
              background: 'linear-gradient(90deg, rgba(255,255,255,0.9), rgba(170,90,255,0.7), transparent)',
              filter: 'blur(16px)',
              opacity: interpolate(frame, [20, 34, 70, 92], [0, 0.9, 0.5, 0], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              }),
            }}
          />
        </AbsoluteFill>
      )}
      <Vignette strength={0.55} inner={0.42} color="#040308" />
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
