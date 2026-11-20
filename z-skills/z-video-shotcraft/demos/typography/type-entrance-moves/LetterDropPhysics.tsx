// Letter drop and stack (letter-drop-physics) — FallingLetterAnimation.
// Brand name "Shotcraft" (BRAND.short), 9 characters arranged in a row according to natural font advance widths (flex layout defines slots only, all motion uses transform without altering layout).
// Character i begins dropping from frame 4+36*(1-(1-i/8)^1.5) (spacing shrinks from 6.5f to 1.6f, R2 hard acceleration):
// 1) Gravity acceleration y = D*(t/24)^2 dropping 720px to the floor, with vertical stretch proportional to velocity + vertical motion blur during the fall;
// 2) Upon landing, 2 decaying bounces (heights 30% / 9%, parabolic 4u(1-u) segments), with squash on each impact
//    and damped rebound; on initial impact, rotate to a seed hash tilt of +/-6 deg and hold (standing slightly askew);
//    a contact shadow beneath each character: larger, blurrier, and fainter with height, condensing into a sharp, compact footprint on touchdown;
// 3) Frame 110 snap beat: 2f inhale expanding to 1.06, then 6f ease-out to snap everything straight (rotate->0, offset->0,
//    scale 1.06->1), subtitle "Every shot lands on the beat." fades in afterward; frames 116-150 hold completely still (>=34f) to finish.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, Grain, SpeedBlur, mix, ramp, tracking } from '../../_fixtures/Polish';
import { BRAND } from '../../_fixtures/Brand';

export const LETTER_DROP_PHYSICS_DURATION = 150;

// Deterministic pseudo-random number generator
const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

const WORD = BRAND.short; // 'Shotcraft' (no descenders, all baselines sit flush on the floor)
const SIZE = 176; // Font size
const FLOOR_Y = 600; // Floor line (character baseline)
const BASE = Math.round(SIZE * 0.886); // Line box top to baseline (measured for SF Pro with lineHeight 1)
const ROW_TOP = FLOOR_Y - BASE; // Line box top: baseline sits directly on the floor line

const PAD = 200; // Motion blur container padding
const DROP = 720; // Drop distance
const T_FALL = 24; // Duration to hit the floor
const T_B1 = 16; // Duration of first bounce (30% height)
const T_B2 = 8; // Duration of second bounce (9% height)
const SNAP = 110; // Beat where characters snap back into alignment
const SNAP_DUR = 6;

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// Start frame: non-linear stagger, accelerating density
const startOf = (i: number) => 4 + 36 * (1 - Math.pow(1 - i / (WORD.length - 1), 1.5));

// Vertical displacement for a single character (relative to floor, negative = above)
const dropY = (t: number): number => {
  if (t <= 0) return -DROP;
  if (t < T_FALL) return -DROP + DROP * (t / T_FALL) ** 2; // Gravity acceleration
  if (t < T_FALL + T_B1) {
    const u = (t - T_FALL) / T_B1;
    return -DROP * 0.3 * 4 * u * (1 - u); // Bounce 1: 30%
  }
  if (t < T_FALL + T_B1 + T_B2) {
    const u = (t - T_FALL - T_B1) / T_B2;
    return -DROP * 0.09 * 4 * u * (1 - u); // Bounce 2: 9%
  }
  return 0;
};

// Ground impact squash: damped oscillation for each of the three impacts (initial landing / bounce 1 / bounce 2) at intensities 1 / 0.45 / 0.18
const IMPACTS: [number, number][] = [
  [T_FALL, 1],
  [T_FALL + T_B1, 0.45],
  [T_FALL + T_B1 + T_B2, 0.18],
];
const squashAt = (t: number) => {
  let s = 0;
  for (const [t0, k] of IMPACTS) {
    const d = t - t0;
    if (d < 0 || d > 16) continue;
    s += k * Math.exp(-d / 2.6) * Math.cos(d * 0.85);
  }
  return s;
};

export const LetterDropPhysics: React.FC = () => {
  const frame = useCurrentFrame();
  // Snap alignment at frame 110: 108-110 inhale expand, 110-116 ease-out settle
  const inhale = ramp(frame, SNAP - 2, 2, EASE.out);
  const snap = ramp(frame, SNAP, SNAP_DUR, EASE.snappy);
  const snapRot = ramp(frame, SNAP, SNAP_DUR + 2, EASE.overshoot); // Snap rotation with slight overshoot
  const pulse = 0.06 * inhale * (1 - snap);
  // Subtitle: fades in after alignment snap
  const sub = ramp(frame, SNAP + 4, 18, EASE.out);

  return (
    <div style={{ width: 1920, height: 1080, overflow: 'hidden', position: 'relative', fontFamily: FONT.sans }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.16 }} grain={0} vignette={0.16} />

      {/* Floor: darkening surface gradient below horizon + faded hairline horizon */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: FLOOR_Y, bottom: 0,
        background: 'linear-gradient(180deg, rgba(40,42,52,0.035) 0%, rgba(40,42,52,0.012) 30%, rgba(40,42,52,0) 64%)',
      }} />
      <div style={{
        position: 'absolute', left: 160, right: 160, top: FLOOR_Y, height: 1,
        background: 'linear-gradient(90deg, rgba(20,22,28,0) 0%, rgba(20,22,28,0.16) 22%, rgba(20,22,28,0.16) 78%, rgba(20,22,28,0) 100%)',
      }} />
      <div style={{
        position: 'absolute', left: 160, right: 160, top: FLOOR_Y + 1, height: 1,
        background: 'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.7) 30%, rgba(255,255,255,0.7) 70%, rgba(255,255,255,0) 100%)',
      }} />

      {/* Letter row: flex slots sized to natural character widths; characters transform inside slots */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: ROW_TOP, height: SIZE,
        display: 'flex', justifyContent: 'center',
        fontSize: SIZE, fontWeight: 800, lineHeight: 1, letterSpacing: tracking(SIZE, true), color: G.ink1,
      }}>
        {WORD.split('').map((ch, i) => {
          const t = frame - startOf(i);
          const y = dropY(t);
          const vy = dropY(t + 0.5) - dropY(t - 0.5);
          const air = -y; // Height above ground
          // Tilt to seed angle (+/-6 deg) on landing, 0 before landing; snaps to zero on snap beat
          const tiltTarget = (h(i + 1) - 0.5) * 12;
          const landP = EASE.out(clamp01((t - T_FALL) / 6));
          const rot = tiltTarget * landP * (1 - snapRot);
          // Standing tilted = resting on one bottom corner: elevate by sin|theta| * half-width so corner stays on floor
          const jitter = -Math.sin((Math.abs(rot) * Math.PI) / 180) * 48;
          // Stretch (fall velocity) + squash (touchdown), volume-preserving: scaleX ~= 1/scaleY
          const stretch = Math.min(1, Math.abs(vy) / 60) * 0.1 * (t < T_FALL ? 1 : 0.6);
          const sq = squashAt(t);
          const sy = (1 + stretch) * (1 - 0.2 * sq) + pulse;
          const sx = (1 - stretch * 0.55) * (1 + 0.15 * sq) + pulse;
          // Contact shadow: sharp and compact near ground, broad and diffuse at height; hidden offscreen
          const lift = clamp01(air / 420);
          const shOp = (t < 0 ? 0 : 0.2) * (1 - lift * 0.85) * clamp01((t + 2) / 8);
          const shW = mix(0.74, 1.3, lift) * (1 + 0.12 * Math.max(0, sq));
          const shBlur = mix(7, 28, lift);
          return (
            <span key={i} style={{ position: 'relative', display: 'inline-block' }}>
              {/* Spacer character: reserves natural advance width, invisible */}
              <span style={{ visibility: 'hidden' }}>{ch}</span>
              {/* Contact shadow */}
              <div style={{
                position: 'absolute', left: '50%', top: BASE - 7, width: '84%', height: 14,
                transform: `translateX(-50%) scaleX(${shW.toFixed(3)})`,
                borderRadius: '50%', background: 'rgba(22,24,34,1)',
                opacity: shOp, filter: `blur(${shBlur.toFixed(1)}px)`,
              }} />
              {/* Motion layer: outer translation carries blur (full during fall, half during bounces to avoid muddy landing); squash/tilt pivots at contact point */}
              {/* Blur layer padded with PAD: SVG filter bounds follow element box, tight box clips blur into hard edges */}
              <div style={{
                position: 'absolute', left: -PAD, right: -PAD, top: -PAD, bottom: -PAD,
                transform: `translateY(${(y + jitter).toFixed(2)}px)`,
              }}>
                <SpeedBlur vx={0} vy={vy} amount={t < T_FALL ? 0.26 : 0.12} max={16}>
                  <div style={{
                    position: 'absolute', left: PAD, right: PAD, top: PAD, bottom: PAD, textAlign: 'center',
                    transform: `rotate(${rot.toFixed(3)}deg) scale(${sx.toFixed(4)}, ${sy.toFixed(4)})`,
                    transformOrigin: '50% 86%',
                  }}>
                    {ch}
                  </div>
                </SpeedBlur>
              </div>
            </span>
          );
        })}
      </div>

      {/* Subtitle: final statement following the alignment snap */}
      <div style={{
        position: 'absolute', left: 0, right: 0, top: FLOOR_Y + 70, textAlign: 'center',
        fontSize: 36, fontWeight: 500, letterSpacing: tracking(36), color: G.ink2,
        opacity: sub, transform: `translateY(${((1 - sub) * 10).toFixed(2)}px)`,
      }}>
        Every shot lands on the beat.
      </div>

      <Grain opacity={0.05} />
    </div>
  );
};
