// riso-misregistration-hit — Risograph misregistration impact frame: Headline slam-stops and splits instantly into two monochrome "plates"
// (mix-blend-mode: multiply over paper), mimicking risograph printing plates drifting out of alignment; two plates diverge in opposite directions (predominantly x, slight y)
// undergoing damped oscillation offset = A·cos(ωt)·exp(-t/τ) over two shakes, snapping hard back into perfect register at frame 72 with a 4f scale impulse settle.
//
// Second-round redesign (Two-color risograph gig poster · Fluorescent pink x Blue):
// - Custom palette: Recycled newsprint #f3eee2 + two risograph inks — Fluorescent pink FLUO #ff4fa3 and Blue BLUE #1f5fc4.
//   In perfect register they multiply into deep purple ink (identical letterforms aligned); when displaced, they reveal pink and blue fringe edges — quintessential riso misregistration.
// - Layout: Swiss grid poster (video-shotcraft riso promo poster). Left-aligned 300px bold two-line headline "CRAFT IT / LOUD." stamped over a large halftone dot sun on the right
//   (pink plate, dot size decreasing radially = genuine halftone), top colophon, bottom 3-column feature highlights (blue plate). Only headline plates separate;
//   background elements remain pinned in register (full-frame misregistration reads as video glitch rather than print defect).
// - Rhythm: Opening sun wipes down like an ink roller across paper (0–16f), info columns stagger into place -> Headline slams in with 8f ease-in
//   -> Impact frame triggers plate separation + 1.2% whole-page screen recoil -> 44f damped oscillation -> 72f hard snap back to register + "ON REGISTER" circular seal stamps down
//   (seal center houses monochrome Mirror Cut emblem — BRAND.md mandates mono edition for single-ink reproduction, printed on blue plate)
//   -> 44f clean hold (subtle camera push).
//
// Timeline (30fps, total 120f):
//   0–18    Preparation: Paper substrate and colophon present from frame 1; sun ink-roller wipe 0–16f; bottom info columns stagger 4–18f
//   20–28   Main action: Headline slams in from off-screen right with ease-in(cubic) (directional velocity blur), impacts at 28f
//   28–71   Aftermath: Dual plates oscillate in counter-phase (period 18f, τ 60f, ~11px single-plate residual remaining prior to 72f)
//   72–76   Register snap: Hard cut to zero offset + 4f scale 1.03->1; circular seal stamps at 72f (scale 1.5->1, 4f)
//   76–120  Hold 44f: Camera smoothly pushes 1.000->1.012 (converging ~110f), ending frames nearly static
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { EASE, FONT, Grain, SpeedBlur, Vignette, bezier, mix, ramp, velocity } from '../../_fixtures/Polish';
import { MARK_PATHS } from '../../_fixtures/Brand';

export const RISO_MISREGISTRATION_HIT_DURATION = 120;

const HIT = 28; // Impact touchdown frame
const SNAP = 72; // Snap-to-register frame
const AX = 20; // Single-plate x misregistration amplitude (plates counter-offset -> total ~40px separation; noticeable under 300px type)
const AY = 8; // Single-plate y misregistration amplitude (subtle, authenticating plate misalignment)
const OMEGA = (2 * Math.PI) / 18; // Oscillation angular frequency 18f, 2.5 cycles across 44f window
const TAU = 60; // Slow decay: visible residual offset remains prior to frame 72, then snaps cleanly to zero

const PAPER = '#f3eee2'; // Recycled newsprint
const FLUO = '#ff4fa3'; // Risograph fluorescent pink ink plate
const BLUE = '#1f5fc4'; // Risograph blue ink plate
const inCubic = bezier(0.55, 0.055, 0.675, 0.19);
const SANS = FONT.sans;

// Monochrome ink plate: Shared glyphs, tinted and offset independently, multiplied over paper
const Plate: React.FC<{ color: string; dx: number; dy: number; scale?: number }> = ({ color, dx, dy, scale = 1 }) => (
  <div style={{
    position: 'absolute', left: 120, top: 250,
    transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${scale})`, transformOrigin: '30% 60%',
    mixBlendMode: 'multiply', color, fontFamily: SANS, fontWeight: 900, fontSize: 300, lineHeight: 0.84,
    letterSpacing: '-0.045em', whiteSpace: 'nowrap',
  }}>
    {/* Top bars of F and T meet exactly under -0.045em tracking; anti-aliasing leaves a hairline seam — tighten 0.01em after F to overlap strokes */}
    <div>CRA<span style={{ marginRight: '-0.01em' }}>F</span>T IT</div>
    <div>LOUD.</div>
  </div>
);

// Halftone sun: Pink plate, dots arranged on grid, dot diameter scales down with radial distance (genuine halftone, not uniform dot matrix)
const SUN_R = 372;
const SUN_STEP = 22;
const SUN_DOTS = (() => {
  const out: { x: number; y: number; r: number }[] = [];
  const n = Math.ceil(SUN_R / SUN_STEP);
  for (let iy = -n; iy <= n; iy++) {
    for (let ix = -n; ix <= n; ix++) {
      // 45° screen angle: Odd rows offset by half cell
      const x = ix * SUN_STEP + (iy % 2 ? SUN_STEP / 2 : 0);
      const y = iy * SUN_STEP * 0.866;
      const d = Math.hypot(x, y) / SUN_R;
      if (d > 1) continue;
      const tone = 1 - Math.pow(d, 2.4); // Solid core, dot size tapers to 0 at perimeter (circular silhouette rather than hexagonal grid)
      const r = (SUN_STEP / 2) * 1.1 * Math.sqrt(tone);
      if (r > 0.9) out.push({ x, y, r });
    }
  }
  return out;
})();

const Sun: React.FC<{ reveal: number }> = ({ reveal }) => (
  <svg width={SUN_R * 2 + 40} height={SUN_R * 2 + 40} viewBox={`${-SUN_R - 20} ${-SUN_R - 20} ${SUN_R * 2 + 40} ${SUN_R * 2 + 40}`}
    style={{
      position: 'absolute', left: 1090, top: 108, mixBlendMode: 'multiply',
      // Ink roller wipe: Top-to-bottom hard-edge mask (printing rolls across once, never dissolves)
      clipPath: `inset(0 0 ${((1 - reveal) * 100).toFixed(2)}% 0)`,
    }}>
    <g fill={FLUO}>
      {SUN_DOTS.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={d.r} />)}
    </g>
  </svg>
);

// Registration mark crosshair: Static layout anchor
const RegMark: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <svg width={40} height={40} viewBox="0 0 40 40" style={{ position: 'absolute', left: x - 20, top: y - 20, mixBlendMode: 'multiply' }}>
    <g fill="none" stroke={BLUE} strokeWidth={1.6} opacity={0.75}>
      <circle cx={20} cy={20} r={9} />
      <path d="M20 1 V39 M1 20 H39" />
    </g>
  </svg>
);

// Circular seal: "ON REGISTER" stamped on registration frame (blue plate, circular typography + central monochrome Mirror Cut emblem; emblem counter-rotates 14° to stay upright)
const Stamp: React.FC<{ s: number; o: number }> = ({ s, o }) => (
  <svg width={300} height={300} viewBox="-130 -130 260 260"
    style={{ position: 'absolute', left: 1480, top: 500, mixBlendMode: 'multiply', opacity: o, transform: `rotate(-14deg) scale(${s.toFixed(4)})` }}>
    <defs>
      <path id="rmh-ring" d="M -88 0 A 88 88 0 1 1 88 0 A 88 88 0 1 1 -88 0" />
    </defs>
    <g fill="none" stroke={BLUE} strokeWidth={5}>
      <circle r={122} />
      <circle r={66} strokeWidth={3} />
    </g>
    <text fill={BLUE} style={{ fontFamily: FONT.mono, fontSize: 28, fontWeight: 700 }}>
      <textPath href="#rmh-ring" textLength={540} lengthAdjust="spacing">ON REGISTER ✶ SHOTCRAFT ✶</textPath>
    </text>
    {/* Emblem bounding box x16–120 / y16–112, center (68,64); scaled to ~66px wide inside inner radius r66 */}
    <g transform="rotate(14) scale(0.64) translate(-68 -64)" fill={BLUE}>
      <path d={MARK_PATHS.frame} />
      <path d={MARK_PATHS.cut} />
    </g>
  </svg>
);

// Impact displacement: Off-screen right 1700px -> 0, 8f ease-in(cubic) (accelerated slam-stop)
const slideAt = (f: number) => mix(1700, 0, ramp(f, 20, HIT - 20, inCubic));

export const RisoMisregistrationHit: React.FC = () => {
  const frame = useCurrentFrame();

  const split = frame >= HIT && frame < SNAP;
  const slideX = frame < HIT ? slideAt(frame) : 0;
  const vx = frame >= 20 && frame < HIT ? velocity(slideAt, frame) : 0;

  // Misregistration oscillation envelope: Damped cosine starting from impact; hard cut to zero at frame 72
  const t = frame - HIT;
  const m = split ? Math.cos(OMEGA * t) * Math.exp(-t / TAU) : 0;
  const dx = AX * m;
  const dy = AY * m;

  // Registration pulse: 4f scale 1.03 -> 1 starting at frame 72
  const pulse = frame >= SNAP && frame < SNAP + 4 ? 1 + 0.03 * (1 - (frame - SNAP) / 4) : 1;
  // Impact recoil: 1.2% page jolt on single frame, exponential recovery (strictly 1 outside 10f window)
  const th = frame - HIT;
  const kick = th >= 0 && th < 10 ? 1 + 0.012 * Math.exp(-th / 2.5) : 1;
  // Camera: Smooth subtle push, converging at 110f
  const cam = 1 + 0.012 * ramp(frame, 0, 110, EASE.smooth);

  // Circular seal: Stamps at 72f, compressed from 1.5 to 1 over 4f (ease-out), static thereafter
  const sp = ramp(frame, SNAP, 4, EASE.out);
  const stampS = frame < SNAP ? 1.5 : mix(1.5, 1, sp);
  const stampO = frame < SNAP ? 0 : Math.min(1, sp * 2.5);

  const sunReveal = ramp(frame, 0, 16, EASE.swift);
  const info = (i: number) => {
    const p = ramp(frame, 4 + i * 4, 14, EASE.snappy);
    return { opacity: p, transform: `translateY(${((1 - p) * 26).toFixed(2)}px)` };
  };

  return (
    <div style={{ width: 1920, height: 1080, background: PAPER, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${(cam * kick).toFixed(5)})`, transformOrigin: '40% 50%' }}>
        {/* Paper substrate: Center illumination + static paper fibers (multiply) */}
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 72% 70% at 42% 44%, #f8f4ea 0%, #f3eee2 58%, #e8e1d1 100%)' }} />
        <Grain opacity={0.11} step={100000} scale={2.4} freq={0.55} blend="multiply" />

        <Sun reveal={sunReveal} />

        {/* Colophon: Four-corner registration crosshairs + top bar (blue plate) */}
        <RegMark x={64} y={64} />
        <RegMark x={1856} y={64} />
        <RegMark x={64} y={1016} />
        <RegMark x={1856} y={1016} />
        <div style={{
          position: 'absolute', left: 120, right: 120, top: 104, display: 'flex', justifyContent: 'space-between',
          fontFamily: FONT.mono, fontSize: 26, fontWeight: 600, letterSpacing: '0.12em', color: BLUE, mixBlendMode: 'multiply',
          opacity: ramp(frame, 0, 10, EASE.out),
        }}>
          <span>VIDEO-SHOTCRAFT — Nº 07</span>
          <span>TWO-COLOUR RISO · 1 OF 300</span>
        </div>
        <div style={{ position: 'absolute', left: 120, right: 120, top: 150, height: 4, background: BLUE, mixBlendMode: 'multiply', transformOrigin: '0 50%', transform: `scaleX(${ramp(frame, 0, 18, EASE.snappy).toFixed(4)})` }} />

        {/* Bottom 3-column performance info (blue plate) */}
        <div style={{ position: 'absolute', left: 120, right: 120, top: 878, height: 4, background: BLUE, mixBlendMode: 'multiply', transformOrigin: '0 50%', transform: `scaleX(${ramp(frame, 2, 18, EASE.snappy).toFixed(4)})` }} />
        <div style={{ position: 'absolute', left: 120, right: 120, top: 906, display: 'grid', gridTemplateColumns: '1.25fr 1fr 1fr', gap: 48, color: BLUE, mixBlendMode: 'multiply' }}>
          {[
            ['SHOT RECIPE CARDS', 'Cinematic product films'],
            ['ONE PROMPT', 'To a finished promo'],
            ['BUILT ON REMOTION', 'For Claude Code & Codex'],
          ].map(([a, b], i) => (
            <div key={i} style={info(i)}>
              <div style={{ fontFamily: SANS, fontSize: 40, fontWeight: 850, letterSpacing: '-0.01em', lineHeight: 1.1 }}>{a}</div>
              <div style={{ fontFamily: SANS, fontSize: 32, fontWeight: 450, letterSpacing: '-0.01em', lineHeight: 1.35, marginTop: 6 }}>{b}</div>
            </div>
          ))}
        </div>

        {/* Impact fly-in: Both plates merged (registered state) flying across screen with directional motion blur */}
        {frame >= 20 && frame < HIT && (
          <SpeedBlur vx={vx} amount={0.09} max={34}>
            <div style={{ position: 'absolute', inset: 0, transform: `translateX(${slideX.toFixed(1)}px)` }}>
              <Plate color={FLUO} dx={0} dy={0} />
              <Plate color={BLUE} dx={0} dy={0} />
            </div>
          </SpeedBlur>
        )}

        {/* Dual-plate misregistration: Pink and blue plates counter-offset, multiplied to produce riso ghosting; zeroed out to deep purple after registration */}
        {frame >= HIT && (
          <>
            <Plate color={FLUO} dx={-dx} dy={dy} scale={pulse} />
            <Plate color={BLUE} dx={dx} dy={-dy} scale={pulse} />
          </>
        )}

        <Stamp s={stampS} o={stampO} />
      </div>

      {/* Ink grain: Fine screen noise gives ink fills authentic riso white pinhole texture (static) + warm sepia vignette */}
      <Grain opacity={0.2} step={100000} freq={1.25} blend="screen" />
      <Vignette strength={0.13} inner={0.55} color="#5a4a32" />
    </div>
  );
};
