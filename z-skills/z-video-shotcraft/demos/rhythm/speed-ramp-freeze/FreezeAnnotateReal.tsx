// freeze-annotate — Freeze on real card stream in motion, marker circle + arrow on target card, thaw and resume.
//
// Redesign ("Review Pause" — porcelain white + cobalt blue marker):
// - look = porcelain (cool white stage, cobalt blue accent). Main focus remains real product project card stream (2x screenshot texture, Q1);
//   cards stand on a cool white plinth with top lighting and contact shadow, rather than flat page screenshots.
// - Freeze feels like hitting pause: at 45f cuts to slope 0 in a single frame — shutter white flash for 3f, cobalt blue framing brackets spring in over 8f,
//   top-left timecode flips from "● LIVE 00:00:01:14" to "❚❚ PAUSED" and halts; other cards desaturate and fade, while the target card is lifted.
// - Annotation uses a cobalt blue marker: single-stroke superellipse (1.08 turns, open-ended, feTurbulence hand-drawn jitter) drawn in 10f ->
//   curved arrow shaft 6f + arrowhead 3f -> top-right 68px bold note "Ship this first." rises from below line + hand-drawn underline ->
//   signature row. Ink fades out 8f before thawing, leaving a comment pin "1" on the target card corner trailing off-screen — persisting the annotation.
// - Thaw: ease-in start (smootherstep), completes one card travel in 22f (average slope >1 compensating for paused time),
//   directional blur during fast sprint, settling with the next card centered and the pinned target card resting on the left.
//
// Timeline (30fps, 158f total):
//   0–45    Stream 1x (26px/f, subtle blur), running timecode — moves from frame 1
//   45      Freeze (hard cut, no ease-in): shutter flash 45–48, framing brackets spring in 45–53, timecode turns to PAUSED
//   45–55   Lift target card, desaturate and fade remaining cards
//   54–64   Single marker circle stroke (10f); 64–70 arrow shaft, 70–73 arrowhead
//   66–78   Note rises; 78–88 underline; 84–96 signature
//   96–108  Hold (reading)
//   104–112 Ink fades, framing brackets retract; pin drops onto card corner at 104
//   112–134 Thaw: ease-in start -> brake to stop, one card pitch (peak ~55px/f, avg slope >1)
//   134–158 Hold 24f: static settle, pinned target card stays on left
import React, { useId } from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import layout from '../../_textures/live-layout.json';
import { EASE, FONT, SpeedBlur, mix, ramp, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const FREEZEANNOTATE_DUR = 158;

const L = LOOKS.porcelain;
const INK = L.accent; // Cobalt blue marker

const CARD_W = 600;
const GAP = 52;
const PITCH = CARD_W + GAP;
const RAIL = layout.projects.cards;
const TARGET_K = 5;
const TARGET_FILE = 'card9.png'; // nano-lab: automated research loop
const SHIFT = RAIL.findIndex((c) => c.file === TARGET_FILE) - TARGET_K;
const fileOf = (k: number) => RAIL[(((k + SHIFT) % RAIL.length) + RAIL.length) % RAIL.length].file;
const cardH = (file: string) => (file === 'card1.png' || file === 'card2.png' ? (CARD_W * 576) / 716 : (CARD_W * 624) / 716);
const RAIL_TOP = 336;
const PX = 26; // Track displacement per source frame (px)

const FREEZE = 45;
const THAW = 112;
const LAND = 134;
const THAW_SRC = PITCH / PX; // Source frame travel for one card during thaw (pinned target card rests on left in end poster)

// Remap: stream slope 1 -> freeze slope 0 (hard cut) -> thaw smootherstep (ease-in start, peak slope ~2.1, settle to 0)
const srcAt = (f: number) => {
  if (f <= FREEZE) return Math.max(0, f);
  if (f <= THAW) return FREEZE;
  const t = Math.min(1, (f - THAW) / (LAND - THAW));
  return FREEZE + THAW_SRC * t * t * t * (t * (6 * t - 15) + 10);
};
// Target card center aligns to screen center when frozen
const OFFSET = 960 - (TARGET_K * PITCH + CARD_W / 2) + FREEZE * PX;
const railX = (f: number) => OFFSET - srcAt(f) * PX;

// Target card display dimensions -> annotation geometry (lifted -16px and scaled 3% during freeze)
const TARGET_H = cardH(TARGET_FILE);
const CX = 960;
const CY = RAIL_TOP + TARGET_H / 2 - 16;
const RX = 1.2 * (CARD_W / 2) * 1.03;
const RY = 1.22 * (TARGET_H / 2) * 1.03;
const SE = 2 / 3; // Superellipse parameter exponent 2/n (n=3)

// Single marker circle: starts top-left, clockwise 1.08 turns, radius tightens 4% (open finish, hand-drawn feel)
const circlePath = (() => {
  const N = 140;
  const a0 = -2.3;
  const pts: string[] = [];
  for (let i = 0; i <= N; i++) {
    const u = i / N;
    const a = a0 + u * Math.PI * 2 * 1.08;
    const k = 1 - 0.04 * u;
    const c = Math.cos(a), sn = Math.sin(a);
    const px = Math.sign(c) * Math.pow(Math.abs(c), SE) * RX * k;
    const py = Math.sign(sn) * Math.pow(Math.abs(sn), SE) * RY * k;
    pts.push(`${(CX + px).toFixed(1)} ${(CY + py).toFixed(1)}`);
  }
  return `M ${pts.join(' L ')}`;
})();

// Timecode (30fps): freezes when paused
const timecode = (f: number) => {
  const total = 30 * 72 + Math.floor(srcAt(f)); // Starting from 00:00:01:12
  const ff = total % 30;
  const ss = Math.floor(total / 30) % 60;
  const mm = Math.floor(total / 1800) % 60;
  const p = (n: number) => String(n).padStart(2, '0');
  return `00:${p(mm)}:${p(ss)}:${p(ff)}`;
};

// Framing brackets
const Bracket: React.FC<{ x: number; y: number; sx: 1 | -1; sy: 1 | -1; s: number }> = ({ x, y, sx, sy, s }) => (
  <div
    style={{
      position: 'absolute',
      left: sx === 1 ? x : x - 64,
      top: sy === 1 ? y : y - 64,
      width: 64,
      height: 64,
      borderLeft: sx === 1 ? `4px solid ${INK}` : undefined,
      borderRight: sx === -1 ? `4px solid ${INK}` : undefined,
      borderTop: sy === 1 ? `4px solid ${INK}` : undefined,
      borderBottom: sy === -1 ? `4px solid ${INK}` : undefined,
      transform: `translate(${(-sx * (1 - s) * 40).toFixed(1)}px, ${(-sy * (1 - s) * 40).toFixed(1)}px)`,
      opacity: Math.min(1, s * 1.5),
    }}
  />
);

export const FreezeAnnotateReal: React.FC = () => {
  const frame = useCurrentFrame();
  const roughId = `rough-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;

  const x0 = railX(frame);
  const v = velocity(railX, frame);
  const frozen = frame >= FREEZE && frame < THAW;
  const blurV = frozen ? 0 : Math.sign(v) * Math.max(0, Math.abs(v) - 8);

  // Freeze focus: lift target card over 10f, fade out others; restore before thawing
  const focus = ramp(frame, FREEZE, 10, EASE.snappy) * (1 - ramp(frame, THAW - 8, 12, EASE.swift));
  const flash = frame >= FREEZE ? 1 - ramp(frame, FREEZE, 4, EASE.out) : 0;
  const frameIn = frame >= FREEZE ? springAt(frame, FREEZE, { damping: 16, stiffness: 260 }) : 0;
  const frameOut = ramp(frame, 104, 8, EASE.exit);
  const bracket = frameIn * (1 - frameOut);

  // Annotation timing
  const draw = ramp(frame, 54, 10, EASE.swift);
  const shaft = ramp(frame, 64, 6, EASE.out);
  const head = ramp(frame, 70, 3, EASE.out);
  const under = ramp(frame, 78, 10, EASE.swift);
  const sign = ramp(frame, 84, 12, EASE.out);
  const fade = 1 - ramp(frame, 104, 8, EASE.out);
  const showInk = frame >= 54 && fade > 0.001;

  // Pin: drops onto top-right corner of target card as ink fades, exits with card
  const pin = frame >= 104 ? springAt(frame, 104, { damping: 13, stiffness: 240 }) : 0;

  // Arrow: top-right note -> top-right edge of circle
  const ax0 = 1296, ay0 = 262;
  const ax1 = CX + RX * 0.72, ay1 = CY - RY * 0.78;
  const qx = ax1 + 30, qy = ay0 + 4;
  const arrowD = `M ${ax0} ${ay0} Q ${qx} ${qy} ${ax1} ${ay1}`;
  const ang = Math.atan2(ay1 - qy, ax1 - qx);
  const wing = (s: number) =>
    `M ${ax1.toFixed(1)} ${ay1.toFixed(1)} L ${(ax1 - Math.cos(ang + s * 0.5) * 34).toFixed(1)} ${(ay1 - Math.sin(ang + s * 0.5) * 34).toFixed(1)}`;

  const cards: React.ReactNode[] = [];
  for (let k = 0; k < 14; k++) {
    const left = x0 + k * PITCH;
    if (left > 1980 || left + CARD_W < -60) continue;
    const file = fileOf(k);
    const isT = k === TARGET_K;
    const h = cardH(file);
    const lift = isT ? focus : 0;
    cards.push(
      <div
        key={k}
        style={{
          position: 'absolute',
          left: k * PITCH,
          top: 0,
          width: CARD_W,
          height: h,
          transform: isT ? `translateY(${(-16 * lift).toFixed(2)}px) scale(${(1 + 0.03 * lift).toFixed(4)})` : undefined,
          opacity: isT ? 1 : 1 - 0.5 * focus,
          filter: !isT && focus > 0.01 ? `saturate(${(1 - 0.9 * focus).toFixed(3)})` : undefined,
          zIndex: isT ? 2 : 1,
        }}
      >
        {/* Two-layer soft shadow: contact shadow + ambient shadow (deepened and expanded when lifted) */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 16,
            boxShadow: `0 2px 4px ${alpha(L.shadow, 0.08)}, 0 ${(24 + 26 * lift).toFixed(0)}px ${(60 + 40 * lift).toFixed(0)}px -18px ${alpha(L.shadow, 0.22 + 0.14 * lift)}`,
          }}
        />
        <Img
          src={staticFile(`textures/live/${file}`)}
          style={{ position: 'relative', width: '100%', height: '100%', display: 'block', borderRadius: 16 }}
        />
        {isT && pin > 0.001 && (
          <div
            style={{
              position: 'absolute',
              right: -22,
              top: -22,
              width: 52,
              height: 52,
              borderRadius: '26px 26px 26px 6px',
              background: INK,
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transform: `scale(${pin.toFixed(4)})`,
              transformOrigin: '0% 100%',
              boxShadow: `0 8px 20px -6px ${alpha(INK, 0.6)}`,
              ...type(26, 750),
            }}
          >
            1
          </div>
        )}
      </div>,
    );
  }

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden', fontFamily: FONT.sans }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.1 }} fill={{ x: 0.5, y: 1.0 }} horizon={0.86} />
      {/* Plinth surface: subtle cool gray ground plane grounding cards on stage */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: RAIL_TOP + TARGET_H + 26,
          height: 120,
          background: `radial-gradient(ellipse 60% 50% at 50% 0%, ${alpha(L.shadow, 0.08)} 0%, ${alpha(L.shadow, 0)} 70%)`,
        }}
      />

      {/* Track rail */}
      <SpeedBlur vx={blurV} amount={0.3} max={26}>
        <div style={{ position: 'absolute', left: 0, top: RAIL_TOP, transform: `translateX(${x0.toFixed(2)}px)` }}>{cards}</div>
      </SpeedBlur>

      {/* Top-left: timecode (freezes on pause) */}
      <div style={{ position: 'absolute', left: 96, top: 96, display: 'flex', alignItems: 'center', gap: 18 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '10px 18px',
            borderRadius: 12,
            background: frozen ? INK : alpha(L.ink, 0.06),
            color: frozen ? '#fff' : L.ink2,
            ...type(24, 750, { mono: true }),
            letterSpacing: '0.12em',
          }}
        >
          {frozen ? (
            <span style={{ display: 'flex', gap: 5 }}>
              <span style={{ width: 6, height: 20, background: '#fff', borderRadius: 1 }} />
              <span style={{ width: 6, height: 20, background: '#fff', borderRadius: 1 }} />
            </span>
          ) : (
            <span style={{ width: 12, height: 12, borderRadius: 6, background: '#e5484d' }} />
          )}
          {frozen ? 'PAUSED' : 'LIVE'}
        </div>
        <span style={{ ...type(30, 600, { mono: true }), color: frozen ? INK : L.ink2 }}>{timecode(frame)}</span>
      </div>
      {/* Top-right: video-shotcraft wordmark + review session (fades out on freeze to make room for note) */}
      <div style={{ position: 'absolute', right: 96, top: 96, display: 'flex', alignItems: 'center', gap: 16, opacity: 1 - focus }}>
        <ShotcraftMark size={44} tone="light" />
        <span style={{ ...type(32, 700), fontFamily: BRAND.font, letterSpacing: '0.02em', color: L.ink }}>{BRAND.name}</span>
        <span style={{ ...type(30, 450), color: L.ink3 }}>Shot review</span>
      </div>

      {/* Marker ink: circle + arrow + underline */}
      {showInk && (
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: fade, mixBlendMode: 'multiply' }}>
          <defs>
            <filter id={roughId}>
              <feTurbulence type="fractalNoise" baseFrequency="0.022" numOctaves="2" seed="11" result="n" />
              <feDisplacementMap in="SourceGraphic" in2="n" scale="6" />
            </filter>
          </defs>
          <g filter={`url(#${roughId})`} fill="none" stroke={INK} strokeLinecap="round" strokeLinejoin="round" opacity={0.92}>
            <path d={circlePath} strokeWidth={11} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - draw} transform={`rotate(-3 ${CX} ${CY})`} />
            {shaft > 0 && <path d={arrowD} strokeWidth={8} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - shaft} />}
            {head > 0 && (
              <>
                <path d={wing(1)} strokeWidth={8} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - head} />
                <path d={wing(-1)} strokeWidth={8} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - head} />
              </>
            )}
            {under > 0 && (
              <path
                d="M 1318 214 C 1430 206 1590 210 1728 202"
                strokeWidth={8}
                pathLength={1}
                strokeDasharray="1 1"
                strokeDashoffset={1 - under}
              />
            )}
          </g>
        </svg>
      )}

      {/* Note: bold cobalt blue rising from underline; author signature */}
      {showInk && frame >= 66 && (
        <div style={{ position: 'absolute', left: 1318, top: 112, opacity: fade, transform: 'rotate(-2deg)', transformOrigin: '0% 100%' }}>
          <div style={{ ...type(68, 820), color: INK, whiteSpace: 'nowrap' }}>
            <TextReveal text="Ship this first." by="word" variant="rise" start={66} each={14} gap={3} />
          </div>
        </div>
      )}
      {showInk && sign > 0 && (
        <div
          style={{
            position: 'absolute',
            left: 1322,
            top: 240,
            opacity: sign * fade,
            transform: `translateY(${mix(10, 0, sign).toFixed(2)}px)`,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            ...type(30, 550),
            color: L.ink2,
          }}
        >
          <span style={{ width: 34, height: 34, borderRadius: 17, background: `linear-gradient(135deg, #8aa4ff, ${INK})`, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', ...type(18, 750) }}>
            M
          </span>
          Marco · design review
        </div>
      )}

      {/* Framing brackets (visible only during freeze) */}
      {bracket > 0.001 && (
        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          <Bracket x={48} y={48} sx={1} sy={1} s={bracket} />
          <Bracket x={1872} y={48} sx={-1} sy={1} s={bracket} />
          <Bracket x={48} y={1032} sx={1} sy={-1} s={bracket} />
          <Bracket x={1872} y={1032} sx={-1} sy={-1} s={bracket} />
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              bottom: 64,
              textAlign: 'center',
              opacity: bracket,
              ...type(22, 700, { mono: true }),
              letterSpacing: '0.24em',
              color: alpha(INK, 0.8),
            }}
          >
            FRAME HELD · 0 FPS
          </div>
        </AbsoluteFill>
      )}

      {/* Shutter white flash */}
      {flash > 0.001 && <AbsoluteFill style={{ background: '#ffffff', opacity: 0.7 * flash, pointerEvents: 'none' }} />}
    </AbsoluteFill>
  );
};
