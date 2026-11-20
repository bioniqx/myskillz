// Ink bleed reveal: Ink wash transition using track mattes.
// Outgoing scene: Chapter half-title page on warm white paper (monospace chapter number + serif title + hairline rule + subhead) with static paper grain.
// Incoming scene FakeDashboard(A) inside SVG <foreignObject> with <mask>: a white circle at ink drop origin (800, 420) acts as track matte.
// Three ink layers (outer to inner):
// 1. Wet halo: A faint dark ring where water soaks paper (large radius, heavy feathering);
// 2. Ink fringe: Deep indigo fibrous bleeding edge, radius leading incoming scene by 20–42px:
//    outer edge translucent with heavy feathering, inner core dense, reading as "wet ink";
// 3. Incoming scene: "Develops" behind ink edge, content always sharp, subtle scale-in 1.035 -> 1 (developing photo feel).
// All 3 mask circles share feTurbulence (baseFrequency 0.02, octaves 3, fixed seed 7) + feDisplacementMap
// (scale 60 -> 160 ramping with frame) for fibrous bleeding edges—the filter displaces mask geometry only, never scene pixels.
// Pacing: 0–14 hold outgoing scene -> 14–22 ink drop impact (small dot overshoots downward) -> 20–98 radius 0 -> 1450
// (Easing.out(quad)) with ±8% low-frequency sine wobble (fading to 0 at frames 78–98, soaking full frame) ->
// 100–130 mask removed to render incoming scene directly, true static hold for 30f.
import React, { useId } from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';
import { EASE, FONT, ramp, mix, Grain } from '../../_fixtures/Polish';

export const INK_BLEED_REVEAL_DURATION = 130;

const SERIF = 'ui-serif, "New York", "Iowan Old Style", Georgia, "Times New Roman", serif';
const PAPER = '#f3efe6'; // Warm white paper
const INK = '#1a1c29'; // Ink tone with slight indigo tint (avoids pure black)
const PAPER_INK = '#2a2620'; // Printed typography ink color

// Outgoing scene: Chapter title page (paper + print typography)—title is video-shotcraft brand slogan, subhead is promo tagline
const PaperPage: React.FC = () => (
  <div style={{
    position: 'absolute', inset: 0, background: `radial-gradient(ellipse 80% 70% at 42% 38%, #f8f5ee 0%, ${PAPER} 55%, #e9e4d8 100%)`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    <div style={{ textAlign: 'center', color: PAPER_INK }}>
      <div style={{ fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.32em', color: '#8a8173', marginBottom: 34 }}>
        CHAPTER 02
      </div>
      <div style={{ fontFamily: SERIF, fontSize: 112, fontWeight: 500, lineHeight: 1.04, letterSpacing: '-0.025em' }}>
        Frame motion.
        <br />
        <span style={{ fontStyle: 'italic' }}>Craft the shot.</span>
      </div>
      <div style={{ width: 120, height: 1.5, background: '#b7ab97', margin: '44px auto 30px' }} />
      <div style={{ fontFamily: SERIF, fontSize: 34, color: '#6f675a', letterSpacing: '-0.005em' }}>
        Every shot, tuned in one place.
      </div>
    </div>
    {/* Paper texture: static grain (huge step = no frame swapping, constant pixels during hold) */}
    <Grain opacity={0.07} step={100000} freq={0.9} blend="multiply" />
  </div>
);

export const InkBleedReveal: React.FC = () => {
  const frame = useCurrentFrame();
  // Filter/mask IDs generated per instance to avoid clashes (clean colons from useId which are invalid in url())
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const bleedId = `inkBleed-${uid}`;
  const featherId = `inkFeather-${uid}`;
  const haloId = `inkHalo-${uid}`;
  const maskNew = `inkMaskNew-${uid}`;
  const maskInk = `inkMaskInk-${uid}`;
  const maskHalo = `inkMaskHalo-${uid}`;

  // Ink drop origin: upper-left off-center
  const cx = 800;
  const cy = 420;

  // Base radius: frames 20–98, 0 -> 1450px (furthest corner ~1300px + 150px bleed displacement margin)
  const baseR = interpolate(frame, [20, 98], [0, 1450], {
    easing: Easing.out(Easing.quad),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // ±8% low-frequency sine wobble = organic non-uniform spreading; amplitude decays to 0 across frames 78–98 for clean freeze
  const wobbleEnv = interpolate(frame, [78, 98], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const r = Math.max(0, baseR * (1 + 0.08 * Math.sin(frame * 0.32) * wobbleEnv));
  // Ink fringe lead distance: narrow at start (20px), widest mid-bleed (~42px)—ink runs ahead on paper, scene follows
  const lead = 20 + 22 * Math.sin(Math.PI * ramp(frame, 20, 78, EASE.linear));
  const rInk = r > 0.5 ? r + lead : 0; // Ink fringe outer edge (translucent, heavily feathered)
  const rCore = r > 0.5 ? r + lead * 0.45 : 0; // Ink core (dense, lightly feathered)
  // Wet halo: expands ~110px beyond ink fringe, very faint
  const rHalo = r > 0.5 ? r + lead + 110 : 0;

  // Bleed divergence: displacement scale 60 -> 160 (edges spread more raggedly with longer fibrous tendrils)
  const dispScale = interpolate(frame, [20, 98], [60, 160], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  // Ink drop: small droplet falls with overshoot across 14–22f, then absorbed into spreading ink edge
  const drop = ramp(frame, 14, 8, EASE.overshoot);
  const dropR = 16 * drop;

  // Incoming scene reveal: scale 1.035 -> 1 (20–100f, ease-out), must return precisely to 1 before unmasking
  const develop = mix(1.035, 1, ramp(frame, 20, 80, EASE.out));

  // At frame 100+ mask is fully white: remove SVG to render scene directly, guaranteeing pixel-perfect freeze
  const settled = frame >= 100;

  return (
    <div style={{ width: 1920, height: 1080, background: PAPER, position: 'relative', overflow: 'hidden' }}>
      {!settled && <PaperPage />}

      {settled ? (
        <div style={{ position: 'absolute', inset: 0 }}>
          <FakeDashboard variant="A" />
        </div>
      ) : (
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute', inset: 0, display: 'block' }}>
          <defs>
            {/* Filter applies only to mask circle—distorting mask edge, not scene content */}
            <filter id={bleedId} x="-40%" y="-40%" width="180%" height="180%">
              <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="7" result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale={dispScale} xChannelSelector="R" yChannelSelector="G" />
            </filter>
            {/* Ink fringe: same fibrous displacement + 1.6px feathering = soft wet-ink edge */}
            <filter id={featherId} x="-40%" y="-40%" width="180%" height="180%">
              <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="7" result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale={dispScale * 1.08} xChannelSelector="R" yChannelSelector="G" result="d" />
              <feGaussianBlur in="d" stdDeviation="3.2" />
            </filter>
            <filter id={`${featherId}c`} x="-40%" y="-40%" width="180%" height="180%">
              <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="3" seed="7" result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale={dispScale * 1.03} xChannelSelector="R" yChannelSelector="G" result="d" />
              <feGaussianBlur in="d" stdDeviation="1" />
            </filter>
            {/* Wet halo: heavily feathered, leaving subtle ambient darkening */}
            <filter id={haloId} x="-40%" y="-40%" width="180%" height="180%">
              <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="7" result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale={dispScale * 1.3} xChannelSelector="R" yChannelSelector="G" result="d" />
              <feGaussianBlur in="d" stdDeviation="34" />
            </filter>
            <mask id={maskHalo} maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
              <rect x="0" y="0" width="1920" height="1080" fill="black" />
              {rHalo > 0 && <circle cx={cx} cy={cy} r={rHalo} fill="white" filter={`url(#${haloId})`} />}
            </mask>
            <mask id={maskInk} maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
              <rect x="0" y="0" width="1920" height="1080" fill="black" />
              {rInk > 0 && <circle cx={cx} cy={cy} r={rInk} fill="white" filter={`url(#${featherId})`} />}
              {dropR > 0.5 && <circle cx={cx} cy={cy} r={dropR} fill="white" />}
            </mask>
            <mask id={`${maskInk}c`} maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
              <rect x="0" y="0" width="1920" height="1080" fill="black" />
              {rCore > 0 && <circle cx={cx} cy={cy} r={rCore} fill="white" filter={`url(#${featherId}c)`} />}
              {dropR > 0.5 && <circle cx={cx} cy={cy} r={dropR * 0.86} fill="white" />}
            </mask>
            <mask id={maskNew} maskUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080">
              <rect x="0" y="0" width="1920" height="1080" fill="black" />
              {r > 0.5 && <circle cx={cx} cy={cy} r={r} fill="white" filter={`url(#${bleedId})`} />}
            </mask>
          </defs>
          {/* 1. Wet halo */}
          <rect x="0" y="0" width="1920" height="1080" fill="#5a4e3a" opacity={0.12} mask={`url(#${maskHalo})`} />
          {/* 2. Ink fringe (includes impact droplet) */}
          <rect x="0" y="0" width="1920" height="1080" fill={INK} opacity={0.42} mask={`url(#${maskInk})`} />
          <rect x="0" y="0" width="1920" height="1080" fill={INK} opacity={0.86} mask={`url(#${maskInk}c)`} />
          {/* 3. Incoming scene reveal */}
          <g mask={`url(#${maskNew})`}>
            <foreignObject x="0" y="0" width="1920" height="1080">
              <div style={{ width: 1920, height: 1080, transform: `scale(${develop})`, transformOrigin: `${cx}px ${cy}px` }}>
                <FakeDashboard variant="A" />
              </div>
            </foreignObject>
          </g>
        </svg>
      )}
    </div>
  );
};
