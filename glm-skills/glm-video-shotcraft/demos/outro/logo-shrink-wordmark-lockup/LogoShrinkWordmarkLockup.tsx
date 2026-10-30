// logo-shrink-wordmark-lockup — Shrink & Lockup icon convergence (motion-lab final spec ported to native Remotion)
// The large neon slit ring quickly shrinks into a solid white central "O" with easeInOut; at the final overshoot brake, it morphs into the video-shotcraft mark.
// The icon then shifts left to make room, while the letters of the "video-shotcraft" wordmark slide in from left to right (opacity + 8px) to complete the lockup.
// An accent-colored motto fades in across the entire line with a slight delay to finish. Design coordinates 480×270 (DesignStage scales proportionally; zoom rasterization keeps letter edges sharp).
// Polish upgrades: deep-field background with hue tint + purple energy halo collapsing alongside the outer ring; dual arcs rotate while shrinking
// (decelerating rotation of 150°), trailing two layers of scale ghosts as motion blur during high-speed segments; a single fine shockwave emits upon braking;
// sliding letters feature 2.5px -> 0 focus blur; motto updated to a matching cool purple instead of contrasting red.
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { FONT, Grain, Vignette } from '../../_fixtures/Polish';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const LOGO_SHRINK_WORDMARK_LOCKUP_DURATION = 132; // 4400ms @30fps

const ACCENT = '#9d94ff'; // Motto accent color: shares hue with neon halo, brightened with reduced saturation
const WORDMARK = BRAND.name; // Lowercase wordmark
const ICON = 30; // Base icon size (px)
const MARK = 32; // Mark size: viewfinder body ≈ 0.81×MARK ≈ 26px, cleanly covering the healed ring
const WORD_W = 172; // Measured width of wordmark row (22px / 700, 15 chars; measured from rendered frame)
const GAP = 9; // Spacing between icon and wordmark
// Icon lockup left offset coupled with letter row left edge: centers the entire group (icon + gap + wordmark)
const SHIFT = -(ICON + GAP + WORD_W) / 2 + ICON / 2;
const ROW_LEFT = SHIFT + ICON / 2 + GAP; // Left edge of letter row relative to screen centerline
const STAGGER = (0.7 - 0.46) / WORDMARK.length; // Many letters: calculate interval via (0.7-0.46)/n so all start before 0.7
const DT = 1 / 131; // Delta t per frame (132f)

// Arc path (degrees, clockwise sweep)
const arcPath = (cx: number, cy: number, r: number, a0: number, a1: number) => {
  const p = (a: number) => [cx + r * Math.cos((a * Math.PI) / 180), cy + r * Math.sin((a * Math.PI) / 180)];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  const large = Math.abs(a1 - a0) > 180 ? 1 : 0;
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${r},${r} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)}`;
};

// Dual-arc group: a0-a1 and its diagonal (+180°) arcs — slit ring with gaps
const Arcs: React.FC<{ a0: number; a1: number; col: string; w: number; blur: number; opacity: number; stroke?: string }> = ({
  a0,
  a1,
  col,
  w,
  blur,
  opacity,
  stroke,
}) => (
  <g opacity={opacity}>
    {[
      [a0, a1],
      [a0 + 180, a1 + 180],
    ].map(([b0, b1], i) => (
      <path
        key={i}
        d={arcPath(15, 15, 10.5, b0, b1)}
        fill="none"
        stroke={stroke ?? col}
        strokeWidth={w}
        strokeLinecap="round"
        style={blur ? { filter: `blur(${blur}px)` } : undefined}
      />
    ))}
  </g>
);

// Main convergence curve: scale 5.4 -> 1 (easeInOut) with a slight 1.06 overshoot brake at the end
const scaleAt = (t: number) => {
  const k = seg(t, 0.02, 0.28, E.inOutCubic);
  const brake = Math.sin(seg(t, 0.26, 0.37) * Math.PI) * 0.06;
  return lerp(k, 5.4, 1) * (1 + brake);
};
// Rotation during convergence: decelerates through 150° ("tightening" gaps while shrinking), imperceptible once healed
const spinAt = (t: number) => -150 * seg(t, 0.0, 0.3, E.outCubic);

export const LogoShrinkWordmarkLockup: React.FC = () => {
  const t = useT();
  const s = scaleAt(t);
  const spin = spinAt(t);
  // Shift left to make room: t 0.34-0.47 after landing
  const shift = seg(t, 0.34, 0.47, E.inOutCubic) * SHIFT;
  // Neon slit state -> solid white O cross-fade (progresses with convergence)
  const heal = seg(t, 0.10, 0.28, E.inOutQuad);
  // White O -> video-shotcraft mark: cross-swapped to mark at the braking moment (in sync with shockwave), already shrunk to final size
  const markIn = seg(t, 0.24, 0.32, E.inOutQuad);
  // Scale ghost trails: intensity scaled by frame delta, 0 at rest
  const ds = Math.abs(scaleAt(t) - scaleAt(t - DT));
  const trail = Math.min(1, ds / 0.35);
  // Shockwave: emits a thin ring on brake rebound (t ≈ 0.28), expanding and dissipating
  const wave = seg(t, 0.28, 0.46, E.outCubic);
  // Energy halo: covers the large ring initially, collapsing alongside convergence and settling into a faint glow behind the icon
  const haloR = lerp(seg(t, 0.02, 0.3, E.inOutCubic), 150, 34);
  const haloA = 0.5 - 0.32 * seg(t, 0.3, 0.5, E.outCubic);

  // Outer layer handles translation + scale; ring rotates in inner layer — mark itself never rotates (brand guideline: maintain cut angle)
  const icon = (sc: number, rot: number, opacity: number, ghost = false) => (
    <div
      style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        width: ICON,
        height: ICON,
        margin: `${-ICON / 2}px 0 0 ${-ICON / 2}px`,
        transform: `translateX(${shift}px) scale(${sc})`,
        opacity,
      }}
    >
      <svg viewBox="0 0 30 30" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible', transform: `rotate(${rot}deg)` }}>
        {/* Neon halo (with slit gaps) */}
        <Arcs a0={-32} a1={122} col="rgba(118,96,255,.62)" w={6.5} blur={2.5} opacity={1 - heal} />
        {/* Neon core: turns pure white past halfway healed */}
        {!ghost && (
          <Arcs a0={-32} a1={122} col="#dfe9ff" w={3.4} blur={0} opacity={(1 - heal * 0.75) * (1 - markIn)} stroke={heal > 0.5 ? '#fff' : '#dfe9ff'} />
        )}
        {/* Healed solid white O (transition state, yields to mark upon braking) */}
        {!ghost && <circle cx={15} cy={15} r={10.5} fill="none" stroke="#fff" strokeWidth={5.5} opacity={heal * (1 - markIn)} />}
      </svg>
      {/* Healed standard state: video-shotcraft mark (inverted white, no glow) */}
      {!ghost && markIn > 0 && (
        <ShotcraftMark size={MARK} tone="dark" style={{ position: 'absolute', left: (ICON - MARK) / 2, top: (ICON - MARK) / 2, opacity: markIn }} />
      )}
    </div>
  );

  // Background color calibration: original mp4 (yuv420p, no color metadata) decoded #05060a to rgb(3,5,9); uses hue-tinted deep field here
  return (
    <AbsoluteFill>
    <DesignStage bg="#06070c" raster="zoom">
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
        {/* Deep field: vertical cool-tone gradient slightly brighter at top */}
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, #0d0f17 0%, #07080d 60%, #05060a 100%)' }} />
        {/* Energy halo (collapses with outer ring) */}
        <div
          style={{
            position: 'absolute',
            left: `calc(50% + ${shift}px - ${haloR}px)`,
            top: `calc(50% - ${haloR}px)`,
            width: haloR * 2,
            height: haloR * 2,
            borderRadius: '50%',
            opacity: haloA,
            background: 'radial-gradient(circle, rgba(110,92,255,0.42) 0%, rgba(110,92,255,0.12) 38%, rgba(110,92,255,0) 70%)',
          }}
        />
        {/* Shockwave: bright thin ring + soft outer glow, thinning and fading as it expands */}
        {wave > 0 && wave < 1 && (
          <div
            style={{
              position: 'absolute',
              left: `calc(50% - ${lerp(wave, 16, 70)}px)`,
              top: `calc(50% - ${lerp(wave, 16, 70)}px)`,
              width: lerp(wave, 32, 140),
              height: lerp(wave, 32, 140),
              borderRadius: '50%',
              boxSizing: 'border-box',
              border: `${lerp(wave, 0.9, 0.25)}px solid rgba(214,220,255,${(0.55 * (1 - wave)).toFixed(3)})`,
              boxShadow: `0 0 ${lerp(wave, 4, 10)}px rgba(130,112,255,${(0.45 * (1 - wave)).toFixed(3)})`,
            }}
          />
        )}
        {/* Scale ghost trails (high-speed segment only): scale and rotation from -1f and -2f */}
        {trail > 0.02 && icon(scaleAt(t - 2 * DT), spinAt(t - 2 * DT), 0.16 * trail, true)}
        {trail > 0.02 && icon(scaleAt(t - DT), spinAt(t - DT), 0.3 * trail, true)}
        {/* Icon: SVG dual-arc slit ring (kinetic state) -> gaps heal on convergence, cross-fading into video-shotcraft mark (standard state) */}
        {icon(s, spin, 1)}
        {/* Letter row (right of icon): left-to-right stagger, opacity 0 -> 1 + translateX 8px -> 0 + focus blur */}
        <div
          style={{
            position: 'absolute',
            left: `calc(50% + ${ROW_LEFT}px)`,
            top: '50%',
            height: ICON,
            marginTop: -ICON / 2,
            display: 'flex',
            alignItems: 'center',
            gap: 0,
          }}
        >
          {[...WORDMARK].map((ch, i) => {
            const lk = seg(t, 0.46 + i * STAGGER, 0.46 + i * STAGGER + 0.10, E.outCubic);
            return (
              <span
                key={i}
                style={{
                  color: '#f3f5fb',
                  font: `700 22px/1 ${BRAND.font}`,
                  letterSpacing: 0.66, // Wordmark +0.03em
                  whiteSpace: 'pre',
                  opacity: lk,
                  transform: `translateX(${lerp(lk, 8, 0)}px)`,
                  filter: lk < 0.999 ? `blur(${lerp(lk, 2.5, 0).toFixed(2)}px)` : undefined,
                  textShadow: '0 0 12px rgba(150,140,255,0.18)',
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
        {/* Accent motto: delayed full-line fade-in with 3px upward settle */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 'calc(50% + 34px)',
            textAlign: 'center',
            color: ACCENT,
            font: `600 12.5px/1 ${FONT.sans}`,
            letterSpacing: 2.6, // 29 chars: tracking 4.6 -> 2.6 to match lockup width
            opacity: seg(t, 0.72, 0.84, E.outQuad),
            transform: `translateY(${lerp(seg(t, 0.72, 0.86, E.outCubic), 3, 0)}px)`,
          }}
        >
          {PITCH.en.motto.toUpperCase()}
        </div>
      </div>
    </DesignStage>
    {/* Vignette and grain placed outside design coordinates at native 1920px so grain is not magnified into blocks by zoom */}
    <Vignette strength={0.55} inner={0.4} color="#000000" />
    <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
