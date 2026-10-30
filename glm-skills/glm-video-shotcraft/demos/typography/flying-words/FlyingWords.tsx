// flying-words — depth tunnel typography: keywords spawn at deep z-distance, flying toward camera along z-axis,
// opacity follows lifecycle curve [0,1,0.5,0.2,0]; stationary camera, deterministic spawn, seamless 2-cycle loop.
//
// Redesign (deep blue night: lightspeed tunnel + foreground wordmark):
// - look = midnight (dark blue-black, electric blue). Native 1920x1080 rendering with explicit perspective math:
//   s = P/(P-z) (P=4400, z -7000->+3200), allowing per-element screen-velocity effects.
// - Three depth layers: 1) Tunnel walls — 10 hairline elliptical rings advancing toward camera (tunnel structure);
//   2) Lightspeed streaks — 56 radial particle streaks (length proportional to screen velocity);
//   3) 22 capability keywords: golden angle layout, distance scale/fog, directional 6-layer text-shadow trails near camera
//   plus defocus on near-camera flyby.
// - Typographic hierarchy: cool white sans 700 base, 6 serif italic keywords, 4 electric blue accented words with bloom.
// - Vanishing point: center electric blue glow breathes 2 cycles per video, tunnel rolls +/-2.5 deg along sin(2*pi*t).
//   Continuous motion with seamless cyclic roll.
// - Foreground: lifecycle curve dips to 0.5 to yield to centered static mark (mono kicker + 112px title +
//   radial vignette; keywords passing through center dim to 20%), demonstrating background viability.
// - Brand: kicker = ShotcraftMark + video-shotcraft, title = brand motto; keywords reflect shotcraft capabilities.
//
// Timeline: t = frame / DURATION (seamless cyclic loop); CYCLES = 2.
//   Per-element u = (t*CYCLES + phase) mod 1: 0 distant spawn -> 0.25 full brightness -> 0.6 mid dip -> 1 exit.
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { FONT } from '../../_fixtures/Polish';
import { LOOKS, SERIF, Stage, alpha } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const FLYING_WORDS_DURATION = 180; // 6000ms @30fps

const L = LOOKS.midnight;
const CYCLES = 2; // Integer cycles for seamless loop

// Capability keyword vocabulary (customizable per project)
const WORDS = ['Timeline', 'Keyframes', 'Easing', 'Camera', 'Depth', 'Parallax', 'Motion blur', 'Springs',
  'Layers', 'Shot cards', 'Typography', 'Lighting', 'Grain', 'Remotion', 'Beat grid', 'Stagger',
  'Transitions', 'Color', 'Workbench', 'Audio sync', 'Storyboard', 'Orbit'];
const N = WORDS.length;
const ACCENT = new Set([3, 7, 12, 19]); // Camera / Springs / Grain / Audio sync
const SERIF_IDX = new Set([1, 5, 10, 14, 17, 21]);
const INKS = ['#f2f5ff', '#c3cbe2', '#8a95b5'];

const P = 4400; // Perspective distance
const Z0 = -7000;
const Z1 = 3200;
const CX = 960;
const CY = 540;

const rand = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

const ITEMS = WORDS.map((w, i) => {
  // Golden-angle distribution avoiding center cluster
  const a = i * 2.39996 + rand(i * 7 + 1) * 0.8;
  const r = 330 + rand(i * 13 + 2) * 660;
  const accent = ACCENT.has(i);
  return {
    text: w, accent, serif: SERIF_IDX.has(i),
    size: 64 + rand(i + 3) * 56,
    color: accent ? '#86a8ff' : INKS[Math.floor(rand(i + 5) * 3)],
    x: Math.cos(a) * r, y: Math.sin(a) * r * 0.6, rz: (rand(i + 21) - 0.5) * 12, ph: i / N,
  };
});

const DUST = Array.from({ length: 56 }, (_, i) => {
  const a = i * 2.39996 + rand(i * 5 + 77) * 1.2;
  const r = 180 + rand(i * 3 + 91) * 1500;
  return { x: Math.cos(a) * r, y: Math.sin(a) * r * 0.62, ph: rand(i * 9 + 13), w: 1 + rand(i + 50) * 1.6 };
});

const RINGS = Array.from({ length: 10 }, (_, k) => ({ ph: k / 10 }));

// Lifecycle opacity curve [0,1,0.5,0.2,0] piecewise linear
const OP = [0, 1, 0.5, 0.2, 0];
const OT = [0, 0.25, 0.6, 0.85, 1];
const curve = (u: number) => {
  for (let k = 0; k < 4; k++) {
    if (u <= OT[k + 1]) return OP[k] + ((OP[k + 1] - OP[k]) * (u - OT[k])) / (OT[k + 1] - OT[k]);
  }
  return 0;
};

// Linear z advancement; drift = 0.5 + u*1.35; roll = tunnel angular rotation
const project = (x: number, y: number, u: number, roll: number, drift = true) => {
  const z = Z0 + (Z1 - Z0) * u;
  const d = drift ? 0.5 + u * 1.35 : 1;
  const s = P / (P - z);
  const c = Math.cos(roll), sn = Math.sin(roll);
  const rx = x * c - y * sn, ry = x * sn + y * c;
  return { sx: CX + rx * d * s, sy: CY + ry * d * s, s };
};

export const FlyingWords: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FLYING_WORDS_DURATION;
  const roll = (2.5 * Math.PI / 180) * Math.sin(t * Math.PI * 2);
  const du = CYCLES / FLYING_WORDS_DURATION; // Delta u per frame
  const glowB = 0.82 + 0.14 * Math.sin(t * Math.PI * 4);

  return (
    <AbsoluteFill>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.5 }} fill={null} intensity={0.5} vignette={0.7} grain={0.08}>
        {/* Tunnel terminus glow: breathes twice per loop */} 
        <div style={{
          position: 'absolute', left: CX - 520, top: CY - 360, width: 1040, height: 720, borderRadius: '50%', opacity: glowB,
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.light, 0.42)} 0%, ${alpha(L.light, 0.12)} 38%, ${alpha(L.light, 0)} 70%)`,
        }} />
      </Stage>

      {/* 1. Tunnel walls + 2. Lightspeed streaks */} 
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        {RINGS.map((rg, k) => {
          const u = (t * CYCLES + rg.ph) % 1;
          const p = project(0, 0, u, roll, false);
          const rx = 1150 * p.s;
          const op = Math.min(1, u / 0.3) * (1 - Math.min(1, Math.max(0, (u - 0.55) / 0.3)));
          if (op <= 0.01) return null;
          return (
            <ellipse key={`r${k}`} cx={CX} cy={CY} rx={rx} ry={rx * 0.6} fill="none"
              stroke={L.accent} strokeOpacity={op * 0.16} strokeWidth={1 + p.s * 0.8}
              transform={`rotate(${(roll * 180) / Math.PI} ${CX} ${CY})`} />
          );
        })}
        {DUST.map((d, i) => {
          const u = (t * CYCLES + d.ph) % 1;
          const u0 = Math.max(0, u - du * 2.6);
          const a = project(d.x, d.y, u0, roll);
          const b = project(d.x, d.y, u, roll);
          const op = curve(u) * 0.75;
          if (op <= 0.01) return null;
          return (
            <line key={`d${i}`} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} stroke="#cfdcff" strokeOpacity={op}
              strokeWidth={d.w * Math.min(2.4, b.s)} strokeLinecap="round" />
          );
        })}
      </svg>

      {/* 3. Keywords: distant fog, mid clarity, near directional trail + blur */} 
      {ITEMS.map((it, i) => {
        const u = (t * CYCLES + it.ph) % 1;
        const p = project(it.x, it.y, u, roll);
        const q = project(it.x, it.y, Math.max(0, u - du), roll);
        const vx = p.sx - q.sx, vy = p.sy - q.sy; // Screen velocity px/frame
        // Keywords dimmed to 20% within foreground title ellipse zone
        const k = ((p.sx - CX) / 760) ** 2 + ((p.sy - CY) / 190) ** 2;
        const occl = k < 1 ? 0.2 + 0.8 * k * k : 1;
        const op = curve(u) * occl;
        if (op <= 0.005) return null;
        const fog = u < 0.22 ? (1 - u / 0.22) * 2.2 : 0;
        const near = u > 0.86 ? (u - 0.86) * 60 : 0;
        const blur = fog + near;
        const sp = Math.hypot(vx, vy);
        const trail = sp > 6
          ? [1, 2, 3, 4, 5, 6].map((j) => {
            const k = (j / 6) * 0.9 / p.s;
            return `${(-vx * k).toFixed(1)}px ${(-vy * k).toFixed(1)}px ${(j * 0.8).toFixed(1)}px ${alpha(it.color, 0.2 - j * 0.026)}`;
          }).join(', ')
          : '';
        const glowS = it.accent ? `0 0 18px ${alpha(L.accent, 0.55)}, 0 0 48px ${alpha(L.accent, 0.3)}` : '';
        return (
          <div key={i} style={{
            position: 'absolute', left: p.sx, top: p.sy, whiteSpace: 'nowrap', lineHeight: 1,
            transform: `translate(-50%,-50%) scale(${p.s.toFixed(4)}) rotate(${it.rz + (roll * 180) / Math.PI}deg)`,
            fontFamily: it.serif ? SERIF : FONT.sans, fontStyle: it.serif ? 'italic' : undefined,
            fontWeight: it.serif ? 500 : 700, fontSize: it.size, letterSpacing: it.serif ? '-0.01em' : '-0.03em',
            color: it.color, opacity: op,
            textShadow: [glowS, trail].filter(Boolean).join(', ') || undefined,
            filter: blur > 0.05 ? `blur(${(blur / Math.max(0.6, p.s)).toFixed(2)}px)` : undefined,
          }}>
            {it.text}
          </div>
        );
      })}

      {/* Foreground title: static for seamless loop, separated by subtle radial vignette */}
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div style={{
          position: 'absolute', left: CX - 760, top: CY - 260, width: 1520, height: 520, borderRadius: '50%',
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha('#04060d', 0.7)} 0%, ${alpha('#04060d', 0.38)} 45%, ${alpha('#04060d', 0)} 72%)`,
        }} />
        <div style={{ position: 'relative', textAlign: 'center' }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18,
            fontFamily: FONT.mono, fontSize: 30, letterSpacing: '0.3em', color: L.accent, marginBottom: 30,
          }}>
            <ShotcraftMark size={42} tone="dark" />
            <span>{BRAND.name}</span>
          </div>
          <div style={{
            fontFamily: FONT.sans, fontSize: 112, fontWeight: 700, letterSpacing: '-0.045em', lineHeight: 1, color: L.ink,
            textShadow: `0 4px 40px ${alpha('#000', 0.6)}`,
          }}>
            {PITCH.en.motto}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
