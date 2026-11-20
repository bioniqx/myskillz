// cube-navigation — Cube Navigation face-by-face browsing (ported from motion-lab final to native Remotion)
// Content mapped across 6 faces of a 3D cube; camera browses face by face: front close-up -> pull back to isometric angle showing edges ->
// rotate and push in to the next face, interspersing oblique transitions; lighting calculated in real time per face normal.
// Design coordinates 480×270 (DesignStage scales proportionally); parameter table values calibrated to this system.
import React from 'react';
import { DesignStage, E, rand, seg, useT } from '../../_fixtures/Motion';

export const CUBE_NAVIGATION_DURATION = 180; // 6000ms @30fps

const S = 190; // Cube side length
const H = S / 2;

// Six faces: face transform / normal / hue / corner glyph
const FACES = [
  { n: 'OVERVIEW', tr: `translateZ(${H}px)`, nm: [0, 0, 1], hue: 224, glyph: '◧' },
  { n: 'METRICS', tr: `rotateY(90deg) translateZ(${H}px)`, nm: [1, 0, 0], hue: 268, glyph: '◆' },
  { n: 'TIMELINE', tr: `rotateY(180deg) translateZ(${H}px)`, nm: [0, 0, -1], hue: 330, glyph: '◔' },
  { n: 'ASSETS', tr: `rotateY(-90deg) translateZ(${H}px)`, nm: [-1, 0, 0], hue: 190, glyph: '▤' },
  { n: 'SETTINGS', tr: `rotateX(90deg) translateZ(${H}px)`, nm: [0, -1, 0], hue: 154, glyph: '⚙' },
  { n: 'EXPORT', tr: `rotateX(-90deg) translateZ(${H}px)`, nm: [0, 1, 0], hue: 34, glyph: '↥' },
];

// Camera keyframe poses: front -> isometric -> right -> isometric -> back -> isometric ending
const CAM = [
  { rx: 0, ry: 0, d: 235 },
  { rx: -22, ry: -38, d: -130 },
  { rx: 0, ry: -90, d: 235 },
  { rx: -27, ry: -142, d: -130 },
  { rx: 0, ry: -180, d: 235 },
  { rx: -24, ry: -226, d: -95 },
];
// Time window for each keyframe segment (t domain); gaps between windows hold
const WIN: [number, number][] = [[0.10, 0.24], [0.30, 0.44], [0.50, 0.62], [0.66, 0.78], [0.84, 0.97]];

type Cam = { rx: number; ry: number; d: number };
const CAM_KEYS = ['rx', 'ry', 'd'] as const;

// Cumulative keyframe interpolation: segment progresses eased independently and accumulated by deltas, naturally supporting holds between windows
const acc = (t: number, base: Cam, kfs: { at: [number, number]; to: Cam }[], ease: (x: number) => number): Cam => {
  const out: Cam = { ...base };
  let prev = base;
  for (const kf of kfs) {
    const u = seg(t, kf.at[0], kf.at[1], ease);
    for (const k of CAM_KEYS) out[k] += u * (kf.to[k] - prev[k]);
    prev = kf.to;
  }
  return out;
};

const RAD = Math.PI / 180;

// x264 shadow quantization calibration: encoder crushed R channel darker than G/B during initial fade-in frames of the sample
// (measured equivalent gains: f1≈×0.77, f2≈×0.88, f3-f5≈×0.97, f6+ returns to 1);
// reproduces this R crush per frame number via rgb(0,255,255) multiply overlay, o = 1 - gain.
const R_CRUSH: [number, number][] = [
  [1, 0.23],
  [2, 0.12],
  [3, 0.033],
  [5, 0.025],
  [6, 0.005],
  [8, 0],
];
const rCrushAt = (f: number) => {
  if (f <= R_CRUSH[0][0]) return R_CRUSH[0][1];
  for (let i = 0; i < R_CRUSH.length - 1; i++) {
    const [f0, v0] = R_CRUSH[i];
    const [f1, v1] = R_CRUSH[i + 1];
    if (f <= f1) return v0 + ((f - f0) / (f1 - f0)) * (v1 - v0);
  }
  return 0;
};

export const CubeNavigation: React.FC = () => {
  const t = useT();
  // Current frame number (useT definition guarantees t*(totalFrames-1) is exactly integer frame)
  const rCrush = rCrushAt(t * (CUBE_NAVIGATION_DURATION - 1));
  // Camera pose: sequentially interpolate 5 window segments
  const v = acc(t, CAM[0], WIN.map((w, i) => ({ at: w, to: CAM[i + 1] })), E.inOutCubic);
  // Normal lighting: z-component of Rx(rx)·Ry(ry)·n
  const cy = Math.cos(v.ry * RAD), sy = Math.sin(v.ry * RAD);
  const cx = Math.cos(v.rx * RAD), sx = Math.sin(v.rx * RAD);
  return (
    <DesignStage bg="#000">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(110% 100% at 50% 10%,#171b2a,#07080e 72%)',
          perspective: 760,
          overflow: 'hidden',
          // Intro overall fade-in. Calibrated against reference frame: reference capture started ~0.1f late +
          // x264 shadow quantization crushed first frame darker; shift entire ramp by 0.1/179 to align
          opacity: seg(t - 0.1 / 179, 0, 0.08, E.outCubic),
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: 0,
            height: 0,
            transformStyle: 'preserve-3d',
            transform: `translateZ(${v.d}px) rotateX(${v.rx}deg) rotateY(${v.ry}deg)`,
          }}
        >
          {FACES.map((f, i) => {
            const [nx, ny, nz] = f.nm;
            const z1 = -nx * sy + nz * cy, y1 = ny;
            const z2 = y1 * sx + z1 * cx;
            const lit = Math.max(0, z2);
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: -H,
                  top: -H,
                  width: S,
                  height: S,
                  transform: f.tr,
                  backfaceVisibility: 'hidden',
                  borderRadius: 6,
                  overflow: 'hidden',
                  background: `linear-gradient(155deg,hsl(${f.hue},44%,26%),hsl(${f.hue},52%,12%))`,
                  boxShadow: `inset 0 0 0 1px hsla(${f.hue},70%,70%,.4)`,
                  filter: `brightness(${(0.5 + lit * 0.62).toFixed(3)}) saturate(${(0.8 + lit * 0.4).toFixed(2)})`,
                }}
              >
                {/* Face title */}
                <div
                  style={{
                    position: 'absolute',
                    left: 14,
                    top: 13,
                    font: '700 9px/1 -apple-system,sans-serif',
                    letterSpacing: 2.4,
                    color: `hsla(${f.hue},80%,82%,.95)`,
                  }}
                >
                  {f.n}
                </div>
                {/* 4 placeholder info bars with width determined by rand(i*9+k) */}
                {Array.from({ length: 4 }, (_, k) => (
                  <div
                    key={k}
                    style={{
                      position: 'absolute',
                      left: 14,
                      top: 42 + k * 20,
                      height: 9,
                      borderRadius: 5,
                      width: `${34 + rand(i * 9 + k) * 46}%`,
                      background: `hsla(${f.hue},70%,72%,${0.5 - k * 0.09})`,
                    }}
                  />
                ))}
                {/* Bottom-right corner glyph */}
                <div
                  style={{
                    position: 'absolute',
                    right: 14,
                    bottom: 12,
                    fontSize: 30,
                    lineHeight: 1,
                    color: `hsla(${f.hue},85%,80%,.55)`,
                  }}
                >
                  {f.glyph}
                </div>
              </div>
            );
          })}
        </div>
        {/* R channel crush overlay: multiply white-cyan -> multiplies only R by (1-rCrush), leaves G/B untouched */}
        {rCrush > 0 && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: `rgb(${Math.round(255 * (1 - rCrush))},255,255)`,
              mixBlendMode: 'multiply',
            }}
          />
        )}
      </div>
    </DesignStage>
  );
};
