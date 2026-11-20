// cursor-flyover — 4-stop tour guided by cursor (redesign)
// Technique: full page overview -> camera flies sequentially into four functional module close-ups, cursor moves in sync, points, clicks leaving ripples, interface responds immediately.
//
// Design decisions
// - look: porcelain (cool white + cobalt blue, SaaS interaction demo). Product is video-shotcraft workbench overview, rendered 1:1 natively on a
//   2400x1500 world canvas (not scaled up from 480x270 design coordinates); 0.66x overview gives full view, 1.3x close-up font size >= 40px readable.
// - Kept four key modules demonstrating the technique, each with an interactive click-and-response:
//   1. Frames rendered: segment control clicks 90D -> big number shifts (old slides up fade out, new rises from underline) + 12 bars spring stagger to new heights
//   2. Shot previews: click data point on curve -> guideline drops, data point scales up, tooltip overshoots and pops out
//   3. Release flags: click toggle switch -> thumb spring slides over, track tints cobalt blue, progress bar progresses 0->25%
//   4. Top shots: click second row -> row background tints + left accent bar + checkbox draws checkmark
//   Finally camera pulls back to overview, all four states active simultaneously — tail frame is a complete tour overview poster.
// - Cursor is "hand", camera is "eye": cursor moves first (swift 16f along a slight arc), camera starts 2f later, settles 6f later (smooth 20f),
//   cursor aims at target for 1 beat then presses (3f scales down to 0.84 with overshoot rebound); camera pulls back ~8% extra mid-flight then pushes back (hop),
//   directional motion blur added by screen speed. Cursor scales inversely 1/s each frame to remain a constant 40px on screen.
//
// Timeline (30fps, 240f = 8s)
//   0-22     Overview: workbench settles 0.62->0.66 push in, cursor centered
//   22-66    Stop 1: 22 cursor starts / 24-44 camera flight / 44 click / 46 UI response / hold until 66
//   66-110   Stop 2 (same structure, +44f each)
//   110-154  Stop 3
//   154-198  Stop 4
//   198-222  Pull back to overview (smooth 24f), all four module states in frame
//   222-239  Hold: slow subtle push-in 1%
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, bezier, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CURSOR_FLYOVER_DURATION = 240; // 8s @30fps

const L = LOOKS.porcelain;
const ACC = L.accent;
const UP = '#0f9d76'; // Positive gain (accent2 darkened for contrast on white)

// --------- World layout (px) ---------
const WW = 2400, WH = 1500;
const MOD = {
  rev: { x: 60, y: 150, w: 1120, h: 640 },
  users: { x: 1220, y: 150, w: 1120, h: 640 },
  flags: { x: 1220, y: 830, w: 1120, h: 640 },
  accts: { x: 60, y: 830, w: 1120, h: 640 },
};
const center = (m: { x: number; y: number; w: number; h: number }) => ({ x: m.x + m.w / 2, y: m.y + m.h / 2 });

// Polyline: 12 points, 9th point is click target (in-module coordinates)
const CH = { x: 64, y: 190, w: 992, h: 360 };
const LY = [0.62, 0.55, 0.58, 0.46, 0.5, 0.4, 0.44, 0.33, 0.37, 0.24, 0.3, 0.18];
const ptX = (i: number) => CH.x + (i / (LY.length - 1)) * CH.w;
const ptY = (i: number) => CH.y + LY[i] * CH.h;
const HOT = 9;

// Four click targets (world coordinates)
const TARGETS = [
  { x: MOD.rev.x + MOD.rev.w - 40 - 60, y: MOD.rev.y + 40 + 30 }, // 90D segment
  { x: MOD.users.x + ptX(HOT), y: MOD.users.y + ptY(HOT) }, // Data point
  { x: MOD.flags.x + MOD.flags.w - 64 - 46, y: MOD.flags.y + 196 + 31 }, // Row 1 switch
  { x: MOD.accts.x + 100, y: MOD.accts.y + 196 + 104 + 50 }, // Row 2 checkbox
];
const CAMS = [
  { x: WW / 2, y: WH / 2 + 30, s: 0.66 },
  { ...center(MOD.rev), s: 1.3 },
  { ...center(MOD.users), s: 1.3 },
  { ...center(MOD.flags), s: 1.3 },
  { ...center(MOD.accts), s: 1.3 },
];
const LEG0 = 22; // Stop 1 cursor start
const LEG = 44; // Period per stop
const legStart = (k: number) => LEG0 + k * LEG;
const clickAt = (k: number) => legStart(k) + 22;
const BACK = 198; // Pull back to overview
const CAM_EASE = bezier(0.55, 0, 0.18, 1); // Crisp start, soft landing

// Camera (pure function of frame, supports fractional frames)
const camAt = (f: number) => {
  let { x, y, s } = CAMS[0];
  s *= mix(0.94, 1, ramp(f, 0, 22, EASE.snappy));
  let hop = 0;
  for (let k = 0; k < 4; k++) {
    const u = ramp(f, legStart(k) + 2, 20, CAM_EASE);
    const to = CAMS[k + 1];
    x = mix(x, to.x, u); y = mix(y, to.y, u); s = mix(s, to.s, u);
    if (k > 0 && u > 0 && u < 1) hop = 0.08 * Math.sin(Math.PI * u);
  }
  const b = ramp(f, BACK, 24, EASE.smooth);
  x = mix(x, CAMS[0].x, b); y = mix(y, CAMS[0].y, b); s = mix(s, CAMS[0].s, b);
  s *= (1 - hop) * (1 + 0.01 * ramp(f, 222, 18, EASE.smooth));
  return { x, y, s };
};

// Cursor (world coordinates): departs before camera, slight arc
const cursorAt = (f: number) => {
  let x = WW / 2 + 40, y = WH / 2 + 80;
  for (let k = 0; k < 4; k++) {
    const u = ramp(f, legStart(k), 16, EASE.swift);
    const to = TARGETS[k];
    const dx = to.x - x, dy = to.y - y;
    const len = Math.max(1, Math.hypot(dx, dy));
    const bow = Math.sin(Math.PI * u) * Math.min(90, len * 0.12);
    const nx = mix(x, to.x, u) + (-dy / len) * bow;
    const ny = mix(y, to.y, u) + (dx / len) * bow;
    x = nx; y = ny;
  }
  return { x, y };
};

// Interface response progress after click
const resp = (f: number, k: number, dur = 16, ease = EASE.snappy) => ramp(f, clickAt(k) + 2, dur, ease);

// --------- Module container ---------
const Module: React.FC<{ m: { x: number; y: number; w: number; h: number }; title: string; meta: string; active: number; children: React.ReactNode }> = ({ m, title, meta, active, children }) => (
  <div style={{
    position: 'absolute', left: m.x, top: m.y, width: m.w, height: m.h, borderRadius: 28, background: L.surface, overflow: 'hidden',
    border: `1.5px solid ${active > 0.01 ? alpha(ACC, 0.18 * active) : L.line}`,
    boxShadow: `inset 0 1.5px 0 #ffffff, ${softShadow(6 + 14 * active, { color: L.shadow, strength: 0.9 })}`,
  }}>
    <div style={{ position: 'absolute', left: 64, top: 56, ...type(34, 650), color: L.ink }}>{title}</div>
    <div style={{ position: 'absolute', left: 64, top: 104, ...type(26, 500), color: L.ink3 }}>{meta}</div>
    {children}
  </div>
);

// ① Revenue
const REV_BARS_A = [0.42, 0.5, 0.46, 0.58, 0.52, 0.6, 0.55, 0.64, 0.6, 0.7, 0.66, 0.74];
const REV_BARS_B = [0.3, 0.38, 0.45, 0.42, 0.55, 0.62, 0.58, 0.7, 0.76, 0.82, 0.88, 0.96];
const Revenue: React.FC<{ f: number }> = ({ f }) => {
  const r = resp(f, 0);
  const seg = ['7D', '30D', '90D'];
  const sel = ramp(f, clickAt(0), 8, EASE.snappy); // Segment slider 30D -> 90D
  return (
    <Module m={MOD.rev} title="Frames rendered" meta={sel > 0.5 ? 'Last 90 days' : 'Last 30 days'} active={r}>
      {/* Segmented control: slider translation */}
      <div style={{ position: 'absolute', right: 40, top: 40, width: 360, height: 60, borderRadius: 16, background: L.surface2, border: `1.5px solid ${L.line}` }}>
        <div style={{ position: 'absolute', top: 5, left: 5 + mix(118, 236, sel), width: 114, height: 47, borderRadius: 12, background: '#ffffff', boxShadow: softShadow(3, { color: L.shadow }) }} />
        {seg.map((s, i) => (
          <div key={s} style={{
            position: 'absolute', top: 0, left: 5 + i * 118, width: 114, height: 57, display: 'flex', alignItems: 'center', justifyContent: 'center',
            ...type(26, 650), color: (i === 1 && sel < 0.5) || (i === 2 && sel >= 0.5) ? L.ink : L.ink3,
          }}>{s}</div>
        ))}
      </div>
      {/* Big number transition */}
      <div style={{ position: 'absolute', left: 60, top: 168, height: 170, width: 700, overflow: 'hidden' }}>
        {[{ v: '2.48M', p: -r }, { v: '7.31M', p: 1 - r }].map(({ v, p }, i) => (
          <div key={i} style={{
            position: 'absolute', left: 0, top: 0, ...type(150, 720), color: L.ink,
            transform: `translateY(${(p * 150).toFixed(1)}px)`, opacity: 1 - Math.abs(p) * 0.9,
          }}>{v}</div>
        ))}
      </div>
      <div style={{
        position: 'absolute', right: 64, top: 236, height: 52, padding: '0 20px', borderRadius: 26, display: 'flex', alignItems: 'center', gap: 8,
        background: alpha(UP, 0.1), color: UP, ...type(30, 700),
      }}>▲ {r > 0.5 ? '24.6%' : '18.2%'}</div>
      {/* Bars: stagger spring to new heights after click */}
      <div style={{ position: 'absolute', left: 64, right: 64, bottom: 64, height: 200, display: 'flex', alignItems: 'flex-end', gap: 18 }}>
        {REV_BARS_A.map((a, i) => {
          const sp = f < clickAt(0) + 2 ? 0 : springAt(f, clickAt(0) + 2 + i * 1.4, { damping: 15, stiffness: 190 });
          const h = mix(a, REV_BARS_B[i], sp);
          const last = i === REV_BARS_A.length - 1;
          return (
            <div key={i} style={{
              flex: 1, height: `${(h * 100).toFixed(2)}%`, borderRadius: 10,
              background: last ? `linear-gradient(180deg, ${ACC}, #5c80ff)` : alpha(ACC, 0.14 + 0.1 * r * (i / 11)),
            }} />
          );
        })}
      </div>
    </Module>
  );
};

// ② Active users
const smoothPath = (pts: [number, number][]) => {
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
    d += ` C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)},${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)},${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
};
const PTS = LY.map((_, i) => [ptX(i), ptY(i)] as [number, number]);
const LINE = smoothPath(PTS);
const Users: React.FC<{ f: number }> = ({ f }) => {
  const r = resp(f, 1);
  const tip = f < clickAt(1) + 2 ? 0 : springAt(f, clickAt(1) + 2, { damping: 14, stiffness: 210 });
  const guide = resp(f, 1, 12, EASE.snappy);
  const hx = ptX(HOT), hy = ptY(HOT);
  const base = CH.y + CH.h;
  return (
    <Module m={MOD.users} title="Shot previews" meta="Weekly · Sep" active={r}>
      <div style={{ position: 'absolute', right: 64, top: 56, ...type(34, 700), color: L.ink }}>48.2k</div>
      <svg width={MOD.users.w} height={MOD.users.h} style={{ position: 'absolute', left: 0, top: 0 }}>
        <defs>
          <linearGradient id="cf2-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={ACC} stopOpacity={0.2} />
            <stop offset="1" stopColor={ACC} stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((k) => (
          <line key={k} x1={CH.x} x2={CH.x + CH.w} y1={CH.y + (k * CH.h) / 3} y2={CH.y + (k * CH.h) / 3} stroke={L.line} strokeWidth={1.5} />
        ))}
        <path d={`${LINE} L${CH.x + CH.w},${base} L${CH.x},${base} Z`} fill="url(#cf2-area)" />
        <path d={LINE} fill="none" stroke={ACC} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" />
        {/* Guide line drops top to bottom */}
        <line x1={hx} x2={hx} y1={hy} y2={hy + (base - hy) * guide} stroke={ACC} strokeWidth={2} strokeDasharray="6 6" opacity={0.8} />
        <circle cx={hx} cy={hy} r={9 + 7 * tip} fill="#ffffff" stroke={ACC} strokeWidth={5} />
        {['Sep 1', 'Sep 8', 'Sep 15', 'Sep 22', 'Sep 29'].map((m, i) => (
          <text key={m} x={CH.x + (i * CH.w) / 4} y={base + 48} fill={L.ink3} fontSize={24} fontFamily={FONT.sans} textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{m}</text>
        ))}
      </svg>
      {/* Tooltip: overshoot popup */}
      <div style={{
        position: 'absolute', left: hx - 150, top: hy - 168, width: 300, height: 124, borderRadius: 20, padding: '20px 26px', boxSizing: 'border-box',
        background: L.ink, color: '#ffffff', boxShadow: softShadow(24, { color: L.shadow, strength: 1.4 }),
        opacity: Math.min(1, tip * 2), transform: `translateY(${((1 - tip) * 16).toFixed(1)}px) scale(${(0.86 + 0.14 * tip).toFixed(3)})`, transformOrigin: '50% 100%',
      }}>
        <div style={{ ...type(22, 600), letterSpacing: '0.06em', color: alpha('#ffffff', 0.6), textTransform: 'uppercase' }}>Sep 22</div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <span style={{ ...type(46, 720) }}>51,204</span>
          <span style={{ ...type(26, 700), color: '#5ee0b8' }}>+12%</span>
        </div>
      </div>
    </Module>
  );
};

// ③ Release flags
const FLAGS = [
  { n: 'Beat-synced cuts', d: 'Snap every cut to the music grid' },
  { n: 'Film-grade SFX', d: 'Layer whooshes and hits per shot' },
  { n: 'JianYing export', d: 'Open the edit as a JianYing draft' },
];
const Toggle: React.FC<{ on: number }> = ({ on }) => (
  <div style={{ position: 'relative', width: 92, height: 54, borderRadius: 27, background: on > 0.5 ? ACC : '#d5dbe6' }}>
    <div style={{ position: 'absolute', inset: 0, borderRadius: 27, background: ACC, opacity: Math.min(1, Math.max(0, on)) }} />
    <div style={{ position: 'absolute', top: 5, left: 5 + 38 * on, width: 44, height: 44, borderRadius: 22, background: '#ffffff', boxShadow: '0 2px 6px rgba(12,26,58,0.25)' }} />
  </div>
);
const Flags: React.FC<{ f: number }> = ({ f }) => {
  const on = f < clickAt(2) + 1 ? 0 : springAt(f, clickAt(2) + 1, { damping: 16, stiffness: 240 });
  const roll = resp(f, 2, 26, EASE.out);
  return (
    <Module m={MOD.flags} title="Release · v4.2" meta="Feature flags" active={resp(f, 2)}>
      {FLAGS.map((fl, i) => {
        const first = i === 0;
        const v = first ? on : i === 1 ? 1 : 0;
        return (
          <div key={fl.n} style={{ position: 'absolute', left: 64, right: 64, top: 196 + i * 140, height: first ? 132 : 100, borderTop: i ? `1.5px solid ${L.line}` : undefined }}>
            <div style={{ position: 'absolute', left: 0, top: i ? 22 : 6, ...type(36, 650), color: L.ink }}>{fl.n}</div>
            <div style={{ position: 'absolute', left: 0, top: i ? 70 : 54, ...type(26, 450), color: L.ink3 }}>{fl.d}</div>
            <div style={{ position: 'absolute', right: 0, top: i ? 22 : 4 }}><Toggle on={v} /></div>
            {first && (
              <div style={{ position: 'absolute', left: 0, right: 0, top: 104, display: 'flex', alignItems: 'center', gap: 18, opacity: Math.min(1, roll * 3) }}>
                <div style={{ flex: 1, height: 8, borderRadius: 4, background: L.surface2, overflow: 'hidden' }}>
                  <div style={{ width: `${(roll * 25).toFixed(2)}%`, height: '100%', borderRadius: 4, background: ACC }} />
                </div>
                <div style={{ ...type(24, 650), color: ACC, width: 210, textAlign: 'right' }}>Rolling out · {Math.round(roll * 25)}%</div>
              </div>
            )}
          </div>
        );
      })}
    </Module>
  );
};

// 4. Top shots (shot card, category, monthly render count)
const ACCTS = [
  { n: 'Crash zoom', p: 'Camera', v: '4,280' },
  { n: 'Cursor flyover', p: 'Camera', v: '3,125' },
  { n: 'Text as mask', p: 'Opening', v: '1,890' },
  { n: 'Logo sting', p: 'Outro', v: '941' },
];
const Accounts: React.FC<{ f: number }> = ({ f }) => {
  const r = resp(f, 3, 14);
  const tick = resp(f, 3, 12, EASE.out);
  return (
    <Module m={MOD.accts} title="Top shots" meta="By renders this month" active={r}>
      {ACCTS.map((a, i) => {
        const sel = i === 1 ? r : 0;
        return (
          <div key={a.n} style={{
            position: 'absolute', left: 40, right: 40, top: 196 + i * 104, height: 100, borderRadius: 18,
            background: sel > 0 ? alpha(ACC, 0.08 * sel) : 'transparent',
            borderTop: i && sel < 0.01 && i !== 2 ? `1.5px solid ${L.line}` : '1.5px solid transparent',
          }}>
            <div style={{ position: 'absolute', left: 0, top: 22, width: 6, height: 56, borderRadius: 3, background: ACC, transform: `scaleY(${sel.toFixed(3)})` }} />
            {/* Checkbox */}
            <div style={{
              position: 'absolute', left: 42, top: 32, width: 36, height: 36, borderRadius: 10, boxSizing: 'border-box',
              border: `2.5px solid ${sel > 0.3 ? ACC : '#c4cbd8'}`, background: sel > 0.3 ? ACC : '#ffffff',
            }}>
              {i === 1 && (
                <svg width={36} height={36} viewBox="0 0 36 36" style={{ position: 'absolute', left: -2.5, top: -2.5 }}>
                  <path d="M10 18.5 L15.5 24 L26 12.5" fill="none" stroke="#ffffff" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={26} strokeDashoffset={26 * (1 - tick)} />
                </svg>
              )}
            </div>
            <div style={{ position: 'absolute', left: 112, top: 28, ...type(36, sel > 0.5 ? 700 : 560), color: L.ink }}>{a.n}</div>
            <div style={{ position: 'absolute', left: 600, top: 30, height: 40, padding: '0 16px', borderRadius: 20, display: 'flex', alignItems: 'center', background: L.surface2, ...type(24, 600), color: L.ink2 }}>{a.p}</div>
            <div style={{ position: 'absolute', right: 32, top: 28, ...type(36, 650), color: L.ink }}>{a.v}</div>
          </div>
        );
      })}
    </Module>
  );
};

// Cursor: macOS style arrow (black core white border + dual drop shadow), constant 40px on screen
const Cursor: React.FC<{ press: number }> = ({ press }) => (
  <svg viewBox="0 0 24 24" width={40} height={40} style={{
    position: 'absolute', left: -3, top: -2, overflow: 'visible',
    filter: 'drop-shadow(0 2px 2px rgba(12,26,58,0.35)) drop-shadow(0 8px 12px rgba(12,26,58,0.25))',
    transform: `scale(${(1 - 0.16 * press).toFixed(3)})`, transformOrigin: '3px 2px',
  }}>
    <path d="M4.5 2.5 L4.5 19.2 L8.9 15 L11.9 21.6 L14.9 20.3 L11.9 13.8 L18.2 13.4 Z" fill="#0d1324" stroke="#ffffff" strokeWidth={1.6} strokeLinejoin="round" />
  </svg>
);

export const CursorFlyover: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(frame);
  const scr = (f: number) => {
    const c = camAt(f);
    return { x: 960 - c.x * c.s, y: 540 - c.y * c.s };
  };
  const a = scr(frame + 0.5), b = scr(frame - 0.5);
  const cur = cursorAt(frame);
  const cx = 960 + (cur.x - cam.x) * cam.s;
  const cy = 540 + (cur.y - cam.y) * cam.s;
  // Press: depresses 1.5f before clickAt, then overshoot rebound
  let press = 0;
  let ripple = -1;
  for (let k = 0; k < 4; k++) {
    const pf = frame - clickAt(k);
    if (pf > -2 && pf < 8) press = Math.max(press, pf < 1 ? ramp(pf, -2, 3, EASE.swift) : 1 - ramp(pf, 1, 6, EASE.overshoot));
    if (pf >= 0 && pf < 18) ripple = pf / 18;
  }
  const intro = ramp(frame, 0, 14, EASE.out);
  return (
    <AbsoluteFill style={{ background: L.bg[1] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: -0.1 }} fill={{ x: 0.1, y: 1 }} />
      <SpeedBlur vx={a.x - b.x} vy={a.y - b.y} amount={0.09} max={8}>
        <div style={{
          position: 'absolute', left: 0, top: 0, width: WW, height: WH, transformOrigin: '0 0',
          transform: `translate(${(960 - cam.x * cam.s).toFixed(2)}px, ${(540 - cam.y * cam.s).toFixed(2)}px) scale(${cam.s.toFixed(5)})`,
          opacity: intro,
        }}>
          {/* Application window base plate */}
          <div style={{
            position: 'absolute', left: -40, top: -30, width: WW + 80, height: WH + 60, borderRadius: 48,
            background: `linear-gradient(180deg, #f4f7fb, #edf1f7)`, border: `1.5px solid ${L.line}`,
            boxShadow: `inset 0 2px 0 #ffffff, ${softShadow(40, { color: L.shadow, strength: 1.2 })}`,
          }} />
          {/* Top bar */}
          <div style={{ position: 'absolute', left: 60, top: 36, right: 60, height: 76, display: 'flex', alignItems: 'center' }}>
            <ShotcraftMark size={60} tone="light" />
            <div style={{ marginLeft: 18, fontFamily: BRAND.font, fontSize: 38, fontWeight: 700, letterSpacing: '0.03em', lineHeight: 1, color: BRAND.ink }}>{BRAND.name}</div>
            <div style={{ marginLeft: 72, display: 'flex', gap: 14 }}>
              {['Overview', 'Shots', 'Renders', 'Releases'].map((t, i) => (
                <div key={t} style={{ height: 56, padding: '0 26px', borderRadius: 16, display: 'flex', alignItems: 'center', ...type(28, i ? 520 : 650), color: i ? L.ink3 : L.ink, background: i ? 'transparent' : '#ffffff', boxShadow: i ? undefined : softShadow(3, { color: L.shadow }) }}>{t}</div>
              ))}
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 18 }}>
              <div style={{ height: 56, width: 360, borderRadius: 16, background: '#ffffff', border: `1.5px solid ${L.line}`, display: 'flex', alignItems: 'center', padding: '0 22px', boxSizing: 'border-box', ...type(26, 450), color: L.ink3 }}>Search shots  ⌘K</div>
              <div style={{ width: 56, height: 56, borderRadius: 28, background: 'linear-gradient(135deg, #ffd2a8, #ff9f7a)', border: '3px solid #ffffff', boxShadow: softShadow(3, { color: L.shadow }) }} />
            </div>
          </div>
          <Revenue f={frame} />
          <Users f={frame} />
          <Flags f={frame} />
          <Accounts f={frame} />
        </div>
      </SpeedBlur>
      {/* Click ripple + cursor (screen space, constant size) */}
      {ripple >= 0 && (
        <div style={{
          position: 'absolute', left: cx - 40, top: cy - 40, width: 80, height: 80, borderRadius: 40,
          border: `3px solid ${alpha(ACC, (1 - ripple) * 0.9)}`, background: alpha(ACC, (1 - ripple) * 0.12),
          transform: `scale(${(0.3 + EASE.out(ripple) * 1.2).toFixed(3)})`,
        }} />
      )}
      <div style={{ position: 'absolute', left: cx, top: cy, opacity: intro }}>
        <Cursor press={press} />
      </div>
    </AbsoluteFill>
  );
};
