// pull-back-isolation — pull-back camera move.
// Camera scale 2.2 -> 0.62 (0-110f, Easing.out(cubic)): starts tight on hero card
// "99.9%" close-up, slowly pulling back to reveal 8 surrounding cards.
// Surrounding cards extinguish radially from near to far (every 8f, opacity->0 + brightness down);
// Background sinks from light canvas to tinted dark #111216 (60-110f); hero white glow fades in (60-100f).
// Frames 110-150 absolute stillness: isolated glowing metric card — climax moment for one number.
//
// Redesign highlights: hero card upgraded to editorial metric card (label + large value +
// 90-day uptime strip + footer); camera laid out at 2.2x zoom for sharp typography;
// surrounding cards sink slightly (scale 0.97) + defocus as they extinguish;
// background cross-fades from soft light to dark, illuminated card top edge emerges.
import React from 'react';
import { useCurrentFrame, interpolate, Easing, AbsoluteFill } from 'remotion';
import { Card, G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, Grain, mix, softShadow } from '../../_fixtures/Polish';

export const PULL_BACK_ISOLATION_DURATION = 150; // 110f pull-back + 40f isolated hold

// 8 surrounding cards: offset relative to hero center (960,540) + dimensions + seed
const SIBS = [
  { dx: -620, dy: -330, w: 360, h: 240, seed: 3 },
  { dx: 10, dy: -390, w: 420, h: 220, seed: 4 },
  { dx: 620, dy: -320, w: 380, h: 260, seed: 5 },
  { dx: -680, dy: 20, w: 340, h: 230, seed: 6 },
  { dx: 700, dy: 40, w: 360, h: 250, seed: 7 },
  { dx: -600, dy: 360, w: 400, h: 240, seed: 8 },
  { dx: 40, dy: 400, w: 440, h: 220, seed: 9 },
  { dx: 640, dy: 350, w: 370, h: 250, seed: 10 },
].map((s) => ({ ...s, dist: Math.hypot(s.dx, s.dy) }));

// Stagger extinguish order by distance to hero card (near cards extinguish first)
const RANKED = SIBS.map((s, i) => i).sort((a, b) => SIBS[a].dist - SIBS[b].dist);
const FADE_START = RANKED.reduce<number[]>((acc, idx, rank) => {
  acc[idx] = 30 + rank * 8;
  return acc;
}, []);
const FADE_DUR = 16;

const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

// Camera layout scale = initial close-up scale: rasterized at 2.2x, scales down only
const Z = 2.2;

// 90-day render success strip: mostly green with 2 degraded days for realistic credibility
const DAYS = Array.from({ length: 45 }, (_, i) => (i === 17 ? 1 : i === 33 ? 2 : 0));

const HeroCard: React.FC<{ rim: number }> = ({ rim }) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      borderRadius: 18,
      background: 'linear-gradient(180deg, #ffffff 0%, #fbfbfa 100%)',
      border: '1px solid rgba(20,22,28,0.08)',
      boxSizing: 'border-box',
      padding: '30px 34px 26px',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: FONT.sans,
      overflow: 'hidden',
      boxShadow: `inset 0 1px 0 rgba(255,255,255,${0.9 + rim * 0.1})`,
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 9, height: 9, borderRadius: 5, background: '#2fa36b', boxShadow: '0 0 0 4px rgba(47,163,107,0.14)' }} />
      <div style={{ fontSize: 17, fontWeight: 600, color: G.ink1, letterSpacing: '-0.01em' }}>Render success</div>
      <div style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 550, color: G.ink2, padding: '3px 9px', borderRadius: 7, background: G.fill, boxShadow: `inset 0 0 0 1px ${G.hairline}` }}>
        90 days
      </div>
    </div>
    <div
      style={{
        marginTop: 18,
        fontSize: 128,
        fontWeight: 700,
        lineHeight: 0.96,
        letterSpacing: '-0.045em',
        color: G.ink1,
        fontVariantNumeric: 'tabular-nums',
      }}
    >
      99.9<span style={{ fontSize: '0.56em', fontWeight: 600, color: G.ink2, marginLeft: '0.04em' }}>%</span>
    </div>
    <div style={{ marginTop: 'auto', display: 'flex', gap: 3, height: 30, alignItems: 'stretch' }}>
      {DAYS.map((d, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            borderRadius: 2,
            background: d === 0 ? 'rgba(47,163,107,0.78)' : d === 1 ? '#e2a23b' : 'rgba(47,163,107,0.4)',
          }}
        />
      ))}
    </div>
    <div style={{ marginTop: 10, display: 'flex', fontSize: 13, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>
      <span>90 days ago</span>
      <span style={{ marginLeft: 'auto' }}>Today</span>
    </div>
  </div>
);

export const PullBackIsolation: React.FC = () => {
  const frame = useCurrentFrame();

  // Camera pull-back: 2.2 (extreme close-up) -> 0.62 (isolated wide)
  const scale = interpolate(frame, [0, 110], [2.2, 0.62], {
    easing: Easing.out(Easing.cubic),
    ...clamp,
  });

  // Background sinks into darkness (60-110f): cross-fade to tinted dark
  const bgT = interpolate(frame, [60, 110], [0, 1], { easing: Easing.inOut(Easing.quad), ...clamp });

  // Hero card glow fade-in (60-100f)
  const glow = interpolate(frame, [60, 100], [0, 1], { easing: Easing.inOut(Easing.quad), ...clamp });

  return (
    <AbsoluteFill style={{ background: G.dark, overflow: 'hidden' }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.3 }} grain={0} />
      <AbsoluteFill style={{ opacity: bgT }}>
        <Backdrop tone="dark" light={{ x: 0.5, y: 0.5 }} accent="#5b63d3" grain={0} vignette={0.6} />
      </AbsoluteFill>

      {/* Camera container: laid out at Z scale, scaled around hero center */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          width: 1920 * Z,
          height: 1080 * Z,
          transformOrigin: `${960 * Z}px ${540 * Z}px`,
          transform: `translate(${960 - 960 * Z}px, ${540 - 540 * Z}px) scale(${scale / Z})`,
        }}
      >
        <div style={{ position: 'relative', width: 1920, height: 1080, zoom: Z }}>
          {/* Surrounding cards: stagger extinguish near-to-far with subtle sink */}
          {SIBS.map((s, i) => {
            const t0 = FADE_START[i];
            const k = interpolate(frame, [t0, t0 + FADE_DUR], [0, 1], clamp);
            // Opacity fades first, followed by darkening to avoid flat gray patches
            const op = 1 - EASE.out(k);
            const dk = k * k;
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: 960 + s.dx - s.w / 2,
                  top: 540 + s.dy - s.h / 2,
                  opacity: op,
                  // Darken + slight defocus: sinking into darkness
                  filter: k > 0.001 ? `brightness(${mix(1, 0.3, dk).toFixed(3)}) blur(${(k * 5).toFixed(2)}px)` : undefined,
                  transform: `scale(${mix(1, 0.97, k)})`,
                }}
              >
                <Card w={s.w} h={s.h} seed={s.seed} />
              </div>
            );
          })}

          {/* Hero card: 520x340 centered; cool white glow in dark environment */}
          <div
            style={{
              position: 'absolute',
              left: 960 - 260,
              top: 540 - 170,
              width: 520,
              height: 340,
              borderRadius: 18,
              boxShadow:
                `${softShadow(18, { strength: 1 - glow * 0.6 })}, ` +
                `0 0 70px rgba(214,222,255,${(glow * 0.32).toFixed(3)}), 0 0 180px rgba(150,162,240,${(glow * 0.2).toFixed(3)})`,
            }}
          >
            <HeroCard rim={glow} />
          </div>
        </div>
      </div>
      <Grain opacity={mix(0.05, 0.09, bgT)} blend={bgT > 0.5 ? 'soft-light' : 'overlay'} />
    </AbsoluteFill>
  );
};
