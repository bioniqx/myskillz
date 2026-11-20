// picker-carousel-feature-cycle — Picker Carousel feature name snap cycle (Remotion)
// Mobile-style vertical picker: focus pill stays fixed while content scrolls through it; each item pauses 0.45s with outQuint
// snap deceleration + 4-5 frame hold; layered control of opacity/fontSize/grayscale by distance from center; on settle, pill performs
// subtle scaleY 1->1.06->1 pulse; fixed square badge on left.
// Design coordinates 480x270 (DesignStage proportional scale). Parameter values calibrated to this coordinate space.
// Polish pass: soft overhead lighting + subtle vignette grain on paper base; line icons with 1.5 stroke
// (focus row uses accent color); pill includes top edge highlight + dual soft shadows; vertical motion blur during rapid scroll
// (tapers naturally during deceleration); dark gradient app icon on left. Preserved timing and parameters.
// Brand adaptation: 7 feature labels showcase video-shotcraft capabilities (Shot Recipe -> Capture -> Camera Moves -> Rhythm -> Audio ->
// Workbench -> Render), icons redrawn; left badge features ShotcraftMark on dark rounded square.
import React from 'react';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { FONT, Grain, SpeedBlur, Vignette } from '../../_fixtures/Polish';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const PICKER_CAROUSEL_FEATURE_CYCLE_DURATION = 108; // 3600ms @30fps

const PAPER = '#F3F3F1';
const INK = '#111113';
const MID = '#8A8A8F';
const ROW_H = 34; // Single row height
const ITEMS = [
  'Shot recipe cards',
  'Real page captures',
  '2.5D camera moves',
  'Beat-synced cuts',
  'Film-grade SFX',
  'Motion workbench',
  'Remotion render',
];
const ACCENT = '#5b63d3';
// 16px grid line icons (matching ITEMS): Recipe Card / Screen Capture / Camera / Rhythm / Speaker / Sliders / Render
const ICONS: string[][] = [
  ['M4 2.5h8c.55 0 1 .45 1 1v9c0 .55-.45 1-1 1H4c-.55 0-1-.45-1-1v-9c0-.55.45-1 1-1z', 'M5.75 5.75h4.5', 'M5.75 8h4.5', 'M5.75 10.25h2.5'],
  ['M2.5 5.5v-3h3', 'M10.5 2.5h3v3', 'M13.5 10.5v3h-3', 'M5.5 13.5h-3v-3', 'M5.5 6h5v4h-5z'],
  ['M3.25 5h6c.4 0 .75.35.75.75v4.5c0 .4-.35.75-.75.75h-6c-.4 0-.75-.35-.75-.75v-4.5c0-.4.35-.75.75-.75z', 'M10 7.25 13.5 5.5v5L10 8.75'],
  ['M3 7v2', 'M5.5 4.5v7', 'M8 2.5v11', 'M10.5 5.5v5', 'M13 7v2'],
  ['M2.5 6.25h2.25L8 3.5v9L4.75 9.75H2.5z', 'M10.5 6a2.8 2.8 0 0 1 0 4', 'M12.25 4.25a5.3 5.3 0 0 1 0 7.5'],
  ['M2.5 4.5h11', 'M2.5 11.5h11', 'M5.5 2.5v4', 'M10.5 9.5v4'],
  ['M3.5 3h9c.55 0 1 .45 1 1v8c0 .55-.45 1-1 1h-9c-.55 0-1-.45-1-1V4c0-.55.45-1 1-1z', 'M6.75 6v4l3.25-2z'],
];
const Icon: React.FC<{ d: string[]; color: string }> = ({ d, color }) => (
  <svg width={13} height={13} viewBox="0 0 16 16" fill="none" style={{ display: 'block' }}>
    {d.map((p, i) => (
      <path key={i} d={p} stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    ))}
  </svg>
);
const STEPS = 5; // Five snap steps
const HOLD = 5 / 14; // Hold fraction at end of each step (~4-5 frames static)

export const PickerCarouselFeatureCycle: React.FC = () => {
  const t = useT();

  // Main timeline: t in [0.05, 0.95] partitioned into 5 steps; outQuint snap during (1-HOLD), hold at end
  const g = seg(t, 0.05, 0.95) * STEPS;
  const step = Math.min(STEPS - 1, Math.floor(g));
  const local = Math.min(1, g - step);
  const mv = E.outQuint(Math.min(1, local / (1 - HOLD)));
  const pos = step + mv;
  // Vertical velocity (design px/frame): vertical motion blur during fast phase, natural taper on settle
  const posAt = (tt: number) => {
    const gg = seg(tt, 0.05, 0.95) * STEPS;
    const st = Math.min(STEPS - 1, Math.floor(gg));
    const lo = Math.min(1, gg - st);
    return st + E.outQuint(Math.min(1, lo / (1 - HOLD)));
  };
  const dt = 0.5 / (PICKER_CAROUSEL_FEATURE_CYCLE_DURATION - 1);
  const vy = -(posAt(t + dt) - posAt(t - dt)) * ROW_H;

  // Settle pulse: after snap completes and enters HOLD, pill executes scaleY 1->1.06->1 pulse
  const land = Math.max(0, (local - (1 - HOLD)) / HOLD);
  const breath = land > 0 ? Math.sin(Math.min(1, land / 0.6) * Math.PI) * 0.06 : 0;

  return (
    <DesignStage bg={PAPER} raster="zoom">
      {/* Paper background */} 
      <div
        style={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
          background: `radial-gradient(ellipse 70% 80% at 46% 30%, #f8f8f6 0%, rgba(248,248,246,0) 70%), linear-gradient(180deg, #f4f4f2 0%, ${PAPER} 55%, #eeeeeb 100%)`,
          fontFamily: FONT.sans,
        }}
      >
        {/* Ambient highlight behind pill lifting focus row from paper base */}
        <div
          style={{
            position: 'absolute',
            left: 240 - 190,
            top: 135 - 40,
            width: 380,
            height: 80,
            background: 'radial-gradient(ellipse 50% 50% at 50% 50%, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0) 70%)',
            opacity: seg(t, 0, 0.05),
          }}
        />
        {/* Picker viewport: 300x(34x5) centered, fades in over first 5% */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: 300,
            height: ROW_H * 5,
            transform: 'translate(-50%,-50%)',
            overflow: 'hidden',
            opacity: seg(t, 0, 0.05),
            // Top/bottom 26% fade mask via alpha mask to prevent seam lines against gradient background
            WebkitMaskImage: 'linear-gradient(180deg, transparent 0%, #000 26%, #000 74%, transparent 100%)',
            maskImage: 'linear-gradient(180deg, transparent 0%, #000 26%, #000 74%, transparent 100%)',
          }}
        >
          {/* Focus pill: fixed position, breathes via scaleY on settle.
              Box-sizing explicit declaration ensures height accuracy with 1px border. */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: ROW_H * 2,
              height: ROW_H,
              boxSizing: 'content-box',
              borderRadius: 999,
              background: 'linear-gradient(180deg, #ffffff 0%, #fbfbfa 100%)',
              border: '1px solid #E3E3E6',
              // Top inner highlight + contact shadow + diffuse drop shadow (key light from above)
              boxShadow: 'inset 0 1px 0 rgba(255,255,255,1), 0 0.5px 1px rgba(16,18,24,.06), 0 3px 9px -2px rgba(16,18,24,.09), 0 10px 22px -10px rgba(16,18,24,.12)',
              transform: `scaleY(${1 + breath})`,
            }}
          />
          {/* Content column: translates vertically through focus pill with motion blur */}
          <SpeedBlur vx={0} vy={vy} amount={0.06} max={0.8}>
          <div
            style={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: 0,
              transform: `translateY(${ROW_H * 2 - pos * ROW_H}px)`,
            }}
          >
            {ITEMS.map((txt, i) => {
              // Distance-based hierarchy: 2-stage opacity, fontSize 17->14, 3-tier grayscale
              const d = Math.abs(i - pos);
              const k2 = Math.min(2, d);
              const o = k2 <= 1 ? lerp(k2, 1, 0.55) : lerp(k2 - 1, 0.55, 0.18);
              return (
                <div
                  key={i}
                  style={{
                    height: ROW_H,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    fontWeight: 600,
                    fontSize: lerp(Math.min(1, d / 2), 17, 14),
                    lineHeight: 1,
                    letterSpacing: '-0.01em',
                    color: d < 0.5 ? INK : d < 1.5 ? MID : '#B9B9BE',
                    opacity: o,
                  }}
                >
                  {/* Icon reveals near center (d < 0.625), accent color on active row */}
                  <span style={{ opacity: Math.max(0, 1 - d * 1.6), marginTop: 0.5 }}>
                    <Icon d={ICONS[i]} color={ACCENT} />
                  </span>
                  <span>{txt}</span>
                </div>
              );
            })}
          </div>
          </SpeedBlur>
        </div>
        {/* Left app badge: dark rounded square housing ShotcraftMark (inverted), subtle delayed fade-in */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            margin: '-12px 0 0 -186px',
            width: 24,
            height: 24,
            borderRadius: 6,
            background: 'linear-gradient(160deg, #2a2b31 0%, #111113 100%)',
            boxShadow: 'inset 0 0.5px 0 rgba(255,255,255,0.22), 0 0 0 0.5px rgba(0,0,0,0.5), 0 2px 5px -1px rgba(16,18,24,0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: seg(t, 0.02, 0.09),
          }}
        >
          <ShotcraftMark size={16} tone="dark" />
        </div>
        <Vignette strength={0.12} inner={0.5} color="#2a2c36" />
        <Grain opacity={0.045} scale={0.25} />
      </div>
    </DesignStage>
  );
};
