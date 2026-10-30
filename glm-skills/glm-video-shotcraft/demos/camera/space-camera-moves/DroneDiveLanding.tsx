import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';
import { FakeDashboard } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, Grain, mix, ramp } from '../../_fixtures/Polish';

// drone-dive-landing: God's-eye view looking down on a dashboard lying flat (near-vertical pitch, scaled down and centered).
// The camera dives down aggressively — pitch levels out, the page scales up and stands upright, ending with an air-cushioned long-tail deceleration
// to park squarely in front of the hero card in close-up. A camera-move translation of an FPV drone dive and landing.
//
// Key redesign points: the page is no longer a thin sheet floating in void — it hovers above a dotted-grid floor
// (ground and page inhabit the same 3D world; during the dive, the grid rushes toward the lens providing a velocity reference);
// an isomorphic contact shadow on the ground tightens and sharpens as it "lands"; before the dive there is a ~2.5% upward anticipation lift;
// after settling, periphery gently dims, focus draws into the hero card, with a 1.2s breathing hold.
//
// hero card = top-left cell of FakeDashboard A grid:
// sidebar 220 + padding 36 = starts at x 256, column width (1628-56)/3 = 524;
// topbar 72 + padding 36 = starts at y 108, row height (936-28)/2 = 454.
// card center (256+262, 108+227) = (518, 335); transform-origin pinned here throughout.
const HERO = { cx: 518, cy: 335, w: 524, h: 454 };
const DIVE_START = 24; // Initial 24f: god's-eye view established + upward anticipation
const DIVE_END = 49; // Primary dive segment 25f, ease-in (cubic) accelerates downward
const LAND_END = 69; // Air-cushion segment 20f, ease-out (quint) long-tail deceleration into true stillness
const DIVE_SHARE = 0.82; // Dive consumes 82% of travel, remaining 18% left for cushion
const PRE_LIFT = 0.025; // Camera lifts upward before dive (travel backs up 2.5%): anticipation before big move
export const DRONE_DIVE_LANDING_DURATION = 105; // Hold 36f (1.2s) after landing

// Page laid out at final zoom scale (CSS zoom), then scaled back down by scale(1/Z):
// 3D compositing layer rasterizes at 1.35x resolution so final close-up text remains sharp (aesthetic rule Q2)
const Z = 1.35;
const LIFT = 150; // Initial hover height (local page px, ~60px after world scale)

// Single travel progress p: anticipation (-2.5%) → dive → air cushion
const travel = (frame: number) => {
  const pre = -PRE_LIFT * ramp(frame, 4, DIVE_START - 4, EASE.smooth);
  if (frame < DIVE_START) return pre;
  const pDive = interpolate(frame, [DIVE_START, DIVE_END], [-PRE_LIFT, DIVE_SHARE], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  if (frame < DIVE_END) return pDive;
  return (
    DIVE_SHARE +
    interpolate(frame, [DIVE_END, LAND_END], [0, 1 - DIVE_SHARE], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.poly(5)),
    })
  );
};

// Ground dot grid: large plane centered on hero, fading radially into distance without hard edges
const FLOOR = { x: -2400, y: -1500, w: 6720, h: 3300 };
const floorStyle: React.CSSProperties = {
  position: 'absolute',
  left: FLOOR.x,
  top: FLOOR.y,
  width: FLOOR.w,
  height: FLOOR.h,
  backgroundImage: 'radial-gradient(circle at 3px 3px, rgba(40,44,60,0.34) 2.2px, rgba(40,44,60,0) 3.2px)',
  backgroundSize: '48px 48px',
  backgroundPosition: `${(-FLOOR.x) % 48}px ${(-FLOOR.y) % 48}px`,
  WebkitMaskImage: `radial-gradient(ellipse ${FLOOR.w * 0.36}px ${FLOOR.h * 0.42}px at ${-FLOOR.x + 960}px ${-FLOOR.y + 600}px, #000 30%, transparent 100%)`,
  maskImage: `radial-gradient(ellipse ${FLOOR.w * 0.36}px ${FLOOR.h * 0.42}px at ${-FLOOR.x + 960}px ${-FLOOR.y + 600}px, #000 30%, transparent 100%)`,
};

const Scene: React.FC = () => {
  const frame = useCurrentFrame();
  const p = travel(frame);

  // 3-axis linkage, all driven by the same p (single continuous maneuver from one "camera")
  const rotX = mix(72, 0, p); // Pitch levels out
  const scale = mix(0.42, 1.35, p); // Scaled-down wide view → hero close-up
  // Translation: start centers full page lying flat; end aligns hero card center to screen center
  const tx = mix(256, 960 - HERO.cx, p);
  const ty = mix(170, 540 - HERO.cy, p);

  // Landing: hover height collapses to 0 with travel (touches down right at end of air cushion)
  const lift = LIFT * Math.pow(1 - Math.min(1, Math.max(0, p)), 1.4);
  // Contact shadow: large and soft when high, offset down-right (key light top-left); tightens and sharpens on touchdown
  const shOff = lift * 0.22;
  const shBlur = 22 + lift * 0.42;
  const shOp = interpolate(p, [0, 0.9, 1], [0.16, 0.12, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      {/* Camera = perspective container; floor + page share the same world, rotating and scaling around hero card center */}
      <AbsoluteFill style={{ perspective: 1400 }}>
        <div
          style={{
            position: 'absolute',
            width: 1920,
            height: 1080,
            transformOrigin: `${HERO.cx}px ${HERO.cy}px`,
            transform: `translate(${tx}px, ${ty}px) rotateX(${rotX}deg) scale(${scale})`,
            transformStyle: 'preserve-3d',
          }}
        >
          {/* Ground dot grid (rushes toward lens during dive = speed reference) */}
          <div style={{ ...floorStyle, opacity: 1 - 0.45 * Math.min(1, Math.max(0, p)) }} />
          {/* Ground contact shadow: isomorphic to page, tightens with landing */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: 1920,
              height: 1080,
              borderRadius: 18,
              background: 'rgba(22,24,34,1)',
              opacity: shOp,
              filter: `blur(${shBlur.toFixed(1)}px)`,
              transform: `translate3d(${(shOff * 0.5).toFixed(1)}px, ${shOff.toFixed(1)}px, 1px) scale(${(1 + lift * 0.0004).toFixed(4)})`,
            }}
          />
          {/* Page body: hovering at height `lift` above ground */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: 1920,
              height: 1080,
              borderRadius: 16,
              overflow: 'hidden',
              transform: `translateZ(${lift.toFixed(2)}px)`,
              boxShadow: '0 0 0 1px rgba(20,22,28,0.10)',
            }}
          >
            <div style={{ width: 1920 * Z, height: 1080 * Z, transform: `scale(${1 / Z})`, transformOrigin: '0 0' }}>
              <div style={{ zoom: Z }}>
                <FakeDashboard variant="A" />
              </div>
            </div>
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// Focus after settling: subtle dimming outside hero card (screen space, hero already centered), visible only during still hold
const Focus: React.FC = () => {
  const frame = useCurrentFrame();
  const k = ramp(frame, LAND_END - 6, 22, EASE.out);
  if (k <= 0) return null;
  // Screen size of hero card at destination = 524×454 × 1.35
  const hw = (HERO.w * 1.35) / 2 + 40;
  const hh = (HERO.h * 1.35) / 2 + 40;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none',
        opacity: k,
        background: `radial-gradient(${hw * 1.9}px ${hh * 1.9}px at 50% 50%, rgba(14,16,24,0) 48%, rgba(14,16,24,0.13) 100%)`,
      }}
    />
  );
};

export const DroneDiveLanding: React.FC = () => (
  <AbsoluteFill>
    {/* Static background placed outside motion blur: multi-sample accumulation across large gradients causes banding */}
    <Backdrop tone="light" light={{ x: 0.5, y: 0.12 }} grain={0} vignette={0.16} />
    <CameraMotionBlur shutterAngle={220} samples={12}>
      <Scene />
    </CameraMotionBlur>
    <Focus />
    {/* Grain placed outside motion blur: prevents being averaged out by multi-sampling */}
    <Grain opacity={0.06} />
  </AbsoluteFill>
);
