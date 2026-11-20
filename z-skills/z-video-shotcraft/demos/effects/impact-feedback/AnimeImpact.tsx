import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { FakeDashboard, Card, G } from '../../_fixtures/Fixtures';
import { EASE, Vignette, bezier, mix, ramp } from '../../_fixtures/Polish';

// anime-impact anime impact frames: crash-zoom halts abruptly on target card over 3 frames,
// inverting entire scene into high-contrast B&W negative + radial focus lines + +/-8px red/cyan chromatic aberration —
// kinetic impact frame, clearing on frame 4 to clean close-up + 6px decaying screen shake.
// Beats: 0-22 establish overview (slow creep 1->1.012, target card accent stroke locks) ->
//       22-28 anticipation pull-back to 0.985 -> 28-34 crash push (6f ease-in cubic to 2.25x,
//       time-sampled motion blur) -> 34-36 impact frames (3f negative/focus lines/RGB split, alternating forms) ->
//       37+ clean close-up + decaying shake + vignette pulse -> 50-120 static hold (>=2s).

export const ANIME_IMPACT_DURATION = 120;

const WIND = 22; // Anticipation pull-back start
const ZOOM_START = 28;
const ZOOM_END = 34; // Crash halt frame
const IMPACT_LEN = 3; // Impact frames duration 3f (34/35/36)
const RECOVER = ZOOM_END + IMPACT_LEN; // 37: Clean close-up recovery

// Target card: row 1, col 2 in 3x2 grid
const CARD = { x: 808, y: 108, w: 524, h: 454 };
const CX = CARD.x + CARD.w / 2; // 1070
const CY = CARD.y + CARD.h / 2; // 335
const SCALE_END = 2.25; // Target close-up scale
const ACCENT = G.accent;

const inCubic = bezier(0.55, 0.055, 0.675, 0.19); // ease-in cubic

// Seeded sinusoidal hash
const rnd = (i: number) => {
  const s = Math.sin(i * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

// Camera: overview creep -> anticipation pull-back -> ease-in push
const camAt = (f: number) => {
  const creep = mix(1, 1.012, ramp(f, 0, WIND, EASE.smooth));
  const wind = mix(creep, 0.985, ramp(f, WIND, ZOOM_START - WIND, EASE.smooth));
  const p = ramp(f, ZOOM_START, ZOOM_END - ZOOM_START, inCubic);
  const scale = f < ZOOM_START ? wind : mix(0.985, SCALE_END, p);
  return { scale, p };
};

const zoomStyle = (f: number): React.CSSProperties => {
  const { scale, p } = camAt(f);
  return {
    position: 'absolute',
    inset: 0,
    transform: `translate(${(960 - CX) * p}px, ${(540 - CY) * p}px) scale(${scale})`,
    transformOrigin: `${CX}px ${CY}px`,
  };
};

// Radial focus lines: 34 outer wedges + 22 needles leaving center clear; phase varies per frame
const SpeedLines: React.FC<{ phase: number }> = ({ phase }) => {
  const cx = 960;
  const cy = 540;
  const R_OUT = 1300; // Extends beyond diagonal (~1101)
  const wedge = (i: number, n: number, k: number, r0Min: number, r0Var: number, wMin: number, wVar: number) => {
    const ang = ((i + 0.5) / n) * Math.PI * 2 + (rnd(k) - 0.5) * 0.24;
    const r0 = r0Min + rnd(k + 1) * r0Var; // Staggered inner endpoints
    const halfW = (wMin + rnd(k + 2) * wVar) / R_OUT; // Outer wedge width
    const ax = cx + Math.cos(ang) * r0 * 1.18; // Horizontally stretched for card aspect ratio
    const ay = cy + Math.sin(ang) * r0;
    const p1 = `${cx + Math.cos(ang - halfW) * R_OUT},${cy + Math.sin(ang - halfW) * R_OUT}`;
    const p2 = `${cx + Math.cos(ang + halfW) * R_OUT},${cy + Math.sin(ang + halfW) * R_OUT}`;
    return `${ax},${ay} ${p1} ${p2}`;
  };
  const thick = Array.from({ length: 34 }, (_, i) => wedge(i, 34, i * 13 + phase * 101, 330, 230, 9, 22));
  const thin = Array.from({ length: 22 }, (_, i) => wedge(i + 0.37, 22, i * 29 + phase * 57 + 7, 420, 260, 2, 4));
  return (
    <svg viewBox="0 0 1920 1080" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
      <defs>
        {/* Soft inner margin: radial fade on inner focus line tips */}
        <radialGradient id="ai-lines-fade" cx="960" cy="540" r="700" gradientUnits="userSpaceOnUse">
          <stop offset="0.38" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.6" stopColor="#fff" stopOpacity="1" />
        </radialGradient>
        <mask id="ai-lines-mask">
          <rect width="1920" height="1080" fill="url(#ai-lines-fade)" />
        </mask>
      </defs>
      <g mask="url(#ai-lines-mask)">
        {thick.map((pts, i) => (
          <polygon key={`a${i}`} points={pts} fill={i % 5 === 0 ? '#0d0e12' : '#f4f2ee'} />
        ))}
        {thin.map((pts, i) => (
          <polygon key={`b${i}`} points={pts} fill="#f4f2ee" opacity={0.85} />
        ))}
      </g>
    </svg>
  );
};

// Target card overlay + overview base; lock = accent stroke progress (0-1)
const Scene: React.FC<{ lock: number }> = ({ lock }) => (
  <>
    <FakeDashboard variant="A" />
    <div style={{ position: 'absolute', left: CARD.x, top: CARD.y }}>
      <Card
        w={CARD.w}
        h={CARD.h}
        seed={9}
        style={{
          boxShadow:
            `0 0 0 ${(1.5 * lock).toFixed(2)}px ${ACCENT}, 0 0 0 ${(6 * lock).toFixed(2)}px rgba(91,99,211,${(0.14 * lock).toFixed(3)}), ` +
            `inset 0 1px 0 rgba(255,255,255,0.9), 0 2px 4px rgba(16,18,24,0.06), 0 ${mix(6, 22, lock)}px ${mix(18, 48, lock)}px -10px rgba(16,18,24,${mix(0.1, 0.22, lock).toFixed(3)})`,
        }}
      />
    </div>
  </>
);

// Time-sampled motion blur: N subframes blended over 0.6f shutter window,
// smoothing subframe steps with gaussian blur during 28-33 flight frames; halt frame is crisp
const SHUTTER = 0.6;
const blurAt = (f: number) => {
  if (f <= ZOOM_START || f >= ZOOM_END) return { n: 1, sd: 0 };
  const a = camAt(f), b = camAt(f - SHUTTER);
  const edge = Math.abs(a.scale - b.scale) * 900 + Math.abs(a.p - b.p) * 160; // Edge displacement px
  const n = Math.max(1, Math.min(12, Math.ceil(edge / 10)));
  return { n, sd: n > 1 ? Math.min(6, (edge / (n - 1)) * 0.45) : 0 };
};

// Sharp center mask tracking card screen position
const sharpMask = (f: number) => {
  const { p } = camAt(f);
  const x = ((CX + (960 - CX) * p) / 1920) * 100;
  const y = ((CY + (540 - CY) * p) / 1080) * 100;
  return `radial-gradient(ellipse 30% 34% at ${x.toFixed(1)}% ${y.toFixed(1)}%, #000 0%, rgba(0,0,0,0.85) 45%, transparent 100%)`;
};

export const AnimeImpact: React.FC = () => {
  const frame = useCurrentFrame();

  const lock = ramp(frame, 6, 14, EASE.out); // Target stroke lights up establishing focal intent
  const impact = frame >= ZOOM_END && frame < RECOVER;
  const phase = impact ? frame - ZOOM_END : 0; // Varies focus line morphology per frame

  // Screen shake: 6px decaying over tau ~ 2.2f with crisp alternating signs
  const since = frame - RECOVER;
  const env = since >= 0 ? 6 * Math.exp(-since / 2.2) : 0;
  const live = env > 0.12;
  const shakeX = live ? env * 0.7 * Math.sin(since * 2.5 + 0.6) : 0;
  const shakeY = live ? env * Math.cos(since * 2.9) : 0;
  const shakeR = live ? env * 0.04 * Math.sin(since * 3.3 + 1.7) : 0;

  // Impact weight: heavy vignette pulse; background dims to pop close-up
  const hitK = frame >= RECOVER ? 1 - ramp(frame, RECOVER, 22, EASE.out) : 0;
  const vig = frame >= RECOVER ? mix(0.16, 0.42, hitK) : 0.12;

  const { n, sd } = blurAt(frame);

  return (
    <AbsoluteFill style={{ background: impact ? '#0d0e12' : G.bg, overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `translate(${shakeX.toFixed(2)}px, ${shakeY.toFixed(2)}px) rotate(${shakeR.toFixed(3)}deg)`,
        }}
      >
        {/* Main layer: high-contrast negative during impact; time-sampled blur during zoom */} 
        <div style={{ position: 'absolute', inset: 0, filter: impact ? 'invert(1) grayscale(1) contrast(1.45)' : 'none' }}>
          {Array.from({ length: n }, (_, k) => (
            <div
              key={k}
              style={{
                ...zoomStyle(frame - (SHUTTER * k) / Math.max(1, n - 1)),
                opacity: k === 0 ? 1 : 1 / (k + 1),
                filter: sd > 0.3 ? `blur(${sd.toFixed(2)}px)` : undefined,
              }}
            >
              <Scene lock={lock} />
            </div>
          ))}
          {/* Radial zoom blur: sharp center copy layered over blurred periphery */} 
          {n > 1 && (
            <div
              style={{
                position: 'absolute', inset: 0,
                WebkitMaskImage: sharpMask(frame),
                maskImage: sharpMask(frame),
              }}
            >
              <div style={zoomStyle(frame)}>
                <Scene lock={lock} />
              </div>
            </div>
          )}
        </div>
        {/* RGB split: red/cyan negative layers offset +/-8px with screen blend */} 
        {impact && (
          <>
            {[
              { dx: -8, dy: phase % 2 === 0 ? 4 : -4, tint: '#ff2a4a' },
              { dx: 8, dy: phase % 2 === 0 ? -4 : 4, tint: '#16e0ff' },
            ].map((c, i) => (
              <div
                key={i}
                style={{ position: 'absolute', inset: 0, mixBlendMode: 'screen', transform: `translate(${c.dx}px, ${c.dy}px)`, isolation: 'isolate' }}
              >
                <div style={{ ...zoomStyle(frame), filter: 'invert(1) grayscale(1) contrast(1.45)' }}>
                  <Scene lock={lock} />
                </div>
                <div style={{ position: 'absolute', inset: 0, background: c.tint, mixBlendMode: 'multiply' }} />
              </div>
            ))}
            {/* Radial focus lines alternating per frame */} 
            <SpeedLines phase={phase} />
          </>
        )}
        {/* Recovery: background dimming around target card */} 
        {frame >= RECOVER && (
          <div style={zoomStyle(frame)}>
            <div
              style={{
                position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: 14,
                boxShadow: `0 0 0 3000px rgba(14,15,20,${mix(0.1, 0.22, hitK).toFixed(3)})`,
              }}
            />
          </div>
        )}
      </div>
      {!impact && <Vignette strength={vig} inner={0.5} color="#0b0c12" />}
    </AbsoluteFill>
  );
};
