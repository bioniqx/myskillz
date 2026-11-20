// cursor-cast-ensemble — figma 0:05 (cursor-badge-cast) + miro ambient cursor ensemble
// Five named colored cursors fly into a whiteboard canvas staggered, drifting continuously to establish a "team presence" atmosphere.
// One cursor (Rita) docks at the central brief card to type the title (cameo); finally, all cursors converge around the card perimeter.
//
// Iteration 2 redesign (porcelain · infinite canvas project kickoff):
// - look = porcelain (cool white + cobalt blue). Context: video-shotcraft storyboard whiteboard: brand mark + board title upper-left, online avatars upper-right,
//   floating dock bottom, with 6 sticky notes (34px legible body) + large central brief card on dot grid.
// - Pervasive identity encoding: 5 team members in 5 colors (Ines cobalt / Kofi emerald / Mei tangerine / Tomás purple / Rita magenta);
//   sticky note backgrounds use soft tints of author colors, author dots in corners; avatars in upper-right pop synchronously on entry.
// - Rita cursor anchors to typing insertion point: title "Ship a launch film by Friday." reveals 88px character-by-character;
//   pointer tip follows insertion point across wraps; card status flips Draft -> Ready upon finish.
// - Space: canvas / sticky notes / brief card / cursors across 4 layers, continuous subtle camera push (1 -> 1.045, focal point on card),
//   distant stickies feature lower parallax and subtle defocus; cursors cast soft shadows + name badges carry tinted glow.
//
// Timeline (30fps, 156f total):
//   0–4      Canvas, stickies, and brief card present from start, camera push begins
//   2–30     Four cursors fly in via spring from four borders (staggered), name badges fade in 10f later; avatars pop synchronously
//   20–46    Rita flies in from top, docking at title origin
//   48–104   Typing: 28 characters + human rhythm jitter (1.6–2.4f/char), steady hand, pointer follows insertion point
//   104–112  Card status Draft -> Ready (green dot)
//   98–126   Remaining four cursors converge around card perimeter (retaining 25% drift), avoiding title
//   126–156  Hold: continuous gentle drift and camera push
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, ramp, mix } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, springAt, type, TYPE } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CURSOR_CAST_ENSEMBLE_DURATION = 156;

const L = LOOKS.porcelain;
const clamp01 = (t: number) => (t < 0 ? 0 : t > 1 ? 1 : t);

const mulberry32 = (a: number) => () => {
  let t = (a += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

type Actor = {
  name: string; initial: string; color: string; tint: string;
  from: [number, number]; home: [number, number]; gather: [number, number];
  delay: number; phase: number;
};

// Badge color = identity encoding: 5 users in 5 colors, matching across stickies, avatars, and cursors
const ACTORS: Actor[] = [
  { name: 'Ines', initial: 'I', color: '#2f5bff', tint: '#e3eaff', from: [-160, 260], home: [330, 470], gather: [318, 372], delay: 2, phase: 0.0 },
  { name: 'Kofi', initial: 'K', color: '#0e9f6e', tint: '#dcf4e8', from: [2080, 220], home: [1600, 470], gather: [1512, 330], delay: 7, phase: 1.7 },
  { name: 'Mei', initial: 'M', color: '#f26a1b', tint: '#ffe9d8', from: [-160, 980], home: [380, 860], gather: [900, 784], delay: 11, phase: 3.1 },
  { name: 'Tomás', initial: 'T', color: '#7b4dff', tint: '#ece4ff', from: [2080, 1000], home: [1540, 880], gather: [1470, 800], delay: 16, phase: 4.4 },
  { name: 'Rita', initial: 'R', color: '#ec2f7c', tint: '#ffe2ee', from: [980, -200], home: [0, 0], gather: [0, 0], delay: 22, phase: 5.6 },
];
const RITA = 4;

// Brief card (canvas coordinates)
const CARD = { x: 432, y: 318, w: 1056, h: 432, pad: 56 };
const TITLE = 'Ship a launch film by Friday.'; // 29 chars with 5 spaces: typing cadence and outro unchanged
const TITLE_FS = 88;
const TITLE_TOP = CARD.y + CARD.pad + 66; // Below eyebrow row
const TYPE0 = 48;
const READY = 106;

// Human typing cadence: 1.6–2.4f per character (deterministic jitter), subtle pause after spaces
const TYPE_AT: number[] = (() => {
  const r = mulberry32(41);
  const at: number[] = [];
  let f = TYPE0;
  for (let i = 0; i < TITLE.length; i++) {
    at.push(f);
    f += 1.6 + r() * 0.8 + (TITLE[i] === ' ' ? 0.9 : 0);
  }
  return at;
})();
const TYPE_END = TYPE_AT[TYPE_AT.length - 1];

// Sticky notes: author = ACTORS index; depth 0 near / 1 far (far layer smaller, softer, lower parallax)
const NOTES = [
  // Sticky notes represent storyboard and production tasks for this film
  { x: 96, y: 156, rot: -3.2, owner: 0, depth: 1, title: 'Open on a crash zoom', meta: '4 votes' },
  { x: 1540, y: 150, rot: 2.6, owner: 1, depth: 1, title: 'Logo sting outro', meta: 'In review' },
  { x: 60, y: 560, rot: 2.2, owner: 2, depth: 0, title: 'Beat map at 120 BPM', meta: '2 comments' },
  { x: 1580, y: 560, rot: -2.4, owner: 3, depth: 0, title: 'Real page captures', meta: 'Due Wed' },
  { x: 560, y: 812, rot: -1.6, owner: 4, depth: 1, title: 'Renders: 214', meta: 'Live count' },
  { x: 1090, y: 820, rot: 1.8, owner: 0, depth: 1, title: 'SFX pass', meta: 'Needs mix' },
];

const ARROW = 'M0.5 0.5 L0.5 17.2 L4.7 13.4 L7.3 19.5 L10 18.3 L7.4 12.3 L13 12.3 Z';
const CK = 4.2; // Cursor scale units (≈84px height)

const Cursor: React.FC<{ a: Actor; badge: number; style?: React.CSSProperties }> = ({ a, badge, style }) => (
  <div style={{ position: 'absolute', ...style }}>
    <svg width={14 * CK} height={21 * CK} viewBox="0 0 14 21" style={{ display: 'block', overflow: 'visible', filter: `drop-shadow(0 3px 4px ${alpha(L.shadow, 0.28)})` }}>
      <path d={ARROW} fill={a.color} stroke="#ffffff" strokeWidth={1.1} strokeLinejoin="round" />
    </svg>
    <div style={{
      position: 'absolute', left: 9.4 * CK, top: 17.6 * CK, whiteSpace: 'nowrap',
      background: `linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0) 50%), ${a.color}`,
      color: '#fff', borderRadius: '6px 18px 18px 18px', padding: '7px 16px 8px',
      ...type(26, 680), letterSpacing: '-0.005em',
      boxShadow: `inset 0 1px 0 rgba(255,255,255,0.3), 0 2px 4px ${alpha(L.shadow, 0.14)}, 0 8px 22px -6px ${alpha(a.color, 0.55)}`,
      opacity: badge, transform: `translateY(${(1 - badge) * 12}px)`,
    }}>
      {a.name}
    </div>
  </div>
);

export const CursorCastEnsemble: React.FC = () => {
  const f = useCurrentFrame();

  // Camera push: gentle push throughout, focused slightly above card center
  const cam = mix(1, 1.045, ramp(f, 0, 156, EASE.swift));
  const camFar = mix(1, 1.02, ramp(f, 0, 156, EASE.swift));

  const gatherT = ramp(f, 98, 28, EASE.smooth);
  const typed = TYPE_AT.filter((t) => f >= t).length;
  const ready = ramp(f, READY, 8, EASE.out);
  const typingHold = clamp01((f - 40) / 8); // Steady hand anchor

  // Cursor positions (canvas coordinates)
  const posOf = (i: number): [number, number] => {
    const a = ACTORS[i];
    const s = springAt(f, a.delay, { damping: 15, stiffness: 80, mass: 0.9 });
    let x = mix(a.from[0], a.home[0], s);
    let y = mix(a.from[1], a.home[1], s);
    const settled = clamp01((f - a.delay - 20) / 12);
    const dX = Math.sin(f * 0.055 + a.phase) * 40 + Math.sin(f * 0.021 + a.phase * 2) * 26;
    const dY = Math.cos(f * 0.047 + a.phase * 1.3) * 32 + Math.cos(f * 0.017 + a.phase) * 20;
    x += dX * settled * (1 - gatherT);
    y += dY * settled * (1 - gatherT);
    x = mix(x, a.gather[0] + dX * 0.25, gatherT);
    y = mix(y, a.gather[1] + dY * 0.25, gatherT);
    return [x, y];
  };

  // Rita: fly-in offset relative to insertion point, locks to insertion point on landing
  const rita = ACTORS[RITA];
  const rs = springAt(f, rita.delay, { damping: 16, stiffness: 70, mass: 1 });
  const anchor0: [number, number] = [CARD.x + CARD.pad, TITLE_TOP];
  const rDrift = 1 - typingHold * (f < TYPE_END + 6 ? 1 : 1 - clamp01((f - TYPE_END - 6) / 14) * 0.75);
  const ritaOff: [number, number] = [
    // Settled offset (12, -8): pointer tip sits upper right of caret, avoiding overlapping typed characters
    (rita.from[0] - anchor0[0]) * (1 - rs) + 12 + Math.sin(f * 0.06 + 1) * 18 * rDrift,
    (rita.from[1] - anchor0[1]) * (1 - rs) - 8 + Math.cos(f * 0.05) * 14 * rDrift,
  ];
  const caretOn = typed < TITLE.length || Math.floor(f / 9) % 2 === 0;

  const avatarPop = (i: number) => springAt(f, ACTORS[i].delay + 8, { damping: 15, stiffness: 190 });

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.36 }} fill={{ x: 0.9, y: 0.95 }} vignette={0.2}>
        {/* Dot grid canvas (far layer, subtle parallax) */}
        <div style={{
          position: 'absolute', inset: -60, transform: `scale(${camFar})`, transformOrigin: '50% 50%',
          backgroundImage: `radial-gradient(${alpha(L.ink, 0.13)} 1.6px, transparent 1.9px)`, backgroundSize: '40px 40px',
          WebkitMaskImage: 'radial-gradient(ellipse 75% 75% at 50% 50%, #000 45%, transparent 100%)',
          maskImage: 'radial-gradient(ellipse 75% 75% at 50% 50%, #000 45%, transparent 100%)',
        }} />
      </Stage>

      {/* Canvas layer (stickies + brief card + cursors) scales with camera push */}
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam})`, transformOrigin: '50% 48%' }}>
        {NOTES.map((n, i) => {
          const o = ACTORS[n.owner];
          const far = n.depth === 1;
          return (
            <div key={i} style={{
              position: 'absolute', left: n.x, top: n.y, width: 288, height: 232, borderRadius: 10,
              background: `linear-gradient(180deg, rgba(255,255,255,0.5), rgba(255,255,255,0) 30%), ${o.tint}`,
              boxShadow: `inset 0 1px 0 rgba(255,255,255,0.9), 0 1px 2px ${alpha(L.shadow, 0.08)}, 0 18px 34px -16px ${alpha(L.shadow, 0.3)}`,
              transform: `rotate(${n.rot}deg) scale(${far ? 0.94 : 1})`,
              filter: far ? 'blur(1.4px) saturate(0.85)' : undefined, opacity: far ? 0.78 : 1,
              padding: '26px 26px 22px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column',
            }}>
              <div style={{ ...type(36, 700), color: alpha(L.ink, 0.86), lineHeight: 1.12 }}>{n.title}</div>
              <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 14, height: 14, borderRadius: 7, background: o.color }} />
                <span style={{ ...type(24, 560), color: alpha(L.ink, 0.5) }}>{o.name} · {n.meta}</span>
              </div>
            </div>
          );
        })}

        {/* Central brief card: active workspace for Rita */}
        <div style={{
          position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: 28,
          background: 'linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%)', border: `1px solid ${L.line}`,
          boxShadow: `inset 0 1px 0 #fff, 0 2px 4px ${alpha(L.shadow, 0.06)}, 0 40px 80px -30px ${alpha(L.shadow, 0.35)}`,
          padding: CARD.pad, boxSizing: 'border-box',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, height: 40 }}>
            <span style={{ ...type(TYPE.label + 2, 700, { caps: true }), letterSpacing: '0.16em', color: L.ink3 }}>Project brief</span>
            <span style={{ width: 5, height: 5, borderRadius: 3, background: L.ink3 }} />
            <span style={{ ...type(28, 520), color: L.ink2 }}>Due Thu, Oct 16</span>
            {/* Status: Draft -> Ready */}
            <span style={{
              marginLeft: 'auto', position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 10, height: 44, padding: '0 18px',
              borderRadius: 22, background: ready > 0.5 ? alpha('#0e9f6e', 0.1) : L.surface2,
              border: `1px solid ${ready > 0.5 ? alpha('#0e9f6e', 0.3) : L.line}`,
              transform: `scale(${1 + 0.06 * Math.sin(Math.PI * ready)})`,
            }}>
              <span style={{ width: 12, height: 12, borderRadius: 6, background: ready > 0.5 ? '#0e9f6e' : L.ink3 }} />
              <span style={{ ...type(26, 650), color: ready > 0.5 ? '#0b7a55' : L.ink2 }}>{ready > 0.5 ? 'Ready' : 'Draft'}</span>
            </span>
          </div>
          {/* Title: character reveal + Rita caret anchor */}
          <div style={{ marginTop: 26, ...type(TITLE_FS, 760), color: L.ink, lineHeight: 1.04, minHeight: TITLE_FS * 2.1 }}>
            {TITLE.slice(0, typed)}
            <span style={{ position: 'relative', display: 'inline-block', width: 0, height: TITLE_FS * 0.8, verticalAlign: '-0.06em' }}>
              <span style={{
                position: 'absolute', left: 3, top: -4, width: 6, height: TITLE_FS * 0.92, borderRadius: 3, background: rita.color,
                opacity: f >= TYPE0 - 6 && caretOn ? 1 : 0,
              }} />
              <Cursor a={rita} badge={ramp(f, rita.delay + 12, 12, EASE.out)} style={{ left: ritaOff[0], top: ritaOff[1], zIndex: 5 }} />
            </span>
          </div>
          {/* Card footer: owner + progress metadata */}
          <div style={{ position: 'absolute', left: CARD.pad, right: CARD.pad, bottom: CARD.pad - 6, display: 'flex', alignItems: 'center', gap: 28 }}>
            <span style={{ display: 'flex' }}>
              {[4, 0, 1].map((k, j) => (
                <span key={k} style={{
                  width: 44, height: 44, borderRadius: 22, background: ACTORS[k].color, marginLeft: j ? -12 : 0, border: '3px solid #fff',
                  display: 'grid', placeItems: 'center', color: '#fff', ...type(20, 760),
                }}>{ACTORS[k].initial}</span>
              ))}
            </span>
            <span style={{ ...type(30, 540), color: L.ink2 }}>3 owners · 12 shots</span>
            <span style={{ marginLeft: 'auto', width: 260, height: 10, borderRadius: 5, background: L.surface2, overflow: 'hidden', border: `1px solid ${L.line}` }}>
              <span style={{ display: 'block', height: '100%', width: `${mix(38, 72, ready)}%`, borderRadius: 5, background: L.accent }} />
            </span>
            <span style={{ ...type(30, 650), color: L.ink, width: 70, textAlign: 'right' }}>{Math.round(mix(38, 72, ready))}%</span>
          </div>
        </div>

        {/* Remaining four cursors */}
        {ACTORS.slice(0, 4).map((a, i) => {
          const [x, y] = posOf(i);
          return <Cursor key={a.name} a={a} badge={ramp(f, a.delay + 10, 12, EASE.out)} style={{ left: x, top: y, zIndex: 10 }} />;
        })}
      </div>

      {/* UI chrome (anchored, immune to push): board title upper left, avatar stack upper right, dock bottom */}
      <div style={{ position: 'absolute', left: 64, top: 48, display: 'flex', alignItems: 'center', gap: 18 }}>
        <span style={{ width: 48, height: 48, borderRadius: 14, background: L.ink, display: 'grid', placeItems: 'center' }}>
          <ShotcraftMark size={34} tone="dark" />
        </span>
        <span style={{ ...type(32, 700), color: L.ink }}>Launch Film Kickoff</span>
        <span style={{ ...type(26, 500), color: L.ink3 }}>{BRAND.name}</span>
      </div>
      <div style={{ position: 'absolute', right: 64, top: 46, display: 'flex', alignItems: 'center', gap: 18 }}>
        <span style={{ display: 'flex' }}>
          {ACTORS.map((a, i) => {
            const p = avatarPop(i);
            return (
              // Slot expands dynamically: avatars slide in smoothly from right without empty gaps
              <span key={a.name} style={{ position: 'relative', width: (i ? 42 : 56) * clamp01(p), height: 56 }}>
                <span style={{
                  position: 'absolute', right: 0, top: 0, width: 56, height: 56, borderRadius: 28, background: a.color, border: '3px solid #fff',
                  boxSizing: 'border-box', display: 'grid', placeItems: 'center', color: '#fff', ...type(24, 760),
                  transform: `scale(${p})`, opacity: clamp01(p * 3), boxShadow: `0 4px 12px -4px ${alpha(a.color, 0.6)}`,
                }}>{a.initial}</span>
              </span>
            );
          })}
        </span>
        <span style={{
          height: 52, padding: '0 22px', borderRadius: 26, background: L.accent, color: '#fff', display: 'grid', placeItems: 'center', ...type(26, 680),
          boxShadow: `0 8px 20px -8px ${alpha(L.accent, 0.7)}`,
        }}>Share</span>
      </div>
      <div style={{
        position: 'absolute', left: '50%', bottom: 40, transform: 'translateX(-50%)', height: 72, padding: '0 14px', borderRadius: 22,
        background: alpha('#ffffff', 0.92), border: `1px solid ${L.line}`, display: 'flex', alignItems: 'center', gap: 6,
        boxShadow: `inset 0 1px 0 #fff, 0 16px 36px -14px ${alpha(L.shadow, 0.3)}`,
      }}>
        {['select', 'hand', 'note', 'text', 'shape', 'pen'].map((k, i) => (
          <span key={k} style={{
            width: 52, height: 52, borderRadius: 14, display: 'grid', placeItems: 'center',
            background: i === 2 ? alpha(L.accent, 0.1) : 'transparent',
          }}>
            <svg width={26} height={26} viewBox="0 0 26 26" fill="none" stroke={i === 2 ? L.accent : L.ink2} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              {k === 'select' && <path d="M7 5v15l4-4 3 6 3-1.4-3-5.8h6z" />}
              {k === 'hand' && <path d="M9 13V7.5a1.5 1.5 0 0 1 3 0V12M12 11V6a1.5 1.5 0 0 1 3 0v5M15 11V7a1.5 1.5 0 0 1 3 0v7c0 4-2.5 6.5-6 6.5S7 18 6 15l-1.5-3a1.5 1.5 0 0 1 2.6-1.5L9 13" />}
              {k === 'note' && <path d="M6 5h14v10l-5 5H6zM15 20v-5h5" />}
              {k === 'text' && <path d="M6 7V5h14v2M13 5v16M10 21h6" />}
              {k === 'shape' && <><rect x={5} y={5} width={9} height={9} rx={2} /><circle cx={17} cy={17} r={4.5} /></>}
              {k === 'pen' && <path d="M5 21l1.2-4.6L17 5.6a2 2 0 0 1 2.8 2.8L9 19.2zM15 7.6l3.4 3.4" />}
            </svg>
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};
