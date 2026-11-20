// card-stack — A deck of cards springs in sequentially from the bottom of the screen into a single stack;
// once all cards settle, the stack fans out in a single motion:
// each card rotates 6.5° per index, shifts horizontally 138px, and steps back one z-layer;
// the fan pivot is below the bottom edge of the cards (transform-origin 50% 130%).
//
// Round 2 redesign (porcelain · template library launch; branding: video-shotcraft shot recipe library):
// - look = porcelain (cool white + ink + cobalt blue, teal accents only). Cards scaled up to native 320×440 px (no longer using 480×270 design coordinates);
//   each represents a designed "template cover" for shots: top 58% generative cover art (gantt / bars / line / rings / table / calendar / kanban / metric),
//   bottom 30px title + mono metadata (each is a shot/template type); only the center "Launch film" card uses a solid cobalt blue cover—it is the featured card pulled out at the end.
// - Card count 9 (odd): center card takes the middle slot, fan is symmetrically balanced; stack order = index (like a fanned hand of cards, left over right),
//   zIndex remains constant throughout to prevent top-card pop when transitioning from stack to fan.
// - Sense of weight: entrance distributes in an "accelerating" rhythm (EASE.out stagger, thud——thud—thud-thud-thud); each landing card compresses the stack downward 5px before rebounding;
//   6f anticipation before fanning (stack tightens 2%); fan deployment uses a low-damping spring (damping 20) settling with subtle inertia; camera zooms out to 0.88 in the same segment.
// - Outro: center card slides out 72px along its own axis + cobalt blue outline + sheen sweep (Q4); headline and subtitle rise into place, forming a launch poster.
//
// Timeline (30fps, 150f total):
//   0–3     Porcelain stage + floor contact shadow + top-left eyebrow already present
//   2–42    9 cards launch sequentially (staggered over 40f, accelerating), each springs in (damping 13) ≈20f to settle, compressing stack 5px on touchdown
//   62–72   Anticipation: stack tightens 2%
//   0–64    Camera very slow zoom-in 1→1.06
//   68–100  Fan unfold (spring damping 20, single gentle overshoot), camera zooms out 1.06→0.88 (smooth 64–106)
//   102–122 Center card pulled out 72px (overshoot) + cobalt outline + sheen; title rises word-by-word (106–), subtitle (116–)
//   122–150 Hold (camera continues very slow creep ×1.017)
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Sheen, Stage, TextReveal, alpha, springAt, stagger, type } from '../../_fixtures/Look';
import { BRAND, MARK_PATHS, ShotcraftMark } from '../../_fixtures/Brand';

export const CARD_STACK_DURATION = 150; // 5000ms @30fps

const L = LOOKS.porcelain;
const N = 9;
const CW = 320;
const CH = 440;
const CX = 960;
const CY = 610; // Card center
const ROT = 6.5; // Fan rotation per card (deg)
const TX = 138; // Fan horizontal shift per card (px)
const FEATURED = 4;

type Kind = 'gantt' | 'bars' | 'line' | 'rings' | 'hero' | 'table' | 'calendar' | 'kanban' | 'metric';
const CARDS: { title: string; meta: string; kind: Kind; tint: string }[] = [
  { title: 'Beat-synced cuts', meta: 'EDIT · 6 TRACKS', kind: 'gantt', tint: '#e9eeff' },
  { title: 'Bar chart rise', meta: 'DATA · 7 BARS', kind: 'bars', tint: '#eef1f6' },
  { title: 'Growth line draw', meta: 'CHART · LIVE DRAW', kind: 'line', tint: '#e3f5f1' },
  { title: 'Gauge readout', meta: 'DATA · 3 RINGS', kind: 'rings', tint: '#e9eeff' },
  { title: 'Launch film', meta: 'TEMPLATE · FEATURED', kind: 'hero', tint: L.accent },
  { title: 'Render queue', meta: 'QUEUE · 6 JOBS', kind: 'table', tint: '#eef1f6' },
  { title: 'Storyboard grid', meta: 'BOARD · 35 FRAMES', kind: 'calendar', tint: '#e3f5f1' },
  { title: 'Shot list', meta: 'PLAN · 3 ACTS', kind: 'kanban', tint: '#e9eeff' },
  { title: 'Stat count-up', meta: 'DATA · KPI', kind: 'metric', tint: '#eef1f6' },
];

const rand = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

// Entrance: launch frames distribute in an "accelerating" cadence (EASE.out mapping: larger initial gaps, tightening toward end); spring 0→1 (damping 13 = one visible bounce)
const START = Array.from({ length: N }, (_, i) => 2 + stagger(i, N, 40, EASE.out));
const inAt = (f: number, i: number) => (f < START[i] ? 0 : springAt(f, START[i], { damping: 13, stiffness: 150 }));
const DROP = 820; // Starting point below viewport

export const CardStack: React.FC = () => {
  const f = useCurrentFrame();
  // Landing compression: as each card settles (≈7f after launch crossing baseline), stack depresses 5px with a 9f sine envelope
  const dip = START.reduce((d, s) => d + Math.sin(clamp01((f - s - 6) / 9) * Math.PI) * 5, 0);
  const squeeze = 1 - 0.02 * Math.sin(clamp01((f - 62) / 10) * Math.PI);
  const fan = f < 68 ? 0 : springAt(f, 68, { damping: 20, stiffness: 95 });
  // Camera: very slow creep forward 1→1.06 during stacked phase (weighting the stack), pulls back to 0.88 during fan-out, creeps slightly during hold
  const camPush = mix(1, 1.06, ramp(f, 0, 64, EASE.smooth));
  const cam = mix(camPush, 0.88, ramp(f, 64, 42, EASE.smooth)) * mix(1, 1.017, ramp(f, 122, 28, EASE.smooth));
  const lift = ramp(f, 102, 18, EASE.overshoot);
  const ring = ramp(f, 104, 12, EASE.out);
  const sheen = ramp(f, 108, 22, EASE.smooth);

  return (
    <AbsoluteFill style={{ background: L.bg[1] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.12 }} fill={null}>
        {/* Floor: subtle tabletop reflection strip */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 860, height: 220, background: `linear-gradient(180deg, ${alpha('#ffffff', 0)} 0%, ${alpha('#ffffff', 0.5)} 40%, ${alpha('#ffffff', 0)} 100%)` }} />
      </Stage>

      {/* Eyebrow header (frame embellishment, fixed to camera) */}
      <div style={{ position: 'absolute', left: 120, top: 96, display: 'flex', alignItems: 'center', gap: 14, opacity: ramp(f, 0, 12, EASE.out) }}>
        <ShotcraftMark size={30} tone="light" />
        <div style={{ fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.1em', color: L.ink2 }}>{`${BRAND.name} · shot recipes`}</div>
      </div>
      <div style={{ position: 'absolute', right: 120, top: 96, fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.16em', color: L.ink3, opacity: ramp(f, 4, 12, EASE.out) }}>
        {`${String(START.filter((s) => f >= s + 6).length).padStart(2, '0')} / ${String(N).padStart(2, '0')}`}
      </div>

      {/* Headline: rises when center card pulls out */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 150, textAlign: 'center' }}>
        <div style={{ ...type(88, 700), color: L.ink }}>
          <TextReveal text="Start from a shot recipe." by="word" variant="rise" start={106} each={18} gap={3} />
        </div>
      </div>

      <AbsoluteFill style={{ transform: `scale(${cam.toFixed(4)})`, transformOrigin: `${CX}px ${CY + 120}px` }}>
        {/* Floor contact shadow: concentrated when stacked, widens with fan expansion */}
        <div style={{
          position: 'absolute', left: CX - mix(220, 760, fan) / 2, top: CY + CH / 2 - 30 + dip, width: mix(220, 760, fan), height: 70,
          borderRadius: '50%', background: `radial-gradient(ellipse at center, ${alpha(L.shadow, 0.28)} 0%, ${alpha(L.shadow, 0)} 70%)`,
          opacity: ramp(f, 6, 20, EASE.out),
        }} />
        <div style={{ position: 'absolute', inset: 0, perspective: '1800px' }}>
          {CARDS.map((c, i) => {
            const p = inAt(f, i);
            const y = (1 - p) * DROP;
            const vy = ((1 - inAt(f + 0.5, i)) - (1 - inAt(f - 0.5, i))) * DROP;
            const blurY = Math.min(10, Math.abs(vy) * 0.18);
            const k = i - (N - 1) / 2;
            // Stack irregularity: deterministic ±3.2° / ±11px mimicking a hand-stacked deck; aligns cleanly on unfold
            const jitR = (rand(i * 3 + 1) - 0.5) * 6.4;
            const jitX = (rand(i * 5 + 2) - 0.5) * 22;
            const tilt = (i % 2 ? 1 : -1) * 9 * (y / DROP); // Alternating tilt angle in mid-flight, converging upon landing
            const rot = mix(jitR + tilt, k * ROT, fan);
            const tx = mix(jitX, k * TX, fan);
            const tz = i * 2;
            const feat = i === FEATURED;
            const ly = feat ? -72 * lift : 0;
            const elev = 6 + (y / DROP) * 50 + (feat ? 26 * lift : 0);
            const visible = f >= START[i];
            if (!visible) return null;
            return (
              <div key={i} style={{
                position: 'absolute', left: CX - CW / 2, top: CY - CH / 2, width: CW, height: CH,
                transformOrigin: '50% 130%',
                transform: `translate3d(${tx.toFixed(2)}px, ${(y + dip + ly).toFixed(2)}px, ${tz}px) rotate(${rot.toFixed(3)}deg) scale(${squeeze.toFixed(4)})`,
                zIndex: i,
              }}>
                {blurY > 0.4 && (
                  <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
                    <filter id={`cs-vb-${i}`} x="-10%" y="-30%" width="120%" height="160%">
                      <feGaussianBlur stdDeviation={`0 ${blurY.toFixed(2)}`} />
                    </filter>
                  </svg>
                )}
                <div style={{
                  position: 'absolute', inset: 0, borderRadius: 22, overflow: 'hidden', background: L.surface,
                  border: `1px solid ${L.line}`, boxSizing: 'border-box',
                  boxShadow: `inset 0 1px 0 rgba(255,255,255,0.9), ${softShadow(elev, { color: L.shadow, strength: 1.15 })}` +
                    (feat && ring > 0 ? `, 0 0 0 ${(3 * ring).toFixed(2)}px ${alpha(L.accent, 0.9 * ring)}` : ''),
                  filter: blurY > 0.4 ? `url(#cs-vb-${i})` : undefined,
                }}>
                  <CardFace c={c} i={i} />
                  {feat && <Sheen progress={sheen} strength={0.7} width={0.18} />}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>

      <div style={{
        position: 'absolute', left: 0, right: 0, top: 268, textAlign: 'center', ...type(34, 450), color: L.ink2,
        opacity: ramp(f, 116, 14, EASE.out), transform: `translateY(${(1 - ramp(f, 116, 18, EASE.snappy)) * 16}px)`,
      }}>
        Nine shot recipes. Every one ready to render.
      </div>
    </AbsoluteFill>
  );
};

// ───────────── Card Face: Cover image + Title + Metadata ─────────────
const COVER_H = 256;
const CardFace: React.FC<{ c: (typeof CARDS)[number]; i: number }> = ({ c, i }) => {
  const hero = c.kind === 'hero';
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <div style={{ position: 'absolute', left: 12, right: 12, top: 12, height: COVER_H, borderRadius: 14, overflow: 'hidden', background: c.tint }}>
        <Cover kind={c.kind} seed={i} />
      </div>
      <div style={{ position: 'absolute', left: 28, right: 28, top: COVER_H + 40 }}>
        <div style={{ fontFamily: FONT.mono, fontSize: 15, letterSpacing: '0.14em', color: hero ? L.accent : L.ink3 }}>{c.meta}</div>
        <div style={{ ...type(32, 650), color: L.ink, marginTop: 10, whiteSpace: 'nowrap' }}>{c.title}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 18 }}>
          {[0, 1, 2].map((k) => (
            <div key={k} style={{ width: 26, height: 26, borderRadius: 13, marginLeft: k ? -14 : 0, border: `2px solid ${L.surface}`, background: ['#c9d3ea', '#b8e3d9', '#dfe3ec'][(k + i) % 3] }} />
          ))}
          <div style={{ fontFamily: FONT.sans, fontSize: 17, color: L.ink3, marginLeft: 4 }}>{`${(2 + rand(i) * 4).toFixed(1)}s · 30 fps`}</div>
        </div>
      </div>
    </div>
  );
};

const Cover: React.FC<{ kind: Kind; seed: number }> = ({ kind, seed }) => {
  const W = 296, H = COVER_H;
  const A = L.accent, T = L.accent2, INK = L.ink;
  const soft = alpha(INK, 0.1);
  switch (kind) {
    case 'gantt':
      return (
        <svg width={W} height={H}>
          {[0, 1, 2, 3, 4, 5].map((r) => {
            const x = 24 + rand(seed * 9 + r) * 110;
            const w = 60 + rand(seed * 5 + r) * 110;
            return <rect key={r} x={x} y={36 + r * 32} width={w} height={18} rx={9} fill={r === 2 ? A : r === 4 ? T : alpha(INK, 0.16)} />;
          })}
          <line x1={168} x2={168} y1={20} y2={236} stroke={A} strokeWidth={2} strokeDasharray="4 5" />
        </svg>
      );
    case 'bars':
      return (
        <svg width={W} height={H}>
          {Array.from({ length: 7 }, (_, k) => {
            const h = 50 + rand(seed * 11 + k) * 130;
            return <rect key={k} x={28 + k * 36} y={214 - h} width={22} height={h} rx={5} fill={k === 5 ? A : alpha(INK, 0.14)} />;
          })}
          <line x1={20} x2={276} y1={214.5} y2={214.5} stroke={soft} />
        </svg>
      );
    case 'line': {
      const pts = Array.from({ length: 9 }, (_, k) => [24 + k * 31, 190 - k * 15 - rand(seed * 7 + k) * 40]);
      const d = pts.map((p, k) => `${k ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
      return (
        <svg width={W} height={H}>
          <path d={`${d} L272,230 L24,230 Z`} fill={alpha(T, 0.18)} />
          <path d={d} fill="none" stroke={T} strokeWidth={4} strokeLinejoin="round" strokeLinecap="round" />
          <circle cx={pts[8][0]} cy={pts[8][1]} r={8} fill={L.surface} stroke={T} strokeWidth={4} />
          <text x={24} y={52} fontFamily={FONT.sans} fontSize={40} fontWeight={700} fill={INK} letterSpacing="-0.03em">+38%</text>
        </svg>
      );
    }
    case 'rings':
      return (
        <svg width={W} height={H}>
          {[0.82, 0.64, 0.46].map((v, k) => {
            const r = 86 - k * 22;
            const C = 2 * Math.PI * r;
            return (
              <g key={k} transform={`rotate(-90 148 128)`}>
                <circle cx={148} cy={128} r={r} fill="none" stroke={alpha(INK, 0.08)} strokeWidth={14} />
                <circle cx={148} cy={128} r={r} fill="none" stroke={k === 0 ? A : k === 1 ? T : alpha(INK, 0.45)} strokeWidth={14} strokeLinecap="round" strokeDasharray={`${C * v} ${C}`} />
              </g>
            );
          })}
        </svg>
      );
    case 'hero':
      return (
        <svg width={W} height={H}>
          <defs>
            <radialGradient id="cs-hero" cx="80%" cy="10%" r="100%">
              <stop offset="0" stopColor="#7d9bff" />
              <stop offset="1" stopColor={A} />
            </radialGradient>
          </defs>
          <rect width={W} height={H} fill="url(#cs-hero)" />
          {[0, 1, 2, 3, 4].map((k) => (
            <circle key={k} cx={250} cy={40} r={60 + k * 44} fill="none" stroke="#ffffff" strokeOpacity={0.22 - k * 0.035} strokeWidth={2} />
          ))}
          {/* Hero template cover insignia replaced with inverted mark (viewfinder paper tone + amber slice), scaled from 128 viewport to 64px, occupying the former "Q4" display position */}
          <g transform="translate(14 140) scale(0.5)">
            <path d={MARK_PATHS.frame} fill={BRAND.paper} />
            <path d={MARK_PATHS.cut} fill={BRAND.amber} />
          </g>
          <text x={24} y={234} fontFamily={FONT.sans} fontSize={30} fontWeight={600} fill="#ffffff" fillOpacity={0.85} letterSpacing="-0.02em">Launch</text>
        </svg>
      );
    case 'table':
      return (
        <div style={{ padding: '26px 22px', display: 'flex', flexDirection: 'column', gap: 0 }}>
          {Array.from({ length: 6 }, (_, r) => (
            <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 12, height: 34, borderBottom: `1px solid ${soft}` }}>
              <div style={{ width: 18, height: 18, borderRadius: 9, background: r === 1 ? A : alpha(INK, 0.14) }} />
              <div style={{ height: 8, width: 70 + rand(seed * 3 + r) * 70, borderRadius: 4, background: alpha(INK, r === 0 ? 0.32 : 0.16) }} />
              <div style={{ flex: 1 }} />
              <div style={{ height: 16, width: 44, borderRadius: 8, background: r === 1 ? alpha(T, 0.3) : alpha(INK, 0.07) }} />
            </div>
          ))}
        </div>
      );
    case 'calendar':
      return (
        <div style={{ padding: 24, display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 7 }}>
          {Array.from({ length: 35 }, (_, k) => {
            const on = rand(seed * 13 + k) > 0.66;
            return <div key={k} style={{ aspectRatio: '1', borderRadius: 6, background: k === 17 ? A : on ? alpha(T, 0.35) : alpha(INK, 0.07) }} />;
          })}
        </div>
      );
    case 'kanban':
      return (
        <div style={{ padding: 22, display: 'flex', gap: 10 }}>
          {[4, 3, 2].map((n, col) => (
            <div key={col} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 9 }}>
              <div style={{ height: 8, width: 40, borderRadius: 4, background: alpha(INK, 0.3) }} />
              {Array.from({ length: n }, (_, r) => (
                <div key={r} style={{ height: 40, borderRadius: 8, background: col === 1 && r === 0 ? A : L.surface, boxShadow: `0 1px 2px ${alpha(INK, 0.1)}`, padding: 9 }}>
                  <div style={{ height: 6, width: 30 + rand(seed + col * 5 + r) * 30, borderRadius: 3, background: col === 1 && r === 0 ? alpha('#ffffff', 0.7) : alpha(INK, 0.18) }} />
                </div>
              ))}
            </div>
          ))}
        </div>
      );
    case 'metric':
    default:
      return (
        <svg width={W} height={H}>
          <text x={24} y={96} fontFamily={FONT.sans} fontSize={66} fontWeight={800} fill={INK} letterSpacing="-0.04em">$2.4M</text>
          <rect x={24} y={116} width={92} height={30} rx={15} fill={alpha(T, 0.22)} />
          <text x={38} y={137} fontFamily={FONT.sans} fontSize={17} fontWeight={700} fill="#007a69">+12.4%</text>
          <path d={Array.from({ length: 12 }, (_, k) => `${k ? 'L' : 'M'}${(24 + k * 22.5).toFixed(1)},${(230 - k * 4 - rand(k + 40) * 26).toFixed(1)}`).join(' ')}
            fill="none" stroke={A} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
  }
};
