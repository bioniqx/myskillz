// carousel-3d — 8 cards arranged into a ring rotating one full revolution: each card revolves around Y, billboarded outward, front/back identical faces +
// backface-visibility:hidden ensuring upright orientation at all times; camera pinned at a shallow down-angle, seamless loop from start to end frame.
//
// Round 2 redesign (Lime · Shot Recipe Gallery; Brand pivot: previous "Training Plan" replaced with video-shotcraft shot recipe cards):
// - look = lime (graphite dark stage + fluorescent yellow-green). Cards enlarged to 340x460 native pixels, ring radius 700px, ring spans ~70% frame width;
//   Card face is a purpose-designed "shot recipe card": mono index, generative graphics (profile / strobe bars / sound wave / rings...),
//   64px large numeral, 30px label — the card rotated to center-front is spotlighted (fluorescent stroke + graphics turn fluorescent + ground glow), others remain graphite gray.
// - Rhythm: No longer static constant speed. Rotation angle = 50% constant baseline + 50% stepped (21f per step = 8f dwell + 13f smooth transition),
//   ring continuously moves (steady loop) but with a "push-dwell" breathing cycle every 45°, letting center-front card be read during dwell;
//   8 steps x 21f = 168f completes one revolution, pixel-perfect loop from last to first frame.
// - Subtitles below ring scroll to change text with each step (index + 72px label), camera fixed (gallery rather than roller coaster).
// - Aerial perspective: Dark overlay proportional to azimuth (backmost 70%) + floor reflection disc + fading reflection ring, grounding the carousel.
//
// Timeline (30fps, 168f total, seamlessly loopable):
//   One beat per 21f: 0–8 dwell (front card spotlights, subtitle freezes) → 8–21 transition (smooth, subtitle rolls up); 8 beats total = 360°
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CAROUSEL_3D_DURATION = 168; // 5600ms @30fps

const L = LOOKS.lime;
const N = 8;
const RADIUS = 700;
const CW = 340;
const CH = 460;
const RING_Y = 470; // Ring center height
const FLOOR = CH / 2 + 10; // Floor level below cards (relative to ring center)
const BEAT = 21; // Frames per step = dwell + transition
const DWELL = 8;

type Kind = 'climb' | 'intervals' | 'pulse' | 'rings' | 'splits' | 'bars' | 'mobility' | 'race';
const CARDS: { name: string; stat: string; unit: string; meta: string; kind: Kind }[] = [
  { name: 'Beat Cuts', stat: '120', unit: 'bpm', meta: 'EDIT · ON THE BEAT', kind: 'splits' },
  { name: 'Steep Tilt', stat: '38°', unit: 'tilt', meta: 'CAMERA · GLIDE', kind: 'climb' },
  { name: 'Sound Design', stat: '−14', unit: 'LUFS', meta: 'SFX · HIT + WHOOSH', kind: 'pulse' },
  { name: 'Gauge Readout', stat: '96', unit: '%', meta: 'DATA · 3 RINGS', kind: 'rings' },
  { name: 'Flash Cuts', stat: '10×', unit: '2 f', meta: 'EDIT · STROBE', kind: 'intervals' },
  { name: 'Chart Rise', stat: '45', unit: 'f', meta: 'DATA · BAR RACE', kind: 'bars' },
  { name: 'Ease Curves', stat: '0.8', unit: 's', meta: 'MOTION · SNAPPY', kind: 'mobility' },
  { name: 'Camera Path', stat: '4.2', unit: 's', meta: 'FLYOVER · 2.5D', kind: 'race' },
];

const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
const rand = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
const hex = (h: string) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
const mixHex = (a: string, b: string, t: number) => {
  const A = hex(a), B = hex(b), q = clamp01(t);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * q)).join(',')})`;
};

// Rotation angle (0→1 rev): 50% constant speed + 50% stepped (dwell DWELL frames + smooth transition); f=168 completes exactly 1 rev
const stepPart = (f: number) => {
  const k = Math.floor(f / BEAT);
  const local = f - k * BEAT;
  return (k + EASE.smooth(clamp01((local - DWELL) / (BEAT - DWELL)))) / N;
};
const turnAt = (f: number) => 0.5 * (f / (N * BEAT)) + 0.5 * stepPart(f);

export const Carousel3D: React.FC = () => {
  const f = useCurrentFrame();
  const spin = turnAt(f) * 360;
  // World azimuth of each card (0 = center front)
  const azimuth = (i: number) => ((((i * 360) / N - spin) % 360) + 540) % 360 - 180;
  const depthOf = (i: number) => (1 - Math.cos((azimuth(i) * Math.PI) / 180)) / 2;
  const hlOf = (i: number) => EASE.smooth(clamp01(1 - Math.abs(azimuth(i)) / 26));

  // Subtitles: freezes current card during dwell, rolls up to next card during transition
  const k = Math.floor(f / BEAT);
  const roll = EASE.smooth(clamp01((f - k * BEAT - DWELL) / (BEAT - DWELL)));

  const renderCard = (i: number, reflect: boolean) => {
    const d = depthOf(i);
    const hl = reflect ? 0 : hlOf(i);
    const face: React.CSSProperties = {
      position: 'absolute', inset: 0, borderRadius: 26, overflow: 'hidden', boxSizing: 'border-box',
      backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden',
      background: `linear-gradient(165deg, ${L.surface2} 0%, ${L.surface} 60%, #0f110d 100%)`,
      border: `1.5px solid ${hl > 0.01 ? alpha(L.accent, 0.25 + 0.6 * hl) : alpha('#ffffff', 0.1)}`,
      boxShadow: `inset 0 1px 0 ${alpha('#ffffff', 0.1)}`,
      ...(reflect
        ? {
            // Opacity must attach to leaf layer: attaching to preserve-3d container flattens the ring
            opacity: 0.08,
            WebkitMaskImage: 'linear-gradient(180deg, rgba(0,0,0,0) 62%, rgba(0,0,0,0.85) 100%)',
            maskImage: 'linear-gradient(180deg, rgba(0,0,0,0) 62%, rgba(0,0,0,0.85) 100%)',
          }
        : {}),
    };
    const body = (
      <>
        <Face i={i} hl={hl} />
        {/* Aerial perspective: darker toward rear (tinted dark overlay, geometry unchanged) */}
        <div style={{ position: 'absolute', inset: 0, background: L.bg[2], opacity: (0.7 * d).toFixed(3) }} />
      </>
    );
    return (
      <div key={i} style={{
        position: 'absolute', left: -CW / 2, top: -CH / 2, width: CW, height: CH, transformStyle: 'preserve-3d',
        // Cards only positioned on ring (orbit around Y + push radius along normal), never rotate on X/Z — always upright
        // Card reaching front pushes out 44px extra along normal (translation only), visually read as "selected" during dwell
        transform: `rotateY(${(i * 360) / N}deg) translateZ(${(RADIUS + 44 * hlOf(i)).toFixed(2)}px)`,
      }}>
        <div style={face}>{body}</div>
        <div style={{ ...face, transform: 'rotateY(180deg)' }}>{body}</div>
      </div>
    );
  };

  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.16 }} fill={{ x: 0.5, y: 1.0 }} intensity={0.5} />

      {/* Fluorescent ground glow beneath center-front card (fixed to frame, does not rotate) */}
      <div style={{
        position: 'absolute', left: 960 - 520, top: RING_Y + 120, width: 1040, height: 420, borderRadius: '50%',
        background: `radial-gradient(ellipse at 50% 40%, ${alpha(L.accent, 0.16)} 0%, ${alpha(L.accent, 0)} 65%)`,
      }} />

      {/* 3D scene: perspective 2200px; camera fixed at shallow down-angle */}
      <div style={{ position: 'absolute', inset: 0, perspective: '2200px', perspectiveOrigin: `50% ${RING_Y - 60}px` }}>
        <div style={{
          position: 'absolute', left: 960, top: RING_Y, width: 0, height: 0, transformStyle: 'preserve-3d',
          transform: `translateZ(${-RADIUS}px) rotateX(-9deg)`,
        }}>
          {/* Floor reflection disc + radial tick ring */}
          <div style={{
            position: 'absolute', left: -RADIUS * 1.35, top: FLOOR - RADIUS * 1.35, width: RADIUS * 2.7, height: RADIUS * 2.7, borderRadius: '50%',
            transform: 'rotateX(90deg)',
            background: `radial-gradient(circle, ${alpha(L.accent, 0.1)} 0%, ${alpha(L.accent, 0.03)} 45%, transparent 66%)`,
          }} />
          <svg width={RADIUS * 2.4} height={RADIUS * 2.4} viewBox={`${-RADIUS * 1.2} ${-RADIUS * 1.2} ${RADIUS * 2.4} ${RADIUS * 2.4}`}
            style={{ position: 'absolute', left: -RADIUS * 1.2, top: FLOOR - RADIUS * 1.2, transform: `rotateX(90deg) rotateZ(${spin}deg)`, overflow: 'visible' }}>
            <circle r={RADIUS * 1.08} fill="none" stroke={alpha('#ffffff', 0.08)} strokeWidth={2} />
            {Array.from({ length: 96 }, (_, t) => {
              const a = (t / 96) * Math.PI * 2;
              const r0 = RADIUS * (t % 12 === 0 ? 1.02 : 1.05);
              return <line key={t} x1={r0 * Math.cos(a)} y1={r0 * Math.sin(a)} x2={RADIUS * 1.08 * Math.cos(a)} y2={RADIUS * 1.08 * Math.sin(a)}
                stroke={t % 12 === 0 ? alpha(L.accent, 0.5) : alpha('#ffffff', 0.12)} strokeWidth={t % 12 === 0 ? 3 : 2} />;
            })}
          </svg>
          {/* Reflection ring: inverted mirroring ground plane */}
          <div style={{ position: 'absolute', transformStyle: 'preserve-3d', transform: `translateY(${FLOOR * 2}px) scaleY(-1) rotateY(${-spin}deg)` }}>
            {Array.from({ length: N }, (_, i) => renderCard(i, true))}
          </div>
          {/* Ring carrier: sole per-frame variable */}
          <div style={{ position: 'absolute', transformStyle: 'preserve-3d', transform: `rotateY(${-spin}deg)` }}>
            {Array.from({ length: N }, (_, i) => renderCard(i, false))}
          </div>
        </div>
      </div>

      {/* Subtitle: index + name, rolls up to switch text per step (clipped window) */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 862, height: 120, overflow: 'hidden' }}>
        {[0, 1].map((j) => {
          const c = (k + j) % N;
          const y = (j - roll) * 120;
          return (
            <div key={j} style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 34,
              transform: `translateY(${y.toFixed(2)}px)`, opacity: 1 - Math.abs(j - roll) * 0.9,
            }}>
              <span style={{ fontFamily: FONT.mono, fontSize: 26, letterSpacing: '0.14em', color: L.accent }}>{`0${c + 1} / 08`}</span>
              <span style={{ ...type(72, 750), color: L.ink }}>{CARDS[c].name}</span>
            </div>
          );
        })}
      </div>

      {/* Frame decorations */}
      <div style={{ position: 'absolute', left: 120, top: 96, display: 'flex', alignItems: 'center', gap: 14 }}>
        <ShotcraftMark size={30} tone="dark" />
        <div style={{ fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.1em', color: L.ink2 }}>{`${BRAND.name} · shot recipes`}</div>
      </div>
      <div style={{ position: 'absolute', right: 120, top: 96, fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.16em', color: L.ink3 }}>
        1080P · 30 FPS
      </div>
    </AbsoluteFill>
  );
};

// ───────────── Card Face (340x460) ─────────────
const Face: React.FC<{ i: number; hl: number }> = ({ i, hl }) => {
  const c = CARDS[i];
  const g = mixHex('#6b7262', L.accent, hl); // Graphic primary color: graphite gray → fluorescent
  return (
    <div style={{ position: 'absolute', inset: 0, padding: 30 }}>
      {/* Top edge lighting */}
      <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(120% 55% at 30% 0%, ${alpha('#ffffff', 0.07)} 0%, transparent 60%)` }} />
      <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', fontFamily: FONT.mono, fontSize: 17, letterSpacing: '0.14em', color: L.ink3 }}>
        <span>{`SHOT ${String(i + 1).padStart(2, '0')}`}</span>
        <span style={{ color: hl > 0.5 ? L.accent : L.ink3 }}>●</span>
      </div>
      <div style={{ position: 'relative', marginTop: 22, height: 150 }}>
        <Graphic kind={c.kind} color={g} seed={i} />
      </div>
      <div style={{ position: 'relative', marginTop: 26, display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span style={{ ...type(72, 800), color: L.ink, letterSpacing: '-0.04em' }}>{c.stat}</span>
        <span style={{ ...type(28, 600), color: L.ink2 }}>{c.unit}</span>
      </div>
      <div style={{ position: 'relative', ...type(32, 650), color: L.ink, marginTop: 10 }}>{c.name}</div>
      <div style={{ position: 'absolute', left: 30, bottom: 28, fontFamily: FONT.mono, fontSize: 17, letterSpacing: '0.12em', color: L.ink3 }}>{c.meta}</div>
    </div>
  );
};

const Graphic: React.FC<{ kind: Kind; color: string; seed: number }> = ({ kind, color, seed }) => {
  const W = 280, H = 150;
  const dim = alpha('#ffffff', 0.1);
  switch (kind) {
    case 'climb': {
      const pts = Array.from({ length: 14 }, (_, k) => [k * (W / 13), 130 - (k % 4 < 2 ? k % 4 : 4 - (k % 4)) * 46 - rand(seed + k) * 10]);
      const d = pts.map((p, k) => `${k ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
      return (
        <svg width={W} height={H}>
          <path d={`${d} L${W},${H} L0,${H} Z`} fill={color} fillOpacity={0.16} />
          <path d={d} fill="none" stroke={color} strokeWidth={4} strokeLinejoin="round" />
        </svg>
      );
    }
    case 'intervals':
      return (
        <svg width={W} height={H}>
          {Array.from({ length: 10 }, (_, k) => (
            <g key={k}>
              <rect x={k * 28} y={20} width={14} height={130} rx={4} fill={color} />
              <rect x={k * 28 + 16} y={100} width={8} height={50} rx={3} fill={dim} />
            </g>
          ))}
        </svg>
      );
    case 'pulse': {
      // SFX card: 4 "hit + decay" sound waves (1 hit every 14 points, alternating polyline with exponentially decaying amplitude)
      const d = Array.from({ length: 57 }, (_, k) => {
        const x = k * 5;
        const beat = k % 14;
        const amp = beat < 2 ? 0 : 62 * Math.exp(-(beat - 2) * 0.32);
        const y = 75 + amp * (k % 2 ? 1 : -1) + Math.sin(k * 0.7) * 2;
        return `${k ? 'L' : 'M'}${x},${y.toFixed(1)}`;
      }).join(' ');
      return <svg width={W} height={H}><path d={d} fill="none" stroke={color} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" /></svg>;
    }
    case 'rings':
      return (
        <svg width={W} height={H}>
          {[0.86, 0.62, 0.4].map((v, k) => {
            const r = 66 - k * 19;
            const C = 2 * Math.PI * r;
            return (
              <g key={k} transform="rotate(-90 75 75)">
                <circle cx={75} cy={75} r={r} fill="none" stroke={dim} strokeWidth={12} />
                <circle cx={75} cy={75} r={r} fill="none" stroke={color} strokeOpacity={1 - k * 0.3} strokeWidth={12} strokeLinecap="round" strokeDasharray={`${C * v} ${C}`} />
              </g>
            );
          })}
          <text x={168} y={70} fontFamily={FONT.mono} fontSize={18} fill={L.ink3} letterSpacing="0.1em">FPS</text>
          <text x={168} y={104} fontFamily={FONT.sans} fontSize={34} fontWeight={700} fill={L.ink}>30</text>
        </svg>
      );
    case 'splits':
      return (
        <svg width={W} height={H}>
          {Array.from({ length: 8 }, (_, k) => {
            const w = 150 + rand(seed * 7 + k) * 110;
            return <rect key={k} x={0} y={k * 19} width={w} height={11} rx={5.5} fill={k === 5 ? color : dim} />;
          })}
          <line x1={210} x2={210} y1={0} y2={150} stroke={color} strokeWidth={2} strokeDasharray="4 5" />
        </svg>
      );
    case 'bars':
      return (
        <svg width={W} height={H}>
          {Array.from({ length: 7 }, (_, k) => {
            const h = 40 + rand(seed * 11 + k) * 105;
            return <rect key={k} x={k * 40} y={150 - h} width={26} height={h} rx={6} fill={k === 4 ? color : dim} />;
          })}
        </svg>
      );
    case 'mobility':
      return (
        <svg width={W} height={H}>
          {[0, 1, 2].map((k) => (
            <path key={k} d={`M 0 ${40 + k * 36} C 70 ${10 + k * 36}, 140 ${80 + k * 36}, 280 ${30 + k * 36}`} fill="none" stroke={k === 1 ? color : dim} strokeWidth={k === 1 ? 5 : 4} strokeLinecap="round" />
          ))}
        </svg>
      );
    case 'race':
    default:
      return (
        <svg width={W} height={H}>
          <path d="M 10 120 C 60 20, 120 140, 170 60 S 250 30, 270 40" fill="none" stroke={dim} strokeWidth={10} strokeLinecap="round" />
          <path d="M 10 120 C 60 20, 120 140, 170 60" fill="none" stroke={color} strokeWidth={10} strokeLinecap="round" />
          <circle cx={170} cy={60} r={12} fill={L.bg[2]} stroke={color} strokeWidth={5} />
          <circle cx={270} cy={40} r={8} fill={L.ink} />
        </svg>
      );
  }
};
