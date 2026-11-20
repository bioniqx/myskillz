// Text video mask (text-as-mask) — Massive headline typography reveals panning product UI inside glyphs; outro scales up to fill frame,
// transitioning internal UI into full-screen takeover. The typography serves as a portal into the product.
//
// Iteration 2 redesign (porcelain stage · dark live dashboard):
// - look = porcelain. Cool porcelain stage with a 470px Black weight "SCALE" cutout acting as a window:
//   exterior stage features key lighting and subtle vignette, casting soft tinted drop shadows beneath typography.
// - Inside window: dark live dashboard "video-shotcraft · Render throughput" (render farm metrics): cobalt-to-cyan streaming area chart flows leftward,
//   frame counters tick, and render queue bars pulse — rich saturated colors and bright vector lines ensure immediate recognition of live UI.
// - Typography entrance: mask wipes up from baseline, settling 1.04->1; eyebrow tracking tightens, subtitle ascends.
// - Takeover: anticipation breath (text 1->0.965, sub/eyebrow exit over 8f) -> exponential zoom-in (log space t^1.8, 24f to 46x zoom);
//   zoom origin anchored on solid stroke of "L"; content compensates by 1/S inverse scale to eliminate distortion;
//   unmasked full-screen UI crossfades in late rush to close glyph seams; dashboard settles 1.32->1 via expo-out 6f after zoom-in.
// - Outro: complete dark dashboard serves as final poster, chart continuing to stream live.
//
// Timeline (30fps, 165f total):
//   0–18    Porcelain stage + typography wipes up from baseline, settling 1.04->1; 6–26 eyebrow, 14–32 subtitle
//   18–96   Internal UI drift (translateX +150 -> -150 with gentle easing); live charts/metrics animate continuously
//   96–104  Anticipation: text shrinks 1->0.965, eyebrow and subtitle exit
//   104–128 Zoom-in rush: mask 0.965->46x (log-space acceleration), takeover layer crossfades ~121–126
//   104–132 Dashboard scales 1.32->1, drift zeroes (expo-out, settling 6f after zoom)
//   132–165 Hold: full-screen dashboard with streaming live chart
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { EASE, FONT, bezier, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const TEXT_AS_MASK_DURATION = 165;

const L = LOOKS.porcelain;

// —— Glyph Mask ——
const WORD = 'SCALE';
const FONT_STACK = 'system-ui, -apple-system, Helvetica Neue, Arial, sans-serif';
const FS = 470;
const BASE_Y = 712; // Baseline
const TEXT_ATTRS = `x="960" y="${BASE_Y}" font-family="${FONT_STACK}" font-size="${FS}" font-weight="900" letter-spacing="-22" text-anchor="middle"`;
const MASK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><text ${TEXT_ATTRS} fill="white">${WORD}</text></svg>`;
const MASK_URL = `url("data:image/svg+xml,${encodeURIComponent(MASK_SVG)}")`;
const SHADOW_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><text ${TEXT_ATTRS} fill="#0c1a3a">${WORD}</text></svg>`;
const SHADOW_URL = `data:image/svg+xml,${encodeURIComponent(SHADOW_SVG)}`;
// Zoom origin: solid stem of "L" (calibrated to anchor zoom through letter opening)
const ORIGIN_X = 1236; // Centerline of "L" vertical stem (x in [1195,1278]) — stems clear screen symmetrically at S≈23x
const ORIGIN_Y = 546; // Centerline of vertical stem (y in [383,709])
const ORIGIN = `${ORIGIN_X}px ${ORIGIN_Y}px`;
const MAX_S = 46;

// —— Beats ——
const IN_END = 18;
const DRIFT0 = 18;
const DRIFT1 = 96;
const BREATH0 = 96;
const RUSH0 = 104;
const RUSH1 = 128;
const LAND1 = 132;
const DASH_S0 = 1.32;

// —— Product in Window: video-shotcraft dark render dashboard (1920x1080) ——
const D = { bg: '#0a0f1e', panel: '#0f1730', panel2: '#131d3b', line: 'rgba(150,180,255,0.12)', ink: '#eef3ff', ink2: '#9aa8c8', ink3: '#5d6a8a', blue: '#4d7cff', teal: '#19d3b4' };

// Deterministic stream curve: u = horizontal sample position (advancing with frame = data streams left)
const wave = (u: number) => 0.52 + 0.17 * Math.sin(u * 0.11) + 0.09 * Math.sin(u * 0.31 + 1.3) + 0.05 * Math.sin(u * 0.73 + 0.4) + 0.12 * Math.max(0, Math.sin(u * 0.045 - 0.6));

const Dashboard: React.FC<{ frame: number }> = ({ frame }) => {
  const flow = frame * 0.55; // Flow rate (samples/frame)
  const CW = 1560, CH = 380, N = 96;
  const pts = Array.from({ length: N + 1 }, (_, i) => {
    const x = (i / N) * CW;
    const y = CH - wave(i + flow) * CH * 0.92;
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = `${line} L${CW} ${CH} L0 ${CH} Z`;
  const last = pts[pts.length - 1];
  const reqs = 1.92 + 0.56 * ramp(frame, 10, 96, EASE.out);
  const bars = Array.from({ length: 24 }, (_, i) => 0.3 + 0.6 * Math.abs(Math.sin(i * 1.7 + frame * 0.05)) * (0.6 + 0.4 * Math.sin(i * 0.45)));
  const regions: [string, number][] = [['opening', 0.92], ['camera', 0.74], ['transition', 0.58], ['outro', 0.41]]; // Shot category render progress
  const Card: React.FC<{ x: number; y: number; w: number; h: number; children: React.ReactNode }> = ({ x, y, w, h, children }) => (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: 22, background: `linear-gradient(180deg, ${D.panel2}, ${D.panel})`, boxShadow: `inset 0 1px 0 rgba(255,255,255,0.06), 0 0 0 1px ${D.line}`, boxSizing: 'border-box', padding: '26px 30px', overflow: 'hidden' }}>{children}</div>
  );
  const Label: React.FC<{ children: React.ReactNode }> = ({ children }) => <div style={{ fontSize: 22, fontWeight: 650, letterSpacing: '0.14em', color: D.ink2, textTransform: 'uppercase' }}>{children}</div>;
  return (
    <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 70% 60% at 60% 30%, #12204a 0%, ${D.bg} 70%)`, fontFamily: FONT.sans, color: D.ink }}>
      {/* Sidebar */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 230, borderRight: `1px solid ${D.line}`, padding: '36px 30px', boxSizing: 'border-box' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ShotcraftMark size={40} tone="dark" />
          <div style={{ fontFamily: BRAND.font, fontSize: 28, fontWeight: 700, letterSpacing: '0.01em' }}>{BRAND.short}</div>
        </div>
        {['Overview', 'Renders', 'Shots', 'Timeline', 'Gallery'].map((t, i) => (
          <div key={t} style={{ marginTop: i ? 14 : 54, fontSize: 24, fontWeight: i === 1 ? 650 : 500, color: i === 1 ? D.ink : D.ink3, padding: '10px 14px', borderRadius: 10, background: i === 1 ? 'rgba(77,124,255,0.16)' : 'transparent' }}>{t}</div>
        ))}
      </div>
      {/* Header */}
      <div style={{ position: 'absolute', left: 290, top: 44, display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ ...type(56, 720), color: D.ink }}>Render throughput</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px', borderRadius: 999, background: 'rgba(25,211,180,0.14)', color: D.teal, fontSize: 24, fontWeight: 650 }}>
          <div style={{ width: 10, height: 10, borderRadius: 5, background: D.teal, boxShadow: `0 0 12px ${D.teal}`, opacity: 0.6 + 0.4 * Math.sin(frame / 5) }} />Live
        </div>
      </div>
      <div style={{ position: 'absolute', right: 60, top: 54, fontSize: 24, color: D.ink2, padding: '10px 18px', borderRadius: 12, boxShadow: `0 0 0 1px ${D.line}` }}>Last 24 hours</div>
      {/* KPI */}
      <Card x={290} y={150} w={520} h={200}>
        <Label>Frames rendered</Label>
        <div style={{ ...type(96, 760), marginTop: 14 }}>{reqs.toFixed(2)}M</div>
      </Card>
      <Card x={834} y={150} w={500} h={200}>
        <Label>Avg shot render</Label>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, marginTop: 14 }}>
          <div style={{ ...type(96, 760) }}>42<span style={{ fontSize: 48, color: D.ink2, marginLeft: 6 }}>s</span></div>
          <div style={{ fontSize: 26, fontWeight: 650, color: D.teal }}>−18%</div>
        </div>
      </Card>
      <Card x={1358} y={150} w={502} h={200}>
        <Label>Render queue</Label>
        <svg width={440} height={100} style={{ marginTop: 16 }}>
          {bars.map((b, i) => <rect key={i} x={i * 18.5} y={100 - b * 100} width={12} height={b * 100} rx={3} fill={i > 17 ? D.teal : D.blue} opacity={0.5 + 0.5 * b} />)}
        </svg>
      </Card>
      {/* Main chart: streaming area graph */}
      <Card x={290} y={376} w={1570} h={470}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Label>Frames / sec</Label>
          <div style={{ fontSize: 22, color: D.ink3, fontFamily: FONT.mono }}>fps · 1s buckets</div>
        </div>
        <svg width={CW} height={CH} style={{ position: 'absolute', left: 4, top: 70, overflow: 'visible' }}>
          <defs>
            <linearGradient id="tam-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={D.blue} stopOpacity={0.55} />
              <stop offset="1" stopColor={D.blue} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="tam-line" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor={D.blue} />
              <stop offset="1" stopColor={D.teal} />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((g) => <line key={g} x1={0} x2={CW} y1={CH * g} y2={CH * g} stroke={D.line} strokeWidth={1.5} />)}
          <path d={area} fill="url(#tam-area)" />
          <path d={line} fill="none" stroke="url(#tam-line)" strokeWidth={5} strokeLinejoin="round" />
          <circle cx={last[0]} cy={last[1]} r={10} fill={D.teal} />
          <circle cx={last[0]} cy={last[1]} r={22} fill={D.teal} opacity={0.22} />
        </svg>
      </Card>
      {/* Categories */}
      <Card x={290} y={870} w={1570} h={170}>
        <div style={{ display: 'flex', gap: 48, alignItems: 'center', height: '100%' }}>
          {regions.map(([name, v]) => (
            <div key={name} style={{ flex: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 24 }}>
                <span style={{ color: D.ink2, fontFamily: FONT.mono }}>{name}</span>
                <span style={{ fontWeight: 650 }}>{Math.round(v * 100)}%</span>
              </div>
              <div style={{ marginTop: 14, height: 12, borderRadius: 6, background: 'rgba(150,180,255,0.1)' }}>
                <div style={{ width: `${v * 100}%`, height: '100%', borderRadius: 6, background: `linear-gradient(90deg, ${D.blue}, ${D.teal})` }} />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export const TextAsMask: React.FC = () => {
  const f = useCurrentFrame();
  const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

  // Entrance: mask wipes up from baseline + settles 1.04->1
  const intro = ramp(f, 0, IN_END, EASE.snappy);
  const wipe = ramp(f, 0, 16, EASE.out);
  const introS = 1.04 - 0.04 * intro;

  // Anticipation breath -> zoom rush (logarithmic ease-in: accelerating scale per frame)
  const breath = ramp(f, BREATH0, RUSH0 - BREATH0, EASE.swift);
  const rush = Math.pow(ramp(f, RUSH0, RUSH1 - RUSH0, EASE.linear), 1.8); // t^1.8 in log space: exponential acceleration
  const s0 = introS * (1 - 0.035 * breath);
  const maskS = s0 * Math.pow(MAX_S / s0, rush);
  // Zoom centers "L" stem to viewport centerline; content layer applies inverse transform to remain static
  const cdx = (960 - ORIGIN_X) * rush;
  const cdy = (540 - ORIGIN_Y) * rush;
  const wrapT = `translate(${cdx.toFixed(2)}px, ${cdy.toFixed(2)}px) scale(${maskS})`;
  const innerT = `scale(${1 / maskS}) translate(${(-cdx).toFixed(2)}px, ${(-cdy).toFixed(2)}px)`;

  // Dashboard: drift (soft endpoints) -> recenters during rush (expo-out, settling 6f after zoom)
  const drift = ramp(f, DRIFT0, DRIFT1 - DRIFT0, bezier(0.3, 0, 0.7, 1));
  const land = ramp(f, RUSH0, LAND1 - RUSH0, EASE.snappy);
  const dx = (150 - 300 * drift) * (1 - land);
  const dy = -110 * (1 - land); // Panel shifts up during drift so stream chart aligns across letter waistline
  const dashS = DASH_S0 + (1 - DASH_S0) * land;
  // Takeover layer: crossfades after stem fills majority of frame to seal letter gaps
  const cover = interpolate(rush, [0.86, 0.95], [0, 1], clamp); // Crossfades once stem fills screen (S≈24x), zero washed-out veil
  // Shadow: retracts during early rush
  const rim = 1 - interpolate(rush, [0, 0.25], [0, 1], clamp);
  // Eyebrow / Subtitle
  const eyebrow = ramp(f, 6, 20, EASE.out);
  const sub = ramp(f, 14, 18, EASE.out);
  const out = 1 - ramp(f, BREATH0, 10, EASE.exit);

  const dash = (
    <div style={{ position: 'absolute', inset: 0, transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${dashS.toFixed(4)})`, transformOrigin: '50% 50%' }}>
      <Dashboard frame={f} />
    </div>
  );
  const clipBottom = `inset(0 0 ${((1 - wipe) * (1080 - BASE_Y + FS * 0.72)).toFixed(1)}px 0)`;

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.42, y: 0.12 }} fill={{ x: 0.85, y: 0.9 }} vignette={0.22} />

      {/* Glyph drop shadow: soft tinted shadow as if window is recessed into stage */}
      <img src={SHADOW_URL} style={{
        position: 'absolute', left: 0, top: 26, width: 1920, height: 1080, opacity: 0.2 * rim * intro, filter: 'blur(22px)',
        transform: wrapT, transformOrigin: ORIGIN, clipPath: clipBottom,
      }} />

      {/* Mask layer: wrapper handles mask + zoom; inner applies 1/S inverse scale to neutralize distortion */}
      <div style={{
        position: 'absolute', inset: 0, transform: wrapT, transformOrigin: ORIGIN, clipPath: clipBottom,
        WebkitMaskImage: MASK_URL, maskImage: MASK_URL, WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat',
        WebkitMaskSize: '1920px 1080px', maskSize: '1920px 1080px',
      }}>
        <div style={{ position: 'absolute', inset: 0, transform: innerT, transformOrigin: ORIGIN }}>{dash}</div>
      </div>

      {/* Takeover layer: unmasked full-screen dashboard matching motion, crossfading during late rush */}
      {cover > 0 && <div style={{ position: 'absolute', inset: 0, opacity: cover }}>{dash}</div>}

      {/* Eyebrow + Subtitle */}
      <div style={{ position: 'absolute', top: 214, width: '100%', textAlign: 'center', opacity: eyebrow * out }}>
        {/* Eyebrow: video-shotcraft logotype (lowercase with tracking collapse entrance) */}
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 14, verticalAlign: 'middle' }}>
          <ShotcraftMark size={44} tone="light" />
          <span style={{ fontFamily: BRAND.font, fontSize: 30, fontWeight: 700, color: L.ink, letterSpacing: `${(0.03 + (1 - eyebrow) * 0.3).toFixed(3)}em` }}>{BRAND.name}</span>
        </span>
      </div>
      <div style={{
        position: 'absolute', top: BASE_Y + 92, width: '100%', textAlign: 'center', fontFamily: FONT.sans, fontSize: 40, fontWeight: 500,
        letterSpacing: '-0.015em', color: L.ink2, opacity: sub * out, transform: `translateY(${((1 - sub) * 16).toFixed(2)}px)`,
      }}>
        From one prompt to <span style={{ color: L.ink, fontWeight: 700 }}>a finished launch film</span>.
      </div>
    </AbsoluteFill>
  );
};
