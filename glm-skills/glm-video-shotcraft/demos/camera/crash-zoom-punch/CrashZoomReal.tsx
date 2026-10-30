// crash-zoom (bounce version, Round 2 redesign) — Real projects page wide view slams directly into card4 close-up in a single beat.
// Core technique preserved: wide hold → anticipatory pull-back → 6f strong ease-in crash push (peak velocity hits on arrival frame) → single visible overshoot bounce settling.
//
// Design decisions
// - look: ember (warm black + orange). The screenshot itself is a warm white paper page; placed in an ember stage, it reads like a screen lit by spotlight:
//   overview presents "product displayed on stage" — browser window tilted back slightly (rotateX 11°), warm orange rim light behind creating a silhouette,
//   reflective floor underneath; the crash push rights the backward tilt simultaneously, arriving at a front-facing close-up (Q6: readable card faces front).
// - Target preview: one beat before the push, four orange corner brackets contract from a large frame to lock onto card4 ("look at this" highlighted in overview first),
//   brackets are placed in page coordinates, naturally becoming the close-up card's reticle after the push — wide view to close-up follows a single line of sight.
// - Settle: surrounding page dimming to warm black (spotlight focus), target card lifts + orange rim light; arrival frame triggers a warm exposure flash (8f decay).
//   Camera then performs a "follow" track — smoothly pans left to yield the card to the golden ratio left position, with a large readout column settling on the right (editorial copy, fictional metrics).
// - Screenshot texture preserved (Q1: existing product page); card4 overlaid with 4x hi-res texture at original position, keeping close-up text crisp (Q2).
//
// Timeline (30fps, 132f)
//   0–34   Wide hold: window already in frame, tilt 13°→11°, zoom 0.70→0.72 ultra-slow creep in (smooth, framing alive without wobble)
//   14–30  Lock: 4 corner brackets contract from +150px outside to 14px outside card (snappy 16f), 4f fade in
//   34–40  Anticipation: zoom backs off ~4%, backward tilt deepens by 1.5°, brackets breathe outward in sync (gathering momentum)
//   40–46  Crash push 6f: strong ease-in in log space 0.69→2.48, tilt zeroes out along same curve, target card screen position converges monotonically toward center
//          — only this section uses temporal motion blur (shutter ≈200°, sub-frame spacing ≤6px, cap 44, isotropic micro-blur per layer to smooth discrete echoes)
//   46–58  Rebound: damped cosine 2.48→2.34, single visible rebound with slight undershoot settling; warm exposure flash with 8f decay starts at hit frame
//   47–64  Focus: periphery dims to 86% (warm black), card lifts + rim light (out curve 16f)
//   56–78  Follow: camera smoothly pans left 320px (swift 22f), card settles into left golden ratio position
//   68–108 Right column readouts: kicker → large numbers rise character-by-character from below line → hairline divider → two explanation lines (staggered 3–4f);
//          right column scrim origin tracks card right edge, never overlapping the hero card
//   108–131 Hold 24f: ultra-slow creep in 1→1.015 + breathing light, final frame is a complete poster
import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import layout from '../../_textures/live-layout.json';
import { Dust, LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { EASE, FONT, Vignette, mix, ramp, softShadow } from '../../_fixtures/Polish';

export const CRASHZOOM_DUR = 132;

const L = LOOKS.ember;
const CARD = layout.projects.cards[3];
const TARGET = { cx: CARD.x + CARD.w / 2, cy: CARD.y + CARD.h / 2 }; // ≈ (960, 772) page coordinates
const CARD_R = 8.5; // Card corner radius in screenshot (page px)

// Browser window crop in page coordinates (page width 1920, content area 408–1512): margins on both sides,
// bottom extends to 1060 — window bottom edge must fall outside frame in close-up (lands at screen y≈1220 under 2.34x)
const WIN = { x: 220, y: 0, w: 1480, h: 1060 };
const CHROME = 54; // Window title bar height (page px)
const WIN_R = 18;
const WIN_C = { x: WIN.x + WIN.w / 2, y: (WIN.y - CHROME + WIN.y + WIN.h) / 2 }; // Window geometric center

const PUSH = 40; // Push start frame
const HIT = 46; // Arrival frame (6f crash push)
const PEAK = 2.48; // Push peak zoom (6% above settle, upper bound of card parameter "3–6% rebound amplitude")
const REST = 2.34; // Settled zoom after rebound (card ≈ 836×730, occupying 68% frame height)
const SHIFT = 56; // Follow pan left start (rebound settled by ~56f)
const CARD_X_END = 640; // Card center screen x after follow pan

// Camera: zoom (page px → screen px), target card screen center sx/sy, backward tilt angle tilt.
// Interpolates "target card screen position" instead of camera center: target converges monotonically toward center during push without swinging out and back.
const camAt = (f: number) => {
  const settle = ramp(f, 0, 34, EASE.smooth);
  const wind = ramp(f, 34, 6, EASE.smooth);
  const z0 = mix(0.7, 0.72, settle) * mix(1, 0.96, wind);
  const tilt0 = mix(13, 11, settle) + 1.5 * wind;
  // Target card screen position in wide view (window geometric center → screen (960,540))
  const wideSx = 960 + (TARGET.cx - WIN_C.x) * z0;
  const wideSy = 540 + (TARGET.cy - WIN_C.y) * z0;
  let zoom = z0;
  let k = 0; // 0 = wide composition, 1 = target centered
  if (f >= PUSH && f < HIT) {
    const p = ramp(f, PUSH, HIT - PUSH, EASE.exit);
    zoom = Math.exp(mix(Math.log(z0), Math.log(PEAK), p)); // Log space: perceived push speed accelerates uniformly
    k = p;
  } else if (f >= HIT) {
    const t = f - HIT;
    zoom = REST + (PEAK - REST) * Math.exp(-t / 2.2) * Math.cos((Math.PI * t) / 5.2);
    zoom *= 1 + 0.015 * ramp(f, 96, 35, EASE.smooth); // Ultra-slow push in tail section keeps frame alive
    k = 1;
  }
  const tilt = f >= PUSH ? tilt0 * (1 - ramp(f, PUSH, HIT - PUSH, EASE.exit)) : tilt0;
  const shift = ramp(f, SHIFT, 22, EASE.swift);
  const sx = mix(wideSx, mix(960, CARD_X_END, shift), k);
  const sy = mix(wideSy, 540, k);
  return { zoom, sx, sy, tilt };
};

// Entire world under a single camera pose (window + page + brackets), reused across motion blur sub-frames
const World: React.FC<{ f: number; lift: number; lock: number; breath: number }> = ({ f, lift, lock, breath }) => {
  const { zoom, sx, sy, tilt } = camAt(f);
  const tx = sx - TARGET.cx * zoom;
  const ty = sy - TARGET.cy * zoom;
  // Corner brackets: padding determined by lock progress and anticipation breath; stroke inverted by zoom, constant 3px on screen
  const pad = mix(150, 14, lock) + 8 * breath;
  const sw = 3 / zoom;
  const arm = 34 / Math.max(1, zoom * 0.7);
  const bx = CARD.x - pad, by = CARD.y - pad, bw = CARD.w + pad * 2, bh = CARD.h + pad * 2;
  const tilted = tilt > 0.01;
  return (
    <AbsoluteFill style={tilted ? { perspective: 2600, perspectiveOrigin: '50% 40%' } : undefined}>
      <AbsoluteFill style={tilted ? { transform: `rotateX(${tilt.toFixed(3)}deg)`, transformOrigin: '50% 60%' } : undefined}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1200, transformOrigin: '0 0', transform: `translate(${tx.toFixed(2)}px, ${ty.toFixed(2)}px) scale(${zoom.toFixed(5)})` }}>
          {/* Window: title bar + viewport, dark tinted dual-layer shadow + top edge rim light */}
          <div
            style={{
              position: 'absolute', left: WIN.x, top: WIN.y - CHROME, width: WIN.w, height: WIN.h + CHROME, borderRadius: WIN_R, overflow: 'hidden',
              background: '#f9f6f1',
              boxShadow: `0 0 0 1px ${alpha('#ffd9bf', 0.22)}, 0 40px 90px -10px rgba(5,1,0,0.75), 0 12px 30px rgba(5,1,0,0.5)`,
            }}
          >
            <div style={{ position: 'absolute', left: 0, top: 0, width: WIN.w, height: CHROME, background: 'linear-gradient(180deg, #f1ebe2, #e9e2d7)', borderBottom: '1px solid rgba(60,40,20,0.12)' }}>
              {['#ef6a5b', '#f2be4f', '#5fc35a'].map((c, i) => (
                <div key={c} style={{ position: 'absolute', left: 24 + i * 24, top: 20, width: 14, height: 14, borderRadius: 7, background: c, boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.12)' }} />
              ))}
              <div style={{ position: 'absolute', left: WIN.w / 2 - 210, top: 12, width: 420, height: 30, borderRadius: 9, background: 'rgba(255,255,255,0.7)', boxShadow: 'inset 0 0 0 1px rgba(60,40,20,0.1)', fontFamily: FONT.sans, fontSize: 15, color: '#8a7a68', display: 'flex', alignItems: 'center', justifyContent: 'center', letterSpacing: '0.01em' }}>
                localhost:3000/projects
              </div>
            </div>
            <div style={{ position: 'absolute', left: 0, top: CHROME, width: WIN.w, height: WIN.h, overflow: 'hidden' }}>
              <div style={{ position: 'absolute', left: -WIN.x, top: -WIN.y, width: 1920, height: layout.projects.pageH }}>
                <Img src={staticFile('textures/live/projects-full.png')} style={{ position: 'absolute', width: 1920 }} />
                {/* Spotlight: massive shadow spread outside card acts as scrim, darkening periphery to warm black; target card casts elevation shadow */}
                {lift > 0.001 && (
                  <div
                    style={{
                      position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R,
                      boxShadow: `0 0 0 4000px rgba(14,6,2,${(0.86 * lift).toFixed(3)}), ${softShadow(14 * lift, { color: '#050100', strength: 2.4 })}`,
                    }}
                  />
                )}
                {/* Hi-res target card overlay at original position, text remains crisp when enlarged (Q2) */}
                <Img src={staticFile('textures/live/card4-hires.png')} style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R }} />
                {/* Rim light: hero card's only lighting effect, conforms to rounded corners (Q4) */}
                {lift > 0.001 && (
                  <div
                    style={{
                      position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R, pointerEvents: 'none',
                      boxShadow: `0 0 0 ${(1.2 / zoom).toFixed(3)}px ${alpha(L.accent, 0.85 * lift)}, 0 0 ${(26 / zoom).toFixed(2)}px ${alpha(L.accent, 0.45 * lift)}`,
                    }}
                  />
                )}
                {/* Lock brackets (page coordinates): contract to spotlight target in wide view, become reticle in close-up */}
                {lock > 0.001 && (
                  <svg
                    width={bw + 40} height={bh + 40} viewBox={`${bx - 20} ${by - 20} ${bw + 40} ${bh + 40}`}
                    style={{ position: 'absolute', left: bx - 20, top: by - 20, overflow: 'visible', opacity: Math.min(1, lock * 4) * (1 - 0.35 * lift) }}
                  >
                    <g fill="none" stroke={L.accent} strokeWidth={sw} strokeLinecap="square">
                      <path d={`M${bx} ${by + arm} V${by} H${bx + arm}`} />
                      <path d={`M${bx + bw - arm} ${by} H${bx + bw} V${by + arm}`} />
                      <path d={`M${bx + bw} ${by + bh - arm} V${by + bh} H${bx + bw - arm}`} />
                      <path d={`M${bx + arm} ${by + bh} H${bx} V${by + bh - arm}`} />
                    </g>
                  </svg>
                )}
              </div>
            </div>
            {/* Top edge rim light: warm inner highlight along window top edge */}
            <div style={{ position: 'absolute', inset: 0, borderRadius: WIN_R, boxShadow: `inset 0 1px 0 ${alpha('#fff4e8', 0.9)}`, pointerEvents: 'none' }} />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// Equal-weight accumulation within shutter window: layer i has opacity 1/(i+1), successive 'over' blending equals arithmetic mean.
// Sub-frame count adapts to frame displacement: pixels traversed by frame edge in shutter window / 6px, capped at 44.
const SHUTTER = 0.55; // Frames (≈200° shutter)
const samplesAt = (f: number) => {
  const a = camAt(f), b = camAt(f - SHUTTER);
  const edge = Math.abs(a.zoom - b.zoom) * 1100 + Math.hypot(a.sx - b.sx, a.sy - b.sy) + Math.abs(a.tilt - b.tilt) * 30;
  return Math.max(1, Math.min(44, Math.ceil(edge / 6)));
};
// Sub-frame spacing (screen px) → add slight isotropic blur per layer to smear discrete echoes into a continuous trail
// (small page text is only ~14px tall; at 6px echo spacing, discrete layers are visibly discernible)
const smearAt = (f: number, n: number) => {
  const a = camAt(f), b = camAt(f - SHUTTER);
  const edge = Math.abs(a.zoom - b.zoom) * 1100 + Math.hypot(a.sx - b.sx, a.sy - b.sy);
  // Only apply blur during genuinely fast frames: displacement <60px gets no blur (avoids blurring slow segments), ≥260px gets full blur
  const fast = Math.min(1, Math.max(0, (edge - 60) / 200));
  return Math.min(4, (edge / Math.max(1, n)) * 0.6 * fast);
};

export const CrashZoomReal: React.FC = () => {
  const frame = useCurrentFrame();
  const lock = ramp(frame, 14, 16, EASE.snappy);
  const breath = ramp(frame, 34, 6, EASE.smooth) * (1 - ramp(frame, PUSH, 4, EASE.exit));
  const lift = ramp(frame, HIT + 1, 16, EASE.out);
  const flash = frame >= HIT ? Math.exp(-(frame - HIT) / 3) : 0;
  // Frame edges during crash push: vignette deepens with push, recedes after settling
  const vig = 0.1 + 0.3 * ramp(frame, PUSH, HIT - PUSH, EASE.exit) - 0.36 * ramp(frame, HIT, 18, EASE.out);
  // Stage is almost completely covered by window after push; in wide view it establishes "product on stage"
  const wideFade = 1 - ramp(frame, PUSH, HIT - PUSH, EASE.exit);
  const n = frame >= PUSH && frame <= HIT + 1 ? samplesAt(frame) : 1;
  const smear = n > 1 ? smearAt(frame, n) : 0;
  const callout = frame >= 58;
  const scrim = ramp(frame, 58, 14, EASE.out);
  // Right column scrim origin tracks card right edge (card right edge + 70px), never overlapping the hero card
  const cam = camAt(frame);
  const scrimX = cam.sx + (CARD.w / 2) * cam.zoom + 70;
  return (
    <Stage look={L} keyLight={{ x: 0.5, y: 0.0 }} fill={{ x: 0.5, y: 1.05 }} horizon={0.86} intensity={0.9} breathe={0.5} vignette={mix(0.1, 0.5, wideFade)}>
      {/* Backlight: warm orange glow behind window silhouetting edges; reflective floor ellipse */}
      <div style={{ position: 'absolute', inset: 0, opacity: wideFade, background: `radial-gradient(ellipse 38% 44% at 50% 46%, ${alpha(L.accent, 0.34)}, ${alpha(L.accent, 0)} 70%)` }} />
      <div style={{ position: 'absolute', left: 360, right: 360, top: 900, height: 160, opacity: wideFade, borderRadius: '50%', background: `radial-gradient(closest-side, ${alpha('#ff9a5c', 0.28)}, ${alpha('#ff9a5c', 0)})`, filter: 'blur(8px)' }} />
      <div style={{ position: 'absolute', inset: 0, opacity: wideFade }}>
        <Dust look={L} count={34} seed={7} drift={0.3} opacity={0.55} color="#ffb27a" />
      </div>

      {n > 1 ? (
        Array.from({ length: n }, (_, i) => (
          <AbsoluteFill key={i} style={{ opacity: 1 / (i + 1), filter: smear > 0.3 ? `blur(${smear.toFixed(2)}px)` : undefined }}>
            <World f={frame - (SHUTTER * i) / (n - 1)} lift={lift} lock={lock} breath={breath} />
          </AbsoluteFill>
        ))
      ) : (
        <World f={frame} lift={lift} lock={lock} breath={breath} />
      )}

      {/* Warm exposure flash at arrival frame: centered on target card, 8f exponential decay */}
      {flash > 0.01 && (
        <div style={{ position: 'absolute', inset: 0, mixBlendMode: 'screen', background: `radial-gradient(ellipse 55% 60% at 50% 50%, ${alpha(L.accent2, 0.32 * flash)}, ${alpha(L.accent, 0.12 * flash)} 55%, ${alpha(L.accent, 0)} 80%)` }} />
      )}

      {/* Right column readouts: positioned in space freed up by follow pan left. Warm black scrim on the right ensures legibility */}
      {callout && (
        <>
          <div style={{ position: 'absolute', inset: 0, opacity: scrim, background: `linear-gradient(90deg, ${alpha('#0e0603', 0)} ${scrimX.toFixed(1)}px, ${alpha('#0e0603', 0.96)} ${(scrimX + 90).toFixed(1)}px, ${alpha('#0e0603', 0.97)} 100%)` }} />
          <div style={{ position: 'absolute', left: 1212, top: 300, width: 620, color: L.ink }}>
            <div style={{ ...type(28, 650, { caps: true }), letterSpacing: '0.2em', color: L.accent, display: 'flex', alignItems: 'center', gap: 16, opacity: ramp(frame, 68, 10, EASE.out), transform: `translateY(${(14 * (1 - ramp(frame, 68, 14, EASE.snappy))).toFixed(2)}px)` }}>
              <span style={{ width: 12, height: 12, borderRadius: 6, background: L.accent, boxShadow: `0 0 14px ${alpha(L.accent, 0.8)}` }} />
              In focus · Efficient Models
            </div>
            {/* clipPath only clips below row box bottom edge: as chars rise from below, unrisen glyphs won't peek through padding */}
            <div style={{ ...type(232, 700), letterSpacing: '-0.055em', marginTop: 26, marginLeft: -10, clipPath: 'inset(-40px -60px 0 -60px)' }}>
              <TextReveal text="−41%" by="char" variant="rise" start={71} each={18} gap={2.2} ease={EASE.snappy} />
            </div>
            <div style={{ height: 2, width: 520, marginTop: 30, background: alpha(L.ink, 0.16), transform: `scaleX(${ramp(frame, 76, 22, EASE.snappy).toFixed(4)})`, transformOrigin: '0 50%' }} />
            <div style={{ ...type(52, 600), marginTop: 30 }}>
              <TextReveal text="inference cost" by="word" variant="blur" start={79} each={16} gap={4} ease={EASE.out} />
            </div>
            <div style={{ ...type(40, 400), color: L.ink2, marginTop: 14 }}>
              <TextReveal text="at equal accuracy, routed per query" by="word" variant="blur" start={83} each={15} gap={2} ease={EASE.out} />
            </div>
          </div>
        </>
      )}
      <Vignette strength={Math.max(0, vig)} inner={0.42} color={L.shadow} cy={0.5} />
    </Stage>
  );
};
