// tilt-reveal (Round 2 redesign)
// Core technique preserved: entire page rotates flat on rotateX; opening shows only a narrow perspective strip at the top edge; camera tilts up to level out, bringing rows of content into view.
//
// Design decisions
// - look: midnight (deep blue night · electric blue). Opening is a "horizon" in the dark — far top edge of the flat-lying page leaves only a
//   glowing narrow band (bright white-blue line on far upper edge + wide-angle blue bloom), like the first ray of light on the skyline.
// - Subject: dark-field render dashboard designed for camera moves — top bar (brand mark + wordmark), 120px headline "Renders are up 38%",
//   full-width glowing area chart, three 76px large-numeral KPIs. Few elements, large typography, high contrast; settles into a clean poster.
//   Page settles with margins in frame (0.84x), revealing stage light all around, with a blue halo "floor reflection" beneath.
// - Camera movement: page hinged at bottom edge, lying flat face-up (viewpoint above page, text inside narrow band is upright); rotateX 86°→−2.2° overshoot→0° leveling out;
//   single progress p drives scale 2.5→0.84, hinge position, viewpoint height, perspective distance; background pool of light and floating dust shift down with reverse parallax relative to pitch — reads as "camera tilts up", rather than the page rotating.
// - Light: during tilt-up, a specular highlight band sweeps from page top to bottom (physical specular sweep from grazing angle variation; Q4: hero gets it once,
//   clipped to rounded corners); glowing line of the area chart draws out across second half of tilt-up; a glowing dot illuminates at the endpoint upon settling.
// - Q2: enlargement avoids transform scale, layouts at target scale + CSS zoom rasterization, then reconstructs perspective with equivalent rotateX'·scaleY;
//   applies vertical-only anti-aliasing pre-blur matching vertical compression ratio while flat, automatically disabling once legible.
//
// Timeline (30fps, 120f total)
//   0–20   Anticipation: narrow band already in frame (that light is there on frame 1), ultra-slow creep 86°→83°, backlight fades in
//   20–60  Tilt-up 40f: asymmetric in-out (gentle start, fast mid-section, zero terminal speed), reaches −2.2° overshoot peak;
//          vertical motion blur applied during fastest frames; 32–62 specular sheen sweeps across page
//   60–70  Soft return to 0° (smooth) — camera settles
//   38–82  Area chart line draws out (out curve, with glowing pen tip), 80f endpoint dot illuminates; 3 KPI cells float up and brighten with stagger (rows lag baseplate by one beat)
//   70–120 Hold 50f: ultra-slow creep in 1→1.018, breathing backlight, final frame is a complete poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { Dust, LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { EASE, FONT, SpeedBlur, mix, ramp } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const TILT_REVEAL_DURATION = 120;

const L = LOOKS.midnight;

const HOLD = 20; // Anticipation creep ends
const MOVE = 40; // Primary tilt-up 20→60
const SETTLE = 10; // Overshoot rebound 60→70
const FROM = 86; // Flat pitch angle (page lies flat toward distance hinged at bottom edge, facing up)
const CREEP = 3 / 86; // Anticipation tilts up 3° first
const OVER = 1 + 2.2 / 86; // Primary tilt overshoots past 0° to +2.2°
const S0 = 2.5; // Scale when flat (narrow band is sufficiently wide and close)
const S1 = 0.84; // Settle scale: page margins reveal stage
const BOT0 = 600; // Screen y of hinge (page bottom edge) when flat — narrow band lands near screen centerline
const BOT1 = 540 + (1080 * S1) / 2 - 18; // Page bottom edge at settle (slightly raised to leave room for floor reflection)
const PAGE_R = 26; // Page corner radius (1x page px)

// Time → Pose (pure function; velocity computed via central difference). Angle follows overshooting q, scale/translation/perspective follow non-overshooting p
const poseAt = (f: number) => {
  const creep = ramp(f, 0, HOLD, EASE.smooth) * CREEP;
  const lift = ramp(f, HOLD, MOVE, EASE.swift);
  const q = mix(creep, OVER, lift) - (OVER - 1) * ramp(f, HOLD + MOVE, SETTLE, EASE.smooth);
  const p = mix(creep, 1, lift);
  return {
    p,
    rotX: FROM * (1 - q),
    scale: mix(S0, S1, p),
    bot: mix(BOT0, BOT1, p),
    eye: mix(BOT0 - 300, 520, p), // Viewpoint height: above page when flat (looking down on front surface), returns to screen center at settle
    persp: mix(700, 1500, p),
  };
};

// ───────────── Page: video-shotcraft dark-field render dashboard (1920×1080 design coordinates) ─────────────

// Area chart data (deterministic): slow climb + two dips + final surge
const SERIES = [22, 26, 24, 31, 35, 33, 38, 44, 41, 47, 52, 49, 55, 61, 58, 66, 71, 69, 78, 86];
const CH = { x: 0, y: 0, w: 1600, h: 300 };
const pt = (i: number) => {
  const x = CH.x + (i / (SERIES.length - 1)) * CH.w;
  const y = CH.y + CH.h - (SERIES[i] / 100) * CH.h;
  return [x, y] as const;
};
// Catmull-Rom → cubic Bezier, smooth polyline
const linePath = (() => {
  let d = '';
  for (let i = 0; i < SERIES.length; i++) {
    const [x, y] = pt(i);
    if (i === 0) { d += `M${x},${y}`; continue; }
    const [x0, y0] = pt(Math.max(0, i - 2));
    const [x1, y1] = pt(i - 1);
    const [x3, y3] = pt(Math.min(SERIES.length - 1, i + 1));
    d += ` C${x1 + (x - x0) / 6},${y1 + (y - y0) / 6} ${x - (x3 - x1) / 6},${y - (y3 - y1) / 6} ${x},${y}`;
  }
  return d;
})();
const areaPath = `${linePath} L${CH.w},${CH.h} L0,${CH.h} Z`;

const KPIS = [
  { k: 'Frames rendered', v: '4.82M', d: '+38%' },
  { k: 'Shots rendered', v: '12,480', d: '+2.1k' },
  { k: 'Cuts on the beat', v: '99.1%', d: '+1.4 pts' },
];

const DashboardPage: React.FC<{ draw: number; dot: number; rows: number[] }> = ({ draw, dot, rows }) => {
  const [lx, ly] = pt(SERIES.length - 1);
  return (
    <div style={{
      position: 'absolute', inset: 0, borderRadius: PAGE_R, overflow: 'hidden', fontFamily: FONT.sans,
      background: `linear-gradient(180deg, #121a2e 0%, ${L.surface} 46%, #0c1222 100%)`,
      boxShadow: `inset 0 0 0 1.5px ${L.line}, inset 0 1.5px 0 rgba(200,215,255,0.16)`,
    }}>
      {/* Top bar: hairline electric blue stroke along bottom edge — becomes the opening "horizon" when lying flat */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 0, height: 104, display: 'flex', alignItems: 'center',
        padding: '0 64px', gap: 22, background: 'rgba(160,190,255,0.035)',
      }}>
        <ShotcraftMark size={48} tone="dark" style={{ flex: 'none' }} />
        <div style={{ ...type(36, 700), fontFamily: BRAND.font, letterSpacing: '0.03em', color: L.ink }}>{BRAND.name}</div>
        <div style={{ display: 'flex', gap: 44, marginLeft: 72, ...type(28, 550), color: L.ink3 }}>
          <span style={{ color: L.ink }}>Overview</span><span>Shots</span><span>Renders</span><span>Gallery</span>
        </div>
        <div style={{
          marginLeft: 'auto', padding: '12px 26px', borderRadius: 999, border: `1.5px solid ${L.line}`,
          ...type(26, 550), color: L.ink2, background: 'rgba(160,190,255,0.05)',
        }}>Last 12 months</div>
        <div style={{ width: 52, height: 52, borderRadius: 26, background: 'linear-gradient(135deg,#5b8cff,#3ee6d0)', boxShadow: `0 0 0 3px ${L.surface}` }} />
      </div>
      <div style={{
        position: 'absolute', left: 0, right: 0, top: 103, height: 2,
        background: `linear-gradient(90deg, ${alpha(L.accent, 0)} 0%, ${L.accent} 22%, #b9cdff 50%, ${L.accent} 78%, ${alpha(L.accent, 0)} 100%)`,
        boxShadow: `0 0 18px ${alpha(L.accent, 0.8)}`,
      }} />

      {/* Title area */}
      <div style={{ position: 'absolute', left: 120, top: 168, opacity: rows[0], transform: `translateY(${(1 - rows[0]) * 18}px)` }}>
        <div style={{ ...type(26, 650, { caps: true }), color: L.accent, letterSpacing: '0.2em' }}>Render studio · Q3 Overview</div>
        <div style={{ ...type(TYPE_H1, 760), color: L.ink, marginTop: 26 }}>
          Renders are up <span style={{ color: L.accent, textShadow: `0 0 40px ${alpha(L.accent, 0.45)}` }}>38%</span>
        </div>
      </div>

      {/* Area chart: spans full width */}
      <div style={{ position: 'absolute', left: 160, top: 420, width: CH.w, height: CH.h + 60, opacity: rows[1] }}>
        {[0.25, 0.5, 0.75, 1].map((g) => (
          <div key={g} style={{ position: 'absolute', left: 0, right: 0, top: CH.h * (1 - g), height: 1.5, background: L.line }} />
        ))}
        <svg width={CH.w} height={CH.h} viewBox={`0 0 ${CH.w} ${CH.h}`} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
          <defs>
            <linearGradient id="mer-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor={L.accent} stopOpacity={0.38} />
              <stop offset="1" stopColor={L.accent} stopOpacity={0} />
            </linearGradient>
            <clipPath id="mer-clip"><rect x={-10} y={-40} width={(CH.w + 20) * draw} height={CH.h + 80} /></clipPath>
          </defs>
          <g clipPath="url(#mer-clip)">
            <path d={areaPath} fill="url(#mer-area)" />
            <path d={linePath} fill="none" stroke={alpha(L.accent, 0.35)} strokeWidth={14} strokeLinecap="round" style={{ filter: 'blur(8px)' }} />
            <path d={linePath} fill="none" stroke="#a9c1ff" strokeWidth={5} strokeLinecap="round" />
          </g>
          {draw > 0.02 && draw < 0.995 && (() => {
            const i = Math.min(SERIES.length - 1, draw * (SERIES.length - 1));
            const i0 = Math.floor(i), i1 = Math.min(SERIES.length - 1, i0 + 1);
            const [ax, ay] = pt(i0), [bx, by] = pt(i1);
            const hx = ax + (bx - ax) * (i - i0), hy = ay + (by - ay) * (i - i0);
            return <circle cx={hx} cy={hy} r={9} fill="#e6edff" style={{ filter: `drop-shadow(0 0 10px ${L.accent})` }} />;
          })()}
          {dot > 0 && (
            <g opacity={dot}>
              <circle cx={lx} cy={ly} r={34 * dot} fill={alpha(L.accent, 0.18)} />
              <circle cx={lx} cy={ly} r={11} fill="#e6edff" stroke={L.accent} strokeWidth={5} />
            </g>
          )}
        </svg>
        <div style={{ position: 'absolute', left: 0, right: 0, top: CH.h + 22, display: 'flex', justifyContent: 'space-between', ...type(24, 550, { caps: true }), color: L.ink3, letterSpacing: '0.14em' }}>
          {['Oct', 'Dec', 'Feb', 'Apr', 'Jun', 'Sep'].map((m) => <span key={m}>{m}</span>)}
        </div>
      </div>

      {/* 3 KPI blocks: large digits + growth */}
      <div style={{ position: 'absolute', left: 120, right: 120, top: 830, display: 'flex', gap: 40 }}>
        {KPIS.map((k, i) => (
          <div key={k.k} style={{
            flex: 1, height: 190, borderRadius: 22, padding: '30px 38px', boxSizing: 'border-box',
            background: `linear-gradient(180deg, ${L.surface2} 0%, rgba(23,32,54,0.6) 100%)`,
            boxShadow: `inset 0 0 0 1.5px ${L.line}, inset 0 1.5px 0 rgba(200,215,255,0.1)`,
            opacity: 0.55 + 0.45 * rows[2 + i], transform: `translateY(${(1 - rows[2 + i]) * 26}px)`,
          }}>
            <div style={{ ...type(26, 550), color: L.ink2 }}>{k.k}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 20, marginTop: 14 }}>
              <div style={{ ...type(76, 720), color: L.ink }}>{k.v}</div>
              <div style={{ ...type(28, 650), color: L.accent2 }}>{k.d}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
const TYPE_H1 = 120;

export const TiltReveal: React.FC = () => {
  const f = useCurrentFrame();
  const { p, rotX, scale: s0, bot, eye, persp } = poseAt(f);
  // Ultra-slow creep in after settling (camera alive during hold)
  const push = mix(1, 1.018, ramp(f, 70, 50, EASE.smooth));
  const scale = s0 * push;
  const botY = 540 + (bot - 540) * push;
  const topY = botY - 1080 * scale; // Layout box top edge (before 3D transform)

  // Tilt angular velocity (°/frame) → screen vertical displacement approx, active only during fast section
  const vRot = poseAt(f + 0.5).rotX - poseAt(f - 0.5).rotX;
  const vy = -vRot * 7;

  // Q2: Equivalent rotateX'·scaleY (on s-scaled plane), projection matches scale(s)·rotateX(r)
  const rad = (rotX * Math.PI) / 180;
  const rEq = (Math.atan2(Math.sin(rad), scale * Math.cos(rad)) * 180) / Math.PI;
  const kEq = Math.sqrt(scale * scale * Math.cos(rad) ** 2 + Math.sin(rad) ** 2) / scale;
  const vScale = kEq * Math.abs(Math.cos((rEq * Math.PI) / 180));
  const sigma = vScale > 0.6 ? 0 : (0.55 / Math.max(0.05, vScale)) * 1.6 - 1.2;

  const flat = Math.min(1, Math.abs(rotX) / 86); // 1 = lying flat
  // Far edge (page top edge) projected screen y: opening "horizon" hangs right here
  const Hs = 1080 * scale * kEq;
  const zFar = -Hs * Math.sin((rEq * Math.PI) / 180);
  const farY = eye + (botY - Hs * Math.cos((rEq * Math.PI) / 180) - eye) * (persp / (persp - zFar));
  const glowUp = ramp(f, 0, 26, EASE.out); // Backlight ramps from dark to bright at start
  // Background parallax: camera tilts up → stage light pool / floating dust shift down relatively
  const bgShift = mix(-150, 0, p);
  // Specular sheen band: sweeps from top to bottom edge as pitch levels out (clipped to page corner radius)
  const sheen = ramp(f, 32, 30, EASE.swift);
  // Content: polyline draw, endpoint dot, staggered rows
  const draw = ramp(f, 38, 44, EASE.out);
  const dot = ramp(f, 80, 14, EASE.overshoot);
  const rows = [0, 1, 2, 3, 4].map((i) => ramp(f, 34 + i * 4, 22, EASE.out));
  // Opening "horizon": electric blue rim light on page top edge; brightest when flat, settles into a highlight on page top edge
  const rim = glowUp * Math.pow(flat, 3);
  rows[0] = Math.max(rows[0], 0.85 + 0.15 * ramp(f, 30, 20, EASE.out)); // Headline visible while flat (readable in narrow band)
  rows[1] = 1;

  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: L.bg[2] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.0 }} fill={{ x: 0.82, y: 0.95 }} intensity={0.75 + 0.25 * glowUp} breathe={0.6}
        style={{ transform: `translateY(${bgShift}px)`, inset: '-160px 0 -160px 0' }}>
        <Dust look={L} count={34} seed={7} drift={0.18} opacity={0.5} />
      </Stage>

      {/* Backlight behind page: blue glow clinging to narrow band when flat; becomes contour rim light around page once upright */}
      <div style={{
        position: 'absolute', left: 960 - 900, width: 1800, top: mix(farY - 90, farY - 40, p), height: mix(180, 1000, p),
        background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.light, 0.55 * glowUp)} 0%, ${alpha(L.light, 0)} 70%)`,
        filter: 'blur(30px)', opacity: 0.9,
      }} />
      {/* Floor reflection: blue halo pool beneath page feet */}
      <div style={{
        position: 'absolute', left: 160, right: 160, top: 1080 - 150, height: 260, opacity: p,
        background: `radial-gradient(ellipse 50% 40% at 50% 30%, ${alpha(L.accent, 0.4)} 0%, ${alpha(L.accent, 0.08)} 55%, ${alpha(L.accent, 0)} 75%)`,
      }} />

      <SpeedBlur vx={0} vy={vy} amount={0.2} max={9}>
        <div style={{ position: 'absolute', inset: 0, perspective: persp, perspectiveOrigin: `50% ${(eye / 1080) * 100}%` }}>
          <div style={{
            position: 'absolute', left: 960 - 960 * scale, top: topY, width: 1920 * scale, height: 1080 * scale,
            transformOrigin: '50% 100%', transform: `rotateX(${rEq}deg) scaleY(${kEq})`,
            borderRadius: PAGE_R * scale, overflow: 'hidden',
            boxShadow: `0 ${40 * scale}px ${120 * scale}px ${alpha(L.shadow, 0.7)}, 0 0 ${60 * scale}px ${alpha(L.light, 0.18 * (1 - flat))}`,
          }}>
            {sigma > 0.5 && (
              <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
                <filter id="tilt-aa" x="0" y="-5%" width="100%" height="110%" colorInterpolationFilters="sRGB">
                  <feGaussianBlur stdDeviation={`0 ${sigma.toFixed(2)}`} />
                </filter>
              </svg>
            )}
            <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, zoom: scale, filter: sigma > 0.5 ? 'url(#tilt-aa)' : undefined }}>
              <DashboardPage draw={draw} dot={dot} rows={rows} />
            </div>
            {/* Grazing light: far edge (lower page, away from hinge) sinks into darkness when flat */}
            <div style={{
              position: 'absolute', inset: 0, pointerEvents: 'none',
              background: `linear-gradient(0deg, ${alpha(L.bg[2], 0.1 * flat)} 0%, ${alpha(L.bg[2], 0.5 * flat)} 45%, ${alpha(L.bg[2], 0.9 * flat ** 1.5)} 100%)`,
            }} />
            {/* Specular sheen band: sweeps once from top edge to bottom edge */}
            {sheen > 0 && sheen < 1 && (
              <div style={{
                position: 'absolute', inset: 0, pointerEvents: 'none', mixBlendMode: 'screen',
                background: `linear-gradient(180deg, transparent ${(sheen * 130 - 30).toFixed(1)}%, ${alpha('#9fb6ff', 0.16 * Math.sin(sheen * Math.PI))} ${(sheen * 130 - 12).toFixed(1)}%, transparent ${(sheen * 130 + 6).toFixed(1)}%)`,
              }} />
            )}
          </div>
        </div>
      </SpeedBlur>

      {/* Horizon rim light: bright hairline along narrow band top edge + wide bloom (screen space, tracks hinge) */}
      {rim > 0.01 && (
        <>
          <div style={{
            position: 'absolute', left: 0, right: 0, top: farY - 60, height: 120, opacity: rim, pointerEvents: 'none',
            background: `radial-gradient(ellipse 46% 50% at 50% 50%, ${alpha(L.accent, 0.5)} 0%, ${alpha(L.accent, 0)} 70%)`,
            mixBlendMode: 'screen',
          }} />
          <div style={{
            position: 'absolute', left: 0, right: 0, top: farY - 1.5, height: 3, opacity: rim, pointerEvents: 'none',
            background: `linear-gradient(90deg, ${alpha('#cfdcff', 0)} 4%, #cfdcff 32%, #ffffff 50%, #cfdcff 68%, ${alpha('#cfdcff', 0)} 96%)`,
            boxShadow: `0 0 14px ${alpha(L.accent, 0.9)}, 0 0 40px ${alpha(L.accent, 0.6)}`,
          }} />
        </>
      )}
    </AbsoluteFill>
  );
};
