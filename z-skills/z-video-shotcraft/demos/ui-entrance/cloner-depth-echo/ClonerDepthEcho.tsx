// cloner-depth-echo — Clone Column (Round 2 redesign · Lime dark stage · Edge deployment)
// Technique unchanged: A main card "photocopies" 7 clones arranged equidistantly along depth into a column → pause a beat for viewers to count → all synchronously accelerate and absorb back into origin → merge and pop bounce.
//
// Design decisions:
// - look = lime (graphite black + fluorescent yellow-green). Protagonist is a video-shotcraft render card "launch-film" (video-shotcraft badge in header):
//   Large 30fps readout + lime green polyline + 8 shot slots at the bottom. Semantic shifts from "multiple replicas" to specific selling point: one prompt = 8 shots rendered simultaneously.
// - Depth: True 3D perspective (perspective 1500), vanishing point at top-left — clones retreat along translateZ to automatically fan toward top-left,
//   with slight dx/dy layering to open up the column; further clones become fainter, blurrier, and "wireframe only" (fill fades, lime green stroke remains), resembling C4D Cloner wireframe echo.
//   Each clone's header switches to its own shot number (S02 / S03 ...) — same recipe, different shots.
// - Layout: Main card right-center (occupying ~36% frame width), column extends toward top-left; bottom-left houses the counter "×8" (260px lime green tabular),
//   advancing one tick per clone pop; after merge, the cleared top-left space reveals the title "One prompt. / Eight shots.", ending as a poster frame.
// - Merge: All 8 shot slots light up simultaneously the exact frame clones return into origin (clones "re-enter" base card), main card undergoes 1→1.06→1 single pulse + one lime green rim flash (Q4 hero-only flash).
//
// Timeline (30fps, 138f total):
//   0–16    Entrance: Main card rises 40px from below + blurs in (snappy), internal content staggered by 2f; counter ×1 already at bottom-left
//   16–24   Anticipation: Main card presses to 0.96, stroke brightens ("copy key pressed")
//   24–44   Fan-out: 7 clones spring-staggered at 2.2f/card into depth (damping 15, slight overshoot), counter +1 per pop, header shot numbers emerge
//   44–76   Hold 32f: Camera ultra-slow push-in 2%, subtle parallax drift across column — legible count of "many cards"
//   76–86   Absorb 10f: All clones ease-in synchronously (accelerating), motion blur along depth proportional to velocity
//   86–104  Merge: Shot slots fully illuminate, main card single pulse 1.06, rim flash once; counter scale-rebounds on same frame
//   92–118  Title rises word-by-word from baseline (top-left), subtitle fades in
//   118–138 Hold 20f: Light breathing + 0.6% ultra-slow push-in, clean settle
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, Dust, TextReveal, alpha, glow, springAt, type } from '../../_fixtures/Look';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const CLONER_DEPTH_ECHO_DURATION = 138;

const L = LOOKS.lime;
const N = 7; // Clone count
const GAP_Z = 250; // Depth spacing between adjacent clones (px)
const SPREAD = 24; // Fan-out start frame
const EACH = 2.2; // Clone stagger (frames/item)
const MERGE = 76; // Absorb start frame
const MERGE_DUR = 10;
const LAND = MERGE + MERGE_DUR; // Merge frame 86

// Main card geometry (screen px, z=0 plane)
const CW = 660;
const CH = 420;
const CX = 1130; // Top-left corner
const CY = 352;
// Perspective: Vanishing point at top-left; retreating clones fan toward top-left
const PERSP = 1500;
const VP = { x: 360, y: 120 };

const TYPE_H1 = 112; // Title font size (slightly reduced h1, fits two lines into top-left vacancy)

const REGIONS = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08']; // Shot numbers (retaining original variable name)
const SPARK = [0.62, 0.58, 0.66, 0.52, 0.55, 0.44, 0.48, 0.36, 0.4, 0.3, 0.33, 0.26, 0.3, 0.22];

const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

// Fan-out progress for clone idx (1..N): physics spring, staggered by EACH frames
const spreadOf = (f: number, idx: number) => (f < SPREAD + (idx - 1) * EACH ? 0 : springAt(f, SPREAD + (idx - 1) * EACH, { damping: 15, stiffness: 150, mass: 0.9 }));
// Absorb: Synchronous strong ease-in across all clones
const mergeOf = (f: number) => ramp(f, MERGE, MERGE_DUR, EASE.exit);
// Clone depth position (0 = base plane, 1 = fanned-out position)
const depthOf = (f: number, idx: number) => spreadOf(f, idx) * (1 - mergeOf(f));

// ───────────── Instance Card ─────────────
const InstanceCard: React.FC<{ region: string; clone: number; lit: number; frame: number; inP: number }> = ({ region, clone, lit, frame, inP }) => {
  // clone: 0 = base card, >0 further away — greater distance fades fill to wireframe outline
  const c = clone / N;
  const fill = clone === 0 ? 1 : mix(0.55, 0.06, c);
  const rise = (k: number) => {
    const p = clone === 0 ? ramp(frame, 4 + k * 2, 14, EASE.snappy) : 1;
    return { opacity: p * inP + (1 - inP) * 0, transform: `translateY(${((1 - p) * 16).toFixed(2)}px)` };
  };
  const pts = SPARK.map((v, i) => `${(i / (SPARK.length - 1)) * 576},${(v * 120).toFixed(1)}`).join(' ');
  return (
    <div
      style={{
        position: 'absolute', inset: 0, borderRadius: 30, overflow: 'hidden',
        background: `linear-gradient(160deg, ${alpha('#20241a', fill)} 0%, ${alpha(L.surface, fill)} 60%, ${alpha('#0f110c', fill)} 100%)`,
        border: `1.5px solid ${clone === 0 ? alpha('#ffffff', 0.12) : alpha(L.accent, mix(0.55, 0.85, c))}`,
        boxShadow: clone === 0
          ? `inset 0 1px 0 ${alpha('#ffffff', 0.1)}, 0 40px 90px -30px ${alpha('#000000', 0.9)}, 0 12px 30px ${alpha('#000000', 0.5)}`
          : `0 0 ${(18 + 20 * c).toFixed(0)}px ${alpha(L.accent, 0.12 + 0.1 * c)}`,
        fontFamily: FONT.sans, color: L.ink,
      }}
    >
      {/* Top edge lighting on card surface: faint lime green inner glow (base only) */}
      {clone === 0 && (
        <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 70% 50% at 30% 0%, ${alpha(L.accent, 0.1)} 0%, transparent 70%)` }} />
      )}
      <div style={{ position: 'absolute', left: 42, right: 42, top: 36, display: 'flex', alignItems: 'center', gap: 14, ...rise(0) }}>
        {/* video-shotcraft mark (dark-mode inverted); clones fade along with card */}
        <ShotcraftMark size={34} tone="dark" style={{ margin: '-4px 0' }} />
        <div style={{ ...type(32, 600, { mono: true }), color: clone === 0 ? L.ink : alpha(L.ink, 0.85) }}>launch-film</div>
        <div style={{ flex: 1 }} />
        <div
          style={{
            ...type(26, 700, { mono: true }), height: 44, padding: '0 16px', borderRadius: 22, display: 'flex', alignItems: 'center',
            background: clone === 0 ? L.accent : alpha(L.accent, 0.14), color: clone === 0 ? L.onAccent : L.accent,
            border: clone === 0 ? 'none' : `1.5px solid ${alpha(L.accent, 0.6)}`,
          }}
        >
          {region}
        </div>
      </div>
      {/* Readout: 30fps rendering — reduced to stroked outline on clones (texture), solid only on base card */}
      <div style={{ position: 'absolute', left: 40, top: 104, display: clone === 0 ? 'flex' : 'none', alignItems: 'baseline', gap: 16, ...rise(1) }}>
        <div
          style={{
            ...type(132, 750), letterSpacing: '-0.05em',
            color: clone === 0 ? L.ink : 'transparent',
            WebkitTextStroke: clone === 0 ? undefined : `1.5px ${alpha(L.accent, 0.7)}`,
          }}
        >
          30<span style={{ fontSize: 72, letterSpacing: '-0.02em', color: clone === 0 ? L.ink2 : 'transparent' }}>fps</span>
        </div>
        <div style={{ ...type(26, 500, { caps: true }), color: L.ink3, letterSpacing: '0.12em', opacity: clone === 0 ? 1 : 0 }}>1080p</div>
      </div>
      {/* Polyline */}
      <svg width={576} height={130} style={{ position: 'absolute', left: 42, top: 246, overflow: 'visible', ...rise(2) }}>
        {clone === 0 && (
          <polygon points={`0,130 ${pts} 576,130`} fill={`url(#cdeFill)`} opacity={0.9} />
        )}
        <defs>
          <linearGradient id="cdeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={L.accent} stopOpacity={0.22} />
            <stop offset="1" stopColor={L.accent} stopOpacity={0} />
          </linearGradient>
        </defs>
        <polyline points={pts} fill="none" stroke={L.accent} strokeWidth={clone === 0 ? 4 : 2.5} strokeLinejoin="round" strokeLinecap="round" opacity={clone === 0 ? 1 : 0.8} />
      </svg>
      {/* Shot slots: 8 bottom slots on base card, all illuminate on merge */}
      {clone === 0 && (
        <div style={{ position: 'absolute', left: 42, right: 42, bottom: 30, display: 'flex', gap: 8, ...rise(3) }}>
          {REGIONS.map((r, i) => {
            const on = i === 0 ? 1 : lit;
            return (
              <div
                key={r}
                style={{
                  flex: 1, height: 34, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  ...type(18, 600, { mono: true }),
                  background: alpha(L.accent, 0.06 + 0.84 * on),
                  color: on > 0.5 ? L.onAccent : L.ink3,
                  border: `1px solid ${alpha(L.accent, 0.18 + 0.5 * on)}`,
                }}
              >
                {r}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ───────────── Counter: Each tick rolls up from below ─────────────
const Counter: React.FC<{ value: number; tickAge: number; punch: number }> = ({ value, tickAge, punch }) => {
  // tickAge: frames elapsed since last +1 (5f scroll duration); punch: merge bounce 0..1..0
  const roll = ramp(tickAge, 0, 5, EASE.snappy);
  const size = 260;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', transform: `scale(${(1 + 0.06 * punch).toFixed(4)})`, transformOrigin: '0% 70%' }}>
      <span style={{ ...type(size * 0.62, 500), color: alpha(L.accent, 0.55), marginTop: size * 0.2, marginRight: 8 }}>×</span>
      {/* Avoid overflow clipping (would clip glow into a box): exiting digit shifts up/fades out, entering digit rises/fades in */}
      <div style={{ position: 'relative', height: size * 1.02, width: size * 0.62 }}>
        {[value - 1, value].map((v, k) => {
          if (v < 1) return null;
          const y = k === 0 ? -roll * 45 : (1 - roll) * 45;
          // Both digits vertically blur by speed during scroll (0 when stationary)
          const spd = roll < 1 ? 1 - roll : 0;
          return (
            <div
              key={k}
              style={{
                position: 'absolute', left: 0, top: 0, ...type(size, 800), letterSpacing: '-0.04em', color: L.accent,
                transform: `translateY(${y.toFixed(2)}%)`, textShadow: glow(L.accent, 0.35 + 0.5 * punch),
                opacity: k === 0 ? clamp01(1 - roll * 1.6) : clamp01(roll * 1.6),
                filter: spd > 0.05 ? `blur(${(spd * 6).toFixed(2)}px)` : undefined,
              }}
            >
              {v}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const ClonerDepthEcho: React.FC = () => {
  const frame = useCurrentFrame();

  // Main card entrance / prep press / merge pulse
  const enter = ramp(frame, 0, 16, EASE.snappy);
  const press = ramp(frame, 16, 8, EASE.swift) * (1 - ramp(frame, SPREAD, 10, EASE.overshoot));
  const popT = clamp01((frame - LAND) / 16);
  const pop = frame >= LAND ? Math.sin(popT * Math.PI) * Math.pow(1 - popT, 0.6) : 0;
  const heroScale = (1 - 0.04 * press) * (1 + 0.06 * pop) * mix(0.94, 1, enter);
  const rimFlash = frame >= LAND ? Math.max(0, 1 - (frame - LAND) / 14) : 0;
  const lit = ramp(frame, LAND - 1, 5, EASE.snappy);

  // Counter: ticks +1 once clone extends past 30%; track last tick frame for roll animation
  let count = 1;
  let lastTick = -99;
  for (let idx = 1; idx <= N; idx++) {
    const f0 = SPREAD + (idx - 1) * EACH + 2;
    if (frame >= f0) { count++; lastTick = f0; }
  }
  const counterPunch = frame >= LAND ? Math.sin(clamp01((frame - LAND) / 12) * Math.PI) : 0;

  // Camera: Ultra-slow push-in during hold; gentle push after merge; subtle parallax drift across column during hold
  const dolly = 1 + 0.02 * ramp(frame, 40, 40, EASE.smooth) + 0.006 * ramp(frame, 100, 38, EASE.smooth);
  const drift = 14 * ramp(frame, 40, 40, EASE.smooth) * (1 - mergeOf(frame));

  // Title & counter labels
  const labelIn = ramp(frame, 6, 16, EASE.out);

  return (
    <AbsoluteFill style={{ fontFamily: FONT.sans, overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.62, y: 0.42 }} fill={{ x: 0.1, y: 0.95 }} breathe={0.6} intensity={0.45}>
        <Dust look={L} count={26} seed={5} drift={0.18} opacity={0.35} color={L.accent} />
        {/* Lime ground glow beneath main card */}
        <div
          style={{
            position: 'absolute', left: CX - 160, top: CY + CH - 40, width: CW + 320, height: 220,
            background: `radial-gradient(ellipse 50% 50% at 50% 40%, ${alpha(L.accent, 0.14 + 0.12 * rimFlash)} 0%, transparent 70%)`,
            opacity: enter,
          }}
        />
      </Stage>

      {/* Camera layer: push-in anchored to main card center */}
      <AbsoluteFill style={{ transform: `scale(${dolly.toFixed(5)})`, transformOrigin: `${CX + CW / 2}px ${CY + CH / 2}px` }}>
        <AbsoluteFill style={{ perspective: PERSP, perspectiveOrigin: `${VP.x}px ${VP.y}px` }}>
          <div style={{ position: 'absolute', inset: 0, transformStyle: 'preserve-3d' }}>
            {/* Clone column: rendered back-to-front for correct occlusion */}
            {Array.from({ length: N }, (_, k) => N - k).map((idx) => {
              const d = depthOf(frame, idx);
              const sp = spreadOf(frame, idx);
              const op = (1 - (idx / N) * 0.72) * clamp01(sp * 2.5) * (1 - mergeOf(frame) * 0.4);
              if (op <= 0.005 || d <= 0.002) return null;
              const z = -GAP_Z * idx * d;
              const dx = (-58 * idx - drift * idx * 0.4) * d;
              const dy = -6 * idx * d;
              // Velocity → motion blur (screen direction along depth, approximated by slight isotropic blur + directional stretch)
              const v = Math.abs(depthOf(frame + 0.5, idx) - depthOf(frame - 0.5, idx)) * GAP_Z * idx;
              const blur = Math.min(10, v * 0.06);
              // Birth flash: brighter stroke for first 8f of fan-out (photocopy snap)
              const born = clamp01(1 - (frame - (SPREAD + (idx - 1) * EACH)) / 8);
              return (
                <div
                  key={idx}
                  style={{
                    position: 'absolute', left: CX, top: CY, width: CW, height: CH,
                    transform: `translate3d(${dx.toFixed(2)}px, ${dy.toFixed(2)}px, ${z.toFixed(2)}px)`,
                    opacity: op,
                    filter: `blur(${(blur + (idx / N) * 1.6).toFixed(2)}px)${born > 0 ? ` drop-shadow(0 0 ${(14 * born).toFixed(1)}px ${alpha(L.accent, 0.7 * born)})` : ''}`,
                  }}
                >
                  <InstanceCard region={REGIONS[idx]} clone={idx} lit={0} frame={frame} inP={1} />
                </div>
              );
            })}

            {/* Base card */}
            <div
              style={{
                position: 'absolute', left: CX, top: CY, width: CW, height: CH,
                transform: `translate3d(0px, ${((1 - enter) * 40).toFixed(2)}px, 0px) scale(${heroScale.toFixed(4)})`,
                opacity: clamp01(enter * 1.4),
                filter: enter < 1 ? `blur(${((1 - enter) * 10).toFixed(2)}px)` : undefined,
              }}
            >
              <InstanceCard region={REGIONS[0]} clone={0} lit={lit} frame={frame} inP={1} />
              {/* Merge rim flash (one-shot, clipped within rounded corners) */}
              <div
                style={{
                  position: 'absolute', inset: 0, borderRadius: 30, pointerEvents: 'none',
                  border: `2px solid ${alpha(L.accent, 0.25 * press + 0.9 * rimFlash)}`,
                  boxShadow: `0 0 ${(50 * rimFlash).toFixed(1)}px ${alpha(L.accent, 0.45 * rimFlash)}, inset 0 0 ${(40 * rimFlash).toFixed(1)}px ${alpha(L.accent, 0.18 * rimFlash)}`,
                }}
              />
            </div>
          </div>
        </AbsoluteFill>
      </AbsoluteFill>

      {/* Top-left: title rising after merge */}
      <div style={{ position: 'absolute', left: 140, top: 168, ...type(TYPE_H1, 780), color: L.ink }}>
        <TextReveal text={'One prompt.'} by="word" variant="rise" start={92} each={16} gap={4} />
        <br />
        <TextReveal text={'Eight shots.'} by="word" variant="rise" start={98} each={16} gap={4} unitStyle={(i) => (i === 1 ? { color: L.accent } : {})} />
      </div>

      {/* Bottom-left: counter */}
      <div style={{ position: 'absolute', left: 128, top: 622, opacity: labelIn, transform: `translateY(${((1 - labelIn) * 20).toFixed(2)}px)` }}>
        <Counter value={count} tickAge={frame - lastTick} punch={counterPunch} />
      </div>
      <div
        style={{
          position: 'absolute', left: 140, top: 900, display: 'flex', alignItems: 'center', gap: 16,
          opacity: labelIn, ...type(32, 600, { mono: true }), color: L.ink2, letterSpacing: '0.04em',
        }}
      >
        <span style={{ width: 40, height: 2, background: L.accent }} />
        {count === 1 ? 'shot rendered' : 'shots rendered · one prompt'}
      </div>
    </AbsoluteFill>
  );
};

