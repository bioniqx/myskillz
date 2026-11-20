// exploded-view (Round 2 redesign)
// Core technique preserved: full page with 3D tilt; components explode along Z-axis in staggered fashion, hover for a beat to reveal depth via parallax, then reassemble in reverse order with a solid slam settle.
//
// Design decisions
// - look: porcelain (cool white · cobalt blue). Apple keynote-style "take it apart to show you": camera shifted to 3/4 axonometric (rotateX 54° +
//   rotateZ −32°); page lies flat like a motherboard on a workbench, with layers stacked upward along page normal — feels far more like an authentic exploded diagram
//   than the original front-facing slight tilt "floating" look.
// - Subject: video-shotcraft motion workbench: chassis baseplate → sidebar (brand mark) → command bar → three render metric cards →
//   render volume chart → AI assistant panel; 6 layers, each with real UI (large digits, cobalt charts), with dashed component slots remaining on baseplate.
// - Callouts: numbered callout list on right during hover (keynote-style callouts): anchor point → polyline leader line draws out → 44px title + 30px description
//   rise sequentially; anchor points calculated in real-time from 3D projection, tracking camera orbit.
// - Reassembly: callouts dismiss first; layers slam back in reverse order with ease-in, settle avoids screen shake (Q3) in favor of 8px group dip-and-rebound +
//   tightened baseplate contact shadow; a single sheen sweeps across the whole page after reassembly (Q4: hero element gets it once); finally, video-shotcraft wordmark + headline land top-left, ending on a poster frame.
//
// Timeline (30fps, 170f total)
//   0–24    Establish: assembled page (0.56x), ultra-slow push-in + orbit start; 18–24 anticipation (layers press down 6px together to gather momentum)
//   22–62   Camera zooms out 0.56→0.47 and pans down, framing the rising layer stack (pushes back in at 106–136 reassembly)
//   24–62   Explode: 5 layers rise with staggered springs (damping 15, single visible overshoot), 5f interval, higher layers arrive later
//   30–104  Hover orbit: rotateZ −32°→−22°, rotateX 54°→50° (smooth), layer parallax conveys depth
//   52–86   Callouts: 8f line draw + 12f text rise per item, 6f interval; 86–104 hold
//   104–114 Callouts dismiss (ease-in, 2f stagger)
//   108–132 Reassembly: reverse ease-in 14f per layer, 3f interval; 132f final layer seats
//   132–142 Slam settle: 8px group dip with damped rebound, contact shadow tightens; 136–160 single sheen sweep
//   140–170 Wordmark fades in, headline "Built in layers." rises word-by-word → hold, final frame poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { LOOKS, Sheen, Stage, TextReveal, alpha, springAt, type } from '../../_fixtures/Look';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark, ShotcraftWordmark } from '../../_fixtures/Brand';

export const EXPLODED_VIEW_DURATION = 170;

const L = LOOKS.porcelain;
const W = 1600;
const H = 1000;
const R = 26; // Page corner radius
const PERSP = 2400;

const EXPLODE = 24;
const STAGGER = 5;
const ASSEMBLE = 108;
const BACK = 3; // Reassembly stagger
const BACK_DUR = 14;

type Layer = {
  key: string; x: number; y: number; w: number; h: number; z: number; r: number; side: 'L' | 'R';
  label: { n: string; t: string; d: string };
};

// Layers (page coordinates + explode height); order = array index (bottom → top)
const LAYERS: Layer[] = [
  { key: 'side', x: 0, y: 0, w: 288, h: H, z: 150, r: R, side: 'L', label: { n: '01', t: 'Navigation', d: 'Every shot, one click away' } },
  { key: 'chart', x: 320, y: 410, w: 860, h: 558, z: 270, r: 22, side: 'L', label: { n: '02', t: 'Insights', d: 'Renders, timing and pace' } },
  { key: 'ai', x: 1204, y: 410, w: 364, h: 558, z: 400, r: 22, side: 'R', label: { n: '03', t: 'Assistant', d: 'Drafts shots you approve' } },
  { key: 'kpi', x: 320, y: 130, w: W - 352, h: 250, z: 520, r: 22, side: 'R', label: { n: '04', t: 'Live metrics', d: 'Updated every second' } },
  { key: 'top', x: 288, y: 0, w: W - 288, h: 100, z: 640, r: 0, side: 'R', label: { n: '05', t: 'Command bar', d: 'Add a shot in one line' } },
];
const N = LAYERS.length;

// ───────────── Per-layer UI (in page coordinate system, relative to layer top-left) ─────────────
const ink = (c: string, s: number, w: number, extra: React.CSSProperties = {}): React.CSSProperties => ({ ...type(s, w), color: c, ...extra });

const SideUI: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#f6f8fc', borderRight: `2px solid ${L.line}` }}>
    <div style={{ position: 'absolute', left: 34, top: 32, display: 'flex', alignItems: 'center', gap: 14 }}>
      <ShotcraftMark size={44} tone="light" style={{ flex: 'none' }} />
      <div style={{ ...ink(L.ink, 32, 700), fontFamily: BRAND.font, letterSpacing: '0.03em' }}>{BRAND.short}</div>
    </div>
    {['Shots', 'Storyboard', 'Timeline', 'Sound', 'Renders', 'Settings'].map((n, i) => (
      <div key={n} style={{
        position: 'absolute', left: 20, right: 20, top: 120 + i * 70, height: 56, borderRadius: 14, display: 'flex', alignItems: 'center',
        padding: '0 18px', gap: 14, background: i === 0 ? alpha(L.accent, 0.1) : undefined,
      }}>
        <div style={{ width: 22, height: 22, borderRadius: 7, border: `3px solid ${i === 0 ? L.accent : L.ink3}`, boxSizing: 'border-box' }} />
        <div style={ink(i === 0 ? L.accent : L.ink2, 26, i === 0 ? 700 : 550)}>{n}</div>
        {i === 0 && <div style={{ marginLeft: 'auto', ...ink('#fff', 20, 700), background: L.accent, borderRadius: 999, padding: '2px 12px' }}>24</div>}
      </div>
    ))}
  </div>
);

const TopUI: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#ffffff', borderBottom: `2px solid ${L.line}`, display: 'flex', alignItems: 'center', padding: '0 32px', gap: 24 }}>
    <div style={{ flex: 1, height: 58, borderRadius: 16, background: L.surface2, boxShadow: `inset 0 0 0 2px ${L.line}`, display: 'flex', alignItems: 'center', padding: '0 22px', gap: 14 }}>
      <svg width={26} height={26} viewBox="0 0 24 24" fill="none" stroke={L.ink3} strokeWidth={2.4} strokeLinecap="round"><circle cx={11} cy={11} r={7} /><path d="M20 20l-4-4" /></svg>
      <div style={ink(L.ink3, 26, 500)}>Add a shot or search recipes…</div>
      <div style={{ marginLeft: 'auto', ...ink(L.ink3, 22, 600, { fontFamily: FONT.mono }), padding: '4px 12px', borderRadius: 8, boxShadow: `inset 0 0 0 2px ${L.line}` }}>⌘K</div>
    </div>
    <div style={{ width: 52, height: 52, borderRadius: 26, background: 'linear-gradient(135deg,#7aa2ff,#2f5bff)' }} />
  </div>
);

const KPIS = [
  { k: 'Avg. render time', v: '1m 42s', d: '−31%' },
  { k: 'Shots rendered', v: '2,184', d: '+12%' },
  { k: 'Cuts on the beat', v: '98.2%', d: '+0.6' },
];
const KpiUI: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, display: 'flex', gap: 24 }}>
    {KPIS.map((k, i) => (
      <div key={k.k} style={{ flex: 1, borderRadius: 22, background: '#fff', boxShadow: `inset 0 0 0 2px ${L.line}`, padding: '34px 36px', boxSizing: 'border-box' }}>
        <div style={ink(L.ink2, 26, 600)}>{k.k}</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 22 }}>
          <div style={ink(L.ink, 68, 780, { whiteSpace: 'nowrap' })}>{k.v}</div>
          <div style={ink(i === 0 ? L.accent2 : L.accent, 28, 700)}>{k.d}</div>
        </div>
      </div>
    ))}
  </div>
);

const VOL = [30, 34, 31, 42, 48, 45, 56, 61, 52, 66, 72, 69, 80, 76, 88];
const ChartUI: React.FC = () => {
  const cw = 860 - 72;
  const ch = 330;
  const pts = VOL.map((v, i) => [(i / (VOL.length - 1)) * cw, ch - (v / 100) * ch] as const);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  return (
    <div style={{ position: 'absolute', inset: 0, borderRadius: 22, background: '#fff', boxShadow: `inset 0 0 0 2px ${L.line}`, padding: '34px 36px', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 18 }}>
        <div style={ink(L.ink, 36, 750)}>Render volume</div>
        <div style={ink(L.ink3, 24, 550)}>Last 14 days</div>
      </div>
      <svg width={cw} height={ch + 10} style={{ position: 'absolute', left: 36, top: 150, overflow: 'visible' }}>
        <defs>
          <linearGradient id="xv-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={L.accent} stopOpacity={0.22} />
            <stop offset="1" stopColor={L.accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0, 0.33, 0.66, 1].map((g) => <line key={g} x1={0} x2={cw} y1={ch * g} y2={ch * g} stroke={L.line} strokeWidth={2} />)}
        <path d={`${line} L${cw},${ch} L0,${ch} Z`} fill="url(#xv-area)" />
        <path d={line} fill="none" stroke={L.accent} strokeWidth={6} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={11} fill="#fff" stroke={L.accent} strokeWidth={6} />
      </svg>
    </div>
  );
};

const AiUI: React.FC = () => (
  <div style={{
    position: 'absolute', inset: 0, borderRadius: 22, padding: '30px 28px', boxSizing: 'border-box',
    background: `linear-gradient(180deg, #ffffff 0%, ${alpha(L.accent, 0.06)} 100%)`, boxShadow: `inset 0 0 0 2px ${alpha(L.accent, 0.35)}`,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 30, height: 30, borderRadius: 10, background: `linear-gradient(135deg, #7aa2ff, ${L.accent})` }} />
      <div style={ink(L.ink, 30, 750)}>Assistant</div>
    </div>
    <div style={{ marginTop: 26, borderRadius: 18, background: L.surface2, padding: '18px 20px', ...ink(L.ink2, 24, 500), lineHeight: 1.35 }}>
      Hero shot lands 6f late. Snap the cut to the kick?
    </div>
    <div style={{ marginTop: 16, borderRadius: 18, background: '#fff', boxShadow: `inset 0 0 0 2px ${L.line}`, padding: '18px 20px', ...ink(L.ink, 24, 550), lineHeight: 1.35 }}>
      “Moved the crash zoom to f240, right on the beat, and…”
    </div>
    <div style={{ position: 'absolute', left: 28, right: 28, bottom: 28, display: 'flex', gap: 12 }}>
      <div style={{ flex: 1, height: 58, borderRadius: 16, background: L.accent, ...ink('#fff', 24, 700), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Approve</div>
      <div style={{ flex: 1, height: 58, borderRadius: 16, boxShadow: `inset 0 0 0 2px ${L.line}`, ...ink(L.ink2, 24, 650), display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Edit</div>
    </div>
  </div>
);

const LAYER_UI: Record<string, React.FC> = { side: SideUI, top: TopUI, kpi: KpiUI, chart: ChartUI, ai: AiUI };

// ───────────── Camera & Projection ─────────────
type Cam = { rx: number; rz: number; s: number; cx: number; cy: number };
const camAt = (f: number): Cam => {
  const orbit = ramp(f, 30, 74, EASE.smooth);
  const push = ramp(f, 0, 170, EASE.smooth);
  const outro = ramp(f, 132, 30, EASE.smooth); // Camera pans right after reassembly, yielding room to top-left headline
  // Camera tracks layer stack height: group pans down during explode to keep top layers in frame; rises back up after reassembly
  const tall = ramp(f, 22, 40, EASE.smooth) * (1 - ramp(f, 106, 30, EASE.smooth));
  return {
    rx: mix(54, 50, orbit),
    rz: mix(-34, -32, ramp(f, 0, 30, EASE.out)) + 10 * orbit,
    s: mix(0.56, 0.47, tall) * mix(1, 1.04, push), // Zoom out during explode to frame layer stack; push back in after reassembly
    cx: mix(-20, 190, outro),
    cy: mix(40, 180, tall) + 70 * outro,
  };
};
// Page point (px,py,pz) → screen coordinates: identical matrix to CSS transform `translate(cx,cy) scale(s) rotateX(rx) rotateZ(rz)` +
// perspective(PERSP) (origin = page center = screen center)
const project = (c: Cam, px: number, py: number, pz: number) => {
  const X = px - W / 2, Y = py - H / 2;
  const a = (c.rz * Math.PI) / 180, b = (c.rx * Math.PI) / 180;
  const x1 = X * Math.cos(a) - Y * Math.sin(a);
  const y1 = X * Math.sin(a) + Y * Math.cos(a);
  const y2 = y1 * Math.cos(b) - pz * Math.sin(b);
  const z2 = y1 * Math.sin(b) + pz * Math.cos(b);
  const x4 = x1 * c.s + c.cx, y4 = y2 * c.s + c.cy;
  const k = PERSP / (PERSP - z2);
  return { x: 960 + x4 * k, y: 540 + y4 * k };
};

// Explode progress per layer: spring ascent × reverse ease-in reassembly
const layerP = (f: number, i: number) => {
  const up = springAt(f, EXPLODE + i * STAGGER, { damping: 15, stiffness: 120 });
  const down = ramp(f, ASSEMBLE + (N - 1 - i) * BACK, BACK_DUR, EASE.exit);
  return up * (1 - down);
};
const CLOSE = ASSEMBLE + (N - 1) * BACK + BACK_DUR; // Reassembly seated frame = 134

export const ExplodedView: React.FC = () => {
  const f = useCurrentFrame();
  const cam = camAt(f);
  // Anticipation: layers press down together; Slam: group sinks with damped rebound
  const crouch = -6 * (ramp(f, 18, 6, EASE.out) * (1 - ramp(f, EXPLODE, 6, EASE.out)));
  const since = f - CLOSE;
  const thud = since >= 0 ? 8 * Math.exp(-since / 3) * Math.cos(since * 0.9) : 0;
  const spread = ramp(f, EXPLODE, 30, EASE.out) * (1 - ramp(f, ASSEMBLE, CLOSE - ASSEMBLE, EASE.exit));
  const sheen = ramp(f, CLOSE + 4, 24, EASE.swift);

  return (
    <AbsoluteFill style={{ overflow: 'hidden', fontFamily: FONT.sans }}>
      <Stage look={L} keyLight={{ x: 0.36, y: 0.05 }} fill={{ x: 0.85, y: 0.9 }} />

      <AbsoluteFill style={{ perspective: PERSP }}>
        <div style={{
          position: 'absolute', left: 960 - W / 2, top: 540 - H / 2, width: W, height: H, transformStyle: 'preserve-3d',
          transform: `translate(${cam.cx}px, ${cam.cy + thud}px) scale(${cam.s}) rotateX(${cam.rx}deg) rotateZ(${cam.rz}deg)`,
        }}>
          {/* Workbench contact shadow: large soft shadow of entire page on workbench (fades during explode, snaps tight on slam) */}
          <div style={{
            position: 'absolute', left: -20, top: 10, width: W + 40, height: H + 40, borderRadius: R + 20,
            background: alpha(L.shadow, 0.28 - 0.08 * spread + 0.06 * Math.max(0, thud / 8)),
            filter: `blur(${40 - 10 * Math.max(0, thud / 8)}px)`, transform: 'translateZ(-30px) translate(30px, 40px)',
          }} />
          {/* Baseplate thickness */}
          <div style={{ position: 'absolute', inset: 0, borderRadius: R, background: '#c9d3e6', transform: 'translateZ(-14px)' }} />
          {/* Baseplate: page background + dashed component slots */}
          <div style={{ position: 'absolute', inset: 0, borderRadius: R, overflow: 'hidden', background: `linear-gradient(160deg, #f3f6fb 0%, ${L.bg[2]} 100%)`, boxShadow: `inset 0 0 0 2px ${L.line}` }}>
            {LAYERS.map((ly) => (
              <div key={ly.key} style={{
                position: 'absolute', left: ly.x + 10, top: ly.y + 10, width: ly.w - 20, height: ly.h - 20, borderRadius: Math.max(10, ly.r - 6),
                border: `3px dashed ${alpha(L.accent, 0.28)}`, background: alpha(L.accent, 0.03), boxSizing: 'border-box', opacity: Math.min(1, spread * 2),
              }} />
            ))}
            {/* Sheen: once after reassembly (clipped to baseplate rounded corners) */}
            <Sheen progress={sheen} color="#ffffff" strength={0.6} width={0.18} />
          </div>
          {/* Layer shadows on baseplate: shift down, blur out, and fade with height (key light top-left → shadow bottom-right) */}
          {LAYERS.map((ly, i) => {
            const p = Math.max(0, layerP(f, i));
            if (p < 0.01) return null;
            const h = ly.z * p;
            return (
              <div key={`sh-${ly.key}`} style={{
                position: 'absolute', left: ly.x + h * 0.18, top: ly.y + h * 0.26, width: ly.w, height: ly.h, borderRadius: ly.r,
                background: alpha(L.shadow, 0.3), filter: `blur(${(10 + h * 0.09).toFixed(1)}px)`, opacity: Math.min(1, p * 1.5) * (0.8 - h / 1400),
                transform: 'translateZ(1px)',
              }} />
            );
          })}
          {/* Movable layers: rise along normal; thickness edge behind (cobalt gray) */}
          {LAYERS.map((ly, i) => {
            const p = layerP(f, i);
            const z = ly.z * p + 2;
            const UI = LAYER_UI[ly.key];
            const box: React.CSSProperties = { position: 'absolute', left: ly.x, top: ly.y, width: ly.w, height: ly.h, borderRadius: ly.r };
            const lifted = Math.min(1, Math.max(0, p) * 4);
            return (
              <React.Fragment key={ly.key}>
                {lifted > 0.02 && <div style={{ ...box, background: '#b9c6de', transform: `translateZ(${Math.max(2.5, z - 8 + crouch).toFixed(2)}px)` }} />}
                <div style={{
                  ...box, overflow: 'hidden', transform: `translateZ(${(z + crouch).toFixed(2)}px)`,
                  boxShadow: lifted > 0.02 ? `0 0 0 2px ${alpha('#ffffff', 0.9 * lifted)}` : undefined,
                }}>
                  <UI />
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </AbsoluteFill>

      {/* Callouts: anchor (3D projection of layer right edge midpoint) → polyline leader → index + title + description */}
      <Callouts f={f} cam={cam} />

      {/* Outro headline */}
      <div style={{ position: 'absolute', left: 120, top: 104 }}>
        <div style={{ opacity: ramp(f, 140, 14, EASE.out) }}><ShotcraftWordmark size={30} tone="light" markScale={1.6} gap={14} /></div>
        <div style={{ ...type(96, 780), color: L.ink, marginTop: 18 }}>
          <TextReveal text="Built in layers." by="word" variant="rise" start={144} each={18} gap={5} />
        </div>
        <div style={{ ...type(36, 450), color: L.ink2, marginTop: 22, opacity: ramp(f, 156, 14, EASE.out), transform: `translateY(${(1 - ramp(f, 156, 14, EASE.out)) * 16}px)` }}>
          Every shot, tuned in one place.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Callouts split into left and right columns: left column attaches to outermost left corner, right column to outermost right corner; leader extends horizontally then bends before column
const COL = { L: 470, R: 1450 }; // Left column right-align guide / Right column left-align guide
const Callouts: React.FC<{ f: number; cam: Cam }> = ({ f, cam }) => {
  const items = LAYERS.map((ly, i) => {
    const z = ly.z * layerP(f, i) + 2;
    const cs = [[ly.x, ly.y], [ly.x + ly.w, ly.y], [ly.x, ly.y + ly.h], [ly.x + ly.w, ly.y + ly.h]].map(([x, y]) => project(cam, x, y, z));
    // Anchor: midpoint of two outermost corners (i.e. outer edge midpoint), reading as "this layer"
    cs.sort((u, v) => (ly.side === 'L' ? u.x - v.x : v.x - u.x));
    const a = { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 };
    return { ly, i, a };
  });
  const placed: { it: (typeof items)[number]; y: number }[] = [];
  (['L', 'R'] as const).forEach((sd) => {
    const col = items.filter((it) => it.ly.side === sd).sort((u, v) => u.a.y - v.a.y);
    const ys: number[] = [];
    col.forEach((it, k) => { ys[k] = k === 0 ? Math.max(150, it.a.y) : Math.max(ys[k - 1] + 140, it.a.y); });
    const over = (ys[ys.length - 1] ?? 0) - 940;
    col.forEach((it, k) => placed.push({ it, y: ys[k] - Math.max(0, over) }));
  });
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {placed.map(({ it, y: ly }) => {
        const start = 52 + it.i * 6;
        const draw = ramp(f, start, 8, EASE.out);
        const rise = ramp(f, start + 6, 12, EASE.snappy);
        const out = ramp(f, 104 + (N - 1 - it.i) * 2, 8, EASE.exit);
        if (draw <= 0 || out >= 1) return null;
        const L_ = it.ly.side === 'L';
        const ax = it.a.x, ay = it.a.y;
        const ex = L_ ? COL.L + 24 : COL.R - 24; // Leader line endpoint
        const kx = L_ ? Math.min(ax - 40, ex + 70) : Math.max(ax + 40, ex - 70); // Bend point: 70px before column
        const len = Math.abs(kx - ax) + Math.hypot(ex - kx, ly - ay);
        const lab = it.ly.label;
        return (
          <React.Fragment key={it.ly.key}>
            <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, opacity: 1 - out }}>
              <path d={`M${ax},${ay} L${kx},${ay} L${ex},${ly}`} fill="none" stroke={L.accent} strokeWidth={2.5}
                strokeDasharray={`${len} ${len}`} strokeDashoffset={len * (1 - draw)} strokeLinejoin="round" />
              <circle cx={ax} cy={ay} r={9 * Math.min(1, draw * 3)} fill={L.accent} stroke="#fff" strokeWidth={4} />
            </svg>
            <div style={{
              position: 'absolute', top: ly - 34, opacity: rise * (1 - out),
              ...(L_ ? { right: 1920 - COL.L, textAlign: 'right' as const } : { left: COL.R }),
              transform: `translateY(${(1 - rise) * 22 + out * -10}px)`,
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, justifyContent: L_ ? 'flex-end' : 'flex-start' }}>
                <span style={{ ...type(26, 700, { mono: true }), color: L.accent }}>{lab.n}</span>
                <span style={{ ...type(44, 760), color: L.ink }}>{lab.t}</span>
              </div>
              <div style={{ ...type(30, 450), color: L.ink2, marginTop: 6, whiteSpace: 'nowrap' }}>{lab.d}</div>
            </div>
          </React.Fragment>
        );
      })}
    </AbsoluteFill>
  );
};
