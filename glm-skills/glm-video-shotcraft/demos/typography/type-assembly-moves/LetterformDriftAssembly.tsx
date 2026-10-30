// letterform-drift-assembly — Stranger Things title style letterform drift convergence.
// Brand name "Shotcraft" split into 9 chars: each drifting in from different directions (h(i) seeded vectors,
// +/-260-360px) with 8px blur + 0.35 opacity, staggered convergence
// (delay i*3f, 45f travel, Easing.out(cubic)). Each char receives a
// "deepen pulse" on lock: ink -> #000 -> ink + stroke 0 -> 3px -> 0 (8f) — on light background
// uses darkening pulse instead of glow. Unified word breathes scale 1 -> 1.04 -> 1 on assembly
// (amplified to 1.04).
// Keyframes: 0-24 staggered launch -> char i [i*3, i*3+45] drifts into place ->
// lock frame i*3+45 triggers 8f deepen pulse (last char 69-77) -> 80-104 word breathing ->
// 104-150 static hold (46f).
//
// Polish pass: soft lighting backdrop; system font stack 700, tinted near-black ink;
// drift bound to rotation (+/-24 deg -> 0) and depth scale (1.22 -> 1) along shared progress p,
// drifting in from camera space rather than 2D sliding; subtle ground shadow emerges below assembled word.
// Total duration 150f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, ramp } from '../../_fixtures/Polish';
import { BRAND } from '../../_fixtures/Brand';

export const LETTERFORM_DRIFT_ASSEMBLY_DURATION = 150;

const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

const WORD = BRAND.short; // 'Shotcraft' — title-style intro on brand name
const TRAVEL = 45; // Drift duration per character (frames)
const STAG = 3; // Stagger interval
const INK = [23, 24, 28]; // G.ink1 #17181c

export const LetterformDriftAssembly: React.FC = () => {
  const frame = useCurrentFrame();
  const chars = WORD.split('');
  const lastLock = (chars.length - 1) * STAG + TRAVEL; // 69

  // Unified word breathing: 80-92 scales to 1.04, 92-104 settles to 1
  const breath =
    frame < 92
      ? interpolate(frame, [80, 92], [1, 1.04], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.cubic),
        })
      : interpolate(frame, [92, 104], [1.04, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.cubic),
        });
  // Ground shadow after assembly
  const ground = ramp(frame, lastLock - 6, 30, EASE.out);

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden' }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.32 }} accent="#5b63d3" grain={0.05} vignette={0.14} />
      {/* Ground shadow: subtle elliptical shadow beneath assembled word */}
      <div
        style={{
          position: 'absolute',
          left: 960 - 520,
          top: 540 + 70,
          width: 1040,
          height: 70,
          borderRadius: '50%',
          background: 'radial-gradient(ellipse 50% 50% at 50% 50%, rgba(20,22,32,0.13), rgba(20,22,32,0) 70%)',
          opacity: ground,
          transform: `scale(${breath})`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transform: `scale(${breath})`,
        }}
      >
        {chars.map((c, i) => {
          const start = i * STAG;
          const lock = start + TRAVEL;
          // Drift progress (translation / blur / opacity / rotation / depth scale share progress p)
          const p = interpolate(frame, [start, lock], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
            easing: Easing.out(Easing.cubic),
          });
          // Seeded initial vector: angle h(i), magnitude 260-360px
          const ang = h(i + 1) * Math.PI * 2;
          const mag = 260 + h(i + 101) * 100;
          const dx = Math.cos(ang) * mag * (1 - p);
          const dy = Math.sin(ang) * mag * (1 - p);
          const rot = (h(i + 201) - 0.5) * 48 * (1 - p);
          const depth = 1 + 0.22 * (1 - p);
          const blur = 8 * (1 - p);
          const op = interpolate(p, [0, 1], [0.35, 1]);
          // Lock deepen pulse: lock -> lock+8, triangular pulse 0 -> 1 -> 0
          const pulse =
            frame <= lock || frame >= lock + 8
              ? 0
              : frame < lock + 4
                ? (frame - lock) / 4
                : (lock + 8 - frame) / 4;
          const color = `rgb(${INK.map((v) => Math.round(v * (1 - pulse))).join(',')})`;
          const strokeW = 3 * pulse;
          const settled = p >= 1 && pulse === 0;
          return (
            <span
              key={i}
              style={{
                fontFamily: FONT.sans,
                fontWeight: 700,
                fontSize: 148,
                letterSpacing: '0.02em',
                color: settled ? G.ink1 : color,
                display: 'inline-block',
                transform: settled
                  ? undefined
                  : `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) rotate(${rot.toFixed(2)}deg) scale(${depth.toFixed(4)})`,
                opacity: op,
                filter: blur > 0.01 ? `blur(${blur.toFixed(2)}px)` : undefined,
                WebkitTextStroke: strokeW > 0.01 ? `${strokeW.toFixed(2)}px #000` : undefined,
              }}
            >
              {c}
            </span>
          );
        })}
      </div>
    </div>
  );
};
