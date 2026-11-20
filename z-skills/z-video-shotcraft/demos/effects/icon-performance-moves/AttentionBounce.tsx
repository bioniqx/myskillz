// Attention bounce (attention-bounce) — macOS Dock vocabulary: Icon bounces in place repeatedly to grab attention, leaping higher each time as camera draws closer.
//
// Second-round redesign (Afternoon window light · Calendar app icon):
// - look = sand (warm beige light · terracotta accent). Background wall receives two diagonal venetian blind sunbeams (lifestyle afternoon vibe); lower screen edge features a
//   continuous frosted cream Dock spanning full width, trimmed by viewport edges; hero is a 360px video-shotcraft app icon — cream squircle base hosting
//   a "Mirror Cut" emblem (viewfinder frame + amber diagonal cut), far more distinctive than generic bell icon. Flanking neighbor icons (sage / slate blue / sand /
//   charcoal) are subdued in low-saturation tones.
// - Bouncing follows physical projectile curves: 4 jump heights at 0.35 -> 0.6 -> 0.85 -> 1.2x icon height, duration proportional to sqrt(height) (14 / 18 / 22 / 26f),
//   vertically stretched in air by velocity, 2f contact squash on impact (heavier with each bounce, final jump reaches 1.2x width by 0.8x height), landing creates glass ripples + droplet splashes.
// - "Attracting focus": Starting from second bounce, neighbor icons gradually defocus and fade (rack focus, background recedes), camera smoothly zooms in 8% during highest jump.
// - Settling: Damped rebound stabilizes -> Badge pops out on same frame, Dock running indicator dot illuminates below -> Utility panel spring-unfolds from top-right corner of icon
//   (parent arrives first, rows staggered by 3f), panel text >= 32px, ending frame forms a complete "New in Shotcraft" poster (launch film storyboard timeline).
//
// Timeline (30fps, total 156f):
//   0–12    Preparation: Dock and icon present on screen, subtle camera push; 6–12f crouch anticipation
//   12–100  4 increasing bounces (jump at 12 / 28 / 48 / 72f, final landing at 100f); neighbors defocus 30–96f; camera pushes 8% closer 72–90f
//   100–110 Settling rebound; badge pops out at 100f; running indicator illuminates
//   106–132 Panel spring unfolds (106f), three rows stagger entry from 114f onward
//   132–156 Hold: Subtle camera push + gently shifting window light, clean settlement
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const ATTENTION_BOUNCE_DURATION = 156; // 5.2s

const L = LOOKS.sand;
const ICON = 360; // Icon dimension (half-screen scale)
const RAD = 82; // squircle corner radius
const CX = 600; // Hero icon center x
const GROUND = 960; // Icon resting baseline y (inside Dock)
const DOCK_TOP = GROUND - ICON - 30;

// 4 Bounces: Jump frame, air duration, peak height (relative to icon height); duration proportional to sqrt(height) (projectile under uniform gravity)
const JUMPS = [
  { start: 12, dur: 14, peak: 0.35 },
  { start: 28, dur: 18, peak: 0.6 },
  { start: 48, dur: 22, peak: 0.85 },
  { start: 72, dur: 26, peak: 1.2 },
];
const LAND = 100; // Final landing frame (72 + 26 + 2f contact buffer)
const LAND_FINAL = JUMPS[3].start + JUMPS[3].dur; // 98

const hs = (n: number) => {
  const x = Math.sin(n * 91.345 + 47.853) * 43758.5453;
  return x - Math.floor(x);
};

// Hero body kinematic state: Altitude y, vertical velocity (normalized), contact squash factor
const body = (f: number) => {
  let y = 0, v = 0, squash = 0;
  JUMPS.forEach((j, ji) => {
    const t = (f - j.start) / j.dur;
    if (t > 0 && t < 1) {
      y = j.peak * ICON * 4 * t * (1 - t);
      v = 1 - 2 * t; // +1 jump takeoff velocity -> 0 apex -> -1 impact touchdown velocity
    }
    // 2f landing contact: Squash factor scales with jump height (final jump 0.2 = width 1.2x, height 0.8x)
    const land = j.start + j.dur;
    const q = 0.1 + 0.1 * (ji / 3);
    if (ji < 3 && f >= land && f < land + 2) squash = q * (1 - (f - land) / 2) + q * 0.4;
  });
  // Crouch anticipation before takeoff
  if (f >= 6 && f < 12) squash = 0.08 * EASE.out((f - 6) / 6);
  // Final landing settle: Squash -> Rebound -> Rest (damped cosine)
  if (f >= LAND_FINAL) {
    const k = f - LAND_FINAL;
    squash = 0.2 * Math.exp(-k * 0.38) * Math.cos(k * 0.72);
  }
  return { y, v, squash };
};

// Landing frame sequence (used for ripples / droplet splashes)
const LANDINGS = JUMPS.map((j, i) => ({ at: j.start + j.dur, k: i }));

// ───────────── App Icon ─────────────

// video-shotcraft app icon: Cream squircle + bright-base "Mirror Cut" emblem (emblem itself has zero glow / drop shadow, soft light covers icon face)
const ShotcraftIcon: React.FC<{ size: number }> = ({ size }) => (
  <div style={{
    position: 'absolute', inset: 0, borderRadius: RAD * (size / ICON), overflow: 'hidden',
    background: 'linear-gradient(180deg, #fffaf2 0%, #f6ecdd 100%)',
    boxShadow: 'inset 0 2px 0 rgba(255,255,255,0.95), inset 0 -6px 14px rgba(120,80,40,0.12), inset 0 0 0 1px rgba(70,45,20,0.08)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    {/* Emblem visible bounds x 16–120 / 128, center shifted right by 4 units: shift left to center on icon */}
    <ShotcraftMark size={size * 0.62} tone="light" style={{ transform: `translateX(${(-size * 0.62 * 4 / 128).toFixed(2)}px)` }} />
    {/* Top specular rim */}
    <div style={{
      position: 'absolute', inset: 0,
      background: 'radial-gradient(ellipse closest-side at 38% 0%, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0) 100%)',
    }} />
  </div>
);

// Neighbor icons: Low-saturation color blocks + simple glyphs
const Neighbor: React.FC<{ kind: number }> = ({ kind }) => {
  const bgs = [
    'linear-gradient(180deg, #9db59a 0%, #6f8f70 100%)',
    'linear-gradient(180deg, #6b7e9c 0%, #44567a 100%)',
    'linear-gradient(180deg, #e9dcc4 0%, #cdb894 100%)',
    'linear-gradient(180deg, #4a4741 0%, #2b2925 100%)',
  ];
  const ink = kind === 2 ? '#6d5d4c' : '#fbf6ef';
  return (
    <div style={{
      position: 'absolute', inset: 0, borderRadius: RAD, overflow: 'hidden', background: bgs[kind],
      boxShadow: 'inset 0 2px 0 rgba(255,255,255,0.35), inset 0 -6px 14px rgba(0,0,0,0.12)',
    }}>
      <svg width={ICON} height={ICON} viewBox="0 0 360 360" style={{ position: 'absolute', inset: 0 }}>
        <g fill="none" stroke={ink} strokeWidth={20} strokeLinecap="round" strokeLinejoin="round">
          {kind === 0 && <path d="M110 250 C 110 150, 190 100, 260 100 C 260 190, 210 250, 110 250 Z M110 250 L 200 160" />}
          {kind === 1 && <g><rect x={90} y={120} width={180} height={130} rx={18} /><path d="M95 130 L180 195 L265 130" /></g>}
          {kind === 2 && <g><rect x={95} y={130} width={170} height={120} rx={22} /><circle cx={180} cy={190} r={36} /><path d="M140 130 L150 108 L210 108 L220 130" /></g>}
          {kind === 3 && <g><path d="M150 240 L150 110 L250 92 L250 222" /><circle cx={128} cy={242} r={24} fill={ink} /><circle cx={228} cy={224} r={24} fill={ink} /></g>}
        </g>
      </svg>
    </div>
  );
};

// ───────────── Utility Panel ─────────────

// Panel content: Launch film storyboard timeline (timecode / shot / technique)
const SLOTS = [
  { time: '00:00', title: 'Hero push-in', meta: '2.5D', c: '#3d5a80' },
  { time: '00:04', title: 'Beat-synced cuts', meta: '12 cuts', c: '#7d9a7e' },
  { time: '00:09', title: 'Logo sting', meta: '+ SFX', c: L.accent },
];

export const AttentionBounce: React.FC = () => {
  const f = useCurrentFrame();
  const { y, v, squash } = body(f);
  const stretch = Math.abs(v) * 0.1 * (y > 0 ? 1 : 0);
  const sx = 1 + squash - stretch * 0.5;
  const sy = 1 - squash + stretch;
  const lift = y / (1.2 * ICON); // 0 resting on floor -> 1 maximum jump height

  // Camera: Subtle opening push 1->1.015; highest jump smoothly pushes to 1.08; hold section adds further 1%
  const zoom = 1 + 0.015 * ramp(f, 0, 72, EASE.smooth) + 0.065 * ramp(f, 72, 18, EASE.smooth) + 0.012 * ramp(f, 110, 46, EASE.smooth);
  const focus = { x: CX + 120, y: 700 };

  // Neighbor rack focus defocus
  const defocus = ramp(f, 30, 66, EASE.swift);

  // Badge, running indicator dot, utility panel
  const badge = f >= LAND ? springAt(f, LAND, { damping: 11, stiffness: 260 }) : 0;
  const dot = ramp(f, LAND + 2, 8, EASE.out);
  const panel = f >= 106 ? springAt(f, 106, { damping: 17, stiffness: 150 }) : 0;
  const row = (i: number) => ramp(f, 114 + i * 3, 16, EASE.snappy);

  // Subtle shifting window light
  const shaft = Math.sin(f / 70) * 14;

  return (
    <AbsoluteFill style={{ background: L.bg[1] }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.05 }} fill={{ x: 0.85, y: 0.2 }} style={{ background: 'linear-gradient(180deg, #e6d9c6 0%, #dccdb8 60%, #d3c3ac 100%)' }}>
        {/* Venetian blind sunbeams: Two diagonal light bars projected across background wall */}
        <div style={{
          position: 'absolute', left: -400 + shaft, top: -200, width: 2800, height: 1500, transform: 'rotate(-24deg)', transformOrigin: '0 0',
          background: `repeating-linear-gradient(90deg, transparent 0px, transparent 250px, ${alpha('#fffaf0', 0.85)} 280px, ${alpha('#fff6e6', 0.7)} 400px, transparent 430px, transparent 620px)`,
          filter: 'blur(6px)', opacity: 0.9, mixBlendMode: 'soft-light',
          WebkitMaskImage: 'linear-gradient(180deg, #000 0%, #000 45%, transparent 75%)', maskImage: 'linear-gradient(180deg, #000 0%, #000 45%, transparent 75%)',
        }} />
      </Stage>

      {/* Camera layer */}
      <AbsoluteFill style={{ transform: `scale(${zoom})`, transformOrigin: `${focus.x}px ${focus.y}px` }}>
        {/* Dock: Frosted cream glass bar spanning full width, trimmed by viewport bounds */}
        <div style={{
          position: 'absolute', left: -80, right: -80, top: DOCK_TOP, height: ICON + 64, borderRadius: 72,
          background: 'linear-gradient(180deg, rgba(255,251,244,0.72) 0%, rgba(250,242,230,0.6) 100%)',
          boxShadow: `inset 0 1.5px 0 rgba(255,255,255,0.95), inset 0 0 0 1px rgba(70,45,20,0.07), ${softShadow(30, { color: L.shadow, strength: 1.1 })}`,
        }} />

        {/* Neighbor icons (rack focus defocus) */}
        {[CX - 420, CX + 420, CX + 840, CX + 1260].map((x, i) => (
          <div key={i} style={{
            position: 'absolute', left: x - ICON / 2, top: GROUND - ICON, width: ICON, height: ICON,
            filter: `blur(${(defocus * 7).toFixed(2)}px) saturate(${1 - 0.3 * defocus})`, opacity: 1 - 0.4 * defocus,
            boxShadow: softShadow(8, { color: L.shadow }), borderRadius: RAD,
          }}>
            <Neighbor kind={i === 0 ? 0 : i} />
          </div>
        ))}

        {/* Impact ripples + droplet splashes */}
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
          {LANDINGS.map(({ at, k }) => {
            const t = (f - at) / 18;
            if (t <= 0 || t >= 1) return null;
            const e = EASE.snappy(t);
            const strength = 0.5 + k * 0.17;
            return (
              <g key={at}>
                <ellipse cx={CX} cy={GROUND + 6} rx={mix(ICON * 0.48, ICON * (0.85 + 0.15 * k), e)} ry={mix(14, 34 + 6 * k, e)}
                  fill="none" stroke={L.ink2} strokeWidth={mix(10, 3, e)} opacity={(1 - t) * strength * 0.3} style={{ filter: 'blur(2.5px)' }} />
                {Array.from({ length: 4 }, (_, i) => {
                  const side = i % 2 ? 1 : -1;
                  const dx = side * (ICON * 0.5 + (40 + 60 * hs(k * 7 + i)) * e * (0.7 + k * 0.25));
                  const dy = -(30 + 40 * hs(k * 11 + i)) * 4 * t * (1 - t) * (0.6 + k * 0.2);
                  return <circle key={i} cx={CX + dx} cy={GROUND - 4 + dy} r={4 + 3 * hs(i + k)} fill={L.ink3} opacity={(1 - t) * 0.7} />;
                })}
              </g>
            );
          })}
        </svg>

        {/* Contact shadow: Small and crisp near floor (fades rapidly with altitude) + large and diffuse at peak height */}
        <div style={{
          position: 'absolute', left: CX - ICON * 0.42 * sx * (1 - lift * 0.4), width: ICON * 0.84 * sx * (1 - lift * 0.4),
          top: GROUND - 10, height: 22, borderRadius: '50%', background: alpha(L.shadow, 0.34), filter: 'blur(7px)', opacity: Math.max(0, 1 - lift * 1.8),
        }} />
        <div style={{
          position: 'absolute', left: CX - ICON * 0.52 * (1 - lift * 0.25), width: ICON * 1.04 * (1 - lift * 0.25),
          top: GROUND - 16, height: 46, borderRadius: '50%', background: alpha(L.shadow, 0.16), filter: 'blur(16px)', opacity: 1 - lift * 0.6,
        }} />

        {/* Running status indicator dot */}
        <div style={{
          position: 'absolute', left: CX - 7, top: GROUND + 16, width: 14, height: 14, borderRadius: 7,
          background: L.ink2, opacity: dot, transform: `scale(${dot})`,
        }} />

        {/* Hero icon (squashed and stretched relative to bottom center) */}
        <div style={{
          position: 'absolute', left: CX - ICON / 2, top: GROUND - ICON - y, width: ICON, height: ICON,
          transform: `scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`, transformOrigin: '50% 100%',
          borderRadius: RAD, boxShadow: softShadow(10 + lift * 40, { color: L.shadow, strength: 1.2 }),
        }}>
          <ShotcraftIcon size={ICON} />
          {/* Notification badge */}
          {badge > 0 && (
            <div style={{
              position: 'absolute', right: -34, top: -34, width: 104, height: 104, borderRadius: 52,
              background: 'linear-gradient(180deg, #e0603a 0%, #c4452a 100%)', color: '#fff8f0',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              ...type(56, 700), letterSpacing: '-0.02em',
              boxShadow: `0 0 0 7px ${L.bg[0]}, 0 10px 22px ${alpha('#7a2a10', 0.35)}`, transform: `scale(${badge})`,
            }}>1</div>
          )}
        </div>

        {/* Utility panel: Spring unfolds from top-right corner of icon */}
        {panel > 0.001 && (
          <div style={{
            position: 'absolute', left: 880, top: 148, width: 860, height: 392, boxSizing: 'border-box',
            transform: `translate(${(1 - panel) * -120}px, ${(1 - panel) * 260}px) scale(${mix(0.2, 1, panel)})`, transformOrigin: '0% 100%',
            opacity: Math.min(1, panel * 2.5),
            background: 'linear-gradient(180deg, #fffdf9 0%, #fbf5ec 100%)', borderRadius: 36, padding: '36px 46px',
            boxShadow: `inset 0 1.5px 0 rgba(255,255,255,1), inset 0 0 0 1px rgba(70,45,20,0.08), ${softShadow(44, { color: L.shadow, strength: 1.25 })}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ ...type(24, 700, { caps: true }), letterSpacing: '0.16em', color: L.accent }}>New in {BRAND.short}</div>
              <div style={{ flex: 1, height: 1.5, background: L.line }} />
            </div>
            <div style={{ ...type(68, 700), color: L.ink, marginTop: 18 }}>Every shot, tuned.</div>
            <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {SLOTS.map((s, i) => {
                const r = row(i);
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 24, height: 58, opacity: r, transform: `translateY(${(1 - r) * 22}px)`,
                  }}>
                    <div style={{ fontFamily: FONT.mono, fontSize: 32, color: L.ink3, width: 112, fontVariantNumeric: 'tabular-nums' }}>{s.time}</div>
                    <div style={{ width: 8, height: 50, borderRadius: 4, background: s.c }} />
                    <div style={{ ...type(36, 600), color: L.ink }}>{s.title}</div>
                    <div style={{ marginLeft: 'auto', ...type(32, 450), color: L.ink2 }}>{s.meta}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
