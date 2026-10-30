// aurora-bloom-bg-flip — Aurora Bloom rising aurora background flip (motion-lab native Remotion port)
// Light grey base lifts a purple-orange soft-focus blob from bottom; entire background plunges to near-black within 0.35s, collapsing blob into afterglow;
// Copy synchronously blurs out -> next line blurs in (accent tone -> white resolve), with empty gap between lines (no cross-fade).
// Copy represents video-shotcraft narrative turning point (Promos took weeks -> Meet video-shotcraft); purple-orange blob/text is the signature
// light color of this effect (DEEPP constant), fully adaptable to project palette on implementation.
// Design coordinates 480×270 (scaled proportionally via DesignStage), parameter values calibrated to this space.
//
// Polish upgrade: Aurora split into 4 layers ("Main purple + Orange core + Magenta transition + White rim melt") with independent relative drift, letting orange core genuinely shine through;
// Flip moment features gentle blob compression (scale −6%) reading as "compressed into afterglow", magenta layer preserves hue preventing muddy grey in dark field;
// Top soft ambient light in light mode / cool skylight in dark mode ensure neither backdrop is flat; full-frame grain prevents banding.
// Copy: Phrase A features subtle camera push during rest phase (preventing dead frames), drifting upward with light during blur-out; Phrase B blurs in with 6px upward settle;
// Global timeline shifted forward by ≈0.06, Phrase B color resolves by t≈0.90, leaving ≈0.5s static freeze at outro (original kept purple text until end).
import React from 'react';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { EASE, FONT as PF, Grain, Vignette } from '../../_fixtures/Polish';
import { BRAND } from '../../_fixtures/Brand';

export const AURORA_BLOOM_BG_FLIP_DURATION = 156; // 5200ms @30fps

// RGB triplet interpolation -> CSS color (effect.js file-level shared mix, inlined here)
const mix = (a: number[], b: number[], k: number) =>
  `rgb(${Math.round(a[0] + (b[0] - a[0]) * k)},${Math.round(a[1] + (b[1] - a[1]) * k)},${Math.round(a[2] + (b[2] - a[2]) * k)})`;
const DEEPP = [124, 92, 255]; // Effect signature light color (deep purple)
const WHITE = [245, 245, 250];
const LIGHT = [236, 236, 236]; // Light mode background
const DARK = [10, 10, 18]; // Dark mode background
const INK = [22, 23, 28]; // Light mode typography (cool near-black)

// Copy (word count / lengths mirror original "For many years / everything changed", pacing depends on this):
// Phrase A has 3 words highlighting old pain points; Phrase B has 2 words revealing brand name (lowercase wordmark)
const WA = 'Promos took weeks'.split(' ');
const WB = ['Meet', BRAND.name];

// Timeline (normalized t)
const RISE: [number, number] = [0.04, 0.56]; // Aurora rising
const FLIP: [number, number] = [0.57, 0.64]; // Background flip ≈0.36s (core mechanic)
const A_OUT = 0.4; // Phrase A first word starts blur-out (stagger 0.04, 0.10 each) -> settles by 0.58
const B_IN = 0.7; // Phrase B first word blur-in (stagger 0.05, 0.11 each); 0.12 ≈ 0.6s empty text pause

export const AuroraBloomBgFlip: React.FC = () => {
  const t = useT();
  // Blob rise + expansion
  const rise = seg(t, RISE[0], RISE[1], E.outCubic);
  const flip = seg(t, FLIP[0], FLIP[1], E.inOutQuad); // Rapid plunge to dark, intentionally swift at ~0.35s
  // Gentle compression of blob group during flip: Compression into afterglow with slight damped rebound (overshoot reads as pressed down then stabilized)
  const squash = seg(t, FLIP[0], FLIP[1] + 0.06, EASE.overshoot);
  // Relative drift of orange core / magenta layer (asynchronous frequencies and phases, internal blob fluidity rather than rigid translation)
  const drift = Math.sin(t * Math.PI * 2.2);
  const drift2 = Math.sin(t * Math.PI * 1.6 + 1.1);

  const blob = (style: React.CSSProperties, color: string, stop = 68): React.CSSProperties => ({
    position: 'absolute',
    borderRadius: '50%',
    filter: 'blur(60px)',
    background: `radial-gradient(circle,${color} 0%,${color.replace(/[\d.]+\)$/, '0)')} ${stop}%)`,
    ...style,
  });

  return (
    <DesignStage bg={mix(LIGHT, DARK, flip)}>
      {/* Light mode top soft light (collapses on flip) + Dark mode cool skylight (appears post-flip), directional lighting on both fields */}
      <div
        style={{
          position: 'absolute', inset: 0, opacity: 1 - flip,
          background: 'radial-gradient(ellipse 70% 60% at 50% 8%, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0) 70%)',
        }}
      />
      <div
        style={{
          position: 'absolute', inset: 0, opacity: flip,
          background: 'radial-gradient(ellipse 80% 60% at 50% 0%, rgba(70,72,120,0.22) 0%, rgba(70,72,120,0) 70%)',
        }}
      />
      {/* Soft-focus blob group: Global translateY rise + scale expansion, compressed into afterglow after flip */}
      <div
        style={{
          position: 'absolute',
          inset: '-10%',
          transform: `translateY(${lerp(rise, 32, -6)}%) scale(${lerp(rise, 1, 1.25) * (1 - 0.06 * squash)})`,
          opacity: lerp(flip, 1, 0.4),
        }}
      >
        {/* Purple primary blob */}
        <div style={blob({ left: '8%', bottom: '-45%', width: '90%', height: '85%' }, 'rgba(107,79,224,.85)')} />
        {/* Magenta transition layer: Intermediate hue between purple and orange, preventing muddy grey bands */}
        <div
          style={blob(
            { left: '22%', bottom: '-36%', width: '60%', height: '58%', transform: `translateX(${drift2 * 6}%)` },
            'rgba(176,86,170,.6)', 64,
          )}
        />
        {/* Orange core: Slow horizontal drift, slightly higher than primary layer, emerging first on rise */}
        <div
          style={blob(
            { left: '32%', bottom: '-18%', width: '44%', height: '46%', transform: `translateX(${drift * 8}%)` },
            'rgba(217,122,74,.9)', 66,
          )}
        />
        {/* White melting edge: Collapses in dark field */}
        <div
          style={{
            ...blob({ left: '-12%', bottom: '-40%', width: '64%', height: '60%' }, 'rgba(255,255,255,.8)', 62),
            opacity: 1 - flip,
          }}
        />
      </div>

      {/* Copy lines: Flex center, both phrases positioned absolute (centered on same origin, non-colliding) */}
      <div
        style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: PF.sans, fontWeight: 600, fontSize: 26, letterSpacing: '-0.022em',
        }}
      >
        {/* Copy A: Subtle push during hold phase, staggered blur-out as blob ascends (drifting upward as light consumes it) */}
        <div style={{ position: 'absolute', transform: `scale(${lerp(seg(t, 0, A_OUT + 0.18, EASE.swift), 1, 1.035)})` }}>
          {WA.map((w, i) => {
            const out = seg(t, A_OUT + i * 0.04, A_OUT + 0.1 + i * 0.04, E.inQuad);
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  margin: '0 .16em',
                  color: mix(INK, INK, 0), // Light mode text color
                  opacity: 1 - out,
                  filter: out > 0.005 ? `blur(${out * 8}px)` : 'none',
                  transform: `translateY(${-out * 5}px)`,
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
        {/* Post-gap Copy B: Staggered blur-in + upward settle + purple->white resolve (turning white on landing = locked in) */}
        <div style={{ position: 'absolute' }}>
          {WB.map((w, i) => {
            const d0 = B_IN + i * 0.05;
            const a = seg(t, d0, d0 + 0.11, E.outQuint);
            const c = seg(t, d0 + 0.06, d0 + 0.15, E.outQuad);
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  margin: '0 .16em',
                  opacity: a,
                  filter: a < 0.995 ? `blur(${(1 - a) * 8}px)` : 'none',
                  transform: `translateY(${(1 - a) * 6}px)`,
                  color: mix(DEEPP, WHITE, c),
                  // Purple glyphs carry subtle self-illumination prior to resolve, extinguished once turned white
                  textShadow: `0 0 ${10 * (1 - c)}px rgba(124,92,255,${(0.45 * a * (1 - c)).toFixed(3)})`,
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
      </div>

      <Vignette strength={lerp(flip, 0.07, 0.55)} inner={0.45} color="#0c0c16" />
      <Grain opacity={lerp(flip, 0.05, 0.09)} blend="soft-light" scale={0.25} />
    </DesignStage>
  );
};
