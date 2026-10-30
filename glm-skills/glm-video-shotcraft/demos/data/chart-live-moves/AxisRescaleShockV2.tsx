// axis-rescale-shock-v2 — axis rescale blowout shock: line climbs normally, new value bursts through the top into the title zone,
// pauses for half a beat, and the y-axis dramatically rescales (old ticks fly out / new ticks slide in / grid densifies / old line compresses toward baseline), new value settles + true value badge pops up.
//
// Second redesign pass (sand Swiss poster / monthly render report):
// - look = sand (beige paper + jet black + terracotta). Instead of "a small chart inside a card", the entire screen is a Swiss-grid financial poster:
//   top-left 120px bold headline "Monthly renders", top-right matching FY total KPI, beneath which sits a full-bleed chart (1540x540 plot area),
//   3px ink baseline + 3px "ceiling" rule line + hairline grid, historical area styled with 45° cross-hatch lines (print feel), month/tick labels 32px.
// - The highlight is the terracotta blowout segment: Dec value launches from Nov, accelerating up to rupture the ceiling rule line (line cracks at impact point, scattering debris),
//   surging directly into the top-right KPI number (shaking the KPI), hovering for half a beat with a soft glow — literally "overflowing the container".
// - Rescale: over 14f old ticks 25k–100k fly out downward, new ticks 100k–400k slide in from top, grid expands from 4 to 8 lines left-to-right,
//   historical polyline and hatched area flatten toward the baseline; blowout point settles to 340k, popping terracotta true value tag, KPI rolls to 833k.
// - Brand pass: overline updated with video-shotcraft mark + wordmark, content updated from revenue to render volume (values and layout preserved).
//
// Timeline (30fps, 168f total):
//   0–20    Rule lines draw in from left, headline words rise, ticks/months fade in (paper and rule start visible at frame 1)
//   14–56   Historical Jan->Nov drawn (42f, asymmetric in-out), pen tip carries ink dot
//   50–62   Warning: ceiling rule line and 100k tick turn terracotta, Nov dot pulses once (anticipation)
//   62–76   Blowout 14f: accelerating surge (ease-in dominant) pierces rule line (~69f rupture: fracture + debris + 10px chart shake) -> strikes KPI
//   76–94   Hover 18f: glowing tip + soft bloom, KPI damped rebound after impact
//   94–108  Rescale 14f (expo-out): ticks swap, grid densifies, old line flattens, endpoint settles back
//   106–126 Endpoint marker settles with overshoot + true value tag pops up; KPI rolls 493k -> 833k
//   126–168 Hold 42f: subtle camera push-in only (1 -> 1.018)
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, bezier, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const AXIS_RESCALE_SHOCK_V2_DURATION = 168;

const L = LOOKS.sand;
const ACC = L.accent; // Terracotta: reserved for blowout segment / events
const INK = L.ink;

// Layout grid
const M = 96;
const X0 = 268; // Plot area left
const X1 = 1800; // Plot area right (Dec)
const PW = X1 - X0;
const CEIL = 362; // Ceiling rule line
const BASE = 902; // Baseline
const PH = BASE - CEIL;
const SHOCK_TOP = CEIL - 226; // Bursts 226px past ceiling, penetrating headline row

const DATA = [22, 30, 26, 38, 35, 47, 44, 58, 55, 66, 72, 340];
const N = DATA.length;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const DRAW0 = 14;
const DRAW1 = 56;
const WARN = 50;
const SHOCK0 = 62;
const SHOCK1 = 76;
const BEAT = 94;
const RESCALE1 = 108;
const MARK = 106;

// Shock burst: slow start, accelerating surge, slight overshoot at peak
const easeShock = bezier(0.7, 0, 0.36, 1.06);

const xOf = (i: number) => X0 + (i / (N - 1)) * PW;

export const AxisRescaleShockV2: React.FC = () => {
  const frame = useCurrentFrame();

  const rescaleP = ramp(frame, BEAT, RESCALE1 - BEAT, EASE.snappy);
  const range = mix(100, 400, rescaleP);
  const yOf = (v: number) => BASE - (v / range) * PH;

  // Historical segment draw-in
  const drawT = ramp(frame, DRAW0, DRAW1 - DRAW0, EASE.swift) * (N - 2);
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= Math.floor(drawT); i++) pts.push([xOf(i), yOf(DATA[i])]);
  if (drawT < N - 2 && drawT > Math.floor(drawT)) {
    const i = Math.floor(drawT);
    const f = drawT - i;
    pts.push([mix(xOf(i), xOf(i + 1), f), mix(yOf(DATA[i]), yOf(DATA[i + 1]), f)]);
  }
  const lineD = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');

  // Blowout segment
  const shockT = ramp(frame, SHOCK0, SHOCK1 - SHOCK0, easeShock);
  const nx = xOf(N - 2);
  const ny = yOf(DATA[N - 2]);
  const topY = mix(SHOCK_TOP, yOf(DATA[N - 1]), rescaleP);
  const hx = mix(nx, X1, Math.min(1, shockT));
  const hy = mix(ny, topY, shockT);
  const shockOn = frame >= SHOCK0;

  // Area fill (including blowout segment)
  const all: Array<[number, number]> = shockOn ? [...pts, [hx, hy]] : pts;
  const areaD = all.length > 1
    ? `M${all[0][0]},${BASE} ` + all.map(([x, y]) => `L${x.toFixed(2)},${y.toFixed(2)}`).join(' ') + ` L${all[all.length - 1][0].toFixed(2)},${BASE} Z`
    : '';

  // Ceiling penetration: intersection of segment with y=CEIL
  const crossX = nx + ((ny - CEIL) / (ny - SHOCK_TOP)) * (X1 - nx);
  const pierced = shockOn && hy <= CEIL + 0.5 && rescaleP < 0.02;
  // Rupture frame (precomputed once): frame where shockT drives hy across CEIL
  let PIERCE = SHOCK1;
  for (let f = SHOCK0; f <= SHOCK1; f += 0.25) {
    if (mix(ny, SHOCK_TOP, ramp(f, SHOCK0, SHOCK1 - SHOCK0, easeShock)) <= CEIL) { PIERCE = f; break; }
  }
  const sinceP = frame - PIERCE;
  const crack = sinceP >= 0 ? ramp(frame, PIERCE, 8, EASE.snappy) * (1 - ramp(frame, BEAT, 14, EASE.smooth)) : 0;

  // Chart shake: damped sine wave, 12f starting at rupture frame
  const kick = sinceP >= 0 && sinceP < 14 ? 10 * Math.exp(-sinceP / 3.4) * Math.sin(sinceP * 1.8) : 0;
  // KPI impact: jolts upward upon peak impact (SHOCK1)
  const sinceTop = frame - (SHOCK1 - 2);
  const kpiKick = sinceTop >= 0 && sinceTop < 16 ? -14 * Math.exp(-sinceTop / 3.8) * Math.cos(sinceTop * 1.5) : 0;

  const warn = ramp(frame, WARN, 10, EASE.out) * (1 - ramp(frame, BEAT, 12, EASE.out));
  const hang = shockOn ? ramp(frame, SHOCK1 - 4, 8, EASE.out) * (1 - ramp(frame, BEAT, 14, EASE.out)) : 0;
  const shockW = mix(12, 7, ramp(frame, BEAT, 16, EASE.out));

  const markS = ramp(frame, MARK, 12, EASE.overshoot);
  const ripple = ramp(frame, MARK + 2, 20, EASE.out);
  const valS = ramp(frame, MARK + 4, 14, EASE.overshoot);
  const totalP = ramp(frame, MARK + 2, 20, EASE.snappy);

  const rule = (d: number) => ramp(frame, d, 20, EASE.snappy);
  const cam = mix(1, 1.018, ramp(frame, 0, AXIS_RESCALE_SHOCK_V2_DURATION, EASE.smooth));

  const OLD = ['25k', '50k', '75k', '100k'];
  const NEW = ['100k', '200k', '300k', '400k'];
  const tickY = (i: number) => BASE - ((i + 1) / 4) * PH;

  // Debris (line fragments ejected from penetration point)
  const shard = (k: number) => {
    if (sinceP < 0 || sinceP > 32) return null;
    const t = sinceP / 32;
    const dir = k % 2 === 0 ? -1 : 1;
    const sp = [1, 0.75, 0.55][k];
    const x = crossX + dir * (18 + 190 * sp * EASE.out(t));
    const y = CEIL - (170 - k * 40) * EASE.out(t) + 300 * t * t;
    const w = [40, 30, 18][k];
    return (
      <rect key={k} x={x - w / 2} y={y - 2} width={w} height={4} fill={ACC} opacity={1 - EASE.exit(t)}
        transform={`rotate(${dir * (240 - k * 50) * t} ${x} ${y})`} />
    );
  };

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.0 }} fill={{ x: 0.95, y: 0.95 }} />

      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam})`, transformOrigin: '60% 45%' }}>
        {/* Headline row */}
        <div style={{ position: 'absolute', left: M, top: 92, display: 'flex', alignItems: 'center', gap: 12, ...type(32, 650, { caps: true }), color: L.ink2, opacity: ramp(frame, 0, 12, EASE.out) }}>
          <ShotcraftMark size={38} tone="light" style={{ marginTop: -2 }} />
          <span style={{ fontFamily: BRAND.font, fontWeight: 700, textTransform: 'none', letterSpacing: '0.03em', color: INK }}>{BRAND.name}</span>
          <span><span style={{ color: L.ink3 }}>·</span> Renders <span style={{ color: L.ink3 }}>· FY2026</span></span>
        </div>
        <div style={{ position: 'absolute', left: M - 6, top: 140, ...type(124, 850), color: INK }}>
          <TextReveal text="Monthly renders" by="word" variant="rise" start={2} each={18} gap={5} />
        </div>

        {/* Top-right KPI: blowout segment surges into here */}
        <div style={{ position: 'absolute', right: 1920 - 1824, top: 92, textAlign: 'right', opacity: ramp(frame, 6, 14, EASE.out) }}>
          <div style={{ ...type(32, 650, { caps: true }), color: totalP > 0.5 ? ACC : L.ink2 }}>FY total</div>
        </div>
        <div style={{
          position: 'absolute', right: 1920 - 1824, top: 140, ...type(124, 850), textAlign: 'right',
          color: totalP > 0.5 ? ACC : INK, transform: `translateY(${kpiKick.toFixed(2)}px)`, opacity: ramp(frame, 8, 14, EASE.out),
        }}>
          {Math.round(mix(493, 833, totalP))}k
        </div>

        {/* Chart group (shake effect applies only here) */}
        <div style={{ position: 'absolute', inset: 0, transform: `translateY(${kick.toFixed(2)}px)` }}>
          {/* Ticks */}
          <div style={{ position: 'absolute', left: M, top: BASE - 48, width: 200, ...type(32, 500), color: L.ink2, opacity: rule(4) }}>0</div>
          {OLD.map((v, i) => {
            const sw = ramp(frame, BEAT + (3 - i) * 2, 12, EASE.snappy);
            const top = i === 3;
            return (
              <div key={i} style={{ position: 'absolute', left: M, top: tickY(i) - 48, width: 200, height: 40, opacity: rule(4 + i * 2) }}>
                <div style={{
                  position: 'absolute', inset: 0, ...type(32, top ? mix(500, 750, warn) : 500),
                  color: top && warn > 0.02 ? ACC : L.ink2, opacity: 1 - sw, transform: `translateY(${(sw * 46).toFixed(2)}px)`,
                  filter: sw > 0.02 && sw < 0.98 ? `blur(${(Math.sin(Math.PI * sw) * 3).toFixed(2)}px)` : undefined,
                }}>{v}</div>
                <div style={{
                  position: 'absolute', inset: 0, ...type(32, 500), color: L.ink2,
                  opacity: sw, transform: `translateY(${((sw - 1) * 46).toFixed(2)}px)`,
                  filter: sw > 0.02 && sw < 0.98 ? `blur(${(Math.sin(Math.PI * sw) * 3).toFixed(2)}px)` : undefined,
                }}>{NEW[i]}</div>
              </div>
            );
          })}

          {/* Months */}
          {MONTHS.map((m, i) => (
            <div key={m} style={{
              position: 'absolute', left: xOf(i) - 50, top: BASE + 22, width: 100, textAlign: 'center',
              ...type(32, i === N - 1 && shockOn ? 750 : 500), color: i === N - 1 && shockOn ? ACC : L.ink2,
              opacity: ramp(frame, 6 + i, 12, EASE.out),
            }}>{m}</div>
          ))}

          <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
            <defs>
              <pattern id="arsHatch" width={12} height={12} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1={0} y1={0} x2={0} y2={12} stroke={INK} strokeOpacity={0.16} strokeWidth={2} />
              </pattern>
              <filter id="arsGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="10" />
              </filter>
            </defs>

            {/* Grid: 3 base lines + 4 densified lines during rescale */}
            {[0, 1, 2].map((i) => (
              <line key={`g${i}`} x1={M} x2={mix(M, 1824, rule(2 + i * 2))} y1={tickY(i)} y2={tickY(i)} stroke={INK} strokeOpacity={0.14} strokeWidth={1.5} />
            ))}
            {[0, 1, 2, 3].map((k) => {
              const d = ramp(frame, BEAT + 1 + k * 2, 12, EASE.snappy);
              const y = BASE - ((2 * k + 1) / 8) * PH;
              return d > 0 ? <line key={`d${k}`} x1={M} x2={mix(M, 1824, d)} y1={y} y2={y} stroke={INK} strokeOpacity={0.08} strokeWidth={1.5} strokeDasharray="2 8" /> : null;
            })}

            {/* Area fill: 45° hatching */}
            {areaD && <path d={areaD} fill="url(#arsHatch)" />}

            {/* Baseline */}
            <line x1={M} x2={mix(M, 1824, rule(0))} y1={BASE} y2={BASE} stroke={INK} strokeWidth={3} />

            {/* Ceiling rule line: turns terracotta on warning, fractures where penetrated */}
            {(() => {
              const c = warn > 0.02 ? ACC : INK;
              const xr = mix(M, 1824, rule(2));
              const gap = 26 * crack;
              const op = 0.85 + 0.15 * warn;
              if (crack <= 0.001) return <line x1={M} x2={xr} y1={CEIL} y2={CEIL} stroke={c} strokeOpacity={op} strokeWidth={3} />;
              return (
                <>
                  <line x1={M} x2={crossX - gap} y1={CEIL} y2={CEIL} stroke={c} strokeOpacity={op} strokeWidth={3} />
                  <line x1={crossX + gap} x2={xr} y1={CEIL} y2={CEIL} stroke={c} strokeOpacity={op} strokeWidth={3} />
                </>
              );
            })()}
            {shard(0)}
            {shard(1)}
            {shard(2)}

            {/* Historical polyline */}
            {lineD && <path d={lineD} fill="none" stroke={INK} strokeWidth={6} strokeLinejoin="round" strokeLinecap="round" />}
            {/* Historical data points */}
            {pts.map(([x, y], i) => (i < pts.length - (drawT < N - 2 ? 1 : 0) ? <circle key={i} cx={x} cy={y} r={6} fill={L.bg[0]} stroke={INK} strokeWidth={3.5} /> : null))}
            {/* Drawing pen tip */}
            {frame >= DRAW0 && frame < DRAW1 + 1 && pts.length > 0 && (
              <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={9} fill={INK} />
            )}
            {/* Warning pulse: Nov point */}
            {frame >= WARN && frame < SHOCK0 + 6 && (() => {
              const t = ramp(frame, WARN, 16, EASE.out);
              return <circle cx={nx} cy={ny} r={mix(10, 46, t)} fill="none" stroke={ACC} strokeWidth={3} opacity={0.7 * (1 - t)} />;
            })()}

            {/* Blowout segment */}
            {shockOn && (
              <>
                {hang > 0.01 && <line x1={nx} y1={ny} x2={hx} y2={hy} stroke={ACC} strokeWidth={shockW + 16} strokeLinecap="round" opacity={0.35 * hang} filter="url(#arsGlow)" />}
                <line x1={nx} y1={ny} x2={hx} y2={hy} stroke={ACC} strokeWidth={shockW} strokeLinecap="round" />
                {markS <= 0 && <circle cx={hx} cy={hy} r={12} fill={L.bg[0]} stroke={ACC} strokeWidth={5} />}
              </>
            )}
            {pierced && sinceP < 10 && (
              <circle cx={crossX} cy={CEIL} r={mix(8, 70, ramp(frame, PIERCE, 10, EASE.out))} fill="none" stroke={ACC} strokeWidth={2.5}
                opacity={0.8 * (1 - ramp(frame, PIERCE, 10, EASE.out))} />
            )}

            {/* Endpoint marker */}
            {markS > 0 && (
              <>
                {ripple < 1 && <circle cx={hx} cy={hy} r={mix(16, 64, ripple)} fill="none" stroke={ACC} strokeWidth={3} opacity={0.6 * (1 - ripple)} />}
                <circle cx={hx} cy={hy} r={15 * markS} fill={ACC} stroke={L.bg[0]} strokeWidth={5 * markS} />
              </>
            )}
          </svg>

          {/* True value badge */}
          {valS > 0 && (
            <div style={{
              position: 'absolute', left: hx - 40 - 330, top: hy - 70, width: 330, height: 140,
              transform: `scale(${valS.toFixed(4)})`, transformOrigin: '100% 50%', opacity: Math.min(1, valS * 1.6),
            }}>
              <div style={{
                position: 'absolute', inset: 0, background: ACC, borderRadius: 6, color: L.onAccent,
                display: 'flex', flexDirection: 'column', justifyContent: 'center', paddingLeft: 30,
                boxShadow: `0 18px 40px -12px ${alpha(L.shadow, 0.45)}`,
              }}>
                <div style={{ ...type(76, 850) }}>340k</div>
                <div style={{ ...type(32, 600), opacity: 0.9 * ramp(frame, MARK + 10, 10, EASE.out), marginTop: 4 }}>▲ 372% vs Nov</div>
              </div>
              <div style={{ position: 'absolute', right: -10, top: 60, width: 20, height: 20, background: ACC, transform: 'rotate(45deg)' }} />
            </div>
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};
