// brace-expand — Brace Expand Reveal (bracket curtain reveal)
// A tight pair of curly braces appears centered at small scale, then springs open left and right with an overshoot while scaling up to title size; the title between the braces reveals from the center like a parted curtain (clip width strictly bound to brace distance), with tracking relaxing slightly after settling.
//
// Round 2 redesign (midnight / developer keynote title card):
// - look = midnight. Composition is a tech product launch title card: monospace 300px electric blue braces (with glow) framing 164px weight-800
//   brand name "video-shotcraft" (all lowercase, text width flush with brace inner cavity); monospace kicker "// shot recipes for your agent" above,
//   subtitle below (brand motto Frame motion. Craft the shot.) revealing word-by-word. Background features an editor-style dot matrix grid
//   (radial fade) + top light + horizon light ribbon, with a cool specular reflection below the braces.
// - Opening: frame 0 has a blinking input cursor at the center (editor feel, not an empty frame); at 6f, the cursor is hard-cut replaced by a tight 0.4x pair of brackets
//   "{}" (snapping into place without fading) — first establishing "this is a pair of braces".
// - Primary action: physical spring ex starting at 14f (damping 14 / stiffness 130: reaches target in ~8f, overshoot peak ~11f ≈9%, one rebound);
//   sc = mix(0.4, 1, ex), curtain half-width x = (HALF - innerEdge) * ex * sc, displacement multiplied with scaling (scale itself pushes braces outward);
//   brace center = ±(x + innerEdge * sc), text clip width = 2x, strictly bound to brace inner edge, sharing the same sc. Braces add directional motion blur from horizontal velocity, settling to 0.
// - Aftermath: tracking relaxes from -0.05em -> -0.03em after settling (breathing room), brace glow decays from peak; kicker and subtitle enter afterwards.
//
// Schedule (30fps, 120f total):
//   0–6     Cursor blinking (centered, present from frame 0)
//   6–14    Small braces "{}" hard-cut appear, hold for 8f
//   14–38   Spring expand: spring reaches target in ~22f, overshoot peak ~25f ≈9%, settles by ~38f; text is "pulled" out from center
//   40–64   Relaxation: tracking -0.05 -> -0.03em (smooth), glow decays
//   44–80   Kicker tracking closes in (44f), subtitle reveals word-by-word (from 54f)
//   80–120  Hold: subtle camera push-in 1 -> 1.012
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, glow, springAt, type } from '../../_fixtures/Look';
import { BRAND, PITCH } from '../../_fixtures/Brand';

export const BRACE_EXPAND_DURATION = 120;

const L = LOOKS.midnight;
const CY = 520; // Headline center line
const HALF = 676; // Final half-distance between brace centers (px)
const BRACE_FS = 300; // Final brace font size
const BRACE_INNER = 64; // Distance from brace glyph center to inner edge (* sc), clip starts here
const TITLE = BRAND.name; // Wordmark lowercase
const TITLE_FS = 164; // Text width ≈ inner cavity width 2*(HALF - innerEdge): fully revealed only at full stretch (adjust HALF or font size if changing copy)
const APPEAR = 6;
const EXPAND = 14;

const expandAt = (f: number) => (f < EXPAND ? 0 : springAt(f, EXPAND, { damping: 14, stiffness: 130 }));
// Curtain half-width x = (HALF - innerEdge) * ex * sc; brace center = ±(x + innerEdge * sc) — when ex=0 inner edges touch forming "{}"
const braceX = (f: number) => {
  const ex = expandAt(f);
  return (HALF - BRACE_INNER) * ex * mix(0.4, 1, ex);
};

const Brace: React.FC<{ ch: string; x: number; sc: number; v: number; glowK: number }> = ({ ch, x, sc, v, glowK }) => (
  <SpeedBlur vx={v} amount={0.22} max={16}>
    <div style={{
      position: 'absolute', left: 960 + x, top: CY, transform: `translate(-50%, -52%) scale(${sc.toFixed(4)})`,
      fontFamily: FONT.mono, fontSize: BRACE_FS, fontWeight: 500, lineHeight: 1, color: L.accent,
      textShadow: glow(L.accent, 0.5 + 0.5 * glowK),
    }}>{ch}</div>
  </SpeedBlur>
);

export const BraceExpand: React.FC = () => {
  const frame = useCurrentFrame();
  const on = frame >= APPEAR;
  const ex = expandAt(frame);
  const sc = mix(0.4, 1, ex);
  const x = braceX(frame);
  const v = braceX(frame + 0.5) - braceX(frame - 0.5); // Brace horizontal velocity (px/frame)

  // Text reveal width: strictly bound to brace inner edges (= 2x), 14px feathering on both sides (collapses when narrow)
  const clipW = Math.max(0, 2 * x);
  const bx = x + BRACE_INNER * sc; // Brace center
  const feather = Math.min(14, clipW / 4);
  const mask = `linear-gradient(90deg, transparent 0px, #000 ${feather}px, #000 calc(100% - ${feather}px), transparent 100%)`;

  // Post-settle tracking relaxation + glow decay (glow peak tracks overshoot)
  const relax = ramp(frame, 40, 24, EASE.smooth);
  const ls = mix(-0.05, -0.03, relax);
  const glowK = Math.min(1, ex) * (1 - ramp(frame, 34, 30, EASE.out));

  // Cursor: 0-6f blinking
  const caretOn = !on && Math.floor(frame / 3) % 2 === 0;

  const cam = 1 + 0.012 * ramp(frame, 70, 50, EASE.smooth);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.02 }} fill={null} horizon={0.66} breathe={0.4}>
        {/* Editor dot matrix: 32px grid, bright center, fading toward edges */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: `radial-gradient(circle, ${alpha('#a9bcff', 0.16)} 1.4px, transparent 1.8px)`,
          backgroundSize: '32px 32px', backgroundPosition: '16px 8px',
          WebkitMaskImage: 'radial-gradient(ellipse 60% 55% at 50% 48%, #000 0%, rgba(0,0,0,0.35) 55%, transparent 85%)',
          maskImage: 'radial-gradient(ellipse 60% 55% at 50% 48%, #000 0%, rgba(0,0,0,0.35) 55%, transparent 85%)',
        }} />
        {/* Cool specular reflection ribbon below braces (broadens as braces expand) */}
        <div style={{
          position: 'absolute', left: 960 - (x + 120), width: 2 * (x + 120), top: CY + 150, height: 90,
          background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.22 * Math.min(1, ex))} 0%, ${alpha(L.accent, 0)} 70%)`,
        }} />
      </Stage>

      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam.toFixed(5)})`, transformOrigin: `50% ${CY}px` }}>
        {/* Kicker: monospace comment */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: CY - 248, textAlign: 'center', color: L.accent2,
          ...type(32, 500, { mono: true }), letterSpacing: `${mix(0.5, 0.08, ramp(frame, 44, 20, EASE.snappy)).toFixed(3)}em`,
          opacity: ramp(frame, 44, 14, EASE.out),
        }}>// shot recipes for your agent</div>

        {/* Headline: clip width bound to brace gap (curtain effect, not fade or typewriter) */}
        {on && (
          <div style={{
            position: 'absolute', left: 960 - clipW / 2, width: clipW, top: CY - 110, height: 220, overflow: 'hidden',
            WebkitMaskImage: mask, maskImage: mask,
          }}>
            <div style={{
              position: 'absolute', left: clipW / 2, top: 110, transform: `translate(-50%, -54%) scale(${sc.toFixed(4)})`,
              fontFamily: FONT.sans, fontSize: TITLE_FS, fontWeight: 800, letterSpacing: `${ls.toFixed(4)}em`, lineHeight: 1,
              whiteSpace: 'nowrap',
              backgroundImage: 'linear-gradient(180deg, #ffffff 0%, #e8eeff 55%, #a9b9e8 100%)',
              WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent', paddingBottom: 8,
            }}>{TITLE}</div>
          </div>
        )}

        {on && <Brace ch="{" x={-bx} sc={sc} v={-v} glowK={glowK} />}
        {on && <Brace ch="}" x={bx} sc={sc} v={v} glowK={glowK} />}

        {/* Opening cursor */}
        {caretOn && (
          <div style={{
            position: 'absolute', left: 960 - 4, top: CY - 60, width: 8, height: 120, borderRadius: 2,
            background: L.accent, boxShadow: glow(L.accent, 0.6),
          }} />
        )}

        {/* Subtitle */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: CY + 170, textAlign: 'center', color: L.ink2, ...type(44, 450) }}>
          <TextReveal text={PITCH.en.motto} by="word" variant="blur" start={54} each={16} gap={3} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
