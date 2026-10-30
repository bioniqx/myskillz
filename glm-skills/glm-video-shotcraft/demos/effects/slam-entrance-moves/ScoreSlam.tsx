// score-slam — broadcast sports score slam entrance: score card slams from 2.6x foreground to screen center,
// detonating shockwave ring + debris sparks + screen shake on impact frame, with squash & rebound settle.
//
// Redesign (graphite night match: final cup score):
// - look = graphite (near-monochrome dark field, champagne gold accents). Night stadium: 4 top floodlights ignite sequentially 0-7f
//   (with downward light cones and volumetric mist); blurred crowd lights in distance. Hero is 1240x400 final score card:
//   team badges + names (Shotcraft vs Keyframes), 220px bold tabular score "3 - 2",
//   top gold "FULL TIME · 90+4′" badge, match metadata row.
// - Rhythm (hover -> slam -> burst -> settle -> read): 0-9f card hovers (2.75->2.6, 10px blur, anticipatory lift) ->
//   9-15f 6-frame ease-in accelerated slam (scale 2.6->0.965, rotate 5->0 deg, blur clears) -> 15f impact frame:
//   shockwave ring (white core + gold glow) + 14 glass/gold leaf shards + 16 sparks +
//   18px vertical screen shake decaying over 5f + 2f white flash -> 15-26f spring rebound to 1.
// - Follow-through: two score digits secondary bounce (+3f / +6f spring 1.16->1), winning side underline wipes in;
//   FULL TIME badge slides from top; headline "Shotcraft lifts the Cup." rises word-by-word with subtitle fading in.
//
// Timeline (30fps, total 135f):
//   0-9     Lead-in: floodlights ignite; score card hovers in foreground with blur
//   9-15    Slam descent (6f ease-in)
//   15-31   Impact triad: ring 16f / shards 20f / sparks 10f / shake 5f / flash 2f
//   15-26   Card squash & rebound; scores secondary bounce at 18f/21f; badge slides out at 24f; gold line at 28f
//   36-64   Headline rises word-by-word + subtitle fades in
//   64-135  Hold: subtle light breathing, camera push 1->1.02, all transients zeroed
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, bezier, mix, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, TextReveal, alpha, springAt } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const SCORE_SLAM_DURATION = 135;

const L = LOOKS.graphite;
const GOLD = L.accent2;
const IMPACT = 15; // Impact frame
const SLAM0 = 9; // Slam start frame
const CW = 1240;
const CH = 400;
const CX = 960;
const CY = 500; // Card center y
const EASE_IN_QUAD = bezier(0.55, 0.085, 0.68, 0.53);

const rnd = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

// Shards: polygonal glass / gold foil, parabolic trajectory + spin + 3D flip
const SHARDS = Array.from({ length: 14 }, (_, i) => {
  const ang = (i / 14) * Math.PI * 2 + (rnd(i + 3) - 0.5) * 0.5;
  return {
    ang, dist: 280 + rnd(i + 11) * 300, size: 22 + rnd(i + 23) * 26, spin: (rnd(i + 31) - 0.5) * 620,
    gold: i % 3 === 0, poly: [0, 1, 2, 3].map((k) => `${(50 + Math.cos(k * 1.7 + i) * (30 + rnd(i * 4 + k) * 20)).toFixed(0)}% ${(50 + Math.sin(k * 1.7 + i) * (30 + rnd(i * 5 + k) * 20)).toFixed(0)}%`).join(', '),
  };
});
const SPARKS = Array.from({ length: 16 }, (_, i) => ({
  ang: (i / 16) * Math.PI * 2 + (rnd(i + 61) - 0.5) * 0.4, dist: 360 + rnd(i + 71) * 320, len: 40 + rnd(i + 81) * 50,
}));
const LIGHTS = [250, 600, 1320, 1670];

const Crest: React.FC<{ code: React.ReactNode; filled: boolean }> = ({ code, filled }) => (
  <div style={{
    width: 108, height: 108, borderRadius: 54, display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: filled ? 'linear-gradient(180deg, #f6f5f1, #cfcdc6)' : 'transparent',
    border: filled ? 'none' : `3px solid ${alpha(L.ink, 0.55)}`,
    boxShadow: filled ? `0 8px 20px -8px #000, inset 0 -3px 0 ${alpha('#000', 0.12)}` : 'none',
    font: `850 30px ${FONT.sans}`, letterSpacing: '0.02em', color: filled ? '#141416' : L.ink,
  }}>
    {code}
  </div>
);

export const ScoreSlam: React.FC = () => {
  const frame = useCurrentFrame();

  // --- Card: 0-9 hover (2.75->2.6), 9-15 accelerate to 0.965, 15+ spring to 1 ---
  const hover = ramp(frame, 0, SLAM0, EASE.smooth);
  const drop = ramp(frame, SLAM0, IMPACT - SLAM0, EASE_IN_QUAD);
  const preScale = mix(2.75, 2.6, hover);
  const settle = springAt(frame, IMPACT, { damping: 14, stiffness: 260 });
  const scale = frame < IMPACT ? mix(preScale, 0.965, drop) : mix(0.965, 1, settle);
  const rot = mix(5, 0, drop);
  const dy = frame < IMPACT ? mix(-40 - 30 * hover, 0, drop) : 0;
  const cardOp = ramp(frame, 0, 6, EASE.out) * mix(0.6, 1, drop); // Translucent during hover
  const height01 = Math.min(1, Math.max(0, (scale - 1) / 1.75));
  const dof = height01 * 10; // Defocus increases closer to camera
  const cardShadow =
    `0 ${(2 + height01 * 14).toFixed(1)}px ${(6 + height01 * 24).toFixed(1)}px ${alpha('#000', 0.5 - height01 * 0.25)}, ` +
    `0 ${(40 + height01 * 80).toFixed(1)}px ${(90 + height01 * 120).toFixed(1)}px -20px ${alpha('#000', 0.85 - height01 * 0.3)}, ` +
    `inset 0 1px 0 ${alpha('#ffffff', 0.14)}, inset 0 0 0 1px ${alpha('#ffffff', 0.09)}`;

  // --- Screen shake: 5f from impact, 18px exponential decay, vertical bias ---
  let shakeX = 0;
  let shakeY = 0;
  if (frame >= IMPACT && frame < IMPACT + 5) {
    const t = frame - IMPACT;
    const amp = 18 * Math.exp(-t * 0.85);
    shakeX = amp * 0.4 * (rnd(frame * 7 + 1) * 2 - 1);
    shakeY = amp * (t === 0 ? 1 : rnd(frame * 13 + 2) * 2 - 1);
  }
  const flash = frame >= IMPACT && frame < IMPACT + 3 ? [0.22, 0.12, 0.04][frame - IMPACT] : 0;

  // --- Shockwave ring: out-cubic expansion, linear dissipation decoupling expansion from fade ---
  const ringT = ramp(frame, IMPACT, 16, EASE.snappy);
  const ringLin = ramp(frame, IMPACT, 16, EASE.linear);
  const ringOn = frame >= IMPACT && frame < IMPACT + 16;
  const ringD = mix(120, 1500, ringT);
  const ringOp = ringLin < 0.6 ? mix(1, 0.65, ringLin / 0.6) : mix(0.65, 0, (ringLin - 0.6) / 0.4);
  const ringW = mix(9, 1.5, ringT);

  // --- Debris 20f / Sparks 10f ---
  const shT = ramp(frame, IMPACT, 20, EASE.out);
  const shLin = ramp(frame, IMPACT, 20, EASE.linear);
  const shOn = frame >= IMPACT && frame < IMPACT + 20;
  const spT = ramp(frame, IMPACT, 10, bezier(0.1, 0.9, 0.2, 1));
  const spLin = ramp(frame, IMPACT, 10, EASE.linear);
  const spOn = frame >= IMPACT && frame < IMPACT + 10;

  // --- Follow-through: score bounce, FULL TIME badge, winning gold bar ---
  const digitPop = (start: number) => (frame < start ? 0 : springAt(frame, start, { damping: 13, stiffness: 300 }));
  const d1 = digitPop(IMPACT + 3);
  const d2 = digitPop(IMPACT + 6);
  const tag = ramp(frame, IMPACT + 9, 12, EASE.snappy);
  const underline = ramp(frame, IMPACT + 13, 14, EASE.snappy);

  const push = 1 + 0.02 * ramp(frame, IMPACT, 120, EASE.swift);
  const breathe = 0.92 + 0.08 * Math.sin(frame / 22);

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: -0.05 }} fill={null} intensity={0.8} horizon={0.8}>
        {/* Distant crowd: blurred warm bokeh lights */} 
        <div style={{ position: 'absolute', left: 0, right: 0, top: 640, height: 440, filter: 'blur(3px)' }}>
          <Dust look={L} count={60} seed={7} drift={0.08} opacity={0.55} color="#f2d9a8" />
        </div>
      </Stage>

      {/* Floodlights igniting 0-7f with light cones + volumetric haze */} 
      {LIGHTS.map((x, i) => {
        const t0 = i * 2;
        const on = frame < t0 ? 0 : frame < t0 + 1 ? 1 : frame < t0 + 2 ? 0.35 : 1;
        const o = on * breathe;
        return (
          <React.Fragment key={i}>
            <div style={{
              position: 'absolute', left: x - 380, top: -40, width: 760, height: 1100, opacity: o,
              background: `radial-gradient(ellipse 34% 100% at 50% 0%, ${alpha('#fff4dc', 0.13)} 0%, ${alpha('#fff4dc', 0.05)} 45%, ${alpha('#fff4dc', 0)} 80%)`,
            }} />
            <div style={{
              position: 'absolute', left: x - 160, top: -150, width: 320, height: 300, borderRadius: '50%', opacity: o,
              background: `radial-gradient(circle, ${alpha('#ffffff', 0.95)} 0%, ${alpha('#fff1d2', 0.45)} 18%, ${alpha('#fff1d2', 0)} 66%)`,
            }} />
          </React.Fragment>
        );
      })}

      <div style={{ position: 'absolute', inset: -40, transform: `translate(${shakeX.toFixed(2)}px, ${shakeY.toFixed(2)}px)` }}>
        <div style={{ position: 'absolute', inset: 40, transform: `scale(${push.toFixed(5)})` }}>
          {/* Shockwave: gold glow + white core ring */} 
          {ringOn && (
            <>
              <div style={{
                position: 'absolute', left: CX - ringD / 2, top: CY - ringD / 2, width: ringD, height: ringD, borderRadius: '50%', opacity: ringOp,
                boxShadow: `0 0 ${(30 + ringT * 40).toFixed(0)}px ${(6 + ringT * 8).toFixed(0)}px ${alpha(GOLD, 0.35)}, inset 0 0 ${(30 + ringT * 40).toFixed(0)}px ${alpha(GOLD, 0.22)}`,
              }} />
              <div style={{
                position: 'absolute', left: CX - ringD / 2, top: CY - ringD / 2, width: ringD, height: ringD, borderRadius: '50%', opacity: ringOp,
                border: `${ringW.toFixed(2)}px solid ${alpha('#fffaf0', 0.95)}`, boxSizing: 'border-box',
              }} />
            </>
          )}

          {/* Sparks: radial streaks */} 
          {spOn && SPARKS.map((s, i) => {
            const r = 160 + s.dist * spT;
            const len = s.len * (1 - spLin) + 6;
            return (
              <div key={i} style={{
                position: 'absolute', left: CX + Math.cos(s.ang) * r - len / 2, top: CY + Math.sin(s.ang) * r * 0.8 - 2, width: len, height: 4, borderRadius: 2,
                background: `linear-gradient(90deg, ${alpha('#fff3d6', 0)}, #fffaf0)`, transform: `rotate(${((s.ang * 180) / Math.PI).toFixed(1)}deg)`,
                opacity: 1 - spLin, boxShadow: `0 0 10px ${alpha(GOLD, 0.8)}`,
              }} />
            );
          })}

          {/* Score card */} 
          <div style={{
            position: 'absolute', left: CX - CW / 2, top: CY - CH / 2, width: CW, height: CH, borderRadius: 34,
            background: `linear-gradient(180deg, #1f2024 0%, ${L.surface} 100%)`, boxShadow: cardShadow, opacity: cardOp,
            transform: `translateY(${dy.toFixed(2)}px) rotate(${rot.toFixed(3)}deg) scale(${scale.toFixed(4)})`,
            filter: dof > 0.4 ? `blur(${dof.toFixed(2)}px)` : undefined, fontFamily: FONT.sans, color: L.ink,
          }}>
            {/* Top edge gold hairline highlight */} 
            <div style={{ position: 'absolute', left: 120, right: 120, top: 0, height: 2, background: `linear-gradient(90deg, ${alpha(GOLD, 0)}, ${alpha(GOLD, 0.8)}, ${alpha(GOLD, 0)})` }} />
            {/* FULL TIME badge sliding from top edge */} 
            <div style={{ position: 'absolute', left: 0, right: 0, top: -26, display: 'flex', justifyContent: 'center', overflow: 'hidden', height: 60 }}>
              <div style={{
                height: 52, padding: '0 24px', borderRadius: 26, background: GOLD, color: '#17130a', display: 'flex', alignItems: 'center',
                font: `800 24px ${FONT.mono}`, letterSpacing: '0.12em', transform: `translateY(${mix(64, 0, tag).toFixed(2)}px)`,
                boxShadow: `0 10px 30px -10px ${alpha(GOLD, 0.8)}`,
              }}>
                FULL TIME · 90+4′
              </div>
            </div>
            {/* Home team */} 
            <div style={{ position: 'absolute', left: 70, top: 88, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, width: 220 }}>
              <Crest code={<ShotcraftMark size={64} tone="light" />} filled />
              <div style={{ font: `750 44px ${FONT.sans}`, letterSpacing: '-0.03em' }}>{BRAND.short}</div>
            </div>
            {/* Away team */} 
            <div style={{ position: 'absolute', right: 70, top: 88, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, width: 220 }}>
              <Crest code="KEY" filled={false} />
              <div style={{ font: `750 44px ${FONT.sans}`, letterSpacing: '-0.03em', color: L.ink2, whiteSpace: 'nowrap' }}>Keyframes</div>
            </div>
            {/* Score */} 
            <div style={{ position: 'absolute', left: 0, right: 0, top: 58, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 56, font: `860 220px ${FONT.sans}`, letterSpacing: '-0.05em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
              <div style={{ position: 'relative', transform: `scale(${mix(1.16, 1, d1).toFixed(4)})` }}>
                3
                <div style={{ position: 'absolute', left: 6, right: 6, bottom: -6, height: 8, borderRadius: 4, background: GOLD, transformOrigin: '0 50%', transform: `scaleX(${underline.toFixed(4)})`, boxShadow: `0 0 18px ${alpha(GOLD, 0.6)}` }} />
              </div>
              <div style={{ width: 54, height: 12, borderRadius: 6, background: alpha(L.ink, 0.35) }} />
              <div style={{ transform: `scale(${mix(1.16, 1, d2).toFixed(4)})`, color: L.ink2 }}>2</div>
            </div>
            {/* Match metadata row */} 
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 34, textAlign: 'center', font: `600 26px ${FONT.mono}`, letterSpacing: '0.14em', color: L.ink3 }}>
              MOTION CUP FINAL · BUILT ON REMOTION
            </div>
          </div>

          {/* Debris shards exploding from impact surface */} 
          {shOn && SHARDS.map((d, i) => {
            const dx = Math.cos(d.ang) * d.dist * shT;
            const dyy = Math.sin(d.ang) * d.dist * 0.75 * shT + 260 * shLin * shLin; // Parabolic trajectory
            const s = d.size * (1 - 0.55 * shLin);
            const flip = Math.abs(Math.cos(shLin * Math.PI * 1.6 + i));
            return (
              <div key={i} style={{
                position: 'absolute', left: CX + Math.cos(d.ang) * 300 + dx - s / 2, top: CY + Math.sin(d.ang) * 120 + dyy - s / 2, width: s, height: s,
                clipPath: `polygon(${d.poly})`,
                background: d.gold ? `linear-gradient(135deg, #8a6a2a, ${GOLD} 45%, #fff3cf 55%, #9c7a34)` : `linear-gradient(135deg, ${alpha('#ffffff', 0.9)}, ${alpha('#c9ccd4', 0.55)})`,
                opacity: shLin < 0.7 ? 1 : 1 - (shLin - 0.7) / 0.3,
                transform: `rotate(${(d.spin * shT).toFixed(1)}deg) scaleY(${Math.max(0.15, flip).toFixed(3)})`,
                filter: i % 4 === 0 ? 'blur(2px)' : undefined,
              }} />
            );
          })}

          {/* Headline + subtitle */} 
          <div style={{ position: 'absolute', left: 0, right: 0, top: CY + CH / 2 + 92, textAlign: 'center', font: `800 84px ${FONT.sans}`, letterSpacing: '-0.04em', color: L.ink, lineHeight: 1 }}>
            <TextReveal text="Shotcraft lifts the" by="word" variant="rise" start={36} each={16} gap={4} />
            <span style={{ color: GOLD }}>
              <TextReveal text=" Cup." by="word" variant="rise" start={48} each={16} gap={4} />
            </span>
          </div>
          <div style={{ position: 'absolute', left: 0, right: 0, top: CY + CH / 2 + 200, textAlign: 'center', font: `500 36px ${FONT.sans}`, color: L.ink2, letterSpacing: '-0.01em', opacity: ramp(frame, 52, 14, EASE.out), transform: `translateY(${mix(12, 0, ramp(frame, 52, 16, EASE.out)).toFixed(2)}px)` }}>
            Camera moves I would have keyframed for a week.
          </div>
        </div>
      </div>

      {/* Impact white flash */} 
      {flash > 0 && <div style={{ position: 'absolute', inset: 0, background: '#fffaf0', opacity: flash, mixBlendMode: 'screen' }} />}
    </AbsoluteFill>
  );
};
