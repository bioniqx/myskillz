// sheen-sweep-retry — Single-point sheen sweep (high-standard retry): A diagonal specular band slowly sweeps across a dark hero card once, clipped by rounded corners, a silent coronation.
//
// Second-round redesign (Warm sand plinth · Titanium black membership card release):
// - look = sand (beige · terracotta). Hero shifts from a "PRO card on grey backdrop" to a 900×567 titanium black metallic card (video-shotcraft Director Card),
//   featuring brushed titanium texture (horizontal hairline grain) + laser-etched monochrome "Mirror Cut" emblem, video-shotcraft wordmark / cardholder / contactless icon + champagne gold chip,
//   layered with 8 stacked slices for metallic rim thickness. Positioned 3D-angled on the right (rotateY facing left text column, rotateX tilted slightly back), left column houses editorial headline
//   "Cinematic, / by default.".
// - Sheen sweep has physical motivation: As card slowly rotates toward light source (rotateY 21°->14°), the specular band sweeps across the surface — not a pasted-on overlay effect,
//   but a reflection driven by angular transition. Four strict constraints preserved: single target (only sweeps hero card), rounded corner clipping, sweeps exactly once, zero residual glow layers before/after.
// - Three-layer light band: Wide soft glow (0.14) + narrow specular core (0.5) screen-blended onto titanium black; where light passes, brushed hairline and etched typography are revealed
//   (bright duplicate pinned to card surface, unveiled by matching 115° moving mask), card's top edge hairline specular catches light simultaneously.
// - Spatial layout: Stage top-left key light + sand ground plinth; two soft drop shadows beneath card (contact shadow + ambient distance shadow) tighten with entrance elevation, outside 3D layer.
//
// Timeline (30fps, total 150f):
//   0–36    Card entrance: Rises from 120px below + settles at 21° (spring damping 24, slow, heavy, zero bounce luxury feel); shadows tighten 4f delayed
//   6–44    Left column: Overline tracking tightens -> Two headline lines emerge from baseline rule (7f stagger) -> Body text fades in and floats up
//   44–58   Hold: Card pauses motionless, allowing viewer to read card details first
//   58–90   Main action: Card turns toward light source (smooth in-out, to 96f) + specular band sweeps once (32f, swift)
//   92–108  Aftermath: CTA pill button rises
//   108–150 Hold: Card drifts imperceptibly (rotateY turns additional 1°, ease-out settle), clean poster composition at outro
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const SHEEN_SWEEP_RETRY_DURATION = 150;

const L = LOOKS.sand;

const W = 900;
const H = 567; // ISO card ratio 1.586
const R = 38;
const CX = 1262; // Card center x
const CY = 520;

const SWEEP_START = 58;
const SWEEP_END = 90;
const TURN_END = 96;

const ENGRAVE = '#57534d'; // Etched tone: Warm grey two steps brighter than titanium black base (readable even at rest)
const LIT = '#efe6d8'; // Specular reflection on etching under light band: Warm white

// Brushed titanium: Horizontal hairline grain (two staggered periodic layers for organic irregularity)
const BRUSH =
  'repeating-linear-gradient(180deg, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1px, transparent 1px, transparent 3px),' +
  'repeating-linear-gradient(180deg, rgba(0,0,0,0.25) 0px, rgba(0,0,0,0.25) 1px, transparent 1px, transparent 7px)';

// Etched emblem: Laser engraving uses monochromatic spec (viewfinder frame and diagonal cut share tone), emblem itself has zero glow / drop shadow
const Mark: React.FC<{ color: string; size?: number }> = ({ color, size = 66 }) => (
  <ShotcraftMark size={size} frameColor={color} cutColor={color} />
);

const Contactless: React.FC<{ color: string }> = ({ color }) => (
  <svg width={46} height={46} viewBox="0 0 24 24" style={{ display: 'block' }}>
    {[4.5, 8, 11.5].map((r, i) => (
      <path key={i} d={`M${6 + i * 3.2} ${12 - r * 0.7}a${r} ${r} 0 0 1 0 ${r * 1.4}`} fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
    ))}
  </svg>
);

// Card surface content (etched layer): tone = font color; lit = illuminated state under sheen sweep (color and shadow swap only)
const Face: React.FC<{ tone: string; lit?: boolean }> = ({ tone, lit }) => {
  // Etched relief: 1px bright bottom edge, 1px dark top edge (recessed groove); lit state switches to glow highlight
  const etch = lit ? `0 0 14px ${alpha(LIT, 0.5)}` : '0 1px 0 rgba(255,255,255,0.10), 0 -1px 0 rgba(0,0,0,0.6)';
  return (
    <div style={{ position: 'absolute', inset: 0, padding: '52px 60px 50px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', color: tone }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Mark color={tone} />
        <div style={{ ...type(42, 620), fontFamily: BRAND.font, letterSpacing: '0.01em', textShadow: etch }}>{BRAND.name}</div>
        <div style={{ marginLeft: 'auto', filter: lit ? `drop-shadow(0 0 8px ${alpha(LIT, 0.5)})` : undefined }}>
          <Contactless color={tone} />
        </div>
      </div>
      <div style={{ flex: 1 }} />
      <div style={{ display: 'flex', alignItems: 'flex-end' }}>
        <div>
          <div style={{ ...type(22, 600, { caps: true }), letterSpacing: '0.3em', opacity: 0.8, textShadow: etch }}>Director</div>
          <div style={{ ...type(36, 500, { mono: true }), letterSpacing: '0.16em', marginTop: 12, textShadow: etch }}>A. MORENO</div>
        </div>
        <div style={{ marginLeft: 'auto', ...type(30, 700, { caps: true }), letterSpacing: '0.34em', textShadow: etch }}>Studio</div>
      </div>
    </div>
  );
};

// Champagne gold chip: Brushed metal texture + contact pad segment dividers
const Chip: React.FC = () => (
  <div
    style={{
      position: 'absolute', left: 60, top: 212, width: 116, height: 88, borderRadius: 16, overflow: 'hidden',
      background: 'linear-gradient(135deg, #e9d3a6 0%, #b8955c 42%, #8c6a39 70%, #d9bd86 100%)',
      boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.5), inset 0 -1px 0 rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.5)',
    }}
  >
    <svg width={116} height={88} viewBox="0 0 116 88" style={{ position: 'absolute', inset: 0 }}>
      <g stroke="rgba(70,48,18,0.55)" strokeWidth={1.4} fill="none">
        <path d="M0 30H38M0 58H38M78 30H116M78 58H116M38 0V88M78 0V88" />
        <rect x={38} y={22} width={40} height={44} rx={9} />
      </g>
    </svg>
  </div>
);

export const SheenSweepRetry: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Card entrance: Slow spring, zero bounce ——
  const enter = springAt(frame, 0, { damping: 24, stiffness: 70, mass: 1.1 });
  const shadowIn = springAt(frame, 4, { damping: 24, stiffness: 70, mass: 1.1 }); // Shadow delayed by 4f
  // —— Turn toward light source: Synchronized with sheen sweep ——
  const turn = ramp(frame, SWEEP_START - 4, TURN_END - SWEEP_START + 4, EASE.smooth);
  const drift = ramp(frame, TURN_END, 150 - TURN_END, EASE.out);
  const rotY = mix(36, 21, enter) - 7 * turn - 1.5 * drift;
  const rotX = mix(16, 9, enter) - 1.5 * turn;
  const lift = mix(120, 0, enter) - 6 * drift;
  const scale = mix(0.94, 1, enter);
  const appear = ramp(frame, 0, 8, EASE.out);

  // —— Sheen sweep: Single pass, conditionally mounted ——
  const sweepOn = frame >= SWEEP_START && frame <= SWEEP_END;
  const p = ramp(frame, SWEEP_START, SWEEP_END - SWEEP_START, EASE.swift);
  // Light band center traverses from 0.45W left of card to 0.45W right of card; mask / light band width is 2W, centered at 50%
  const bandC = mix(-0.45 * W, 1.45 * W, p);
  const bandX = bandC - W;
  const bandMask = `linear-gradient(115deg, transparent 38%, #000 50%, transparent 62%)`;
  const topX = bandC + ((H / 2) * Math.cos((65 * Math.PI) / 180)) / Math.sin((115 * Math.PI) / 180);

  const cta = ramp(frame, 92, 16, EASE.snappy);

  return (
    <AbsoluteFill style={{ overflow: 'hidden', fontFamily: FONT.sans }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.08 }} fill={{ x: 0.9, y: 0.95 }} horizon={0.86} intensity={1}>
        {/* Plinth ground: Lower 1/4 subtle desktop vignetting + distant soft plinth rim */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 820, bottom: 0, background: `linear-gradient(180deg, ${alpha(L.shadow, 0)} 0%, ${alpha(L.shadow, 0.08)} 100%)` }} />
      </Stage>

      {/* Under-card drop shadows: Contact shadow (crisp & compact) + ambient distance shadow (diffuse & wide), tightening with entrance altitude */}
      <div
        style={{
          position: 'absolute', left: CX - W * 0.42 + 40, top: CY + H * 0.44 + mix(60, 0, shadowIn), width: W * 0.84, height: 70,
          borderRadius: '50%', background: alpha(L.shadow, mix(0.08, 0.34, shadowIn)), filter: 'blur(26px)', opacity: appear,
        }}
      />
      <div
        style={{
          position: 'absolute', left: CX - W * 0.5 + 90, top: CY + H * 0.3, width: W, height: 220,
          borderRadius: '50%', background: alpha(L.shadow, mix(0.05, 0.2, shadowIn)), filter: 'blur(70px)', opacity: appear,
        }}
      />

      {/* Hero card: 3D angled plinth view */}
      <div style={{ position: 'absolute', inset: 0, perspective: 2400, perspectiveOrigin: `${CX}px ${CY - 120}px` }}>
        <div
          style={{
            position: 'absolute', left: CX - W / 2, top: CY - H / 2, width: W, height: H, opacity: appear,
            transformStyle: 'preserve-3d',
            transform: `translateY(${lift.toFixed(2)}px) rotateX(${rotX.toFixed(3)}deg) rotateY(${rotY.toFixed(3)}deg) scale(${scale.toFixed(4)})`,
          }}
        >
          {/* Metallic rim thickness: 8 stacked layers forming ~6px depth, darker toward back */}
          {Array.from({ length: 8 }, (_, i) => (
            <div
              key={i}
              style={{
                position: 'absolute', inset: 0, borderRadius: R,
                transform: `translateZ(${(-(i + 1) * 0.8).toFixed(1)}px)`,
                background: i < 2 ? '#8d877e' : mix(0, 1, i / 7) > 0.5 ? '#2a2826' : '#5c5852',
              }}
            />
          ))}
          {/* Front face */}
          <div
            style={{
              position: 'absolute', inset: 0, borderRadius: R, overflow: 'hidden', // Rounded corner clip: all illumination clipped by card edge
              background: 'linear-gradient(140deg, #2d2b29 0%, #1b1a19 42%, #121110 72%, #1d1c1a 100%)',
              boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08), inset 0 1.5px 0 rgba(255,255,255,0.16)',
            }}
          >
            <div style={{ position: 'absolute', inset: 0, backgroundImage: BRUSH, opacity: 0.6 }} />
            {/* Static ambient light: Top-left key light direction */}
            <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 70% 90% at 12% 0%, rgba(255,240,220,0.09) 0%, rgba(255,240,220,0) 62%)' }} />
            <Chip />
            <Face tone={ENGRAVE} />

            {sweepOn && (
              <>
                {/* Under light band: Brushed grain catches specular reflection (fixed to card face, mask moves with light band) */}
                <div
                  style={{
                    position: 'absolute', inset: 0, backgroundImage: BRUSH.replace(/0\.05\)/g, '0.22)'), mixBlendMode: 'screen',
                    WebkitMaskImage: bandMask, maskImage: bandMask, WebkitMaskSize: `${2 * W}px 100%`, maskSize: `${2 * W}px 100%`,
                    WebkitMaskPosition: `${bandX.toFixed(1)}px 0`, maskPosition: `${bandX.toFixed(1)}px 0`,
                    WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat',
                  }}
                />
                {/* Under light band: Etched typography highlights */}
                <div
                  style={{
                    position: 'absolute', inset: 0,
                    WebkitMaskImage: bandMask, maskImage: bandMask, WebkitMaskSize: `${2 * W}px 100%`, maskSize: `${2 * W}px 100%`,
                    WebkitMaskPosition: `${bandX.toFixed(1)}px 0`, maskPosition: `${bandX.toFixed(1)}px 0`,
                    WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat',
                  }}
                >
                  <Face tone={LIT} lit />
                </div>
                {/* Broad soft wash + narrow hot core: Screen blended over titanium black */}
                <div
                  style={{
                    position: 'absolute', top: 0, left: bandX, width: 2 * W, height: H, mixBlendMode: 'screen', pointerEvents: 'none',
                    background:
                      'linear-gradient(115deg, transparent 36%, rgba(255,244,228,0.06) 43%, rgba(255,244,228,0.14) 47.5%, rgba(255,248,238,0.5) 50%, rgba(255,244,228,0.14) 52.5%, rgba(255,244,228,0.06) 57%, transparent 64%)',
                  }}
                />
                {/* Top edge hairline catches specular glint */}
                <div
                  style={{
                    position: 'absolute', left: 0, top: 0, right: 0, height: 2,
                    background: `linear-gradient(90deg, transparent ${(topX - 170).toFixed(1)}px, rgba(255,250,240,0.85) ${topX.toFixed(1)}px, transparent ${(topX + 170).toFixed(1)}px)`,
                  }}
                />
              </>
            )}
          </div>
        </div>
      </div>

      {/* Left column: Editorial headline block */}
      <div style={{ position: 'absolute', left: 150, top: 256, width: 640 }}>
        <div
          style={{
            ...type(24, 700, { caps: true }), color: L.accent, opacity: ramp(frame, 6, 18, EASE.out),
            letterSpacing: `${mix(0.5, 0.28, ramp(frame, 6, 26, EASE.snappy)).toFixed(3)}em`, display: 'flex', alignItems: 'center', gap: 16,
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: 5, background: L.accent, display: 'inline-block' }} />
          {BRAND.name}
        </div>
        <div style={{ marginTop: 34 }}>
          <TextReveal
            text={'Cinematic,\nby default.'}
            by="line"
            variant="rise"
            start={12}
            each={24}
            gap={7}
            style={{ ...type(118, 760), letterSpacing: '-0.045em', lineHeight: 1.06, color: L.ink }}
          />
        </div>
        <div
          style={{
            marginTop: 40, ...type(34, 450), lineHeight: 1.38, color: L.ink2,
            opacity: ramp(frame, 30, 18, EASE.out), transform: `translateY(${mix(14, 0, ramp(frame, 30, 22, EASE.snappy)).toFixed(1)}px)`,
          }}
        >
          Shot recipe cards for your agent.
          <br />
          From screenshot to showreel.
        </div>
        <div
          style={{
            marginTop: 48, display: 'inline-flex', alignItems: 'center', gap: 14, padding: '18px 30px', borderRadius: 999,
            background: L.ink, color: L.surface, ...type(30, 600),
            boxShadow: `0 10px 26px -10px ${alpha(L.shadow, 0.5)}`,
            opacity: cta, transform: `translateY(${mix(22, 0, cta).toFixed(1)}px)`,
          }}
        >
          Make your first film
          <span style={{ color: '#f0a07c' }}>→</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
