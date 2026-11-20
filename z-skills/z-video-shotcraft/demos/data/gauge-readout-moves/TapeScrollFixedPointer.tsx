// tape-scroll-fixed-pointer — scrolling tape with fixed pointer (world moves, pointer stays fixed: value magnitude = visible displacement distance)
//
// Second redesign pass (porcelain precision instrument / avionics speed tape grammar):
// - look = porcelain (cool white + cobalt blue). The centerpiece is a vertical scale tape spanning full frame height, fading out top and bottom (minor ticks every 10, major ticks every 50 +
//   64px numerals). A cobalt blue readout window + pointer notch are pinned to the screen centerline: 128px white readout inside the window, with tape scrolling behind it.
//   No longer a small boxed ruler — the tape itself is the "world" of the frame.
// - Narrative: slow climb capped at old limit (dashed "Old limit" (140k) right above window, readout held at 122) -> upgrade takes effect,
//   old limit line breaks and fades out -> anticipation pull-back -> tape sprint (peak ~100px/f, vertical motion blur with speed) -> overshoots 444 ->
//   spring brake rebounds to 416 -> settles at 420, new limit marker (cobalt blue triangle bug) aligns precisely with pointer.
// - Left layout: branded overline (video-shotcraft · frames / hour) + 124px headline "Throughput"; after settling, second line "tripled." rises in cobalt blue
//   (conclusion follows data arrival), followed by "▲ 200%" chip popup + "140k → 420k" monospace summary.
//
// Timeline (30fps, 150f total):
//   0–14    Anticipation: stage initialized, tape resting at 60, headline first line rises
//   10–48   Slow climb 60->122 (swift: accelerates out, decelerates near ceiling — "hitting the cap", limit line right at upper edge of readout window)
//   48–56   Hold beneath upper limit; 52f old limit line breaks and fades out (upgrade active)
//   56–61   Anticipation: slight pull-back 122->117
//   61–83   Sprint 117->444 (22f, bezier .55,0,.25,1), tape vertically blurred with speed
//   83–110  Spring brake: 444->416->420 (~16% single visible rebound), locked to constant after 110f
//   96–124  Aftermath: "tripled." rises (98f), chip pops up (108f), summary fades in (114f)
//   110–150 Hold: subtle camera push-in 1.0->1.025, final frame is a complete conclusion poster
import React from 'react';
import { AbsoluteFill, spring, useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, bezier, mix, ramp, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND } from '../../_fixtures/Brand';

export const TAPE_SCROLL_FIXED_POINTER_DURATION = 150;

const L = LOOKS.porcelain;
const PXU = 5; // px / unit: tick mark every 10 units = 50px
const CY = 540; // Pointer centerline (screen y)
const TAPE_X = 1000; // Tape left edge
const TAPE_W = 520;
const TICK_R = TAPE_X + TAPE_W - 40; // Tick right edge (extending leftward)
const NUM_R = TAPE_X + 310; // Number right-alignment line
const WIN_X = TAPE_X - 30; // Readout window
const WIN_W = 400;
const WIN_H = 150;
const OLD_LIMIT = 140; // Old limit 140k x 3 = new limit 420k (+200%)
const NEW_LIMIT = 420;

const SPRINT = bezier(0.55, 0, 0.25, 1); // Sprint: rapid acceleration, extended deceleration
// Rebound spring: 444 -> 420, rebounds to 416 (overshoot 4/24 ≈ 17%) -> derived damping
const SET_STIFF = 140;
const SET_DAMP = (() => {
  const lp = Math.log(4 / 24);
  return 2 * (-lp / Math.sqrt(Math.PI * Math.PI + lp * lp)) * Math.sqrt(SET_STIFF);
})();

// Readout timeline (pure frame function, clamped throughout)
const valueAt = (f: number): number => {
  if (f <= 10) return 60;
  if (f <= 48) return mix(60, 122, ramp(f, 10, 38, EASE.swift));
  if (f <= 56) return 122;
  if (f <= 61) return mix(122, 117, ramp(f, 56, 5, EASE.smooth));
  if (f <= 83) return mix(117, 444, SPRINT((f - 61) / 22));
  if (f >= 110) return NEW_LIMIT;
  return mix(444, NEW_LIMIT, spring({ frame: f - 83, fps: 30, config: { stiffness: SET_STIFF, damping: SET_DAMP, mass: 1 } }));
};

export const TapeScrollFixedPointer: React.FC = () => {
  const frame = useCurrentFrame();
  const v = valueAt(frame);
  const vy = velocity((f) => valueAt(f) * PXU, frame); // Tape velocity (px/frame)
  const speed = Math.abs(vy);
  const yOf = (u: number) => CY + (v - u) * PXU; // Screen y of unit u (larger numbers on top)

  // Ticks (render only visible range)
  const ticks: React.ReactNode[] = [];
  const uMin = Math.floor((v - 130) / 10) * 10;
  for (let u = Math.max(0, uMin); u <= v + 130; u += 10) {
    const y = yOf(u);
    const major = u % 50 === 0;
    ticks.push(
      <div key={`t${u}`} style={{
        position: 'absolute', left: TICK_R - (major ? 150 : 70), top: y - (major ? 2 : 1), width: major ? 150 : 70, height: major ? 4 : 2,
        borderRadius: 2, background: major ? L.ink : alpha(L.ink, 0.32),
      }} />,
    );
    if (major) {
      // Numbers fade out before sliding behind readout window (avoids clipping at edges)
      const near = Math.min(1, Math.max(0, (Math.abs(y - CY) - WIN_H / 2 - 36) / 30));
      ticks.push(
        <div key={`n${u}`} style={{ opacity: near,
          position: 'absolute', left: NUM_R - 260, width: 260, top: y - 40, height: 80, lineHeight: '80px', textAlign: 'right',
          ...type(64, 600), letterSpacing: '-0.03em', color: alpha(L.ink, 0.82),
        }}>{u}</div>,
      );
    }
  }

  // Old limit line: breaks and fades out at 52f (both halves sliding outward)
  const brk = ramp(frame, 52, 14, EASE.out);
  const oldY = yOf(OLD_LIMIT);
  // New limit bug: scrolls with tape, lights up when bug aligns with pointer after settle
  const newY = yOf(NEW_LIMIT);
  const locked = ramp(frame, 104, 10, EASE.out);

  const head = ramp(frame, 0, 20, EASE.snappy);
  const push = 1 + 0.025 * ramp(frame, 90, 60, EASE.smooth);
  const readBlur = Math.min(6, speed * 0.06);
  const chip = ramp(frame, 108, 14, EASE.overshoot);
  const recap = ramp(frame, 114, 16, EASE.out);
  const glowK = Math.min(1, speed / 60); // Cobalt blue outer glow on readout window during sprint

  return (
    <AbsoluteFill style={{ fontFamily: FONT.sans, overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.68, y: 0.3 }} fill={null} />
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push.toFixed(4)})`, transformOrigin: '62% 50%' }}>
        {/* ── World layer: scale tape (moves as a whole) ── */}
        <div style={{
          position: 'absolute', left: TAPE_X, top: 0, width: TAPE_W, height: 1080,
          WebkitMaskImage: 'linear-gradient(180deg, transparent 0%, #000 22%, #000 78%, transparent 100%)',
          maskImage: 'linear-gradient(180deg, transparent 0%, #000 22%, #000 78%, transparent 100%)',
        }}>
          {/* Tape surface: subtle gradient white + left/right hairlines */}
          <div style={{
            position: 'absolute', inset: 0, background: `linear-gradient(90deg, ${alpha('#ffffff', 0.35)} 0%, ${alpha('#ffffff', 0.85)} 60%, ${alpha('#ffffff', 0.6)} 100%)`,
            borderLeft: `1px solid ${L.line}`, borderRight: `1px solid ${L.line}`,
          }} />
        </div>
        <div style={{
          position: 'absolute', inset: 0,
          WebkitMaskImage: 'linear-gradient(180deg, transparent 2%, #000 24%, #000 76%, transparent 98%)',
          maskImage: 'linear-gradient(180deg, transparent 2%, #000 24%, #000 76%, transparent 98%)',
        }}>
          <SpeedBlur vx={0} vy={vy} amount={0.12} max={12}>
            {ticks}
            {/* Old limit: dashed line + label, breaks after upgrade */}
            {brk < 1 && oldY > -40 && oldY < 1120 && (
              <>
                <div style={{
                  position: 'absolute', left: TAPE_X - 10 - brk * 80, top: oldY - 1.5, width: TAPE_W / 2 + 10, height: 3, opacity: 1 - brk,
                  backgroundImage: `repeating-linear-gradient(90deg, ${L.ink2} 0 14px, transparent 14px 24px)`,
                }} />
                <div style={{
                  position: 'absolute', left: TAPE_X + TAPE_W / 2 + brk * 80, top: oldY - 1.5, width: TAPE_W / 2 - 16, height: 3, opacity: 1 - brk,
                  backgroundImage: `repeating-linear-gradient(90deg, ${L.ink2} 0 14px, transparent 14px 24px)`,
                }} />
                <div style={{
                  position: 'absolute', left: TAPE_X + TAPE_W + 28, top: oldY - 22, opacity: 1 - brk, whiteSpace: 'nowrap',
                  ...type(32, 600, { caps: true }), letterSpacing: '0.1em', color: L.ink2,
                }}>Old limit</div>
              </>
            )}
            {/* New limit bug: cobalt blue triangle anchored to right edge of tape */}
            {newY > -60 && newY < 1140 && (
              <>
                <svg width={44} height={56} style={{ position: 'absolute', left: TICK_R + 6, top: newY - 28, overflow: 'visible' }}>
                  <path d="M 4 28 L 40 6 L 40 50 Z" fill={L.accent} stroke={L.accent} strokeWidth={6} strokeLinejoin="round" />
                </svg>
                <div style={{
                  position: 'absolute', left: TAPE_X + TAPE_W + 28, top: newY - 22, whiteSpace: 'nowrap',
                  ...type(32, 700, { caps: true }), letterSpacing: '0.1em', color: L.accent,
                  opacity: 0.55 + 0.45 * locked,
                }}>New limit</div>
              </>
            )}
          </SpeedBlur>
        </div>

        {/* ── Fixed layer: readout window + pointer notch (fixed pointer) ── */}
        <div style={{
          position: 'absolute', left: WIN_X, top: CY - WIN_H / 2, width: WIN_W, height: WIN_H, borderRadius: 26,
          background: `linear-gradient(180deg, ${L.accent} 0%, #2448d8 100%)`,
          boxShadow: `inset 0 1px 0 rgba(255,255,255,0.35), 0 24px 50px -16px ${alpha(L.shadow, 0.45)}, 0 4px 10px ${alpha(L.shadow, 0.16)}, 0 0 ${(30 + 50 * glowK).toFixed(1)}px ${alpha(L.accent, 0.18 + 0.32 * glowK)}`,
          overflow: 'hidden', opacity: head,
        }}>
          {/* Readout inside window (vertically blurred with speed during sprint) */}
          <div style={{
            position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, display: 'flex', alignItems: 'baseline', justifyContent: 'flex-end',
            paddingRight: 48, paddingTop: 10, boxSizing: 'border-box', color: L.onAccent, whiteSpace: 'nowrap',
          }}>
            <span style={{ ...type(128, 700), letterSpacing: '-0.04em', lineHeight: '140px', filter: readBlur > 0.4 ? `blur(${readBlur.toFixed(2)}px)` : undefined }}>
              {Math.round(v)}
            </span>
            <span style={{ ...type(48, 600), marginLeft: 10, opacity: 0.75 }}>k</span>
          </div>
          {/* Top highlight on window surface */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: '45%', background: 'linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0))' }} />
        </div>
        {/* Pointer: cobalt blue needle + triangle extending from right side of window toward ticks */}
        <div style={{ position: 'absolute', left: WIN_X + WIN_W - 2, top: CY - 2, width: TICK_R - (WIN_X + WIN_W) + 2, height: 4, background: L.accent, opacity: head, borderRadius: 2 }} />
        <svg width={40} height={44} style={{ position: 'absolute', left: WIN_X + WIN_W - 6, top: CY - 22, overflow: 'visible', opacity: head }}>
          <path d="M 2 4 L 30 22 L 2 40 Z" fill={L.accent} stroke={L.accent} strokeWidth={4} strokeLinejoin="round" />
        </svg>
      </div>

      {/* ── Left typography ── */}
      <div style={{ position: 'absolute', left: 150, top: 300, width: 760 }}>
        <div style={{ ...type(26, 650, { caps: true }), letterSpacing: '0.24em', color: L.accent, opacity: head, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ width: 36, height: 3, background: L.accent, borderRadius: 2 }} />
          <span><span style={{ fontFamily: BRAND.font, fontWeight: 700, textTransform: 'none', letterSpacing: '0.03em' }}>{BRAND.name}</span> · frames / hour</span>
        </div>
        <div style={{ marginTop: 34, ...type(124, 750), color: L.ink }}>
          <TextReveal text="Throughput" by="word" variant="rise" start={2} each={18} gap={5} />
        </div>
        <div style={{ ...type(124, 750), color: L.accent, height: 130 }}>
          <TextReveal text="tripled." by="char" variant="rise" start={98} each={14} gap={1.6} />
        </div>
        <div style={{ marginTop: 40, height: 60, display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{
            height: 60, padding: '0 24px', borderRadius: 30, display: 'flex', alignItems: 'center', background: alpha(L.accent2, 0.12),
            border: `1px solid ${alpha(L.accent2, 0.35)}`, color: '#00866f', ...type(34, 700), whiteSpace: 'nowrap',
            opacity: Math.min(1, chip * 1.5), transform: `scale(${mix(0.6, 1, chip).toFixed(4)})`, transformOrigin: '0% 50%',
          }}>▲ 200%</div>
          <div style={{ ...type(36, 500, { mono: true }), color: L.ink2, opacity: recap, transform: `translateX(${mix(-16, 0, recap).toFixed(2)}px)`, whiteSpace: 'nowrap' }}>
            140k → 420k
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
      <div style={{ position: 'absolute', left: 150, top: 300, width: 760 }}>
        <div style={{ ...type(26, 650, { caps: true }), letterSpacing: '0.24em', color: L.accent, opacity: head, display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ width: 36, height: 3, background: L.accent, borderRadius: 2 }} />
          <span><span style={{ fontFamily: BRAND.font, fontWeight: 700, textTransform: 'none', letterSpacing: '0.03em' }}>{BRAND.name}</span> · frames / hour</span>
        </div>
        <div style={{ marginTop: 34, ...type(124, 750), color: L.ink }}>
          <TextReveal text="Throughput" by="word" variant="rise" start={2} each={18} gap={5} />
        </div>
        <div style={{ ...type(124, 750), color: L.accent, height: 130 }}>
          <TextReveal text="tripled." by="char" variant="rise" start={98} each={14} gap={1.6} />
        </div>
        <div style={{ marginTop: 40, height: 60, display: 'flex', alignItems: 'center', gap: 24 }}>
          <div style={{
            height: 60, padding: '0 24px', borderRadius: 30, display: 'flex', alignItems: 'center', background: alpha(L.accent2, 0.12),
            border: `1px solid ${alpha(L.accent2, 0.35)}`, color: '#00866f', ...type(34, 700), whiteSpace: 'nowrap',
            opacity: Math.min(1, chip * 1.5), transform: `scale(${mix(0.6, 1, chip).toFixed(4)})`, transformOrigin: '0% 50%',
          }}>▲ 200%</div>
          <div style={{ ...type(36, 500, { mono: true }), color: L.ink2, opacity: recap, transform: `translateX(${mix(-16, 0, recap).toFixed(2)}px)`, whiteSpace: 'nowrap' }}>
            140k → 420k
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
