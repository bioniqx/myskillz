// Font weight pump (font-weight-pump) — title strokes thicken on each beat and bounce back, pulsating with the bass.
//
// Round 2 redesign (club poster / echo type stack):
// - look = aurora (deep violet night / neon purple-pink). Hero text is 250px "LOUDER": resting as thin weight 250 with open gaps
//   (each letter pinned inside a slot sized for weight 900), drum hits instantly fill the slot into a solid bold, then power-decay back to thin —
//   the expanding and collapsing gaps themselves visualize the beat. Characters do not translate or reflow; only attributes animate.
// - Rhythmic progression (128 BPM, 14f per beat, two bars + one drop):
//   Bar 1 pulses hero text only; Bar 2 sprouts outlined echo lines above and below, lagging 2f behind the beat and pushed outward by the blast (follow-through);
//   Beat 9 drop: hero text pumps to 900 and settles at weight 780 with a purple-to-pink gradient; echo lines push outward then return,
//   a horizontal light streak sweeps across (Q4: hero only once) — the final frame settles into a complete poster.
// - Rebound stagger: center contracts first, edges contract later (decay window 9f -> 13f), reading as impact rippling outward;
//   downbeat of each bar: extra scaleX +6%, tinted pink. Bottom 8+1 step sequencer acts as a silent reference (lit step = current beat).
// - No full-screen beat pump / shake: only text, back glow, and sequencer steps react to beats.
//
// Timeline (30fps, 165f total):
//   0-15    Setup: thin LOUDER, empty sequencer, eyebrow header (video-shotcraft mark + wordmark) in place, soft breathing glow behind text
//   16-58   Bar 1, 4 beats (16/30/44/58), 9-13f decay window per beat, beat interval 14f > decay window
//   64-72   Echo lines fade in and split vertically
//   72-114  Bar 2, 4 beats, echo lines lag 2f and get pushed out 26px
//   128     Drop: 900 weight + gradient + streak, settles to 780 within ~12f; subtitle (video-shotcraft value prop) rises word by word
//   140-165 Hold
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const FONT_WEIGHT_PUMP_DURATION = 165;

const L = LOOKS.aurora;

const BEATS = [16, 30, 44, 58, 72, 86, 100, 114];
const DROP = 128;
const DOWN = new Set([0, 4]); // Downbeat on the first beat of each bar
const TEXT = 'LOUDER';
const SIZE = 240;
const CY = 505; // Hero row center (slightly above screen center to make room for subtitle and sequencer below)
const W_REST = 250; // Resting font weight (light)
const W_PEAK = 900;
const W_FINAL = 780; // Settled font weight after the drop
const DECAY = 9; // Decay window for center characters
const SPREAD = 1.6; // Decay window increases by 1.6f per character away from center
const ECHO_IN = 64;
const ECHO_DY = 0.85 * SIZE; // Echo row vertical spacing
const LAG = 2; // Echo lines lag 2f behind hero text

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const hex = (c: string) => [1, 3, 5].map((k) => parseInt(c.slice(k, k + 2), 16));
const mixRgb = (a: string, b: string, k: number) => {
  const A = hex(a), B = hex(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * k)).join(',')})`;
};

// Power-decay envelope after impact: t=0 -> 1, t>=decay -> exact 0
const envAt = (frame: number, beat: number, decay: number) => {
  const t = frame - beat;
  if (t < 0 || t >= decay) return 0;
  return Math.pow(1 - t / decay, 0.8);
};
// Max envelope and beat index for a given frame (beat interval 14f > max decay window 13f, only one active beat at any moment)
const pulse = (frame: number, decay: number) => {
  let env = 0;
  let beat = -1;
  BEATS.forEach((b, i) => {
    const e = envAt(frame, b, decay);
    if (e > env) { env = e; beat = i; }
  });
  return { env, beat };
};
// Drop: spikes to 1 then settles to resting level (0.75 of 0->1 range ~= weight 780)
const dropEnv = (frame: number, decay: number) => {
  const t = frame - DROP;
  if (t < 0) return 0;
  const fin = (W_FINAL - W_REST) / (W_PEAK - W_REST);
  return fin + (1 - fin) * Math.pow(1 - clamp01(t / (decay + 4)), 1.4);
};

const CHARS = TEXT.split('');
const CENTER = (CHARS.length - 1) / 2;
const GRAD = (i: number) => mixRgb(L.accent, L.accent2, i / (CHARS.length - 1)); // Purple-to-pink gradient after drop (sampled per character)

// Text row: each character pinned inside a 900-weight slot, thickening in place
const Row: React.FC<{ frame: number; lag?: number; outline?: boolean; opacity?: number }> = ({ frame, lag = 0, outline = false, opacity = 1 }) => {
  const f = frame - lag;
  const drop = clamp01(f - DROP + 1) > 0;
  return (
    <div style={{ display: 'flex', whiteSpace: 'pre', ...type(SIZE, W_REST), letterSpacing: '-0.01em', lineHeight: 1, opacity }}>
      {CHARS.map((ch, i) => {
        const decay = DECAY + Math.max(0, Math.abs(i - CENTER) - 0.5) * SPREAD;
        const { env: e0, beat } = pulse(f, decay);
        const de = dropEnv(f, decay);
        const e = Math.max(e0, de);
        const weight = Math.round(W_REST + (W_PEAK - W_REST) * e);
        const down = beat >= 0 && DOWN.has(beat);
        const hitCol = down ? L.accent2 : L.accent;
        const tint = drop ? 1 : Math.min(1, e0 * 1.25);
        const col = drop ? GRAD(i) : mixRgb(L.ink, hitCol === L.accent2 ? L.accent2 : '#c9b8ff', tint);
        const shine = drop ? 0.35 + 0.65 * Math.pow(1 - clamp01((f - DROP) / 24), 2) : e0;
        return (
          <span key={i} style={{ position: 'relative', display: 'inline-block' }}>
            <span style={{ visibility: 'hidden', fontWeight: W_PEAK }}>{ch}</span>
            <span style={{
              position: 'absolute', left: '50%', top: 0, transform: 'translateX(-50%)', fontWeight: weight,
              color: outline ? 'transparent' : col,
              WebkitTextStroke: outline ? `2px ${alpha(drop ? L.accent : L.ink, 0.55)}` : undefined,
              textShadow: !outline && shine > 0.05
                ? `0 0 ${(18 * shine).toFixed(1)}px ${alpha(drop ? GRAD(i) : hitCol, 0.5 * shine)}, 0 0 ${(70 * shine).toFixed(1)}px ${alpha(drop ? GRAD(i) : hitCol, 0.35 * shine)}`
                : 'none',
            }}>
              {ch}
            </span>
          </span>
        );
      })}
    </div>
  );
};

export const FontWeightPump: React.FC = () => {
  const frame = useCurrentFrame();
  const { env, beat } = pulse(frame, DECAY);
  const dEnv = frame >= DROP ? Math.pow(1 - clamp01((frame - DROP) / 16), 1.2) : 0;
  const down = beat >= 0 && DOWN.has(beat);
  const scaleX = 1 + 0.06 * (down ? env : 0) + 0.08 * dEnv; // Horizontal expansion on downbeats / drop (transform without altering layout)
  const intro = ramp(frame, 0, 12, EASE.out);
  // Echo: fades in and separates from frame 64; pushed outward 26px with a 2f lag each beat; pushed 60px on drop then settles
  const echoIn = ramp(frame, ECHO_IN, 10, EASE.snappy);
  const { env: eEnv } = pulse(frame - LAG, DECAY + 2);
  const eDrop = frame >= DROP + LAG ? Math.pow(1 - clamp01((frame - DROP - LAG) / 18), 1.6) : 0;
  const echoPush = mix(-40, 0, echoIn) + 26 * eEnv * echoIn + 60 * eDrop;
  const breathe = 0.5 + 0.5 * Math.sin(frame / 9);
  const glowA = 0.1 + 0.05 * breathe * (1 - clamp01(frame / 16)) + 0.3 * env * (down ? 1.3 : 1) + 0.4 * dEnv + (frame >= DROP ? 0.12 : 0);
  // Horizontal streak: sweeps from left to right once on the drop
  const streak = ramp(frame, DROP, 16, EASE.out);
  const bar = frame >= BEATS[4] ? 2 : 1;

  const label: React.CSSProperties = { ...type(30, 600, { caps: true }), letterSpacing: '0.16em' };

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.5 }} fill={{ x: 0.85, y: 0.15 }} intensity={0.7} />

      {/* Backlight glow behind text: pulses with beats, strictly behind the title */}
      <div style={{
        position: 'absolute', left: 260, right: 260, top: CY - 240, height: 480, borderRadius: '50%',
        background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(down || frame >= DROP ? L.accent2 : L.accent, Math.min(0.6, glowA))} 0%, ${alpha(L.accent, 0)} 100%)`,
        mixBlendMode: 'screen',
      }} />

      {/* Eyebrow header */}
      <div style={{ position: 'absolute', left: 120, top: 92, display: 'flex', alignItems: 'center', gap: 14, opacity: intro }}>
        <ShotcraftMark size={46} tone="dark" />
        {/* Lowercase wordmark, bypasses eyebrow uppercase styling */}
        <span style={{ ...type(30, 700), fontFamily: BRAND.font, letterSpacing: '0.03em', color: L.ink }}>{BRAND.name}</span>
      </div>
      <div style={{ position: 'absolute', right: 120, top: 96, ...label, color: L.ink2, opacity: intro, fontVariantNumeric: 'tabular-nums' }}>
        128 BPM <span style={{ color: L.ink3, marginLeft: 18 }}>{`BAR ${bar} / 2`}</span>
      </div>

      {/* Echo lines (outlined): one row above, one row below */}
      {[-1, 1].map((s) => (
        <div key={s} style={{
          position: 'absolute', left: 0, right: 0, top: CY - SIZE / 2 + s * (ECHO_DY + echoPush), display: 'flex', justifyContent: 'center',
          opacity: echoIn, transform: `scaleX(${(1 + (scaleX - 1) * 0.5).toFixed(4)})`,
        }}>
          <Row frame={frame} lag={LAG} outline opacity={0.75} />
        </div>
      ))}

      {/* Hero text */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: CY - SIZE / 2, display: 'flex', justifyContent: 'center',
        transform: `scaleX(${scaleX.toFixed(4)})`,
      }}>
        <Row frame={frame} />
      </div>

      {/* Drop streak: single pass crossing the hero text */}
      {streak > 0 && streak < 1 && (
        <div style={{
          position: 'absolute', left: mix(-600, 1920, streak), top: CY - 4, width: 600, height: 6, borderRadius: 3,
          background: `linear-gradient(90deg, ${alpha('#ffffff', 0)} 0%, ${alpha('#ffffff', 0.9)} 70%, ${alpha('#ffffff', 0)} 100%)`,
          boxShadow: `0 0 30px ${alpha(L.accent2, 0.8)}`, opacity: 1 - streak * 0.6, mixBlendMode: 'screen',
        }} />
      )}

      {/* Subtitle: rises word by word after the drop */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 850, textAlign: 'center', ...type(40, 500), color: L.ink2 }}>
        <TextReveal text="Beat-synced cuts, right on the drop." by="word" variant="rise" start={DROP + 8} each={14} gap={2.5} />
      </div>

      {/* Step sequencer: 8 beats + drop */}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 944, display: 'flex', justifyContent: 'center', gap: 16, opacity: intro }}>
        {[...BEATS, DROP].map((b, i) => {
          const isDrop = i === BEATS.length;
          const e = isDrop ? dEnv : envAt(frame, b, DECAY);
          const passed = frame >= b;
          const dn = DOWN.has(i) || isDrop;
          const col = dn ? L.accent2 : L.accent;
          return (
            <div key={i} style={{
              width: isDrop ? 132 : 54, height: 54, borderRadius: 12, position: 'relative', marginLeft: i === 4 || isDrop ? 22 : 0,
              background: alpha(L.ink, 0.05), boxShadow: `inset 0 0 0 1.5px ${alpha(dn ? L.accent2 : L.ink, dn ? 0.35 : 0.14)}`,
              transform: `scale(${(1 + 0.12 * e).toFixed(3)})`,
            }}>
              <div style={{
                position: 'absolute', inset: 0, borderRadius: 12, background: col,
                opacity: e > 0.02 ? Math.max(isDrop ? 0.9 : 0, 0.35 + 0.65 * e) : passed ? (isDrop ? 0.9 : 0.28) : 0,
                boxShadow: e > 0.02 ? `0 0 ${(30 * e).toFixed(1)}px ${alpha(col, 0.8)}` : 'none',
              }} />
              {isDrop && (
                <span style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  ...type(22, 800, { caps: true }), letterSpacing: '0.2em', color: passed ? L.onAccent : L.ink3,
                }}>
                  Drop
                </span>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
        {[...BEATS, DROP].map((b, i) => {
          const isDrop = i === BEATS.length;
          const e = isDrop ? dEnv : envAt(frame, b, DECAY);
          const passed = frame >= b;
          const dn = DOWN.has(i) || isDrop;
          const col = dn ? L.accent2 : L.accent;
          return (
            <div key={i} style={{
              width: isDrop ? 132 : 54, height: 54, borderRadius: 12, position: 'relative', marginLeft: i === 4 || isDrop ? 22 : 0,
              background: alpha(L.ink, 0.05), boxShadow: `inset 0 0 0 1.5px ${alpha(dn ? L.accent2 : L.ink, dn ? 0.35 : 0.14)}`,
              transform: `scale(${(1 + 0.12 * e).toFixed(3)})`,
            }}>
              <div style={{
                position: 'absolute', inset: 0, borderRadius: 12, background: col,
                opacity: e > 0.02 ? Math.max(isDrop ? 0.9 : 0, 0.35 + 0.65 * e) : passed ? (isDrop ? 0.9 : 0.28) : 0,
                boxShadow: e > 0.02 ? `0 0 ${(30 * e).toFixed(1)}px ${alpha(col, 0.8)}` : 'none',
              }} />
              {isDrop && (
                <span style={{
                  position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  ...type(22, 800, { caps: true }), letterSpacing: '0.2em', color: passed ? L.onAccent : L.ink3,
                }}>
                  Drop
                </span>
              )}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
