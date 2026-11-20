// basic-3d-scene — impress.js spatial steps (round 2 redesign)
// Cards scattered in 3D space (x, y, z, rotation, scale); camera flies sequentially inverting poses,
// pulling back to OVERVIEW at the end. Core formula: camera = stepTransform.inverse().
//
// Design decisions
// - look: graphite (monochrome dark ground with champagne gold accents) — spatial 3-chapter narrative.
//   Three chapters: Frame / Craft / Ship, culminating in brand outro "Craft the shot."
// - 1240x700 native 1:1 layout for sharp text without scaling blur; 150px title + 420px light chapter digits.
// - Spatial depth: 70 3D dust motes fixed in world space providing true camera parallax;
//   non-current cards defocus based on stop distance; 30% mid-flight pull-back hop.
// - Gold progress bar advances during card holds; titles reveal word-by-word 8f before landing.
// - Motion blur: shutter 0.5f time-sampled adaptive sub-frames during flight, zero overhead during holds.
//
// Timeline (30fps, 225f = 7.5s)
//   0-36    Stop 1 Capture: camera settles smoothly (30f); title rises at 2f; progress line fills
//   36-64   Flight 1->2 (28f): slide right + rotate 38 deg, 30% hop
//   64-96   Stop 2 Connect: 32f hold
//   96-128  Flight 2->3 (32f): 90 deg tilt alignment
//   128-158 Stop 3 Ship: 30f hold
//   158-190 Flight 3->Overview (32f): 1/2.7 camera pull-back
//   184-212 Outro: title reveal "Craft the shot."
//   206-224 Hold: gentle 1.5% push-in to final poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, bezier, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, SERIF, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const BASIC_3D_SCENE_DURATION = 225; // 7.5s @30fps

const L = LOOKS.graphite;
const GOLD = L.accent2;
const CW = 1240; // Native card dimensions (1:1 on screen at alignment)
const CH = 700;
const PERSP = 2600;

type Pose = { x: number; y: number; z: number; rx: number; ry: number; rz: number; s: number };
// Stop poses (camera inverts these): Stop 2 yaw -38 deg, Stop 3 roll 90 deg, Overview s=2.7
const POSES: Pose[] = [
  { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0, s: 1 },
  { x: 1690, y: -260, z: -650, rx: 0, ry: -38, rz: 0, s: 1 },
  { x: 2590, y: 830, z: -850, rx: 0, ry: 0, rz: 90, s: 1 },
  { x: 594, y: 480, z: -400, rx: 0, ry: 0, rz: 0, s: 2.7 },
];
const CHAPTERS = [
  { no: '01', kicker: 'Frame', title: 'Frame.', body: 'Real page captures, staged for the camera.' },
  { no: '02', kicker: 'Craft', title: 'Craft.', body: 'Shot recipe cards turn moves into code.' },
  { no: '03', kicker: 'Ship', title: 'Ship.', body: 'One prompt to a finished promo.' },
];

// Flight schedule (frames): [start, end]
const FLIGHTS: [number, number][] = [[36, 64], [96, 128], [158, 190]];
const ARRIVE = [0, 64, 128, 190]; // Landing frames for each stop
const HOLD_END = [36, 96, 158, 225];
const FLY_EASE = bezier(0.62, 0, 0.16, 1); // Asymmetric in-out easing
const HOP = 0.3; // Mid-flight hop zoom ratio

// Camera pose as pure function of frame (supports fractional frames for blur sampling)
const camAt = (f: number) => {
  const cam: Pose = { ...POSES[0] };
  // Intro: gentle push-in from 1.06x distance
  cam.s = mix(1.06, 1, ramp(f, 0, 30, EASE.snappy));
  let af = 0; // Cumulative flight progress (0..3)
  let hop = 0;
  FLIGHTS.forEach(([a, b], i) => {
    const u = ramp(f, a, b - a, FLY_EASE);
    af += u;
    const p = POSES[i + 1];
    (Object.keys(cam) as (keyof Pose)[]).forEach((k) => {
      cam[k] = mix(cam[k], p[k], u);
    });
    if (i < 2 && u > 0 && u < 1) hop = HOP * Math.sin(Math.PI * u);
  });
  cam.s *= 1 + hop;
  // Gentle 1.5% push-in during holds
  let creep = 0;
  for (let i = 0; i < 3; i++) {
    creep += ramp(f, ARRIVE[i] + 4, HOLD_END[i] - ARRIVE[i], EASE.smooth) * (1 - ramp(f, FLIGHTS[i][0], 14, EASE.smooth));
  }
  cam.s *= 1 - 0.015 * creep;
  // Gentle 1.5% push-in after overview settles
  cam.s *= 1 - 0.015 * ramp(f, 196, 29, EASE.smooth);
  return { cam, af };
};

const camTransform = (c: Pose) =>
  `scale(${(1 / c.s).toFixed(5)}) rotateZ(${(-c.rz).toFixed(4)}deg) rotateY(${(-c.ry).toFixed(4)}deg) rotateX(${(-c.rx).toFixed(4)}deg) translate3d(${(-c.x).toFixed(3)}px,${(-c.y).toFixed(3)}px,${(-c.z).toFixed(3)}px)`;
const poseTransform = (p: Pose) =>
  `translate3d(${p.x}px,${p.y}px,${p.z}px) rotateX(${p.rx}deg) rotateY(${p.ry}deg) rotateZ(${p.rz}deg) scale(${p.s})`;

const hash = (n: number) => {
  const x = Math.sin(n * 91.345 + 47.853) * 43758.5453;
  return x - Math.floor(x);
};
// 3D dust particles fixed in world space; parallax driven by camera motion
const MOTES = Array.from({ length: 70 }, (_, i) => ({
  x: -2600 + hash(i * 3.1) * 6800,
  y: -2000 + hash(i * 5.7 + 1) * 4800,
  z: -3200 + hash(i * 7.3 + 2) * 3600,
  r: 3 + hash(i * 11.9 + 3) * 7,
  a: 0.25 + hash(i * 13.1 + 4) * 0.55,
}));

// ───────── Chapter Cards ─────────
const ChapterCard: React.FC<{ i: number; frame: number; focus: number }> = ({ i, frame, focus }) => {
  const c = CHAPTERS[i];
  const arrive = ARRIVE[i];
  const reveal = arrive - (i === 0 ? -2 : 8); // Title begins rising before arrival
  const hold = ramp(frame, arrive, HOLD_END[i] - arrive, EASE.smooth); // Progress line
  const numIn = ramp(frame, reveal - 4, 26, EASE.out);
  const bodyIn = ramp(frame, reveal + 8, 18, EASE.out);
  return (
    <div style={{ position: 'absolute', inset: 0, padding: '74px 84px', boxSizing: 'border-box', fontFamily: FONT.sans }}>
      {/* Large light chapter digits: cropped by card edge as typographic texture */}
      <div style={{
        position: 'absolute', right: -36, bottom: -118, ...type(560, 200), letterSpacing: '-0.06em',
        color: 'transparent', backgroundImage: `linear-gradient(170deg, ${alpha('#ffffff', 0.16)} 10%, ${alpha('#ffffff', 0.02)} 70%)`,
        WebkitBackgroundClip: 'text', backgroundClip: 'text',
        transform: `translateY(${((1 - numIn) * 60).toFixed(1)}px)`, opacity: numIn,
      }}>{c.no}</div>
      {/* Eyebrow */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, ...type(26, 600, { mono: true }), letterSpacing: '0.14em', color: L.ink3, textTransform: 'uppercase' }}>
        <span style={{ color: GOLD }}>{c.no}</span>
        <span style={{ width: 44, height: 1, background: alpha(GOLD, 0.6) }} />
        <span>Chapter · {c.kicker}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12, textTransform: 'none', fontFamily: BRAND.font, fontSize: 28, fontWeight: 700, letterSpacing: '0.03em', color: L.ink2 }}>
          <ShotcraftMark size={32} tone="dark" />{BRAND.name}
        </span>
      </div>
      {/* Title: rises word by word */}
      <div style={{ marginTop: 150, ...type(156, 760), color: L.ink }}>
        <TextReveal text={c.title} by="char" variant="rise" start={reveal} each={20} gap={1.8} />
      </div>
      <div style={{
        marginTop: 34, maxWidth: 820, ...type(44, 420), lineHeight: 1.3, color: L.ink2, textWrap: 'balance',
        opacity: bodyIn, transform: `translateY(${((1 - bodyIn) * 18).toFixed(1)}px)`,
      }}>{c.body}</div>
      {/* Bottom: 3-stage progress with gold current stage fill */}
      <div style={{ position: 'absolute', left: 84, right: 84, bottom: 70, display: 'flex', gap: 14 }}>
        {[0, 1, 2].map((k) => (
          <div key={k} style={{ flex: 1, height: 3, borderRadius: 2, background: alpha('#ffffff', 0.1), overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${(k < i ? 1 : k === i ? hold : 0) * 100}%`,
              background: k === i ? `linear-gradient(90deg, ${alpha(GOLD, 0.7)}, ${GOLD})` : alpha('#ffffff', 0.45),
              boxShadow: k === i ? `0 0 ${10 * focus}px ${alpha(GOLD, 0.6)}` : undefined,
            }} />
          </div>
        ))}
      </div>
    </div>
  );
};

// ───────── Overview Outro (scaled 2.7x in world space, viewed at 1/2.7 = 1:1) ─────────
const OverviewPlate: React.FC<{ frame: number }> = ({ frame }) => {
  const st = 184;
  const kick = ramp(frame, st, 22, EASE.snappy);
  const sub = ramp(frame, st + 20, 18, EASE.out);
  return (
    <div style={{ position: 'absolute', left: -960, top: -540, width: 1920, height: 1080, pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', left: 120, bottom: 128 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, ...type(24, 600, { mono: true }), letterSpacing: `${mix(0.6, 0.16, kick).toFixed(3)}em`, color: GOLD, opacity: kick, textTransform: 'uppercase' }}>
          <ShotcraftMark size={40} tone="dark" />
          <span style={{ textTransform: 'none', fontFamily: BRAND.font, fontSize: 30, fontWeight: 700, letterSpacing: '0.03em', color: L.ink }}>{BRAND.name}</span>
          <span>· Three chapters, one film</span>
        </div>
        <div style={{ marginTop: 26, ...type(150, 400, { serif: true }), letterSpacing: '-0.035em', color: L.ink }}>
          <TextReveal text="Craft the shot." by="word" variant="rise" start={st + 6} each={22} gap={5} />
        </div>
        <div style={{ marginTop: 22, ...type(38, 420), color: L.ink2, opacity: sub, transform: `translateY(${((1 - sub) * 14).toFixed(1)}px)` }}>
          Shot recipes for cinematic product films.
        </div>
      </div>
    </div>
  );
};

// Complete world (at given frame)
const World: React.FC<{ f: number; frame: number }> = ({ f, frame }) => {
  const { cam, af } = camAt(f);
  const over = ramp(f, FLIGHTS[2][0], FLIGHTS[2][1] - FLIGHTS[2][0], EASE.smooth);
  const plateOn = ramp(frame, 176, 16, EASE.out);
  return (
    <div style={{ position: 'absolute', left: '50%', top: '50%', width: 0, height: 0, transformStyle: 'preserve-3d', transform: camTransform(cam) }}>
      {MOTES.map((m, k) => (
        <div key={k} style={{
          position: 'absolute', left: -m.r, top: -m.r, width: m.r * 2, height: m.r * 2, borderRadius: '50%',
          transform: `translate3d(${m.x}px,${m.y}px,${m.z}px)`,
          background: `radial-gradient(circle, ${alpha('#f4efe4', m.a)} 0%, ${alpha('#f4efe4', 0)} 70%)`,
        }} />
      ))}
      {CHAPTERS.map((_, i) => {
        const p = POSES[i];
        // enter/exit: defocus based on distance from current stop
        const d = Math.min(1, Math.abs(af - i));
        const focus = Math.max(1 - d, over * 0.85);
        const lift = (1 - d) * 18;
        return (
          <div key={i} style={{
            position: 'absolute', left: -CW / 2, top: -CH / 2, width: CW, height: CH, borderRadius: 34, overflow: 'hidden',
            transform: `${poseTransform(p)} translateZ(${lift.toFixed(2)}px)`,
            background: `radial-gradient(ellipse 80% 90% at 18% 0%, ${alpha('#ffffff', 0.07)} 0%, ${alpha('#ffffff', 0)} 60%), linear-gradient(165deg, #202226 0%, #16171a 55%, #111214 100%)`,
            border: `1.5px solid ${alpha('#ffffff', 0.08 + 0.08 * focus)}`,
            boxShadow: `inset 0 1.5px 0 ${alpha('#ffffff', 0.12)}, 0 30px 80px -10px rgba(0,0,0,0.7), 0 6px 18px rgba(0,0,0,0.5)`,
            opacity: 0.22 + 0.78 * focus,
            filter: focus < 0.985 ? `blur(${((1 - focus) * 7).toFixed(2)}px)` : undefined,
          }}>
            {/* Top illuminated edge */}
            <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 2, background: `linear-gradient(90deg, transparent, ${alpha('#ffffff', 0.35 * (0.4 + 0.6 * focus))}, transparent)` }} />
            <ChapterCard i={i} frame={frame} focus={focus} />
          </div>
        );
      })}
      {/* Overview outro: reveals during final flight */}
      <div style={{ position: 'absolute', left: 0, top: 0, transform: poseTransform(POSES[3]), opacity: plateOn }}>
        <OverviewPlate frame={frame} />
      </div>
    </div>
  );
};

// Time-sampled motion blur: shutter 0.5f adaptive sub-frame accumulation
const SHUTTER = 0.5;
const samplesAt = (f: number) => {
  const a = camAt(f).cam, b = camAt(f - SHUTTER).cam;
  const disp = Math.hypot(a.x - b.x, a.y - b.y) / a.s + Math.abs(a.z - b.z) * 0.4
    + (Math.abs(a.ry - b.ry) + Math.abs(a.rz - b.rz)) * 14 + Math.abs(Math.log(a.s / b.s)) * 1400;
  return Math.max(1, Math.min(8, Math.ceil(disp / 5)));
};

export const Basic3DScene: React.FC = () => {
  const frame = useCurrentFrame();
  const flying = FLIGHTS.some(([a, b]) => frame > a && frame < b);
  const n = flying ? samplesAt(frame) : 1;
  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: -0.08 }} fill={{ x: 0.85, y: 1.05 }} breathe={0.6} intensity={0.55} />
      <AbsoluteFill style={{ overflow: 'hidden' }}>
        {Array.from({ length: n }, (_, i) => (
          <AbsoluteFill key={i} style={{ perspective: `${PERSP}px`, opacity: 1 / (i + 1) }}>
            <World f={n > 1 ? frame - (SHUTTER * i) / (n - 1) : frame} frame={frame} />
          </AbsoluteFill>
        ))}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
