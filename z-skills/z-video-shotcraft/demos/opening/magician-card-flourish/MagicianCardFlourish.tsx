// magician-card-flourish — Magician card flourish: blue starburst flashes, conjuring a card from light,
// spinning rapidly on an arc toward camera, snapping into a hard freeze, followed by a sheen sweep.
//
// Iteration 2 redesign (midnight blue · premiere invitation):
// - look = midnight. The card is designed as a deep navy video-shotcraft "Launch Film" premiere ticket:
//   center emblem = video-shotcraft mark resting upon concentric rings and cross needles inherited from the starburst, bold Launch / Film typography +
//   ticket numbering; holographic foil shifts color with rotation angle (iridescent during flight, freezing on landing). Card back features crest + mark.
// - Composition: Card lands at screen left 1/3 (cx=700, height ≈ 86% viewport), right side dedicated to promotional copy —
//   revealed line-by-line after lock-in, creating a cohesive invitation poster during hold.
// - Starburst: X-shaped diagonal needle beams + central specular pip / blue glow / radial spikes, rotating 90 deg over 9f.
//   Flash point = card landing position: viewers locate the flash, card emerges from it, loops on an arc, and returns to lock in place.
// - Ejection: slow-in (first 14% time covers 6% path) -> explosive kickoff -> cubic ease-out arc deceleration;
//   13 full rotations along diagonal axis, with angular velocity decaying at power 2.4 over the final 60%; integer turns guarantee front-facing freeze.
// - Freeze = zero-rebound lock (magical snap). On landing: blue optical pulse ripples outward from card borders,
//   backlight strikes up, stage key light lifts; 8f later a diagonal sheen sweeps across the card (clipped to border radius).
//
// Timeline (30fps, 156f total):
//   0–9     Starburst flash (9f, ramp 2.5f -> shimmer -> collapse, 90 deg rotation); stage dimmed to cool ambient
//   9–57    Flight 48f: slow-in 7f -> eject -> arc ease-out; CameraMotionBlur wraps flight only
//   57      Hard freeze; optical pulse 57–79, backlight and stage light 53–85 ramp up
//   65–91   Single sheen sweep (26f)
//   62–100  Right-side typography: eyebrow letter-spacing collapse 63 -> 2-line title rises 67/74 -> body copy by word 86
//   104–156 Hold: subtle backlight breathing, floating dust motes, settling into final ~1.7s invitation poster
import React, { useId } from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';
import { EASE, FONT, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

const L = LOOKS.midnight;

const CARD_W = 380;
const CARD_H = 540;
// Diagonal axis (card diagonal direction, normalized)
const AX = CARD_W / Math.hypot(CARD_W, CARD_H);
const AY = CARD_H / Math.hypot(CARD_W, CARD_H);

// —— Timeline (30fps / 156 frames) ——
export const MAGICIAN_CARD_FLOURISH_DURATION = 156;
const TAKEOFF = 9; // Card lifts off after 0.3s (9f) intro light flash
const FLASH_END = 12; // Flash tail fades completely (collapse trails 3 frames)
const FLIGHT = 48; // Flight duration (frames)
const LAND = TAKEOFF + FLIGHT; // f=57 hard freeze
const SHEEN_START = LAND + 8; // Sheen begins 8 frames after freeze
const SHEEN_DUR = 26; // Sheen duration (single pass)
const TURNS = 13; // Total flight rotations (integer -> lands exactly front-facing)
const FINAL_SCALE = 1.72; // Final scale: card height 540*1.72 ≈ 929 ≈ 86% frame height
const CX = 700; // Landing center (= flash point)
const CY = 540;
const TEXT_X = 1130; // Right copy left margin

// Card front: 380x540 design coordinates; rasterized via zoom at FINAL_SCALE for native sharpness on freeze
const CardFace: React.FC<{ theta: number }> = ({ theta }) => {
  const gid = useId().replace(/[^a-zA-Z0-9]/g, '');
  // Holographic foil: hue scrolls with spin angle (iridescent in flight, static once theta freezes)
  const holo = (theta * 0.9) % 360;
  return (
    <div style={{
      width: CARD_W, height: CARD_H, borderRadius: 24, boxSizing: 'border-box', padding: '22px 24px 24px',
      position: 'relative', overflow: 'hidden', fontFamily: FONT.sans, color: L.ink,
      background: 'linear-gradient(165deg, #16244a 0%, #0d1631 46%, #080d20 100%)',
      boxShadow: 'inset 0 0 0 1px rgba(170,200,255,0.16), inset 0 1px 0 rgba(255,255,255,0.22)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Holographic foil: sweep over emblem area, screen blend */}
      <div style={{
        position: 'absolute', inset: 0, mixBlendMode: 'screen', opacity: 0.28,
        background: `conic-gradient(from ${holo}deg at 50% 40%, rgba(91,140,255,0.0), rgba(62,230,208,0.5), rgba(91,140,255,0.0), rgba(167,139,250,0.45), rgba(91,140,255,0.0))`,
        WebkitMaskImage: 'radial-gradient(ellipse 70% 46% at 50% 40%, #000 0%, transparent 75%)',
      }} />
      {/* Brand row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, position: 'relative' }}>
        <ShotcraftMark size={22} tone="dark" />
        <div style={{ fontFamily: BRAND.font, fontSize: 14, fontWeight: 700, letterSpacing: '0.03em' }}>{BRAND.name}</div>
        <div style={{ marginLeft: 'auto', fontFamily: FONT.mono, fontSize: 11, color: L.ink2, letterSpacing: '0.04em' }}>SC 01 · TAKE 01</div>
      </div>
      {/* Emblem: concentric rings + cross needles (starburst motif) + video-shotcraft mark */}
      <div style={{ flex: 1, position: 'relative' }}>
        <svg viewBox="-190 -150 380 300" width={332} height={262} style={{ position: 'absolute', left: 0, top: 6 }}>
          <defs>
            <radialGradient id={`halo${gid}`}>
              <stop offset="0" stopColor="#5b8cff" stopOpacity="0.55" />
              <stop offset="1" stopColor="#5b8cff" stopOpacity="0" />
            </radialGradient>
            <linearGradient id={`ray${gid}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="#bcd4ff" stopOpacity="0.9" />
              <stop offset="1" stopColor="#5b8cff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <circle r={130} fill={`url(#halo${gid})`} />
          {/* Rings and needles originate outside mark border (≈56 units) to avoid intersecting viewfinder aperture */}
          {[68, 94, 120].map((r, i) => (
            <circle key={r} r={r} fill="none" stroke={`rgba(170,200,255,${0.18 - i * 0.04})`} strokeWidth={0.8} />
          ))}
          {[-38, 52, 142, 232].map((d, i) => (
            <path key={d} transform={`rotate(${d})`} d={`M 62 -0.9 L ${i % 2 ? 110 : 180} 0 L 62 0.9 Z`} fill={`url(#ray${gid})`} />
          ))}
        </svg>
        {/* Mark centered in SVG (viewBox centered at origin) */}
        <ShotcraftMark size={112} tone="dark" style={{ position: 'absolute', left: 166 - 56, top: 6 + 131 - 56 }} />
      </div>
      {/* Title */}
      <div style={{ position: 'relative' }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.24em', color: L.accent, marginBottom: 8 }}>PREMIERE · REEL 01</div>
        <div style={{ fontSize: 58, fontWeight: 760, letterSpacing: '-0.045em', lineHeight: 0.92 }}>Launch</div>
        <div style={{ fontSize: 58, fontWeight: 300, letterSpacing: '-0.04em', lineHeight: 0.98, color: '#c9d6f5' }}>Film</div>
      </div>
      {/* Bottom ticket stub row */}
      <div style={{
        position: 'relative', display: 'flex', alignItems: 'center', marginTop: 18, paddingTop: 12,
        borderTop: '1px dashed rgba(170,200,255,0.22)', fontFamily: FONT.mono, fontSize: 11, color: L.ink2, letterSpacing: '0.06em',
      }}>
        <span>ADMIT ONE</span>
        <span style={{ marginLeft: 'auto' }}>1920×1080 · 30 FPS</span>
      </div>
    </div>
  );
};

// Card back: deep navy + delicate filigree + centered video-shotcraft mark
const CardBack: React.FC = () => (
  <div style={{
    position: 'absolute', inset: 0, borderRadius: 24, overflow: 'hidden',
    background: 'linear-gradient(160deg, #1b2a55 0%, #101a3a 55%, #0a1028 100%)',
    boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.12), inset 0 1px 0 rgba(255,255,255,0.18)',
  }}>
    <div style={{
      position: 'absolute', inset: 0,
      background:
        'repeating-linear-gradient(45deg, rgba(150,180,255,0.07) 0 1px, transparent 1px 12px), ' +
        'repeating-linear-gradient(-45deg, rgba(150,180,255,0.07) 0 1px, transparent 1px 12px)',
    }} />
    <div style={{
      position: 'absolute', inset: 22, borderRadius: 14, boxShadow: 'inset 0 0 0 1px rgba(200,215,255,0.24)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <ShotcraftMark size={120} tone="dark" />
    </div>
  </div>
);

// —— Intro Starburst ——
// X-shaped diagonal needle beams (major 840 / minor 420) + center pip + blue bloom + radial spikes; 90 deg rotation over 9f.
const SpawnFlash: React.FC<{ f: number }> = ({ f }) => {
  const SPIKE_ID = `mcf-needle-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;
  if (f > FLASH_END) return null;
  const grow = interpolate(f, [0, 2.5], [0.2, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad) });
  const shrink = interpolate(f, [6, TAKEOFF, FLASH_END], [1, 0.3, 0.05], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.quad) });
  const s = grow * shrink;
  const flicker = 0.94 + 0.06 * (0.5 + 0.5 * Math.sin(f * 1.9) * Math.sin(f * 0.83 + 1.7));
  const opacity = interpolate(f, [0, 1.5, 6, FLASH_END], [0.35, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) * flicker;
  const rot = interpolate(f, [0, FLASH_END], [0, 90], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });
  const needle = (deg: number, len: number, w0: number) => (
    <g key={`${deg}-${len}-${w0}`} transform={`rotate(${deg})`}>
      <path d={`M 0 ${-w0 / 2} L ${len} 0 L 0 ${w0 / 2} Z`} fill={`url(#${SPIKE_ID})`} />
      <path d={`M 0 ${-w0 / 2} L ${len} 0 L 0 ${w0 / 2} Z`} fill={`url(#${SPIKE_ID})`} transform="scale(-1,1)" />
    </g>
  );
  return (
    <div style={{ position: 'absolute', left: CX, top: CY, width: 0, height: 0, transform: `scale(${s})`, opacity, pointerEvents: 'none' }}>
      <div style={{
        position: 'absolute', left: -13, top: -13, width: 26, height: 26, borderRadius: 13,
        background: 'radial-gradient(circle, #ffffff 0%, rgba(225,245,255,0.95) 45%, rgba(140,215,255,0) 80%)', filter: 'blur(0.6px)',
      }} />
      <div style={{
        position: 'absolute', left: -70, top: -70, width: 140, height: 140, borderRadius: 70,
        background: 'radial-gradient(circle, rgba(90,175,255,0.75) 0%, rgba(50,130,245,0.35) 45%, rgba(40,110,235,0) 75%)', filter: 'blur(4px)',
      }} />
      <svg width={260} height={260} viewBox="-130 -130 260 260" style={{ position: 'absolute', left: -130, top: -130, transform: `rotate(${-rot * 0.6}deg)` }}>
        {[15, 52, 88, 123, 160, 197, 231, 268, 305, 341].map((deg, i) => {
          const ln = 46 + ((i * 37) % 3) * 16;
          return (
            <g key={deg} transform={`rotate(${deg})`} opacity={0.75}>
              <path d={`M 8 -1.1 L ${ln} 0 L 8 1.1 Z`} fill="rgba(150,210,255,0.85)" filter="blur(0.8px)" />
            </g>
          );
        })}
      </svg>
      <svg width={3200} height={3200} viewBox="-1600 -1600 3200 3200" style={{ position: 'absolute', left: -1600, top: -1600, transform: `rotate(${rot}deg)` }}>
        <defs>
          <linearGradient id={SPIKE_ID} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#eaf6ff" stopOpacity="1" />
            <stop offset="0.05" stopColor="#8cc8ff" stopOpacity="0.95" />
            <stop offset="0.3" stopColor="#3f9bff" stopOpacity="0.88" />
            <stop offset="0.62" stopColor="#2277f2" stopOpacity="0.6" />
            <stop offset="0.88" stopColor="#1b64e0" stopOpacity="0.25" />
            <stop offset="1" stopColor="#1a5fd8" stopOpacity="0" />
          </linearGradient>
        </defs>
        <g filter="blur(7px)" opacity={0.75}>{needle(-38, 826, 26)}</g>
        <g filter="blur(1.8px)">{needle(-38, 840, 8)}</g>
        {needle(-38, 819, 3)}
        <g filter="blur(5px)" opacity={0.75}>{needle(52, 413, 20)}</g>
        <g filter="blur(1.5px)">{needle(52, 420, 6.5)}</g>
        {needle(52, 410, 2.6)}
      </svg>
    </div>
  );
};

// Flight trajectory (pure function of frame; freezes fully at tEff=1)
const flight = (f: number) => {
  const tEff = Math.min(1, Math.max(0, (f - TAKEOFF) / FLIGHT));
  // Spin: rapid near-linear first 40%, power-2.4 decay thereafter; spinP(1)=1 -> exact full rotations -> front-facing freeze
  const spinP = tEff < 0.4 ? tEff * 1.55 : 0.62 + 0.38 * (1 - Math.pow(1 - (tEff - 0.4) / 0.6, 2.4));
  const theta = TURNS * 360 * Math.min(1, spinP);
  // Path progress: slow-in (first 14% time covers 6% path) -> ejection -> cubic ease-out deceleration
  const tp = tEff < 0.14 ? 0.06 * (tEff / 0.14) ** 2 : 0.06 + 0.94 * (1 - Math.pow(1 - (tEff - 0.14) / 0.86, 3));
  // Arc: swings out toward upper-right from landing point, returning to dock
  const arc = Math.sin(tp * Math.PI);
  const cx = CX + arc * 470;
  const cy = CY - arc * 230;
  // Depth: perspective scale=F/(F+z), z pulls in from distance to 0
  const FOCAL = 900;
  const z = 14000 * (1 - tp);
  const scale = FINAL_SCALE * (FOCAL / (FOCAL + z));
  return { tEff, theta, cx, cy, scale };
};

const Card: React.FC = () => {
  const f = useCurrentFrame();
  const { theta, cx, cy, scale } = flight(f);
  const facingBack = Math.cos((theta * Math.PI) / 180) < 0;
  const sheenP = ramp(f, SHEEN_START, SHEEN_DUR, EASE.smooth);
  const sheenOn = f >= SHEEN_START && f <= SHEEN_START + SHEEN_DUR;
  const W = CARD_W * FINAL_SCALE;
  const H = CARD_H * FINAL_SCALE;
  const R = 24 * FINAL_SCALE;
  const landed = f >= LAND;
  const sin = Math.sin((theta * Math.PI) / 180);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', left: cx - W / 2, top: cy - H / 2, width: W, height: H,
        transform: `scale(${scale / FINAL_SCALE})`, transformOrigin: '50% 50%', opacity: f >= TAKEOFF ? 1 : 0,
      }}>
        <div style={{
          width: '100%', height: '100%', position: 'relative', borderRadius: R,
          transform: `perspective(${1300 * FINAL_SCALE}px) rotate3d(${AX}, ${AY}, 0, ${theta}deg)`, transformOrigin: '50% 50%',
          // Post-freeze: dual-layer colored shadows + subtle blue rim glow
          boxShadow: landed
            ? `0 40px 90px -20px rgba(0,2,10,0.9), 0 12px 30px rgba(0,2,10,0.6), 0 0 0 1px rgba(140,175,255,0.18), 0 0 80px ${alpha(L.accent, 0.22)}`
            : `0 0 70px ${alpha(L.accent, 0.55)}, 0 0 0 1px rgba(160,195,255,0.35)`, // In flight: retains conjuring glow (trails under motion blur)
        }}>
          <div style={{ position: 'absolute', inset: 0, zoom: FINAL_SCALE }}>
            <CardFace theta={theta} />
            <div style={{ opacity: facingBack ? 1 : 0, position: 'absolute', inset: 0 }}><CardBack /></div>
          </div>
          {/* Dynamic side rim light during rotation; freezes with theta */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: R, pointerEvents: 'none', mixBlendMode: 'screen',
            background: `linear-gradient(${115 + sin * 30}deg, rgba(255,255,255,0) 30%, rgba(200,220,255,${0.08 + 0.16 * Math.abs(sin)}) 50%, rgba(255,255,255,0) 70%)`,
          }} />
          {/* Single sheen post-freeze: diagonal highlight sweeps left to right (clipped to border radius) */}
          {sheenOn && (
            <div style={{ position: 'absolute', inset: 0, borderRadius: R, overflow: 'hidden', pointerEvents: 'none' }}>
              <div style={{
                position: 'absolute', top: '-45%', bottom: '-45%', left: `${-70 + sheenP * 215}%`, width: '34%', transform: 'rotate(16deg)',
                background: 'linear-gradient(100deg, rgba(255,255,255,0) 0%, rgba(210,225,255,0.10) 35%, rgba(235,242,255,0.34) 50%, rgba(210,225,255,0.10) 65%, rgba(255,255,255,0) 100%)',
                mixBlendMode: 'screen',
              }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Landing optical pulse: rounded contour ripples outward from card perimeter and fades
const LandPulse: React.FC = () => {
  const f = useCurrentFrame();
  if (f < LAND || f > LAND + 24) return null;
  const p = ramp(f, LAND, 22, EASE.out);
  const W = CARD_W * FINAL_SCALE;
  const H = CARD_H * FINAL_SCALE;
  const grow = 1 + p * 0.14;
  return (
    <div style={{
      position: 'absolute', left: CX - W / 2, top: CY - H / 2, width: W, height: H, borderRadius: 24 * FINAL_SCALE,
      transform: `scale(${grow})`, opacity: (1 - p) * 0.9, pointerEvents: 'none',
      boxShadow: `0 0 0 ${(2.5 - p * 1.5).toFixed(2)}px ${alpha('#9cc0ff', 0.9)}, 0 0 40px ${alpha(L.accent, 0.7)}, inset 0 0 40px ${alpha(L.accent, 0.35)}`,
    }} />
  );
};

// Right typography: reveals post-freeze (eyebrow tracking collapse -> 2-line title rises -> body word-by-word)
const Copy: React.FC = () => {
  const f = useCurrentFrame();
  const rule = ramp(f, 62, 22, EASE.snappy);
  return (
    <div style={{ position: 'absolute', left: TEXT_X, top: 300, width: 700, color: L.ink }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 34 }}>
        <div style={{ width: 56 * rule, height: 2, background: L.accent, boxShadow: `0 0 12px ${alpha(L.accent, 0.8)}` }} />
        <TextReveal text="NOW SHOWING" variant="track" start={63} each={20} gap={0.8}
          style={{ ...type(TYPE_LABEL, 700, { caps: true }), letterSpacing: '0.26em', color: L.accent }} />
      </div>
      <div style={{ ...type(132, 780), color: L.ink }}>
        <TextReveal text={'Craft\nthe shot.'} by="line" variant="rise" start={67} each={22} gap={7} />
      </div>
      <div style={{ ...type(36, 420), color: L.ink2, marginTop: 40, maxWidth: 600, lineHeight: 1.38, letterSpacing: '-0.01em' }}>
        <TextReveal text={'Cinematic product videos,\ncrafted by your agent.'} by="word" variant="blur" start={86} each={16} gap={1.6} />
      </div>
    </div>
  );
};
const TYPE_LABEL = 24;

export const MagicianCardFlourish: React.FC = () => {
  const f = useCurrentFrame();
  const moving = f >= TAKEOFF && f <= LAND;
  // Stage light: dimmed during starburst (solitary key light), illuminates around landing, subtle breathing during hold
  const lit = ramp(f, LAND - 6, 30, EASE.out);
  const back = lit * (1 + 0.06 * Math.sin((f - LAND) / 16));
  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <Stage look={L} keyLight={{ x: CX / 1920, y: 0.1 }} fill={null} intensity={0.25 + 0.75 * lit} vignette={0.6}>
        {/* Card backlight: blue halo striking up after landing */}
        <div style={{
          position: 'absolute', left: CX - 620, top: CY - 560, width: 1240, height: 1120, opacity: back,
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.light, 0.38)} 0%, ${alpha(L.light, 0.1)} 42%, ${alpha(L.light, 0)} 70%)`,
        }} />
        <Dust look={L} count={26} seed={7} drift={0.22} opacity={0.35 + 0.35 * lit} />
      </Stage>
      {moving ? (
        <CameraMotionBlur shutterAngle={150} samples={7}>
          <Card />
        </CameraMotionBlur>
      ) : (
        <Card />
      )}
      <LandPulse />
      <Copy />
      {/* Starburst excluded from CameraMotionBlur to prevent multisampling ghosting on fine needle rays */}
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', pointerEvents: 'none' }}>
        <SpawnFlash f={f} />
      </div>
    </AbsoluteFill>
  );
};
