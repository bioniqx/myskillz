// counter-tick-sparks — Number tick sparks
// Central large counter 0 → 12,847 (easeOut digit ticks); whenever crossing each thousand tick frame,
// 6–10 large sparks emit from top of number (initial velocity upward 9–13px/f, gravity pulls down dying within 14–18f);
// final value reveal jump doubles to 20 sparks + number pops 1.1x and settles back.
// All sparks conditionally unmounted after lifespan expires, true static ≥40f.
// Frame determinism: tick frames pre-resolved from the same easeOut curve (module-level evaluation), sparks = pure age closed-form ballistic trajectory.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

const AMBER = '#b45309';
const TARGET = 12847;
const COUNT_END = 78; // Count end frame
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
const valueAt = (f: number) => Math.round(TARGET * easeOutCubic(Math.min(Math.max(f / COUNT_END, 0), 1)));

const frac = (x: number) => x - Math.floor(x);
const rnd = (i: number, salt: number) => frac(Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453);

// Pre-resolve tick frames: frames crossing each thousand mark + final value reveal frame
const TICKS: { f: number; big: boolean }[] = (() => {
  const out: { f: number; big: boolean }[] = [];
  let prev = 0;
  for (let f = 1; f <= COUNT_END; f++) {
    const v = valueAt(f);
    if (Math.floor(v / 1000) > Math.floor(prev / 1000)) out.push({ f, big: false });
    prev = v;
  }
  out.push({ f: COUNT_END, big: true }); // Final value reveal
  return out;
})();

const SPARK_LIFE = 18;
const GRAV = 0.9;

export const CounterTickSparks: React.FC = () => {
  const frame = useCurrentFrame();
  const value = valueAt(frame);

  // Final value reveal pop 1.1x rebound
  const popScale =
    1 +
    0.1 *
      interpolate(frame, [COUNT_END, COUNT_END + 5, COUNT_END + 16], [0, 1, 0], {
        easing: Easing.out(Easing.quad),
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });

  const TOP_Y = 452; // Top edge of number (spark emission line)
  const CX = 960;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 110, width: '100%', textAlign: 'center' }}>
        <TitleBlock text="COUNTER TICK SPARKS" size={72} />
      </div>

      {/* Counter card */}
      <div style={{
        position: 'absolute', left: 560, top: 400, width: 800, height: 330,
        background: G.card, border: `2px solid ${G.border}`, borderRadius: 16,
        boxSizing: 'border-box', boxShadow: '0 4px 14px rgba(0,0,0,0.08)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20,
      }}>
        <div style={{ height: 14, width: 220, background: G.bar, borderRadius: 7 }} />
        <div style={{
          fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 800, fontSize: 168,
          color: G.ink, letterSpacing: -3, lineHeight: 1, fontVariantNumeric: 'tabular-nums',
          transform: `scale(${popScale})`,
        }}>
          {value.toLocaleString('en-US')}
        </div>
        <div style={{ height: 10, width: 150, background: G.line, borderRadius: 5 }} />
      </div>

      {/* Sparks: one cluster per tick, conditionally unmounted after lifespan expires */}
      {TICKS.map((tick, t) => {
        const age = frame - tick.f;
        if (age <= 0 || age >= SPARK_LIFE) return null;
        const n = tick.big ? 20 : 6 + Math.floor(rnd(t, 21) * 5); // 6–10, final jump 20
        return Array.from({ length: n }).map((_, i) => {
          const salt = t * 31 + i;
          // Initial velocity: upward 9–13px/f, horizontal ±4.5px/f fan spread (final jump wider)
          const vy = -(9 + rnd(salt, 2) * 4);
          const vx = (rnd(salt, 3) - 0.5) * (tick.big ? 13 : 9);
          const x0 = CX + (rnd(salt, 4) - 0.5) * (tick.big ? 560 : 380); // Distributed along top edge of number
          const x = x0 + vx * age;
          const y = TOP_Y + vy * age + 0.5 * GRAV * age * age;
          const life = 1 - age / SPARK_LIFE;
          const size = (tick.big ? 7 : 5.5) * (0.4 + 0.6 * life);
          return (
            <div key={`${t}-${i}`} style={{
              position: 'absolute', left: x, top: y, width: size, height: size,
              borderRadius: size / 2, background: AMBER, opacity: life,
              boxShadow: `0 0 ${6 * life}px ${AMBER}`,
            }} />
          );
        });
      })}
    </div>
  );
};
