// timeline-travel — horizontal timeline pan (Kingdom-style)
// Camera accelerates horizontally along scale axis, passing v1.0, v2.0, v3.0, and Today ticks in sequence.
// Passing each tick springs its card upright with overshoot + brief pause, while camera keeps moving;
// At final tick, 4f hard stop occurs with 1.28x zoom-in. World layer only changes translateX/scale.
// f0–12 initial rest; from f114 true freeze for 46f (160f total).
//
// Polish upgrade: extend export duration (workbench originally inferred 104f, cutting off right at hard stop frame, so Today card and zoom-in never appeared);
// replace debug title with fixed header; replace gray wireframe Card with publication-grade milestone cards (version chip / year / title / description / metric, with Today card using accent color);
// replace 6px dark bar ticks with glowing nodes + two-tier version/year labels, with hairline stem connecting card and node; sprint section adds
// horizontal SpeedBlur proportional to camera speed (0 during stationary/slow sections); background layer features large years panning at 0.35x parallax, cross-fading based on distance to provide distant reference; soft light field + grain.
import React from 'react';
import { useCurrentFrame, interpolate, Easing, spring } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, FONT, Grain, SpeedBlur, innerHighlight, softShadow, tracking } from '../../_fixtures/Polish';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const TIMELINE_TRAVEL_DURATION = 160;

const W = 1920;
const AXIS_Y = 700;
const TICK_GAP = 1400; // Tick spacing (world coordinates)
const TICKS = [
  // video-shotcraft release history (monthly major releases starting July 2026); year = date on card/tick, far = large background parallax text (month)
  { label: 'v1.0', year: 'Jul 2026', far: 'Jul', x: 960, title: 'Public launch', desc: 'Shot recipe cards, a template and a gallery.', metric: 'Remotion render' },
  { label: 'v2.0', year: 'Aug 2026', far: 'Aug', x: 960 + TICK_GAP, title: 'Camera & sound', desc: '2.5D camera moves with beat-synced SFX.', metric: 'Beat-synced cuts' },
  { label: 'v3.0', year: 'Sep 2026', far: 'Sep', x: 960 + TICK_GAP * 2, title: 'Motion workbench', desc: 'Every shot, tuned in one place.', metric: 'Live preview' },
  { label: 'Today', year: 'Oct 2026', far: 'Oct', x: 960 + TICK_GAP * 3, title: 'One-prompt promos', desc: 'Direct the film. Let the agent shoot it.', metric: 'Claude Code & Codex' },
];
const WORLD_W = 960 + TICK_GAP * 3 + 960;

const TRAVEL_START = 12;
const TRAVEL_END = 104; // Hard stop frame
const ZOOM_END = 114;

// Camera X: in-out easing, slow early on and fast later (primarily poly(3) in, with snappy out deceleration at the end)
// Composed of two segments: 0–0.82 acceleration (Easing.in(poly(2.2))), 0.82–1 hard braking
const camXAt = (f: number): number => {
  const total = TICKS[3].x - 960; // Total world distance to travel
  const t = interpolate(f, [TRAVEL_START, TRAVEL_END], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Acceleration -> cruise -> hard brake: segmented easing, first 15% gentle start, middle near-constant acceleration sprint, final 12% sharp deceleration
  const eased = interpolate(t, [0, 0.15, 0.88, 1], [0, 0.055, 0.9, 1], {
    easing: Easing.inOut(Easing.quad),
  });
  return eased * total;
};

// Pop-up frame for each card: the moment camera center sweeps across that tick (precomputed to avoid per-frame inversion)
// Inverted via camXAt: find the frame where camX == tick.x - 960
const popFrameOf = (tickX: number): number => {
  for (let f = TRAVEL_START; f <= TRAVEL_END; f++) {
    if (camXAt(f) >= tickX - 960) return f;
  }
  return TRAVEL_END;
};

const CARD_W = 360;
const CARD_H = 240;
const STEM = 36; // Stem length from card bottom to axis

const MilestoneCard: React.FC<{ i: number }> = ({ i }) => {
  const t = TICKS[i];
  const hero = i === TICKS.length - 1;
  return (
    <div
      style={{
        width: CARD_W,
        height: CARD_H,
        boxSizing: 'border-box',
        borderRadius: 18,
        padding: '24px 26px',
        background: hero ? 'linear-gradient(180deg, #ffffff 0%, #f7f7ff 100%)' : '#ffffff',
        border: hero ? '1px solid rgba(91,99,211,0.35)' : `1px solid ${G.hairline}`,
        boxShadow: `${innerHighlight(0.9)}, ${softShadow(hero ? 18 : 8, { strength: hero ? 1.3 : 1 })}`,
        display: 'flex',
        flexDirection: 'column',
        fontFamily: FONT.sans,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            height: 30,
            padding: '0 12px',
            borderRadius: 8,
            background: hero ? G.accent : G.fill,
            color: hero ? '#fff' : G.ink2,
            fontFamily: FONT.mono,
            fontSize: 18,
            fontWeight: 650,
            lineHeight: '30px',
          }}
        >
          {hero ? 'v4.0' : t.label}
        </div>
        <div style={{ marginLeft: 'auto', fontSize: 20, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>{t.year}</div>
      </div>
      <div style={{ marginTop: 18, fontSize: 32, fontWeight: 700, letterSpacing: tracking(32), color: G.ink1 }}>{t.title}</div>
      <div style={{ marginTop: 8, fontSize: 23, lineHeight: 1.3, color: G.ink2 }}>{t.desc}</div>
      <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 20, fontWeight: 600, color: hero ? G.accent : G.ink3 }}>
        <div style={{ width: 8, height: 8, borderRadius: 4, background: hero ? G.accent : '#c4c6cc' }} />
        {t.metric}
      </div>
    </div>
  );
};

const TickStop: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const tick = TICKS[i];
  const hero = i === TICKS.length - 1;
  const pop = popFrameOf(tick.x) - 6; // Pop 6f early so it stands upright exactly as the camera sweeps past
  const s = spring({
    frame: frame - pop,
    fps: 30,
    config: { damping: 11, stiffness: 160, mass: 0.9 }, // Pronounced overshoot
    durationInFrames: 26,
  });
  const appeared = frame >= pop;
  // Node "lit up": turns from hollow gray to solid on the same beat as card pop-up
  const lit = interpolate(frame, [pop, pop + 6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <div style={{ position: 'absolute', left: tick.x, top: 0 }}>
      {/* Tick node: outer glow halo + solid core */}
      <div
        style={{
          position: 'absolute',
          left: -16,
          top: AXIS_Y - 16,
          width: 32,
          height: 32,
          borderRadius: 16,
          background: hero ? 'rgba(91,99,211,0.16)' : 'rgba(20,22,28,0.06)',
          transform: `scale(${(0.6 + 0.4 * lit).toFixed(3)})`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: -8,
          top: AXIS_Y - 8,
          width: 16,
          height: 16,
          borderRadius: 8,
          boxSizing: 'border-box',
          border: `3px solid ${hero ? G.accent : G.ink1}`,
          background: lit > 0.5 ? (hero ? G.accent : G.ink1) : '#f4f4f2',
        }}
      />
      {/* Tick labels: version + year */}
      <div style={{ position: 'absolute', left: -110, top: AXIS_Y + 34, width: 220, textAlign: 'center', fontFamily: FONT.sans }}>
        <div style={{ fontWeight: 720, fontSize: 40, letterSpacing: tracking(40), color: hero ? G.accent : G.ink1 }}>{tick.label}</div>
        <div style={{ marginTop: 2, fontSize: 28, fontWeight: 500, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>{tick.year}</div>
      </div>
      {/* Card springs upright from tick line: scaleY 0->1 anchored at bottom (with overshoot), accompanied by slight horizontal squeeze */}
      {appeared && (
        <>
          <div
            style={{
              position: 'absolute',
              left: -0.5,
              top: AXIS_Y - 8 - STEM * Math.min(1, s),
              width: 1,
              height: STEM * Math.min(1, s),
              background: hero ? 'rgba(91,99,211,0.5)' : 'rgba(20,22,28,0.22)',
            }}
          />
          <div
            style={{
              position: 'absolute',
              left: -CARD_W / 2,
              top: AXIS_Y - 8 - STEM - CARD_H,
              transform: `scaleY(${s}) scaleX(${0.85 + 0.15 * s})`,
              transformOrigin: '50% 100%',
              opacity: Math.min(1, s * 2),
            }}
          >
            <MilestoneCard i={i} />
          </div>
        </>
      )}
    </div>
  );
};

export const TimelineTravel: React.FC = () => {
  const frame = useCurrentFrame();
  const camX = camXAt(frame);
  const vx = -(camXAt(frame + 0.5) - camXAt(frame - 0.5)); // World layer screen velocity (px/f, negative is leftward)

  // Zoom into final tick after hard stop: scale 1 -> 1.28, centered on Today tick
  const zoom = interpolate(frame, [TRAVEL_END, ZOOM_END], [1, 1.28], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const headIn = interpolate(frame, [0, 14], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });

  return (
    <div style={{ width: W, height: 1080, overflow: 'hidden', position: 'relative', fontFamily: FONT.sans }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.22 }} accent={G.accent} vignette={0.16} grain={0} />
      {/* Background parallax: large year panned at 0.35x speed, zoomed at only 0.35x magnitude (background sits outside zoom layer);
          fades in/out based on distance from camera center, showing only the active year at any time */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${(1 + (zoom - 1) * 0.35).toFixed(4)})`,
          transformOrigin: '50% 62%',
        }}
      >
        {TICKS.map((t, i) => {
          const d = Math.abs(camX - i * TICK_GAP) / TICK_GAP; // 0 = tick directly facing camera
          const op = Math.max(0, 1 - d / 0.62);
          if (op <= 0) return null;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 960 + i * TICK_GAP * 0.35 - camX * 0.35 - 500,
                width: 1000,
                top: 210,
                textAlign: 'center',
                fontSize: 280,
                lineHeight: 1,
                fontWeight: 800,
                letterSpacing: '-0.05em',
                color: `rgba(20,22,28,${(0.04 * op).toFixed(4)})`,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {t.far}
            </div>
          );
        })}
      </div>
      {/* Zoom layer: scaled with origin slightly below screen center (landing point of the final tick) */}
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${zoom})`, transformOrigin: '50% 62%' }}>
        {/* World layer: the only horizontally panning container; horizontal motion blur during sprint */}
        <SpeedBlur vx={vx} amount={0.16} max={9}>
          <div style={{ position: 'absolute', left: 0, top: 0, width: WORLD_W, height: 1080, transform: `translateX(${(-camX).toFixed(2)}px)` }}>
            {/* Main axis line */}
            <div
              style={{
                position: 'absolute',
                left: 200,
                top: AXIS_Y - 1,
                width: WORLD_W - 400,
                height: 2,
                background: 'linear-gradient(90deg, rgba(20,22,28,0) 0%, rgba(20,22,28,0.22) 4%, rgba(20,22,28,0.22) 96%, rgba(20,22,28,0) 100%)',
              }}
            />
            {/* Minor tick marks (subtle short bars serving as speed reference) */}
            {Array.from({ length: 22 }).map((_, i) =>
              i % 5 === 0 ? null : (
                <div
                  key={i}
                  style={{
                    position: 'absolute',
                    left: 960 + i * (TICK_GAP / 5) - 1,
                    top: AXIS_Y - 9,
                    width: 2,
                    height: 18,
                    background: 'rgba(20,22,28,0.2)',
                    borderRadius: 1,
                  }}
                />
              ),
            )}
            {TICKS.map((_, i) => (
              <TickStop key={i} i={i} frame={frame} />
            ))}
          </div>
        </SpeedBlur>
      </div>
      {/* Fixed header */}
      <div style={{ position: 'absolute', left: 120, top: 96, opacity: headIn, transform: `translateY(${((1 - headIn) * 8).toFixed(2)}px)` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: 30, fontWeight: 650, letterSpacing: tracking(30, true), textTransform: 'uppercase', color: G.accent }}>
          <ShotcraftMark size={36} tone="light" />
          Release history
        </div>
        <div style={{ marginTop: 6, fontSize: 56, fontWeight: 720, letterSpacing: tracking(56), color: G.ink1 }}>Shipping every month</div>
      </div>
      <Grain opacity={0.05} />
    </div>
  );
};
