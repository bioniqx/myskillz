// glass-pill-dictation-typing — Glass Pill Dictation
// Fixed-width frosted glass pill emerges at 1.25x scale, floating down into resting slot; interior illuminated left-to-right with warm gradient ("awaiting voice input");
// Caret precedes typing, followed by uniform text output; interior warmth recedes with typing progress, resolving into neutral frosted glass.
// An understated beat focused on three clean actions: settle, type, and light fade.
//
// Iteration 2 redesign (sand daylight · frosted glass):
// - look = sand (beige + terracotta). Light daylight field: warm ambient "sun" disk and soft glow clusters behind pill;
//   pill renders authentic frosted glass with backdrop-filter, top specular hairline, volumetric shading, and dual-layer drop shadows.
// - Scaled for tactile materiality: 1240x132 glass bar, 56px dictation typography, 92px waveform button; minimal composition with bottom brand mark.
// - Tri-level lighting causality bound to parameter g (1->0): terracotta-to-apricot gradient inside pill, backdrop sun glow, and floor reflection beneath pill
//   all recede synchronously as typing advances; audio button transitions from solid terracotta to stroked neutral.
// - Curves: landing scale 1.25->1 uses snappy ease-out (20f), opacity reaches 1 in 2f, depth-of-field blur 6px->0 over first 14f;
//   typing runs at steady 2f/char; lighting fades smooth in-out.
//
// Timeline (30fps, 100f total):
//   0–2      Pill appears at full opacity, light at peak
//   0–20     Landing: scale 1.25->1 (snappy) + blur 6px->0 (first 14f); caret appears at 2f
//   8–64     Typing: 28 characters steady at 2f/char
//   10–72    Light recession: g 1->0 (smooth), all 3 light layers fade in sync with audio button
//   66–74    Caret withdraws
//   74–100   Hold: neutral frosted glass bar + sentence, ambient light gently breathes
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, ramp, mix } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const GLASS_PILL_DICTATION_TYPING_DURATION = 100;

const L = LOOKS.sand;
// Embedded glow: terracotta -> apricot (brand accent pair)
const WARM = '#d9643a';
const APRICOT = '#ffb070';

const PW = 1240; // Fixed width: avoids resizing during typing to read as input pill rather than chip
const PH = 132;
const PX = (1920 - PW) / 2;
const PY = 540 - PH / 2;
const BTN = 92;
const BARS = [30, 16, 24, 13, 20]; // Waveform bar baseline heights
const TEXT = 'Cut a launch film for my app'; // 28 characters, matching original length
const TYPE0 = 8;
const CPF = 2; // Frames per character (uniform)

const hexRgb = (h: string) => {
  const n = parseInt(h.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const mixHex = (a: string, b: string, t: number) => {
  const A = hexRgb(a), B = hexRgb(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
};

export const GlassPillDictationTyping: React.FC = () => {
  const f = useCurrentFrame();

  const appear = ramp(f, 0, 2, EASE.linear);
  const land = ramp(f, 0, 20, EASE.snappy);
  const s = mix(1.25, 1, land);
  const defocus = 6 * (1 - ramp(f, 0, 14, EASE.out));
  const n = Math.floor(Math.min(1, Math.max(0, (f - TYPE0) / (TEXT.length * CPF))) * TEXT.length + 1e-6);
  const caret = ramp(f, 2, 2, EASE.linear) * (1 - ramp(f, 66, 8, EASE.out));
  const g = 1 - ramp(f, 10, 62, EASE.smooth); // Light: recedes with typing progress
  const breathe = 0.5 + 0.5 * Math.sin(f / 22);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.36, y: 0.12 }} fill={{ x: 0.8, y: 0.9 }} vignette={0.22}>
        {/* Ambient "sun" behind pill: key warm light source, recedes with interior light */}
        {/* Light center positioned directly behind right section of pill: frosted glass diffuses it */}
        <div style={{
          position: 'absolute', left: 1330, top: 470, width: 1100, height: 900, marginLeft: -550, marginTop: -450, borderRadius: '50%',
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(APRICOT, 0.15 + 0.6 * g)} 0%, ${alpha(APRICOT, 0.1 + 0.42 * g)} 18%, ${alpha(WARM, 0.06 + 0.26 * g)} 40%, ${alpha(WARM, 0.02 + 0.08 * g)} 62%, ${alpha(WARM, 0)} 80%)`,
        }} />
        {/* Distant ambient light clusters for frosted glass diffusion */}
        {[
          { x: 520, y: 470, r: 220, c: '#fff4e4', a: 0.9 },
          { x: 820, y: 620, r: 160, c: '#e9b08a', a: 0.35 },
          { x: 1460, y: 610, r: 200, c: '#f6d2a8', a: 0.55 },
        ].map((b, i) => (
          <div key={i} style={{
            position: 'absolute', left: b.x - b.r + Math.sin(f / 40 + i) * 6, top: b.y - b.r, width: b.r * 2, height: b.r * 2, borderRadius: '50%',
            background: `radial-gradient(circle, ${alpha(b.c, b.a)} 0%, ${alpha(b.c, 0)} 70%)`,
          }} />
        ))}
        {/* Ground reflection: warm spill beneath pill, extinguishes with g */}
        <div style={{
          position: 'absolute', left: PX + PW * 0.35, width: PW * 0.75, top: PY + PH * 0.9, height: 220,
          background: `radial-gradient(ellipse 50% 40% at 60% 20%, ${alpha(WARM, 0.22 * g)} 0%, ${alpha(WARM, 0)} 72%)`,
          opacity: appear,
        }} />
      </Stage>

      {/* Pill glass body */}
      <div style={{
        position: 'absolute', left: PX, top: PY, width: PW, height: PH, borderRadius: PH / 2, overflow: 'hidden', boxSizing: 'border-box',
        display: 'flex', alignItems: 'center', padding: `0 20px 0 58px`, opacity: appear,
        transform: `scale(${s})`, filter: defocus > 0.05 ? `blur(${defocus.toFixed(2)}px)` : undefined,
        background: `linear-gradient(180deg, ${alpha('#ffffff', 0.62)} 0%, ${alpha('#fffaf3', 0.42)} 55%, ${alpha('#f3e7d8', 0.5)} 100%)`,
        backdropFilter: 'blur(26px) saturate(1.3)', WebkitBackdropFilter: 'blur(26px) saturate(1.3)',
        border: `1.5px solid ${alpha('#ffffff', 0.85)}`,
        // Dual-layer drop shadows (tight contact + wide diffused shadow, contracting on landing)
        boxShadow: `0 0 0 1px ${alpha(L.shadow, 0.07)}, inset 0 2px 0 ${alpha('#ffffff', 0.95)}, inset 0 -10px 24px ${alpha('#c9a888', 0.22)}, ` +
          `0 ${mix(10, 4, land).toFixed(1)}px ${mix(20, 10, land).toFixed(1)}px ${alpha(L.shadow, 0.12)}, 0 ${mix(60, 36, land).toFixed(1)}px 70px -28px ${alpha(L.shadow, 0.4)}, ` +
          `0 0 ${60 * g}px ${alpha(APRICOT, 0.45 * g)}`,
      }}>
        {/* Embedded warm gradient: soft left to rich right, fades with typing */}
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', opacity: g,
          background: `linear-gradient(90deg, ${alpha(WARM, 0)} 0%, ${alpha(WARM, 0.18)} 38%, ${alpha(WARM, 0.62)} 78%, ${alpha(APRICOT, 0.95)} 100%)`,
        }} />
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none', opacity: g * 0.7, mixBlendMode: 'screen',
          background: `radial-gradient(ellipse 34% 130% at 100% 100%, ${alpha('#ffe2b8', 0.9)} 0%, ${alpha('#ffe2b8', 0)} 70%)`,
        }} />
        {/* Top specular edge: tapered at ends, clipped to rounded corners */}
        <div style={{
          position: 'absolute', left: PH * 0.45, right: PH * 0.45, top: 3, height: 1.5, pointerEvents: 'none',
          background: `linear-gradient(90deg, ${alpha('#ffffff', 0)}, ${alpha('#ffffff', 0.95)} 20%, ${alpha('#ffffff', 0.7)} 75%, ${alpha('#ffffff', 0)})`,
        }} />
        {/* Dictated text + caret */}
        <div style={{ position: 'relative', ...type(56, 500), letterSpacing: '-0.015em', color: L.ink, whiteSpace: 'pre', flex: 'none' }}>
          {TEXT.slice(0, n)}
        </div>
        <div style={{
          position: 'relative', width: 4, height: 62, marginLeft: 4, borderRadius: 2, flex: 'none', opacity: caret,
          background: mixHex(L.ink, WARM, 0.8 * g),
        }} />
        {/* Waveform button: solid warm terracotta -> stroked neutral */}
        <div style={{
          position: 'relative', marginLeft: 'auto', width: BTN, height: BTN, borderRadius: BTN / 2, flex: 'none', boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          background: `linear-gradient(180deg, ${alpha('#ffffff', 0.35 * g)}, ${alpha('#ffffff', 0)}), ${alpha(WARM, 0.92 * g)}`,
          border: `1.5px solid ${g > 0.5 ? alpha('#ffffff', 0.5) : alpha(L.ink, 0.16 + 0.1 * (1 - g))}`,
          boxShadow: `inset 0 1.5px 0 ${alpha('#ffffff', 0.5)}, 0 ${6 * g}px ${18 * g}px -6px ${alpha(WARM, 0.8 * g)}`,
        }}>
          {BARS.map((h, i) => (
            <div key={i} style={{
              width: 5, borderRadius: 3, height: h + 2.4 * Math.sin(f * 0.5 + i * 1.7),
              background: mixHex(L.ink2, '#fffaf3', g),
            }} />
          ))}
        </div>
      </div>

      {/* Brand mark (static, appears with pill) */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 112, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 14,
        opacity: ramp(f, 4, 16, EASE.out) * (0.9 + 0.1 * breathe),
      }}>
        <ShotcraftMark size={34} tone="light" />
        <span style={{ ...type(30, 650), color: L.ink2 }}>{BRAND.name}</span>
        <span style={{ ...type(30, 450), color: L.ink3 }}>· speak or type</span>
      </div>
    </AbsoluteFill>
  );
};
