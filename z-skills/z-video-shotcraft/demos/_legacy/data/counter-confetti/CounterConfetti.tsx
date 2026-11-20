// counter-confetti — Number sprint with confetti burst (motion-lab finalized to native Remotion)
// Large counter 0 -> 1000 sprints with easeOutQuart, scale follows [0.2, 1.3, 1.3, 1] overshoot;
// 5 frames before counter settles, 8-color confetti bursts from both sides with gravity drop and spin drift.
// Design coordinates 480x270 (uniformly scaled via DesignStage); parameters are calibrated to this coordinate space.
import React from 'react';
import { DesignStage, E, lerp, rand, seg, useT } from '../../_fixtures/Motion';

export const COUNTER_CONFETTI_DURATION = 138; // 4600ms @30fps

const PAL = ['#ff6b8b', '#ffb347', '#ffe86b', '#7bff9e', '#5fd8ff', '#6c8cff', '#c86cff', '#ff6cf0'];
const BURST = 0.52; // Anticipatory burst before count reaches target (0.56)

// Static parameters for 52 confetti pieces (seeds match effect.js exactly for deterministic reproducibility)
const BITS = Array.from({ length: 52 }, (_, i) => {
  const isRect = rand(i * 3) > 0.4;
  const w = 5 + rand(i + 2) * 6;
  const h = isRect ? 8 + rand(i + 5) * 7 : w;
  const side = i % 2 ? 1 : -1;
  return {
    w,
    h,
    isRect,
    color: PAL[i % 8],
    x0: side * 250, // Originates from screen sides (px, relative to center)
    y0: (rand(i + 30) - 0.5) * 60,
    vx: -side * (150 + rand(i * 5 + 1) * 300), // Rushes toward screen center
    vy: -(230 + rand(i * 7 + 3) * 220),
    g: 900 + rand(i + 60) * 520,
    spin: (rand(i + 90) - 0.5) * 1500,
    d: rand(i + 120) * 0.06, // Slight per-piece stagger
  };
});

export const CounterConfetti: React.FC = () => {
  const t = useT();
  // Counter: easeOutQuart sprint
  const p = seg(t, 0.06, 0.56, E.outQuart);
  const val = Math.round(p * 1000);
  // Scale overshoot [0.2, 1.3, 1.3, 1]
  const s1 = seg(t, 0.06, 0.3, E.outCubic);
  const s2 = seg(t, 0.56, 0.72, E.outBack);
  const sc = lerp(s1, 0.2, 1.3) + s2 * (1 - 1.3);
  // Impact shockwave ring
  const rp = seg(t, 0.545, 0.75, E.outQuart);
  return (
    <DesignStage bg="radial-gradient(80% 80% at 50% 45%,#161a2b,#07080e 75%)">
      {/* Central glow */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '47%',
          width: 340,
          height: 340,
          margin: -170,
          borderRadius: '50%',
          background: 'radial-gradient(circle,rgba(120,160,255,.28),transparent 66%)',
          opacity: 0.35 + seg(t, 0.5, 0.62, E.outCubic) * 0.65 - seg(t, 0.72, 1) * 0.5,
        }}
      />
      {/* Large counter (gradient fill text with outer scale overshoot) */}
      <div style={{ position: 'absolute', left: '50%', top: '47%', transformOrigin: '50% 50%', transform: `scale(${sc})` }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            transform: 'translate(-50%,-50%)',
            whiteSpace: 'nowrap',
            fontWeight: 800,
            fontSize: 74,
            lineHeight: 1,
            // Original font -apple-system is not resolved in Remotion headless browser (falls back to Arial);
            // add Helvetica fallback — metrics match original SF Pro glyph-for-glyph
            fontFamily: "-apple-system,Helvetica,'Segoe UI',sans-serif",
            letterSpacing: -2,
            background: 'linear-gradient(180deg,#ffffff,#a9bcff)',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            color: 'transparent',
            textShadow: '0 0 34px rgba(130,160,255,.28)',
            opacity: Math.min(1, seg(t, 0.02, 0.12) * 1.2),
          }}
        >
          {val.toLocaleString('en-US')}
        </div>
      </div>
      {/* Bottom label: fade-in + letter-spacing tightening */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '70%',
          transform: 'translate(-50%,0)',
          fontWeight: 700,
          fontSize: 10,
          lineHeight: 1,
          fontFamily: '-apple-system,Helvetica,sans-serif', // Same as above: Helvetica fallback to align with source

          color: '#7d88a8',
          opacity: seg(t, 0.62, 0.78, E.outCubic),
          letterSpacing: lerp(seg(t, 0.62, 0.82, E.outCubic), 11, 5),
        }}
      >
        METRIC THIS WEEK
      </div>
      {/* Impact shockwave ring */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '47%',
          width: 120,
          height: 120,
          margin: -60,
          borderRadius: '50%',
          border: '2px solid rgba(160,190,255,.8)',
          // Original render lacked global border-box: 120px was content-width, 2px border expanded to 124px
          // (Remotion injected * { box-sizing: border-box }, explicit content-box matches original)
          boxSizing: 'content-box',
          opacity: rp > 0 ? (1 - rp) * 0.9 : 0,
          transform: `scale(${0.35 + rp * 2.6})`,
        }}
      />
      {/* Confetti: anticipatory burst + gravity drop + rotation */}
      {BITS.map((b, i) => {
        const u = seg(t, BURST + b.d, 1);
        const life = u * 1.1; // Second-scale timeframe
        const x = b.x0 + b.vx * life;
        const y = b.y0 + b.vy * life + 0.5 * b.g * life * life;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: '50%',
              top: '50%',
              width: b.w,
              height: b.h,
              background: b.color,
              borderRadius: b.isRect ? 2 : '50%',
              willChange: 'transform',
              opacity: u <= 0 ? 0 : Math.min(1, u * 8) * (1 - seg(u, 0.74, 1) * 0.95),
              transform: `translate(calc(-50% + ${x}px),calc(-50% + ${y}px)) rotate(${b.spin * life}deg) scale(${0.8 + (1 - u) * 0.35})`,
            }}
          />
        );
      })}
    </DesignStage>
  );
};
