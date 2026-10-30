// quad-split-parallel-scenes — Quad Split parallel montage
// Technique: Hard cut to 2x2 quad split; four quadrants run independent micro-scenes in parallel,
// with key beats staggered by 3–6 frames and zero transitions throughout, leveraging parallel density for information impact (inner content can be swapped; stagger schedule is the formula).
//
// Redesign (Ember — four live launch day scenes):
// - look = ember (warm black, orange, amber accents). Four quadrants show four events happening simultaneously during a video-shotcraft promo release, arranged in checkerboard brightness:
//   TL Cream: browser opens local preview (Launch film.) | TR Warm black: terminal running npx remotion render + whip-zoom to "promo.mp4 ready"
//   BL Solid orange: "Prompt. Render. Ship." three massive words slamming down (Swiss poster) | BR Latte: cursor clicks Approve -> Publish -> live notification pops up
//   8px warm black gap + 20px corner radius between panels like a bento launch board; typography resized for 1080p legibility (>=32px, main word 132px).
// - Stagger schedule (frames at 30fps) — any adjacent major events separated by >=3f, never simultaneous:
//     TL  tabs pop in at 6 / 11 / 16 / 21; 0–40 address bar typing; 44 page load (headline slides in); continuous inQuad slow push 1->1.1
//     TR  0–24 command typing; 27 / 33 two output lines; 37 final line appears + 37–47 whip zoom 1->1.85 (sin envelope blur)
//     BL  14 "Write."; 30 "Ship."; 49 "Repeat." (overshoot drop)
//     BR  4–14 card slides in; 14–25 cursor moves to Approve; 25 click; 27–33 button becomes Approved; 38–50 moves to Publish; 52 click; 56 toast pops up
//   Cursor blink periods are desynchronized (16f vs 14f + 5 phase).
// - Extended to 90f: 0–62 parallel bombardment, 62–90 all four panels settle on final poster hold (cursor blink and slow push only).
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, Grain, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const QUAD_SPLIT_PARALLEL_SCENES_DURATION = 90;

const L = LOOKS.ember;
const CREAM = '#f7eee4';
const LATTE = '#e9d7c4';
const ORANGE = L.accent;
const DARK = '#160d09';

// Quad geometry: outer margin = gap width 8px
const G = 8;
const QW = (1920 - 3 * G) / 2; // 948
const QH = (1080 - 3 * G) / 2; // 528
const QUADS = [
  { x: G, y: G },
  { x: 2 * G + QW, y: G },
  { x: G, y: 2 * G + QH },
  { x: 2 * G + QW, y: 2 * G + QH },
];

const blink = (f: number, period: number, phase = 0) => (Math.floor((f + phase) / (period / 2)) % 2 === 0 ? 1 : 0);
const typed = (s: string, f: number, a: number, b: number) => s.slice(0, Math.floor(ramp(f, a, b - a, EASE.linear) * s.length));

// Quad common: corner label (texture-level micro text)
const Corner: React.FC<{ n: string; label: string; color: string }> = ({ n, label, color }) => (
  <div style={{ position: 'absolute', left: 34, top: 28, ...type(20, 700, { caps: true }), letterSpacing: '0.2em', color, opacity: 0.7 }}>
    {n} — {label}
  </div>
);

// ───────────── TL: Browser opening local preview (localhost preview) ─────────────
const URL = 'localhost:3000/promo';
const TABS = ['Recipes', 'Gallery', 'Docs', 'Promo'];
const QuadTL: React.FC<{ f: number }> = ({ f }) => {
  const push = mix(1, 1.1, Math.pow(Math.min(1, f / 90), 2)); // inQuad slow push: ambient motion
  const load = ramp(f, 44, 14, EASE.snappy);
  return (
    <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 90% 90% at 30% 20%, #fffaf3 0%, ${CREAM} 55%, #efe2d3 100%)` }}>
      <div style={{
        position: 'absolute', left: 104, top: 112, width: 740, height: 390, borderRadius: 20, background: '#fffdf9', overflow: 'hidden',
        border: '1px solid rgba(60,30,10,0.10)', boxShadow: `inset 0 1px 0 #fff, 0 2px 4px rgba(60,30,10,0.08), 0 30px 60px -24px rgba(60,30,10,0.35)`,
        transform: `scale(${push})`, transformOrigin: '50% 90%',
      }}>
        {/* Tab bar */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 58, padding: '0 18px', background: '#f3e9de' }}>
          <div style={{ display: 'flex', gap: 8, alignSelf: 'center', marginRight: 10 }}>
            {['#ff6a52', '#ffbd3d', '#5fcf6a'].map((c) => <i key={c} style={{ width: 13, height: 13, borderRadius: 7, background: c }} />)}
          </div>
          {TABS.map((t, i) => {
            const k = ramp(f, 6 + i * 5, 9, EASE.overshoot);
            const active = i === TABS.length - 1;
            if (k <= 0) return null;
            return (
              <div key={t} style={{
                padding: '9px 20px 11px', borderRadius: '12px 12px 0 0', ...type(24, active ? 650 : 500),
                background: active ? '#fffdf9' : 'rgba(60,30,10,0.05)', color: active ? DARK : '#8c7867',
                transform: `scale(${k})`, transformOrigin: '50% 100%',
              }}>{t}</div>
            );
          })}
        </div>
        {/* Address bar */}
        <div style={{ margin: '16px 22px', height: 62, borderRadius: 31, background: '#f6eee5', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 14 }}>
          <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="#a08c7a" strokeWidth={2.2}><rect x={5} y={10} width={14} height={10} rx={2} /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          <span style={{ ...type(34, 550), color: DARK }}>{typed(URL, f, 0, 40)}</span>
          <span style={{ width: 3, height: 36, background: ORANGE, opacity: f < 44 ? blink(f, 16) : 0, marginLeft: -10 }} />
        </div>
        {/* Page: loads at 44f, headline slides in from below */}
        <div style={{ position: 'absolute', left: 44, top: 168, right: 44 }}>
          <div style={{ height: 6, borderRadius: 3, background: ORANGE, width: `${load * 100}%`, opacity: 1 - ramp(f, 56, 6, EASE.linear), marginBottom: 20 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, opacity: load }}>
            <ShotcraftMark size={30} tone="light" />
            <span style={{ fontFamily: BRAND.font, fontSize: 24, fontWeight: 700, letterSpacing: '0.03em', lineHeight: 1, color: DARK }}>{BRAND.name}</span>
          </div>
          <div style={{ overflow: 'hidden', marginTop: 8 }}>
            <div style={{ ...type(96, 850), color: DARK, transform: `translateY(${(1 - load) * 110}%)` }}>Launch film.</div>
          </div>
          <div style={{ ...type(32, 500), color: '#7a6555', marginTop: 12, opacity: ramp(f, 50, 10, EASE.out) }}>{PITCH.en.taglines[0]}</div>
        </div>
      </div>
      <Corner n="01" label="Web" color="#9b8a7a" />
    </div>
  );
};

// ───────────── TR: Terminal render + whip zoom ─────────────
const CMD = 'npx remotion render';
const QuadTR: React.FC<{ f: number }> = ({ f }) => {
  const zip = ramp(f, 37, 10, EASE.smooth);
  const zoom = mix(1, 1.85, zip);
  const blur = 5 * Math.sin(Math.PI * zip);
  const old = 1 - 0.92 * zip; // Early lines fade to background during whip zoom
  const line = (at: number) => ramp(f, at, 5, EASE.out);
  const mono = (s: number, w = 500): React.CSSProperties => ({ ...type(s, w, { mono: true }), whiteSpace: 'pre' });
  return (
    <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 80% 90% at 70% 10%, #2a1810 0%, ${DARK} 60%, #0d0705 100%)` }}>
      <div style={{
        position: 'absolute', left: 80, top: 100, width: 800,
        transform: `translateY(${(-40 * zip).toFixed(2)}px) scale(${zoom})`, transformOrigin: '0px 225px', filter: blur > 0.2 ? `blur(${blur.toFixed(2)}px)` : undefined,
      }}>
        <div style={{ ...mono(36), color: L.ink, opacity: old }}>
          <span style={{ color: ORANGE }}>$ </span>{typed(CMD, f, 0, 24)}
          <span style={{ display: 'inline-block', width: 20, height: 38, verticalAlign: '-6px', background: L.ink, opacity: f < 27 ? blink(f, 14, 5) : 0 }} />
        </div>
        <div style={{ ...mono(32), color: L.ink2, marginTop: 30, opacity: line(27) * old, transform: `translateX(${(1 - line(27)) * -16}px)` }}>
          <span style={{ color: L.accent2 }}>✓</span> bundle     1.8s
        </div>
        <div style={{ ...mono(32), color: L.ink2, marginTop: 14, opacity: line(33) * old, transform: `translateX(${(1 - line(33)) * -16}px)` }}>
          <span style={{ color: L.accent2 }}>✓</span> frames     900/900
        </div>
        <div style={{ ...mono(40, 700), color: L.ink, marginTop: 36, opacity: line(37) }}>
          <span style={{ color: ORANGE, textShadow: `0 0 18px ${alpha(ORANGE, 0.8)}` }}>●</span> promo.mp4 <span style={{ color: L.accent2 }}>ready</span>
        </div>
      </div>
      <Corner n="02" label="Render" color={L.ink3} />
    </div>
  );
};

// ───────────── BL: Three words slamming down ─────────────
const WORDS: Array<[string, number]> = [['Prompt.', 14], ['Render.', 30], ['Ship.', 49]];
const QuadBL: React.FC<{ f: number }> = ({ f }) => (
  <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(150deg, #ff8340 0%, ${ORANGE} 45%, #e8541c 100%)` }}>
    <div style={{ position: 'absolute', left: 64, top: 70 }}>
      {WORDS.map(([w, at], i) => {
        const s = Math.min(1, Math.max(0, (f - at) / 8));
        if (s <= 0) return <div key={w} style={{ height: 132 * 0.98 }} />;
        const y = (1 - EASE.overshoot(s)) * -70;
        const last = i === WORDS.length - 1;
        return (
          <div key={w} style={{
            ...type(132, 900), lineHeight: 0.98, color: last ? CREAM : DARK, opacity: Math.min(1, s * 3),
            transform: `translateY(${y.toFixed(2)}px) scale(${mix(1.12, 1, EASE.snappy(s)).toFixed(4)})`, transformOrigin: '0% 100%',
          }}>{w}</div>
        );
      })}
    </div>
    <Corner n="03" label="Brand" color={DARK} />
  </div>
);

// ───────────── BR: Approval -> Publish -> Live notification ─────────────
// Cursor anchors (quad coordinates, tip)
const P_START: [number, number] = [860, 470];
const P_APPROVE: [number, number] = [270, 318];
const P_PUBLISH: [number, number] = [560, 318];
const qBez = (a: number[], b: number[], c: number[], t: number): [number, number] => {
  const u = 1 - t;
  return [u * u * a[0] + 2 * u * t * b[0] + t * t * c[0], u * u * a[1] + 2 * u * t * b[1] + t * t * c[1]];
};
const QuadBR: React.FC<{ f: number }> = ({ f }) => {
  const slide = ramp(f, 4, 10, EASE.snappy);
  const m1 = ramp(f, 14, 11, EASE.swift);
  const m2 = ramp(f, 38, 12, EASE.swift);
  const p = m2 > 0 ? qBez(P_APPROVE, [470, 250], P_PUBLISH, m2) : qBez(P_START, [620, 520], P_APPROVE, m1);
  const press = (at: number) => Math.sin(Math.PI * Math.min(1, Math.max(0, (f - at) / 5)));
  const approved = ramp(f, 27, 6, EASE.snappy);
  const published = f >= 54;
  const toast = ramp(f, 56, 10, EASE.overshoot);
  return (
    <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 90% 90% at 70% 20%, #f4e6d6 0%, ${LATTE} 60%, #dcc5ae 100%)` }}>
      {/* Release approval card */}
      <div style={{
        position: 'absolute', left: 120, top: 120, width: 620, padding: '30px 34px', borderRadius: 22, background: '#fffaf4',
        border: '1px solid rgba(60,30,10,0.10)', boxShadow: '0 2px 4px rgba(60,30,10,0.08), 0 26px 50px -22px rgba(60,30,10,0.4)',
        transform: `translateX(${(1 - slide) * -60}px)`, opacity: slide,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ ...type(40, 750), color: DARK }}>Launch film · cut 3</div>
          <div style={{ marginLeft: 'auto', display: 'flex' }}>
            {['#e8541c', '#3d5a80', '#c4552d'].map((c, i) => (
              <div key={c} style={{ width: 40, height: 40, borderRadius: 20, background: c, border: '3px solid #fffaf4', marginLeft: i ? -12 : 0, ...type(18, 700), color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{'MJR'[i]}</div>
            ))}
          </div>
        </div>
        <div style={{ ...type(30, 500), color: '#7a6555', marginTop: 10 }}>12 shots · 2 reviewers</div>
        <div style={{ display: 'flex', gap: 16, marginTop: 30 }}>
          <div style={{
            width: 260, height: 70, borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
            border: `2px solid ${approved > 0.5 ? '#2f9e5b' : 'rgba(60,30,10,0.22)'}`, background: approved > 0.5 ? 'rgba(47,158,91,0.12)' : 'transparent',
            ...type(32, 650), color: approved > 0.5 ? '#237a46' : DARK, transform: `scale(${1 - 0.06 * press(25)})`,
          }}>{approved > 0.5 ? 'Approved ✓' : 'Approve'}</div>
          <div style={{
            width: 280, height: 70, borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: published ? ORANGE : DARK, ...type(32, 700), color: published ? L.onAccent : CREAM,
            opacity: mix(0.45, 1, approved), transform: `scale(${1 - 0.06 * press(52)})`,
          }}>{published ? 'Published' : 'Publish'}</div>
        </div>
      </div>
      {/* Live notification: closing accent */}
      {toast > 0 && (
        <div style={{
          position: 'absolute', right: 56, bottom: 44, padding: '20px 26px', borderRadius: 18, background: DARK, display: 'flex', alignItems: 'center', gap: 16,
          boxShadow: '0 24px 50px -18px rgba(30,12,4,0.7)', transform: `translateY(${(1 - toast) * 40}px) scale(${mix(0.85, 1, toast)})`, opacity: Math.min(1, toast * 2),
        }}>
          <span style={{ width: 16, height: 16, borderRadius: 8, background: ORANGE, boxShadow: `0 0 14px ${ORANGE}` }} />
          <span style={{ ...type(32, 650), color: CREAM }}>Live · <span style={{ fontVariantNumeric: 'tabular-nums' }}>{Math.round(3214 * ramp(f, 56, 30, EASE.snappy)).toLocaleString('en-US')}</span> views</span>
        </div>
      )}
      {/* Cursor */}
      {f >= 10 && f < 76 && (
        <svg width={34} height={46} viewBox="-1 -1 18 26" style={{
          position: 'absolute', left: p[0], top: p[1], overflow: 'visible', opacity: ramp(f, 10, 4, EASE.out) * (1 - ramp(f, 68, 8, EASE.exit)),
          transform: `scale(${1 - 0.18 * Math.max(press(25), press(52))})`, transformOrigin: '0 0', filter: 'drop-shadow(0 3px 5px rgba(40,20,8,0.4))',
        }}>
          <path d="M0 0 L0 20.5 L4.9 15.9 L8.1 23.4 L11.4 22 L8.3 14.7 L14.8 14.7 Z" fill={DARK} stroke="#fff" strokeWidth={1.6} strokeLinejoin="round" />
        </svg>
      )}
      <Corner n="04" label="Review" color="#8f735c" />
    </div>
  );
};

export const QuadSplitParallelScenes: React.FC = () => {
  const f = useCurrentFrame();
  const scenes = [<QuadTL f={f} />, <QuadTR f={f} />, <QuadBL f={f} />, <QuadBR f={f} />];
  return (
    <AbsoluteFill style={{ fontFamily: FONT.sans, overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.5 }} fill={null} grain={0} vignette={0.3} />
      {QUADS.map((q, i) => (
        <div key={i} style={{
          position: 'absolute', left: q.x, top: q.y, width: QW, height: QH, borderRadius: 20, overflow: 'hidden',
          boxShadow: `inset 0 1px 0 ${alpha('#ffffff', i === 1 ? 0.06 : 0.35)}`,
        }}>
          {scenes[i]}
        </div>
      ))}
      <Grain opacity={0.06} blend="overlay" />
    </AbsoluteFill>
  );
};
