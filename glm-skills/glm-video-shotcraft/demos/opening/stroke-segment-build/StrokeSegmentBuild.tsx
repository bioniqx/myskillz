// stroke-segment-build — Fragmented stroke letter assembly (Alien style): title disassembled into disjoint stroke segments igniting out of order.
// Early 70% is indecipherable until final "key segments" strike, locking immediate legibility.
//
// Iteration 2 redesign (aurora night · neon signboard):
// - look = aurora. "SHIP" drawn as 400px geometric monoline letterforms split into 16 disjoint neon glass tubes (with electrode gaps) mounted on a deep violet wall.
//   Each tube strike simulates authentic neon ignition: flash-cut-flash-half-flash flicker over 7f, settling at 0.58 baseline; sign remains in fragmented half-lit state until climax.
// - Cadence (sparse -> dense -> breath -> 1, 2, 3 -> surge): first 13 segments stagger on an ease-out curve (spacing accelerating from 9f down to 3f),
//   followed by a 14f held breath (subtle electrical hum), then the 3 key segments (S spine, H bar, P bowl) strike on 7f/6f beats.
//   As the final key strikes, full current surges: all tubes spike 0.58 -> 1 -> 1.25 before settling, sign bloom swells, and wall/floor illuminate.
// - Environment: wall ambient reflectance scales with lit tube count; polished ground reflects lower sign
//   (blur + falloff) with a specular ground highlight band; gentle 1->1.035 camera push throughout.
// - Subtitle reveals only after climax: video-shotcraft logotype (lowercase) ● ONE PROMPT, ONE FILM.
//
// Timeline (30fps, 165f total):
//   0–12    Dark wall + faint ambient glow (avoiding pure black)
//   12–72   First 13 segments strike in disordered sequence (9f -> 3f acceleration)
//   72–86   Held breath 14f: no new segments, subtle tube current hum
//   86/93/99 Three key segments strike: S spine -> H bar -> P bowl
//   105     Final segment ignites = climax: electrical surge + bloom + wall/floor light up
//   113–129 Subtitle rises
//   129–165 Hold: sign glows steadily, gentle camera push
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { EASE, FONT, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, stagger } from '../../_fixtures/Look';
import { BRAND } from '../../_fixtures/Brand';

export const STROKE_SEGMENT_BUILD_DURATION = 165;

const L = LOOKS.aurora;
const TUBE = '#ff5cab'; // Tube base color (neon pink)
const GLOW = L.accent2; // Bloom glow
const CORE = '#fff2f8'; // Incandescent white core

// —— Glyph geometry: 260x400 per glyph, gap 70; monoline geometric, stroke width 30 ——
const LW = 260;
const LH = 400;
const ADV = LW + 70;
const WORD_W = ADV * 3 + LW; // 1250
const OX = (1920 - WORD_W) / 2;
const OY = 190;
const SW = 30;

type Seg = { d: string; key?: boolean };
const at = (k: number) => (x: number) => x + ADV * k;
const S = at(0);
const H = at(1);
const I = at(2);
const P = at(3);
const SEGS: Seg[] = [
  // S — 6 segments (split into opposing arcs)
  { d: `M ${S(228)} 92 C ${S(214)} 44 ${S(176)} 20 ${S(130)} 20` }, // 0 top hook
  { d: `M ${S(130)} 20 C ${S(72)} 20 ${S(34)} 54 ${S(34)} 104` }, // 1 upper-left arc
  { d: `M ${S(34)} 104 C ${S(34)} 156 ${S(78)} 178 ${S(130)} 196` }, // 2 upper spine
  { d: `M ${S(130)} 196 C ${S(186)} 214 ${S(228)} 240 ${S(228)} 296`, key: true }, // 3 lower spine (key)
  { d: `M ${S(228)} 296 C ${S(228)} 348 ${S(186)} 380 ${S(130)} 380` }, // 4 lower-right arc
  { d: `M ${S(130)} 380 C ${S(80)} 380 ${S(42)} 356 ${S(30)} 306` }, // 5 tail hook
  // H — 4 segments
  { d: `M ${H(34)} 20 L ${H(34)} 196` }, // 6 left vertical upper
  { d: `M ${H(34)} 204 L ${H(34)} 380` }, // 7 left vertical lower
  { d: `M ${H(226)} 20 L ${H(226)} 380` }, // 8 right vertical
  { d: `M ${H(58)} 200 L ${H(202)} 200`, key: true }, // 9 crossbar (key)
  // I — 2 segments
  { d: `M ${I(130)} 20 L ${I(130)} 196` }, // 10 upper
  { d: `M ${I(130)} 204 L ${I(130)} 380` }, // 11 lower
  // P — 4 segments
  { d: `M ${P(34)} 20 L ${P(34)} 196` }, // 12 vertical upper
  { d: `M ${P(34)} 204 L ${P(34)} 380` }, // 13 vertical lower
  { d: `M ${P(58)} 20 L ${P(140)} 20 C ${P(196)} 20 ${P(228)} 56 ${P(228)} 108` }, // 14 bowl top
  { d: `M ${P(228)} 108 C ${P(228)} 160 ${P(196)} 196 ${P(140)} 196 L ${P(58)} 196`, key: true }, // 15 bowl bottom (key)
];

// Disordered trigger schedule: first 13 segments jump across characters (unreadable), key segments held for climax
const ORDER = [14, 5, 8, 10, 0, 13, 6, 1, 11, 4, 12, 7, 2, 3, 9, 15];
const FIRST = 12;
const SPAN = 60; // First 13 segment starts distributed across 12–72
const KEY_AT = [86, 93, 99]; // Three beats following 14f pause
const STRIKE = 7; // Single-tube strike duration (frames)
const REVEAL = KEY_AT[2] + 6; // 105
const startOf = (rank: number) => (rank < 13 ? FIRST + stagger(rank, 13, SPAN, EASE.out) : KEY_AT[rank - 13]);

// Neon ignition flicker: flash-cut-flash-half-flash -> steady at 0.58 (reaches 1 on climax)
const strike = (f: number, s: number) =>
  interpolate(f, [s, s + 1, s + 2, s + 3, s + 4, s + 5, s + STRIKE], [0, 1, 0.12, 0.95, 0.4, 1, 0.58], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

// Deterministic electrical hum: subtle brightness modulation (decorrelated phases per tube)
const hum = (f: number, i: number) => 1 + 0.035 * Math.sin(f * 0.9 + i * 2.3) * Math.sin(f * 0.37 + i);

// Climax bloom pulse: expands sign wide-glow synchronously with electrical surge
const Sign: React.FC<{ frame: number; surge: number; reveal: number; idPrefix: string }> = ({ frame, surge, reveal, idPrefix }) => {
  const lit = SEGS.map((seg, i) => {
    const s = startOf(ORDER.indexOf(i));
    if (frame < s) return null; // Unlit segments unrendered (clean silence without leaking outline)
    const b = strike(frame, s);
    const settled = frame >= s + STRIKE;
    const level = settled ? 0.58 + 0.42 * reveal : b;
    return { i, d: seg.d, b: level * (settled ? hum(frame, i) : 1) * (1 + 0.25 * surge) };
  }).filter((x): x is NonNullable<typeof x> => x !== null);
  // Electrode gaps: 4% gap omitted on each tube endpoint
  const dash = { pathLength: 1, strokeDasharray: '0.92 1', strokeDashoffset: -0.04 } as const;
  return (
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
      <defs>
        <filter id={`${idPrefix}w`} x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="22" /></filter>
        <filter id={`${idPrefix}n`} x="-20%" y="-40%" width="140%" height="180%"><feGaussianBlur stdDeviation="6" /></filter>
      </defs>
      <g transform={`translate(${OX} ${OY})`} fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* Wide bloom (ambient wall halo) */}
        <g filter={`url(#${idPrefix}w)`}>
          {lit.map((g) => <path key={g.i} d={g.d} stroke={GLOW} strokeWidth={SW + 46} opacity={Math.min(1, 0.4 * g.b + 0.4 * surge)} {...dash} />)}
        </g>
        {/* Near glow (halo immediately around tube) */}
        <g filter={`url(#${idPrefix}n)`}>
          {lit.map((g) => <path key={g.i} d={g.d} stroke={TUBE} strokeWidth={SW + 12} opacity={Math.min(1, 0.75 * g.b)} {...dash} />)}
        </g>
        {/* Neon tube body + incandescent core */}
        {lit.map((g) => <path key={g.i} d={g.d} stroke={TUBE} strokeWidth={SW} opacity={Math.min(1, 0.35 + 0.65 * g.b)} {...dash} />)}
        {lit.map((g) => <path key={g.i} d={g.d} stroke={CORE} strokeWidth={SW * 0.32} opacity={Math.min(1, g.b)} {...dash} />)}
      </g>
    </svg>
  );
};

export const StrokeSegmentBuild: React.FC = () => {
  const frame = useCurrentFrame();
  const litCount = ORDER.reduce((n, _, rank) => n + (frame >= startOf(rank) + 1 ? 1 : 0), 0);
  // Climax: tubes ramp 0.72 -> 1; current surges (spikes to 1.25 then settles)
  const reveal = ramp(frame, REVEAL, 8, EASE.snappy);
  const surge = interpolate(frame, [REVEAL, REVEAL + 3, REVEAL + 22], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASE.out });
  const pulse = 1 + 0.02 * surge;
  const ambient = 0.12 + 0.5 * (litCount / SEGS.length) + 0.35 * reveal + 0.3 * surge; // Wall surface illumination
  const push = 1 + 0.035 * ramp(frame, 0, STROKE_SEGMENT_BUILD_DURATION, EASE.smooth);
  const kicker = ramp(frame, REVEAL + 8, 16, EASE.out);

  const FLOOR = 780; // Wall-floor intersection line
  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <AbsoluteFill style={{ transform: `scale(${push})`, transformOrigin: '50% 45%' }}>
        <Stage look={L} keyLight={{ x: 0.5, y: 0.0 }} fill={null} intensity={0.35} vignette={0.7}>
          {/* Wall: ambient magenta-violet illumination scaling with lit segments */}
          <div style={{
            position: 'absolute', left: 160, top: -40, width: 1600, height: 960, opacity: Math.min(1, ambient),
            background: `radial-gradient(ellipse 50% 46% at 50% 46%, ${alpha(GLOW, 0.28)} 0%, ${alpha(L.light, 0.12)} 45%, ${alpha(L.light, 0)} 72%)`,
          }} />
          {/* Floor: darker tone + specular highlight band at intersection */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: FLOOR, bottom: 0, background: `linear-gradient(180deg, ${alpha('#05030a', 0.55)} 0%, ${alpha('#05030a', 0.85)} 100%)` }} />
          <div style={{
            position: 'absolute', left: 260, width: 1400, top: FLOOR - 40, height: 120, opacity: Math.min(1, ambient * 0.9),
            background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(GLOW, 0.3)} 0%, ${alpha(GLOW, 0)} 70%)`,
          }} />
        </Stage>

        {/* Floor reflection: mirrored along floor line, blurred, fading downward */}
        <div style={{
          position: 'absolute', inset: 0, transform: `translateY(${2 * FLOOR}px) scaleY(-1)`, transformOrigin: '0 0', opacity: 0.42,
          filter: 'blur(5px)', // Mask in local pre-mirror coordinates: local y>=FLOOR flips onto wall (must be transparent)
          WebkitMaskImage: `linear-gradient(180deg, transparent ${FLOOR - 340}px, rgba(0,0,0,0.9) ${FLOOR - 40}px, #000 ${FLOOR - 1}px, transparent ${FLOOR}px)`,
        }}>
          <div style={{ position: 'absolute', inset: 0, transform: `scale(${pulse})`, transformOrigin: `960px ${OY + LH / 2}px` }}>
            <Sign frame={frame} surge={surge} reveal={reveal} idPrefix="ssbr" />
          </div>
        </div>

        {/* Neon signboard */}
        <div style={{ position: 'absolute', inset: 0, transform: `scale(${pulse})`, transformOrigin: `960px ${OY + LH / 2}px` }}>
          <Sign frame={frame} surge={surge} reveal={reveal} idPrefix="ssb" />
        </div>

        {/* Subtitle revealed only after climax settles */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: OY + LH + 62, textAlign: 'center', fontFamily: FONT.sans,
          fontSize: 32, fontWeight: 600, letterSpacing: '0.34em', color: L.ink2, opacity: kicker,
          transform: `translateY(${((1 - kicker) * 14).toFixed(2)}px)`,
        }}>
          {/* Brand wordmark lowercase per spec with tighter tracking; tagline in wide-tracked uppercase */}
          <span style={{ fontFamily: BRAND.font, fontWeight: 700, letterSpacing: '0.06em', color: L.ink }}>{BRAND.name}</span>
          <span style={{ color: TUBE, margin: '0 0.5em 0 0.8em' }}>●</span> ONE PROMPT, ONE FILM
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
