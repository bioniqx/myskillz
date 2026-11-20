// crash-impact hard slam stop (Round 2 redesign) — Same rapid push-in as crash-zoom, but instead of rebounding at arrival, it slams to a stop with a screen shake:
// high-frequency jitter + 6f exponential decay, then absolute stillness. Contrast point: sense of weight ("this is the one") vs the bounce version's elasticity ("look at this").
//
// Design decisions
// - look: lime (graphite dark field + fluorescent yellow-green). Distinct from the ember bounce version (ember · tilted browser window · editorial readouts):
//   this version adopts a "tactical HUD" visual language — the real projects page becomes a front-facing monitor screen, with a faint grid across the stage;
//   a fluorescent reticle scans across the overview (card1 → card5 → card4, snappy stepping), locking onto card4 before the crash zoom.
// - Weight of the slam stop: an "impact frame" on arrival — area outside the card is flooded with fluorescent yellow-green (1f), crushed to near-black within 3f (a sudden flash like a heavy drop throwing up dust,
//   rather than a warm overexposure); two fluorescent shockwave rings expand outward from the card edge; screen shake 14px·e^(−t/1.8), first beat sinking along impact direction.
//   Target card does not float or glow — it is "slammed down firmly", not "bounced up". This is the only whole-screen effect in the entire sequence (R4).
// - After settling: a single scanline sweeps top-to-bottom across the card face (Q4: only lighting effect, clipped to rounded corners); HUD readouts stagger into place on both sides:
//   left column monospace readouts for TARGET / OWNER / STATE, right column 240px fluorescent "P0" + description. Final frame is a complete poster.
// - Screenshot texture preserved (Q1); card4 overlaid with 4x hi-res texture at original position, keeping close-up text crisp (Q2).
//
// Timeline (30fps, 126f)
//   0–4    Overview: monitor screen already in frame, grid and badges visible, stage zoom 0.78 starts creeping in by 2%
//   4–30   Scan: reticle hops to card1 (4f) → 10f hops to card5 → 20f hops to card4 (8f snappy each), 28f tightens lock + LOCK tag
//   32–40  Anticipation: zoom backs off ~3% (smooth), reticle breathes outward once
//   40–46  Crash zoom 6f: strong ease-in in log space 0.76→2.35, target card screen position converges monotonically toward center; only this section uses temporal motion blur
//   46     Slam stop: impact frame (46 fluorescent / 47 afterglow / 48+ near-black) + shockwave rings; 46–52 screen shake decays to zero (clean shake, no blur)
//   52–68  Scanline sweeps card face (16f); 54–84 left/right HUD readouts stagger into place (label → value, 3–4f per beat)
//   84–125 Hold 42f: ultra-slow creep 1→1.012, final frame cleanly settles
import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import layout from '../../_textures/live-layout.json';
import { EASE, Grain, Vignette, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';

export const CRASHIMPACT_DUR = 126;

// Replace lime's key light with cooler gray-green: stage light doesn't compete with fluorescent accent (fluorescent reserved for reticle / impact / P0)
const L = { ...LOOKS.lime, light: '#9aa58a' };
const LIME = L.accent;
const CARDS = layout.projects.cards;
const CARD = CARDS[3];
const TARGET = { cx: CARD.x + CARD.w / 2, cy: CARD.y + CARD.h / 2 }; // ≈ (960, 772) page coordinates
const CARD_R = 8.5; // Card corner radius in screenshot (page px)
// Monitor crop (page coordinates): cropped around card4 as center, showing three rows of cards in wide view
const CROP = { x: 395, y: 222, w: 1130, h: 1100 };
const CROP_C = { x: CROP.x + CROP.w / 2, y: CROP.y + CROP.h / 2 };
const SCREEN_R = 22; // Monitor screen corner radius (page px)

const PUSH = 40;
const HIT = 46;
const Z_WIDE = 0.78;
const Z_HIT = 2.35; // Settle zoom: card ≈ 840×733, occupying 68% frame height, leaving ~540px left/right for HUD readouts

// Camera: zoom + screen position of target card center (interpolates "target position" instead of camera center: target converges monotonically toward screen center during crash push)
const camAt = (f: number) => {
  const creep = mix(Z_WIDE, Z_WIDE * 1.02, ramp(f, 0, 32, EASE.smooth));
  const wind = creep * mix(1, 0.97, ramp(f, 32, 8, EASE.smooth));
  const wideSx = 960 + (TARGET.cx - CROP_C.x) * wind;
  const wideSy = 540 + (TARGET.cy - CROP_C.y) * wind;
  if (f < PUSH) return { zoom: wind, sx: wideSx, sy: wideSy };
  const p = ramp(f, PUSH, HIT - PUSH, EASE.exit); // Stops on arrival: no bounce phase
  const zoom = Math.exp(mix(Math.log(wind), Math.log(Z_HIT), p)) * (1 + 0.012 * ramp(f, 84, 41, EASE.smooth));
  return { zoom, sx: mix(wideSx, 960, p), sy: mix(wideSy, 540, p) };
};

// Slam stop screen shake (screen space, deterministic): cosine initial phase ensures frame 0 starts at envelope peak and points downward (continuing impact direction),
// frequency ~2.9 rad/f makes adjacent frames almost flip sign — high-frequency "hard shake" rather than handheld wobble; x-axis amplitude 0.55, micro-rotation 0.025°/px
const shakeAt = (f: number) => {
  const t = f - HIT;
  if (t < 0) return { sx: 0, sy: 0, rot: 0 };
  const env = 14 * Math.exp(-t / 1.8);
  if (env < 0.15) return { sx: 0, sy: 0, rot: 0 };
  return { sx: env * 0.55 * Math.sin(t * 2.4 + 0.6), sy: env * Math.cos(t * 2.9), rot: env * 0.025 * Math.sin(t * 3.7 + 1.9) };
};

// Scanning reticle: hops sequentially across card1 → card5 → card4 (center and dimensions in page coordinates), snappy stepping
const HOPS = [
  { at: 4, c: CARDS[0] },
  { at: 10, c: CARDS[4] },
  { at: 20, c: CARD },
];
const reticleAt = (f: number) => {
  const box = (c: typeof CARD) => ({ x: c.x + c.w / 2, y: c.y + c.h / 2, w: c.w, h: c.h });
  let r = box(HOPS[0].c);
  for (let i = 1; i < HOPS.length; i++) {
    const u = ramp(f, HOPS[i].at, 8, EASE.snappy);
    const b = box(HOPS[i].c);
    r = { x: mix(r.x, b.x, u), y: mix(r.y, b.y, u), w: mix(r.w, b.w, u), h: mix(r.h, b.h, u) };
  }
  return r;
};

// Entire world under a single camera pose (monitor + page + reticle + shockwave), reused across motion blur sub-frames
const World: React.FC<{ f: number; frame: number }> = ({ f, frame }) => {
  const { zoom, sx, sy } = camAt(f);
  const tx = sx - TARGET.cx * zoom;
  const ty = sy - TARGET.cy * zoom;
  const px = (n: number) => n / zoom; // Screen px → page px (constant line width)
  // Reticle
  const r = reticleAt(frame);
  const show = ramp(frame, 3, 6, EASE.out);
  const lock = ramp(frame, 28, 8, EASE.snappy);
  const breath = ramp(frame, 32, 8, EASE.smooth) * (1 - ramp(frame, PUSH, 5, EASE.exit));
  const pad = mix(26, 10, lock) + 16 * breath;
  const arm = px(30);
  const bx = r.x - r.w / 2 - pad, by = r.y - r.h / 2 - pad, bw = r.w + pad * 2, bh = r.h + pad * 2;
  // Slam stop: impact frame outside card (fluorescent) → crushed to near-black in 3f
  const t = frame - HIT;
  const crush = t >= 0;
  const impact = t < 0 ? 0 : t < 1 ? 0.8 : t < 2 ? 0.22 : 0; // Impact frame: 1f fluorescent → 1f afterglow → near-black
  const scrimColor = `rgba(${Math.round(mix(11, 198, impact))},${Math.round(mix(12, 244, impact))},${Math.round(mix(9, 50, impact))},${(t < 0 ? 0 : 1).toFixed(3)})`;
  return (
    <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: layout.projects.pageH, transformOrigin: '0 0', transform: `translate(${tx.toFixed(2)}px, ${ty.toFixed(2)}px) scale(${zoom.toFixed(5)})` }}>
      {/* Monitor: crops the CROP region of the page; outside is the stage */}
      <div style={{
        position: 'absolute', left: CROP.x, top: CROP.y, width: CROP.w, height: CROP.h, borderRadius: SCREEN_R, overflow: 'hidden',
        background: '#f9f6f1',
        boxShadow: `0 0 0 ${px(1.5)}px ${alpha(LIME, 0.35)}, 0 ${px(40)}px ${px(110)}px ${px(-10)}px rgba(0,0,0,0.85)`,
      }}>
        <div style={{ position: 'absolute', left: -CROP.x, top: -CROP.y, width: 1920, height: layout.projects.pageH }}>
          <Img src={staticFile('textures/live/projects-full.png')} style={{ position: 'absolute', width: 1920 }} />
          {/* Slight dimming on overview page to avoid clashing with dark stage */}
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(12,14,10,0.1)' }} />
          {/* Crosshair scanlines: run across monitor screen, tracking reticle center */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: r.y, height: px(1.2), background: alpha('#2d3a00', 0.35 * show * (1 - lock * 0.6)) }} />
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: r.x, width: px(1.2), background: alpha('#2d3a00', 0.35 * show * (1 - lock * 0.6)) }} />
        </div>
      </div>
      {/* Slam stop dimming: massive shadow spread outside card acts as scrim (impact frame starts fluorescent then near-black) */}
      {crush && (
        <div style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R, boxShadow: `0 0 0 6000px ${scrimColor}` }} />
      )}
      {/* "Tabletop" after dimming: faint cool gray pool of light behind card, dark field is not a dead flat color (not a halo — card itself does not glow) */}
      {crush && (
        <div style={{
          position: 'absolute', left: CARD.x - CARD.w * 1.6, top: CARD.y - CARD.h * 1.3, width: CARD.w * 4.2, height: CARD.h * 3.6,
          background: `radial-gradient(ellipse 50% 50% at 50% 46%, ${alpha('#c9d4b8', 0.09 * (1 - impact))}, ${alpha('#c9d4b8', 0)} 70%)`,
        }} />
      )}
      {/* Hi-res target card overlay at original position (Q2) */}
      <Img src={staticFile('textures/live/card4-hires.png')} style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R }} />
      {/* Scanline: sweeps top-to-bottom across card face once after settling, clipped to rounded corners (Q4) */}
      {frame >= 52 && frame <= 70 && (
        <div style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R, overflow: 'hidden', pointerEvents: 'none' }}>
          {(() => {
            const y = mix(-0.12, 1.08, ramp(frame, 52, 16, EASE.swift)) * CARD.h;
            return (
              <>
                <div style={{ position: 'absolute', left: 0, right: 0, top: y - 60, height: 60, background: `linear-gradient(180deg, ${alpha(LIME, 0)}, ${alpha(LIME, 0.16)})` }} />
                <div style={{ position: 'absolute', left: 0, right: 0, top: y - px(1.5), height: px(3), background: alpha(LIME, 0.95), boxShadow: `0 0 ${px(14)}px ${alpha(LIME, 0.8)}` }} />
              </>
            );
          })()}
        </div>
      )}
      {/* Shockwave: two rounded-rect rings expand outward from card edge (page coordinates, constant screen stroke width) */}
      {t >= 0 && t < 20 && [0, 3].map((d, k) => {
        const u = ramp(frame, HIT + d, 16, EASE.snappy);
        const grow = mix(0, k ? 60 : 110, u);
        const op = (1 - u) * (k ? 0.6 : 1) * (frame >= HIT + d ? 1 : 0);
        return (
          <div key={k} style={{
            position: 'absolute', left: CARD.x - grow, top: CARD.y - grow, width: CARD.w + grow * 2, height: CARD.h + grow * 2,
            borderRadius: CARD_R + grow * 0.5, border: `${px(k ? 2 : 4)}px solid ${alpha(LIME, op)}`, boxSizing: 'border-box',
            boxShadow: `0 0 ${px(20)}px ${alpha(LIME, op * 0.5)}`,
          }} />
        );
      })}
      {/* Card edge: fluorescent hairline stroke after settling ("locked" reticle state) */}
      {t >= 0 && (
        <div style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: CARD_R, boxShadow: `0 0 0 ${px(2)}px ${alpha(LIME, 0.9)}`, pointerEvents: 'none' }} />
      )}
      {/* Reticle corner brackets (page coordinates; stroke inverted by zoom, constant 4px on screen) */}
      {show > 0 && (
        <svg width={bw + 80} height={bh + 80} viewBox={`${bx - 40} ${by - 40} ${bw + 80} ${bh + 80}`}
          style={{ position: 'absolute', left: bx - 40, top: by - 40, overflow: 'visible', opacity: show }}>
          <g fill="none" stroke={LIME} strokeWidth={px(4)} strokeLinecap="square">
            <path d={`M${bx} ${by + arm} V${by} H${bx + arm}`} />
            <path d={`M${bx + bw - arm} ${by} H${bx + bw} V${by + arm}`} />
            <path d={`M${bx + bw} ${by + bh - arm} V${by + bh} H${bx + bw - arm}`} />
            <path d={`M${bx + arm} ${by + bh} H${bx} V${by + bh - arm}`} />
          </g>
          {/* Center crosshair */}
          <g stroke={LIME} strokeWidth={px(2)} opacity={1 - lock}>
            <path d={`M${r.x - px(14)} ${r.y} H${r.x + px(14)} M${r.x} ${r.y - px(14)} V${r.y + px(14)}`} />
          </g>
        </svg>
      )}
    </div>
  );
};

// Equal-weight accumulation within shutter window: layer i has opacity 1/(i+1), successive 'over' blending equals arithmetic mean; sub-frame spacing ≤8px, capped at 36
const SHUTTER = 0.55;
const edgeAt = (f: number) => {
  const a = camAt(f), b = camAt(f - SHUTTER);
  return Math.abs(a.zoom - b.zoom) * 1100 + Math.hypot(a.sx - b.sx, a.sy - b.sy);
};

// HUD readouts (screen space): label → value, staggered arrival
const Readout: React.FC<{ frame: number; at: number; label: string; children: React.ReactNode }> = ({ frame, at, label, children }) => {
  const a = ramp(frame, at, 12, EASE.snappy);
  return (
    <div style={{ marginBottom: 46 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, ...type(22, 600, { mono: true }), letterSpacing: '0.2em', color: LIME, opacity: a, textTransform: 'uppercase' }}>
        <span style={{ height: 2, width: mix(0, 28, a), background: LIME }} />
        {label}
      </div>
      <div style={{ marginTop: 12, opacity: ramp(frame, at + 3, 10, EASE.out), transform: `translateX(${((1 - ramp(frame, at + 3, 14, EASE.snappy)) * -24).toFixed(1)}px)` }}>{children}</div>
    </div>
  );
};

export const CrashImpactReal: React.FC = () => {
  const frame = useCurrentFrame();
  const { sx, sy, rot } = shakeAt(frame);
  const n = frame >= PUSH && frame <= HIT ? Math.max(1, Math.min(36, Math.ceil(edgeAt(frame) / 8))) : 1;
  const smear = n > 1 ? Math.min(4, (edgeAt(frame) / n) * 0.5 * Math.min(1, Math.max(0, (edgeAt(frame) - 60) / 200))) : 0;
  const wide = 1 - ramp(frame, PUSH, HIT - PUSH, EASE.exit);
  const vig = frame < HIT ? 0.35 + 0.25 * ramp(frame, PUSH, HIT - PUSH, EASE.exit) : mix(0.75, 0.4, ramp(frame, HIT, 16, EASE.out));
  // Reticle tag (screen space, tracks reticle in overview; dismissed when crash zoom begins)
  const cam = camAt(frame);
  const r = reticleAt(frame);
  const lock = ramp(frame, 28, 8, EASE.snappy);
  const tagX = cam.sx + (r.x - r.w / 2 - TARGET.cx) * cam.zoom - 12;
  const tagY = cam.sy + (r.y + r.h / 2 - TARGET.cy) * cam.zoom + 22; // Tag pinned to bottom-left of reticle (first card1 is on top row; pinning to top edge would overlap screen title)
  const hop = frame < 10 ? '01' : frame < 20 ? '05' : '04';
  return (
    <AbsoluteFill style={{ background: L.bg[2], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: -0.1 }} fill={{ x: 0.5, y: 1.1 }} intensity={0.6} breathe={0.4} vignette={0.2}>
        {/* Stage grid: parallax follows 30% of camera zoom, dissolves into dark field after crash zoom */}
        <div style={{
          position: 'absolute', inset: -400, opacity: 0.55 * wide + 0.1,
          transform: `scale(${(1 + (cam.zoom / Z_WIDE - 1) * 0.3).toFixed(4)})`,
          backgroundImage: `linear-gradient(${alpha(LIME, 0.07)} 1.5px, transparent 1.5px), linear-gradient(90deg, ${alpha(LIME, 0.07)} 1.5px, transparent 1.5px)`,
          backgroundSize: '64px 64px', backgroundPosition: '400px 400px',
          WebkitMaskImage: 'radial-gradient(ellipse 60% 60% at 50% 50%, #000 30%, transparent 80%)',
        }} />
      </Stage>

      {/* Screen shake layer: full page + scrim + shockwave shake together (page far exceeds frame at 2.35x, shaking shows no edges) */}
      <AbsoluteFill style={{ transform: `translate(${sx.toFixed(2)}px, ${sy.toFixed(2)}px) rotate(${rot.toFixed(4)}deg)` }}>
        {n > 1 ? (
          Array.from({ length: n }, (_, i) => (
            <AbsoluteFill key={i} style={{ opacity: 1 / (i + 1), filter: smear > 0.3 ? `blur(${smear.toFixed(2)}px)` : undefined }}>
              <World f={frame - (SHUTTER * i) / (n - 1)} frame={frame} />
            </AbsoluteFill>
          ))
        ) : (
          <World f={frame} frame={frame} />
        )}
      </AbsoluteFill>

      {/* Overview HUD: monospace labels at top two corners of monitor + reticle tag */}
      <AbsoluteFill style={{ opacity: wide, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', left: 960 - (CROP.w / 2) * cam.zoom, top: 540 - (CROP.h / 2) * cam.zoom - 50, display: 'flex', gap: 14, alignItems: 'center', ...type(22, 600, { mono: true }), letterSpacing: '0.18em', color: L.ink2, opacity: ramp(frame, 0, 8, EASE.out) }}>
          <span style={{ width: 10, height: 10, borderRadius: 5, background: LIME, boxShadow: `0 0 12px ${alpha(LIME, 0.8)}` }} />
          LIVE · /PROJECTS
        </div>
        <div style={{ position: 'absolute', right: 960 - (CROP.w / 2) * cam.zoom, top: 540 - (CROP.h / 2) * cam.zoom - 50, ...type(22, 600, { mono: true }), letterSpacing: '0.18em', color: L.ink3 }}>
          10 PROJECTS · SCANNING
        </div>
        {frame >= 4 && (
          <div style={{
            position: 'absolute', left: tagX, top: tagY, height: 34, padding: '0 12px', display: 'flex', alignItems: 'center', gap: 10, borderRadius: 4,
            background: lock > 0.5 ? LIME : alpha('#0b0d06', 0.85), color: lock > 0.5 ? L.onAccent : LIME,
            border: `1.5px solid ${LIME}`, ...type(22, 700, { mono: true }), letterSpacing: '0.14em',
            opacity: ramp(frame, 4, 4, EASE.out), transform: `scale(${mix(1.25, 1, ramp(frame, 28, 6, EASE.snappy)).toFixed(3)})`, transformOrigin: '0 0',
          }}>
            {lock > 0.5 ? `LOCK ${hop}` : `SCAN ${hop}`}
          </div>
        )}
      </AbsoluteFill>

      {/* Settle HUD: left column monospace readouts, right column P0 */}
      {frame >= 52 && (
        <AbsoluteFill style={{ pointerEvents: 'none', transform: `translate(${(sx * 0.4).toFixed(2)}px, ${(sy * 0.4).toFixed(2)}px)` }}>
          <div style={{ position: 'absolute', left: 104, top: 262 }}>
            <Readout frame={frame} at={54} label="Target">
              <div style={{ ...type(64, 600, { mono: true }), color: L.ink }}>04<span style={{ color: L.ink3 }}>/10</span></div>
            </Readout>
            <Readout frame={frame} at={58} label="Owner">
              <div style={{ ...type(48, 600), color: L.ink }}>Yuki</div>
            </Readout>
            <Readout frame={frame} at={62} label="State">
              <div style={{ ...type(48, 600), color: L.ink, display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ width: 16, height: 16, borderRadius: 8, background: LIME, boxShadow: `0 0 16px ${alpha(LIME, 0.9)}` }} />
                Active
              </div>
            </Readout>
          </div>
          <div style={{ position: 'absolute', left: 1452, top: 258, width: 400 }}>
            <div style={{ ...type(22, 600, { mono: true }), letterSpacing: '0.2em', color: LIME, opacity: ramp(frame, 60, 10, EASE.out) }}>PRIORITY · THIS SPRINT</div>
            <div style={{ ...type(250, 800, { mono: true }), letterSpacing: '-0.04em', color: LIME, marginTop: 18, marginLeft: -12, textShadow: `0 0 60px ${alpha(LIME, 0.35)}` }}>
              <TextReveal text="P0" by="char" variant="rise" start={62} each={16} gap={3} />
            </div>
            <div style={{ height: 2, width: 360, marginTop: 28, background: alpha(L.ink, 0.18), transform: `scaleX(${ramp(frame, 70, 18, EASE.snappy).toFixed(4)})`, transformOrigin: '0 50%' }} />
            <div style={{ ...type(40, 500), color: L.ink, marginTop: 28 }}>
              <TextReveal text="7 open questions" by="word" variant="blur" start={74} each={14} gap={3} ease={EASE.out} />
            </div>
            <div style={{ ...type(32, 400), color: L.ink2, marginTop: 10 }}>
              <TextReveal text="Routing ships first." by="word" variant="blur" start={79} each={14} gap={3} ease={EASE.out} />
            </div>
          </div>
        </AbsoluteFill>
      )}
      <Vignette strength={vig} inner={0.4} color={L.shadow} cy={0.5} />
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
