// oscilloscope-stream-v2 — oscilloscope stream: curve write-head anchored on the right oscillating vertically while past data scrolls off to the left;
// midway burst spike (amplitude 2.2x, readout jumps larger and turns accent color), finally braking to true freeze.
//
// Second redesign pass (midnight dark blue / full-bleed oscilloscope monitoring wall):
// - look = midnight (deep blue night + electric blue), with coral red reserved exclusively for events (spikes only). No longer "a small chart in a card":
//   the entire frame is an oscilloscope screen — 1728x520 full-bleed plot area, graticule grid (major solid lines + minor dot matrix + center reticle),
//   electric blue phosphor trace (solid line + two-layer bloom), write-head at 86%: vertical scanline + glow dot + horizontal readout reference line.
// - Typography hierarchy: top-left video-shotcraft mark + wordmark overline (render farm · fps) + LIVE indicator, 168px live readout (sample-and-hold every 3 frames like a real instrument);
//   top-right p99 latency / error rate secondary readouts, jumping along with the spike.
// - Spike event: as write-head passes, trace turns coral red and thickens, large readout scales up + turns coral red, p99 jumps to 3 digits;
//   after writing, a "Burst" event badge + vertical drop-line pins to the peak and drifts leftward with the stream.
// - Braking: flow rate brakes with out-cubic (initial velocity matches flow rate, no velocity jump), LIVE -> PAUSED, write-head dot turns off;
//   camera then gently pushes in 3% aimed at the spike (clear focus and destination), followed by true freeze hold.
//
// Timeline (30fps, 165f total):
//   0–16    Screen lights up: graticule expands from center, trace already streaming (live broadcast feel, content present at frame 1), readout/overline float in
//   0–104   Constant flow 8px/f (sample window translation is mechanical semantic, intentionally constant speed)
//   46–68   Spike write-in (readout / secondary readouts jump with envelope); ~70f event tag pops up with overshoot
//   104–118 Braking 14f (out-cubic)
//   118–165 Hold 47f: camera gently pushes in 1 -> 1.03 toward the peak (smooth), all else frozen
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const OSCILLOSCOPE_STREAM_V2_DURATION = 165;

const L = LOOKS.midnight;
const TRACE = L.accent; // Electric blue
const HOT = '#ff6b5b'; // Event color: coral red (reserved for spike)

// Plot area
const PX = 96;
const PW = 1728;
const PY = 404;
const PH = 520;
const HEAD = Math.round(PW * 0.86); // Write-head position (plot area x)

const SPEED = 8;
const FREEZE0 = 104;
const FREEZE1 = 118;
const OFFSET = 1400; // World coordinate offset: window already contains complete history at frame 0

// Effective time (world x): constant speed, out-cubic braking during FREEZE; braking distance = SPEED*dur/3 (continuous initial speed)
const worldAt = (f: number) => {
  if (f <= FREEZE0) return OFFSET + f * SPEED;
  const brake = (SPEED * (FREEZE1 - FREEZE0)) / 3;
  return OFFSET + FREEZE0 * SPEED + brake * ramp(f, FREEZE0, FREEZE1 - FREEZE0, (x) => 1 - Math.pow(1 - x, 3));
};

// Spike: write-head passes worldX [S0, S0+SW] starting at f46; main peak is a sharp Gaussian pulse (+2.2x normal amplitude),
// flanked by minor precursor / aftershock peaks, with baseline jitter doubled within the spike segment
const S0 = OFFSET + 46 * SPEED;
const SW = 176;
const SC = S0 + SW * 0.5;
const gauss = (x: number, c: number, w: number) => Math.exp(-Math.pow((x - c) / w, 2));
const bump = (x: number) => 2.2 * gauss(x, SC, 26) + 0.45 * gauss(x, SC - 62, 18) + 0.6 * gauss(x, SC + 48, 20);
const burstK = (x: number) => Math.min(1, bump(x) / 2.2);
const wave = (x: number) =>
  0.34 * Math.sin(x * 0.019) + 0.27 * Math.sin(x * 0.047 + 1.7) + 0.18 * Math.sin(x * 0.011 + 4.2) + 0.11 * Math.sin(x * 0.083 + 2.3);
const inSpike = (x: number) => gauss(x, SC, SW * 0.45);
const signal = (x: number) => wave(x) * (1 + 0.6 * inSpike(x)) + bump(x);
const valueOf = (x: number) => 1350 + signal(x) * 560; // fps (rendered frames / second)
const MAXV = 3000;
const yOf = (x: number) => PH - (valueOf(x) / MAXV) * PH;

const PEAK_X = (() => {
  let best = S0;
  for (let x = S0; x <= S0 + SW; x += 0.5) if (signal(x) > signal(best)) best = x;
  return best;
})();

const fmt = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const hexMix = (a: string, b: string, t: number) => {
  const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const A = p(a);
  const B = p(b);
  return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
};

export const OscilloscopeStreamV2: React.FC = () => {
  const frame = useCurrentFrame();
  const T = worldAt(frame); // Writehead world x
  const worldOf = (px: number) => T - (HEAD - px);

  // Trace sampling (left of writehead)
  const STEP = 4;
  const pts: Array<[number, number, number]> = [];
  for (let px = 0; px <= HEAD; px += STEP) pts.push([px, yOf(worldOf(px)), worldOf(px)]);
  if (pts[pts.length - 1][0] !== HEAD) pts.push([HEAD, yOf(T), T]);
  const toD = (a: Array<[number, number, number]>) => a.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const lineD = toD(pts);
  const areaD = `${lineD} L${HEAD},${PH} L0,${PH} Z`;
  const spike = pts.filter(([, , w]) => w >= S0 + 10 && w <= Math.min(T, S0 + SW - 10));
  const spikeD = spike.length > 1 ? toD(spike) : '';
  const headY = yOf(T);
  const freshD = toD(pts.filter(([x]) => x >= HEAD - 284));

  // Readout: sample & hold every 3 frames; peak envelope drives scale + color
  const held = worldAt(Math.floor(frame / 3) * 3);
  // Readout heat: peak intensity within +-40px of writehead
  const spikeK = Math.max(burstK(T), 0.8 * burstK(T - 30), 0.5 * burstK(T - 60));
  const hot = EASE.out(Math.min(1, spikeK * 1.6));
  const readScale = 1 + 0.08 * spikeK;
  const p99 = Math.round(42 + 84 * spikeK + 2 * Math.sin(frame / 5));
  const errRate = (0.02 + 0.12 * spikeK).toFixed(2);

  const live = 1 - ramp(frame, FREEZE0, FREEZE1 - FREEZE0, EASE.out);
  const pulse = 0.5 + 0.5 * Math.cos((frame / 24) * Math.PI * 2);

  // Event tag: pops up as writehead passes peak, pinned to peak drifting left
  const peakPx = HEAD - (T - PEAK_X);
  const peakY = yOf(PEAK_X);
  const passF = (PEAK_X - OFFSET) / SPEED;
  const tagIn = ramp(frame, passF + 3, 14, EASE.overshoot);

  // Screen illumination
  const on = ramp(frame, 0, 16, EASE.snappy);
  const headIn = ramp(frame, 2, 16, EASE.out);

  // Gentle push toward peak after brake
  const push = ramp(frame, FREEZE1 - 4, 165 - FREEZE1 + 4, EASE.smooth);
  const cam = mix(1, 1.025, push);
  const camOX = PX + mix(HEAD, peakPx, 0.6);
  const camOY = PY + PH * 0.45;

  const gridV = 12;
  const gridH = 6;

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.62, y: 0.55 }} fill={{ x: 0.08, y: 0.1 }} intensity={0.8} breathe={0.4} />

      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam.toFixed(5)})`, transformOrigin: `${camOX}px ${camOY}px` }}>
        {/* Eyebrow + LIVE */}
        <div style={{ position: 'absolute', left: PX, top: 92, display: 'flex', alignItems: 'center', gap: 22, opacity: headIn }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <ShotcraftMark size={40} tone="dark" />
            <span style={{ ...type(32, 700), fontFamily: BRAND.font, letterSpacing: '0.03em', color: L.ink }}>{BRAND.name}</span>
          </span>
          <span style={{ ...type(32, 500, { caps: true }), color: L.ink3 }}>render-farm · prod · fps</span>
          <span style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '6px 16px 6px 12px', borderRadius: 99,
            background: live > 0.5 ? alpha(L.accent2, 0.12) : alpha('#ffffff', 0.06),
            border: `1px solid ${live > 0.5 ? alpha(L.accent2, 0.35) : alpha('#ffffff', 0.12)}`,
            ...type(26, 750, { caps: true }), color: live > 0.5 ? L.accent2 : L.ink3,
          }}>
            <span style={{
              width: 12, height: 12, borderRadius: 6, background: live > 0.5 ? L.accent2 : L.ink3,
              boxShadow: live > 0.5 ? `0 0 0 ${(3 + 5 * pulse).toFixed(1)}px ${alpha(L.accent2, 0.25 * (1 - pulse))}` : 'none',
            }} />
            {live > 0.5 ? 'Live' : 'Paused'}
          </span>
        </div>

        {/* Large readout */}
        <div style={{
          position: 'absolute', left: PX - 8, top: 140, display: 'flex', alignItems: 'baseline', gap: 22,
          transform: `scale(${readScale.toFixed(4)})`, transformOrigin: 'left bottom', opacity: headIn,
        }}>
          <span style={{
            ...type(176, 700), color: hexMix('#f2f5ff', HOT, hot),
            textShadow: hot > 0.02 ? `0 0 40px ${alpha(HOT, 0.35 * hot)}` : undefined,
          }}>{fmt(valueOf(held))}</span>
          <span style={{ ...type(48, 500), color: hexMix('#a9b4d0', HOT, hot) }}>fps</span>
        </div>

        {/* Top-right secondary readout */}
        <div style={{ position: 'absolute', right: 1920 - PX - PW, top: 150, display: 'flex', gap: 72, opacity: ramp(frame, 6, 14, EASE.out) }}>
          {[
            { k: 'p99 frame time', v: `${p99}`, u: 'ms', hotK: hot },
            { k: 'Failed jobs', v: errRate, u: '%', hotK: hot * 0.8 },
          ].map((s) => (
            <div key={s.k} style={{ textAlign: 'right' }}>
              <div style={{ ...type(32, 500), color: L.ink3 }}>{s.k}</div>
              <div style={{ marginTop: 8 }}>
                <span style={{ ...type(84, 650), color: hexMix('#f2f5ff', HOT, s.hotK) }}>{s.v}</span>
                <span style={{ ...type(36, 500), color: L.ink2, marginLeft: 8 }}>{s.u}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Oscilloscope screen */}
        <div style={{ position: 'absolute', left: PX, top: PY, width: PW, height: PH }}>
          <svg width={PW} height={PH + 80} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible' }}>
            <defs>
              <linearGradient id="osArea" x1="0" y1="0" x2="0" y2={PH} gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor={TRACE} stopOpacity={0.3} />
                <stop offset="1" stopColor={TRACE} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="osFade" x1="0" y1="0" x2={PW} y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#fff" stopOpacity={0} />
                <stop offset="0.14" stopColor="#fff" stopOpacity={1} />
                <stop offset="1" stopColor="#fff" stopOpacity={1} />
              </linearGradient>
              <mask id="osMask" maskUnits="userSpaceOnUse" x={-20} y={-200} width={PW + 40} height={PH + 300}>
                <rect x={-20} y={-200} width={PW + 40} height={PH + 300} fill="url(#osFade)" />
              </mask>
              <filter id="osGlowA" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="5" /></filter>
              <filter id="osGlowB" x="-10%" y="-40%" width="120%" height="180%"><feGaussianBlur stdDeviation="16" /></filter>
              <radialGradient id="osHead">
                <stop offset="0" stopColor="#ffffff" stopOpacity={1} />
                <stop offset="0.25" stopColor={hexMix('#5b8cff', HOT, hot)} stopOpacity={0.8} />
                <stop offset="1" stopColor={hexMix('#5b8cff', HOT, hot)} stopOpacity={0} />
              </radialGradient>
              <linearGradient id="osFresh" x1={HEAD - 280} y1="0" x2={HEAD} y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0" stopColor="#ffffff" stopOpacity={0} />
                <stop offset="1" stopColor="#ffffff" stopOpacity={0.95} />
              </linearGradient>
            </defs>

            {/* Grid: major lines + minor dot grid + center crosshair; expands from center */}
            <g opacity={on}>
              {Array.from({ length: gridV + 1 }, (_, i) => {
                const x = (i / gridV) * PW;
                const reach = (PH / 2) * on;
                return <line key={`v${i}`} x1={x} x2={x} y1={PH / 2 - reach} y2={PH / 2 + reach} stroke={L.accent} strokeOpacity={i === 0 || i === gridV ? 0.22 : 0.1} strokeWidth={1.2} />;
              })}
              {Array.from({ length: gridH + 1 }, (_, i) => {
                const y = (i / gridH) * PH;
                const reach = (PW / 2) * on;
                return <line key={`h${i}`} x1={PW / 2 - reach} x2={PW / 2 + reach} y1={y} y2={y} stroke={L.accent} strokeOpacity={i === 0 || i === gridH ? 0.22 : 0.1} strokeWidth={1.2} />;
              })}
              {Array.from({ length: gridV * 5 + 1 }, (_, i) => (
                <line key={`tk${i}`} x1={(i / (gridV * 5)) * PW} x2={(i / (gridV * 5)) * PW} y1={PH / 2 - (i % 5 ? 5 : 10)} y2={PH / 2 + (i % 5 ? 5 : 10)} stroke={L.accent} strokeOpacity={0.28} strokeWidth={1.2} />
              ))}
            </g>

            {/* Trace: area fill + two-layer glow + solid line (fades off left edge) */}
            <g mask="url(#osMask)">
              <path d={areaD} fill="url(#osArea)" />
              <path d={lineD} fill="none" stroke={TRACE} strokeWidth={10} opacity={0.5} filter="url(#osGlowB)" />
              <path d={lineD} fill="none" stroke={TRACE} strokeWidth={5} opacity={0.75} filter="url(#osGlowA)" />
              <path d={lineD} fill="none" stroke="#cfdcff" strokeWidth={3.5} strokeLinejoin="round" strokeLinecap="round" />
              {/* Newest 280px: bright phosphor fresh segment */}
              <path d={freshD} fill="none" stroke="url(#osFresh)" strokeWidth={4.5} strokeLinejoin="round" strokeLinecap="round" opacity={0.4 + 0.6 * live} />
              {spikeD && (
                <>
                  <path d={spikeD} fill="none" stroke={HOT} strokeWidth={14} opacity={0.55} filter="url(#osGlowB)" />
                  <path d={spikeD} fill="none" stroke={HOT} strokeWidth={5} strokeLinejoin="round" strokeLinecap="round" />
                </>
              )}
            </g>

            {/* Writehead: vertical scanline + horizontal reference + beam spot */}
            <line x1={HEAD} x2={HEAD} y1={0} y2={PH} stroke={hexMix('#5b8cff', HOT, hot)} strokeOpacity={0.45 * live + 0.12} strokeWidth={1.5} />
            <line x1={HEAD} x2={PW} y1={headY} y2={headY} stroke={hexMix('#cfdcff', HOT, hot)} strokeOpacity={0.4} strokeWidth={1.5} strokeDasharray="4 6" />
            <circle cx={HEAD} cy={headY} r={70} fill="url(#osHead)" opacity={0.55 * live} />
            <circle cx={HEAD} cy={headY} r={9} fill={hexMix('#ffffff', HOT, hot * 0.6)} stroke={L.bg[1]} strokeWidth={3} />

            {/* Event: peak marker + vertical drop line */}
            {tagIn > 0 && peakPx > 40 && (
              <g opacity={Math.min(1, tagIn * 1.5)}>
                <line x1={peakPx} x2={peakPx} y1={peakY + 14} y2={PH} stroke={HOT} strokeOpacity={0.5} strokeWidth={1.5} strokeDasharray="3 5" />
                <circle cx={peakPx} cy={peakY} r={9 * tagIn} fill={HOT} stroke={L.bg[1]} strokeWidth={3} />
              </g>
            )}

            {/* Timeline */}
            {['−50s', '−40s', '−30s', '−20s', '−10s', 'now'].map((t, i) => (
              <text key={t} x={(HEAD * (i + 1)) / 6} y={PH + 52} textAnchor="middle" fill={i === 5 ? L.ink2 : L.ink3}
                style={{ ...type(32, 500), fontFamily: FONT.sans }} opacity={headIn}>{t}</text>
            ))}
          </svg>

          {/* Y-axis ticks (in-screen top-left, atop grid lines) */}
          {['3k', '2k', '1k'].map((t, i) => (
            <div key={t} style={{ position: 'absolute', left: 14, top: (i * 2 * PH) / 6 + 8, ...type(28, 600), color: L.ink3, opacity: on }}>{t}</div>
          ))}

          {/* Event tag */}
          {tagIn > 0 && peakPx > 40 && (
            <div style={{
              position: 'absolute', left: peakPx + 22, top: peakY - 36, height: 72, padding: '0 26px 0 20px',
              display: 'flex', alignItems: 'center', gap: 14, borderRadius: 14, whiteSpace: 'nowrap',
              background: `linear-gradient(180deg, ${alpha(HOT, 0.22)}, ${alpha(HOT, 0.12)})`, border: `1px solid ${alpha(HOT, 0.55)}`,
              boxShadow: `0 16px 40px -10px ${alpha('#000000', 0.6)}`,
              transform: `scale(${tagIn.toFixed(4)})`, transformOrigin: '0% 50%', opacity: Math.min(1, tagIn * 1.5),
            }}>
              <span style={{ ...type(32, 800, { caps: true }), color: HOT }}>Burst</span>
              <span style={{ ...type(32, 600), color: '#ffe3de' }}>{fmt(valueOf(PEAK_X))} fps</span>
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
