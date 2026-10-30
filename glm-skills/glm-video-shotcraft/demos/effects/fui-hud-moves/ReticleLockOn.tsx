// reticle-lock-on — reticle lock-on bracket snap (Iron Man HUD / Ender's Game)
// FakeDashboard at rest. 4-corner L-bracket viewfinder flies in from off-screen,
// contracts with overshoot to snap tight around target card corners; card illuminates on lock +
// small tag pops above. Motion remains live — capture in flight.
// f0-14 static rest; f14-24 fly-in; f20-46 contract (with overshoot); f46 lock-on;
// f48-58 label pops; static hold >=30f (total 90f).
//
// Polish pass: full duration 90f; target frame calibrated to fixture card geometry (524x454);
// brackets styled with 5px round stroke in accent color + white backing border + center crosshairs;
// diagonal motion blur during fly-in;
// continuous asymmetric overshoot contraction overlapping fly-in; snap pulse on lock-on frame,
// target card brightens with rounded gradient + accent stroke, background subtly dims; tag styled as dark pill
// (status dot + card name + mono lock index); slow camera push toward target.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';
import { EASE, FONT, Grain, SpeedBlur, mix, ramp } from '../../_fixtures/Polish';

export const RETICLE_LOCK_ON_DURATION = 90; // 3s: fly-in -> lock-on -> label -> static hold >=1s

// Target: variant A card 2 (row 1 center). Geometry: 524x454 @ x=808, y=108
const CARD_X = 808;
const CARD_Y = 108;
const CARD_W = 524;
const CARD_H = 454;
const PAD = 16; // Breathing margin between bracket and card

const TCX = CARD_X + CARD_W / 2;
const TCY = CARD_Y + CARD_H / 2;

const FLY_IN = 14; // Fly-in start
const FLY_END = 24; // Fly-in complete (frame in place)
const SHRINK0 = 20; // Contraction start (overlaps fly-in by 4f)
const UNDER = 40; // Overshoot timestamp (0.94x)
const LOCK_END = 46; // Lock-on frame
const LABEL0 = LOCK_END + 2;
const LABEL_END = LOCK_END + 12;

const ARM = 58; // L-arm length
const THICK = 5; // L-stroke width
const INK = G.accent; // Bracket color: accent color

const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

// Fly-in translation (px): frame rushes in from bottom-right, ease-out cubic
const flyAt = (f: number) => {
  const t = interpolate(f, [FLY_IN, FLY_END], [0, 1], { easing: Easing.out(Easing.cubic), ...clamp });
  return { x: (1 - t) * 1100, y: (1 - t) * 620 };
};
// Contraction scale: 2.2 -> 0.94 (swift overshoot) -> 1 (ease-out settle)
const shrinkAt = (f: number) =>
  f < UNDER ? mix(2.2, 0.94, ramp(f, SHRINK0, UNDER - SHRINK0, EASE.swift)) : mix(0.94, 1, ramp(f, UNDER, LOCK_END - UNDER, EASE.out));

export const ReticleLockOn: React.FC = () => {
  const frame = useCurrentFrame();

  const fly = flyAt(frame);
  const fly0 = flyAt(frame - 0.5);
  const fly1 = flyAt(frame + 0.5);
  const shrink = shrinkAt(frame);
  // Lock snap: brackets pinch inward 6px then rebound over 4f
  const bite = interpolate(frame, [LOCK_END, LOCK_END + 1, LOCK_END + 5], [0, 1, 0], clamp);
  const hw = (CARD_W / 2 + PAD) * shrink - 6 * bite;
  const hh = (CARD_H / 2 + PAD) * shrink - 6 * bite;

  // Lock frame: card illuminates (flash 0.55 settling to 0.28, clipped to card radius)
  const glow = interpolate(frame, [LOCK_END, LOCK_END + 3, LOCK_END + 10], [0, 0.55, 0.28], clamp);
  // Focus dim: periphery subtly dims to 0.10 over 10f
  const focus = interpolate(frame, [LOCK_END - 2, LOCK_END + 10], [0, 1], { easing: Easing.out(Easing.cubic), ...clamp });

  // Label: pops above top-left bracket post-lock (scale overshoot + fade-in)
  const labelT = interpolate(frame, [LABEL0, LABEL_END], [0, 1], { easing: Easing.out(Easing.back(1.8)), ...clamp });

  // Camera: continuous slow push toward target (1 -> 1.035, smooth)
  const cam = mix(1, 1.035, ramp(frame, 0, RETICLE_LOCK_ON_DURATION - 1, EASE.smooth));

  const showReticle = frame >= FLY_IN;
  const locked = frame >= LOCK_END;
  const reticleOp = interpolate(frame, [FLY_IN, FLY_IN + 3], [0, 1], clamp);

  // 4 L-corners: pos = center +/- (hw, hh), mirrored
  const corners = [
    { x: TCX - hw, y: TCY - hh, sx: 1, sy: 1 },
    { x: TCX + hw, y: TCY - hh, sx: -1, sy: 1 },
    { x: TCX - hw, y: TCY + hh, sx: 1, sy: -1 },
    { x: TCX + hw, y: TCY + hh, sx: -1, sy: -1 },
  ];
  // L-stroke: white backing (+2px) + accent core, round caps
  const stroke = (w: number, h: number, under: boolean): React.CSSProperties => ({
    position: 'absolute', left: under ? -2 : 0, top: under ? -2 : 0,
    width: w + (under ? 4 : 0), height: h + (under ? 4 : 0), borderRadius: 4,
    background: under ? 'rgba(255,255,255,0.92)' : INK,
    boxShadow: under ? '0 2px 6px rgba(16,18,40,0.18)' : 'none',
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam})`, transformOrigin: `${TCX}px ${TCY}px` }}>
        <FakeDashboard variant="A" />
        {/* Focus dimming: large box-shadow cutout around target card */} 
        {focus > 0 && (
          <div style={{
            position: 'absolute', left: CARD_X, top: CARD_Y, width: CARD_W, height: CARD_H, borderRadius: 14,
            boxShadow: `0 0 0 3000px rgba(16,18,28,${(0.1 * focus).toFixed(3)})`, pointerEvents: 'none',
          }} />
        )}
        {/* Lock illumination: rounded gradient + accent hairline stroke */} 
        {locked && (
          <div style={{
            position: 'absolute', left: CARD_X, top: CARD_Y, width: CARD_W, height: CARD_H, borderRadius: 14,
            overflow: 'hidden', pointerEvents: 'none',
            boxShadow: `0 0 0 1.5px rgba(91,99,211,${(0.55 * focus).toFixed(3)}), 0 18px 48px -16px rgba(91,99,211,${(0.35 * focus).toFixed(3)})`,
          }}>
            <div style={{
              position: 'absolute', inset: 0, opacity: glow,
              background: 'linear-gradient(180deg, rgba(255,255,255,1) 0%, rgba(255,255,255,0.55) 60%, rgba(255,255,255,0.35) 100%)',
            }} />
          </div>
        )}
        {showReticle && (
          <SpeedBlur vx={fly1.x - fly0.x} vy={fly1.y - fly0.y} amount={0.3} max={22}>
            <div style={{ position: 'absolute', left: 0, top: 0, transform: `translate(${fly.x}px, ${fly.y}px)`, opacity: reticleOp }}>
              {corners.map((c, i) => (
                <div key={i} style={{ position: 'absolute', left: c.x, top: c.y, transform: `scale(${c.sx}, ${c.sy})`, transformOrigin: '0 0' }}>
                  {/* L-bracket: horizontal + vertical arms (backing then core) */} 
                  <div style={stroke(ARM, THICK, true)} />
                  <div style={stroke(THICK, ARM, true)} />
                  <div style={stroke(ARM, THICK, false)} />
                  <div style={stroke(THICK, ARM, false)} />
                </div>
              ))}
              {/* Center crosshair: visible during flight, fades post-lock */} 
              {[0, 1].map((k) => (
                <div key={k} style={{
                  position: 'absolute', left: TCX - (k ? 1.5 : 14), top: TCY - (k ? 14 : 1.5), width: k ? 3 : 28, height: k ? 28 : 3,
                  borderRadius: 2, background: INK, opacity: 0.8 * (1 - focus), boxShadow: '0 0 0 2px rgba(255,255,255,0.85)',
                }} />
              ))}
            </div>
          </SpeedBlur>
        )}
        {/* Info label: pops above top-left bracket */} 
        {frame >= LABEL0 && (
          <div style={{
            position: 'absolute', left: TCX - hw + 2, top: TCY - hh - 70,
            transform: `scale(${labelT})`, transformOrigin: '0 100%', opacity: Math.min(1, labelT * 1.5),
            display: 'flex', alignItems: 'center', gap: 14, whiteSpace: 'nowrap',
            background: 'linear-gradient(180deg, #23252c 0%, #17181d 100%)', color: '#fff', fontFamily: FONT.sans,
            padding: '10px 16px 10px 14px', borderRadius: 12,
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.10), 0 0 0 1px rgba(0,0,0,0.25), 0 2px 4px rgba(16,18,24,0.18), 0 16px 32px -10px rgba(16,18,24,0.45)',
          }}>
            <div style={{ width: 12, height: 12, borderRadius: 6, background: '#8a91ff', boxShadow: '0 0 0 4px rgba(138,145,255,0.22)' }} />
            <span style={{ fontSize: 30, fontWeight: 600, letterSpacing: '-0.015em' }}>Top pages</span>
            <span style={{
              fontFamily: FONT.mono, fontSize: 18, fontWeight: 500, letterSpacing: '0.08em', color: 'rgba(255,255,255,0.55)',
              padding: '4px 8px', borderRadius: 6, background: 'rgba(255,255,255,0.07)',
            }}>LOCK 02</span>
          </div>
        )}
      </div>
      <Grain opacity={0.035} />
    </div>
  );
};
