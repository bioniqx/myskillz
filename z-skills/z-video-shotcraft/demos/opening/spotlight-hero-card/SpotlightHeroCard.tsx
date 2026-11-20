// spotlight-hero-card — Spotlight sweeps across UI to target hero card -> oblique push-in -> card elevates into hover ->
// dual contour light beams trace borders -> reseats. A hero-focused opener establishing the centerpiece object.
//
// Iteration 2 redesign (graphite theater · tungsten spotlight):
// - look = graphite. UI screenshot placed in a darkened theater: full page dimmed to ~14% ambient luminance,
//   with full native UI color preserved only within the spotlight pool. Light is warm tungsten white with a volumetric light cone from above carrying subtle dust motes.
//   Lamp strikes on decisively: 2f flash -> 1f rebound -> steady hold, akin to a stage light thrown on switch.
// - Light pool roves across 3 intermediate stations (operator searching) -> locks onto card: pool contracts + lock-on pulse + surround dims further.
// - Camera: Frontal wide -> 18f push into oblique left close-up (rotY 34 deg dominant + rotX 8 deg), locking completely on arrival.
// - Card: rise (overshoot) -> hover sin bob -> reseat (gentle touchdown compression + champagne landing ring). Hover shadow falls opposite key light,
//   diffusing with altitude (key light consistently top-right).
// - Contour beams: champagne gold + white core (graphite accent2), tracing 2 laps around hero: lap 1 brisk and bright, lap 2 slow and subtle.
// - 3D annotations (shared 3D space and camera): bold white typography "Your product, / in motion." on dark UI,
//   with a champagne marker bar growing behind the keyword; annotation drops back flush to UI plane as card reseats,
//   locking into a hero poster: card in spotlight + headline.
//
// Timeline (30fps, 172f total):
//   0–6     Dark field: page ~14% brightness; f2–6 lamp strike (flash-rebound-steady)
//   6–34    Spotlight roves across 3 stations (smooth in-out with 2–3f pauses)
//   34–44   Lock-on: pool narrows to card + 6% pulse, surround dims 0.80->0.90
//   40–58   Camera pushes into oblique close-up (18f), high-res card texture crossfades 40–46
//   56–66   Card pops up (10f overshoot); 66–124 hover bob (40f cycle)
//   68–82   Contour beam lap 1 (fast, bright); 88–108 lap 2 (slow, soft)
//   70–84   Annotation entrance (rise + de-blur), 84–96 marker bar extends
//   124–142 Reseat (18f); annotation synchronously drops flush; 142 touchdown: landing ring + compression
//   142–172 Hold: camera locked, gentle dust drift in beam, subtle breathing in light pool
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam2D, CamKey2D } from '../../_fixtures/PageCam2D';
import { EASE, FONT, Grain, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, alpha } from '../../_fixtures/Look';
import layout from '../../_textures/live-layout.json';

export const SPOTLIGHT_HERO_CARD_DURATION = 172;

const L = LOOKS.graphite;
const GOLD = L.accent2; // Champagne gold: beam / marker / landing ring
const BEAM_CORE = 'rgba(255,250,238,0.98)';
const LAMP = '255,238,212'; // Warm tungsten white
const PATCH = 'oklch(97.5% 0.008 82)';

const PAGE_H = layout.projects.pageH;
const MAIN = 3;
const CARD = layout.projects.cards[MAIN];
const MCX = CARD.x + CARD.w / 2; // ≈ 960
const MCY = CARD.y + CARD.h / 2; // 772
const RADIUS = 16;

// —— Beats ——
const LOCK = 34;
const PUSH0 = 40;
const PUSH1 = 58;
const RISE0 = 56;
const RISE1 = 66;
const RESEAT0 = 124;
const LAND = 142;

const CAM_KEYS: CamKey2D[] = [
  { frame: 0, cx: 960, cy: 600, zoom: 0.8, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: PUSH0, cx: 960, cy: 600, zoom: 0.8, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: PUSH1, cx: MCX - 105, cy: MCY - 10, zoom: 2.6, rotX: 8, rotY: 34, rotZ: 2, persp: 1200 },
  { frame: SPOTLIGHT_HERO_CARD_DURATION, cx: MCX - 105, cy: MCY - 10, zoom: 2.6, rotX: 8, rotY: 34, rotZ: 2, persp: 1200 },
];
const PUSH_EASE = Easing.bezier(0.35, 0, 0.2, 1);
const POP_EASE = Easing.bezier(0.2, 1.25, 0.3, 1);
const RESEAT_EASE = Easing.bezier(0.4, 0, 0.3, 1.05);

const clampOpt = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// Pure function page camera matching PageCam2D 3D coordinate math, enabling annotation layer to share identical camera
const camAt = (frame: number) => {
  let a = CAM_KEYS[0];
  let b = CAM_KEYS[CAM_KEYS.length - 1];
  for (let i = 0; i < CAM_KEYS.length - 1; i++) {
    if (frame >= CAM_KEYS[i].frame && frame <= CAM_KEYS[i + 1].frame) { a = CAM_KEYS[i]; b = CAM_KEYS[i + 1]; break; }
  }
  const t = a.frame === b.frame ? 1 : interpolate(frame, [a.frame, b.frame], [0, 1], { ...clampOpt, easing: PUSH_EASE });
  const m = (x?: number, y?: number) => (x ?? 0) + ((y ?? 0) - (x ?? 0)) * t;
  return { cx: m(a.cx, b.cx), cy: m(a.cy, b.cy), zoom: m(a.zoom, b.zoom), rotX: m(a.rotX, b.rotX), rotY: m(a.rotY, b.rotY), rotZ: m(a.rotZ, b.rotZ), persp: m(a.persp, b.persp) };
};
const NoteCam: React.FC<{ frame: number; children: React.ReactNode }> = ({ frame, children }) => {
  const c = camAt(frame);
  return (
    <AbsoluteFill style={{ overflow: 'hidden', pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', inset: 0, perspective: `${c.persp * c.zoom}px`, perspectiveOrigin: '960px 540px' }}>
        <div style={{
          position: 'absolute', width: 1920, height: PAGE_H, zoom: c.zoom, transformOrigin: `${c.cx}px ${c.cy}px`, transformStyle: 'preserve-3d',
          transform: `translate(${960 / c.zoom - c.cx}px, ${540 / c.zoom - c.cy}px) rotateY(${c.rotY}deg) rotateX(${c.rotX}deg) rotateZ(${c.rotZ}deg)`,
        }}>
          {children}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const SpotlightHeroCard: React.FC = () => {
  const frame = useCurrentFrame();

  // --- Lamp strike: flash -> rebound -> steady (stage light switch) ---
  const lamp = interpolate(frame, [1, 3, 4, 6], [0, 1, 0.62, 1], clampOpt);

  // --- Spotlight wander (screen %): 3 waypoints with brief pauses -> locks onto card -> centers during push-in ---
  const ST = [4, 10, 13, 19, 22, 28, LOCK, PUSH1];
  const spotX = interpolate(frame, ST, [24, 24, 72, 72, 38, 38, 50, 60], { ...clampOpt, easing: EASE.smooth });
  const spotY = interpolate(frame, ST, [30, 30, 40, 40, 62, 62, 64, 55], { ...clampOpt, easing: EASE.smooth });
  const poolBase = interpolate(frame, [22, LOCK, PUSH1], [400, 300, 470], { ...clampOpt, easing: EASE.swift });
  const pulse = interpolate(frame, [LOCK, LOCK + 4, LOCK + 10], [0, 0.06, 0], clampOpt);
  const breathe = 1 + 0.015 * Math.sin((frame - LAND) / 14) * ramp(frame, LAND, 20, EASE.out);
  const poolRx = poolBase * (1 + pulse) * breathe;
  const poolRy = poolBase * interpolate(frame, [PUSH0, PUSH1], [0.8, 0.92], clampOpt) * (1 + pulse) * breathe;
  const dark = interpolate(frame, [0, LOCK, PUSH1], [0.9, 0.92, 0.94], clampOpt); // Surround dimming
  // Post-lock: screen-space circle transitions to page-space card-shaped mask (shared camera). Card sits above this dark field in z,
  // maintaining full native edge-to-edge brightness while falloff occurs outside. Both lights crossfade during push-in.
  const cardLight = ramp(frame, LOCK + 4, PUSH1 - LOCK - 4, EASE.smooth);
  const holdBreath = 1 + 0.012 * Math.sin((frame - LAND) / 14) * ramp(frame, LAND, 20, EASE.out);

  // --- Card: rise -> hover -> reseat ---
  const rise = interpolate(frame, [RISE0, RISE1], [0, 1], { ...clampOpt, easing: POP_EASE });
  const reseat = interpolate(frame, [RESEAT0, LAND], [0, 1], { ...clampOpt, easing: RESEAT_EASE });
  const lift = rise * (1 - reseat);
  const bob = Math.sin(((frame - RISE1) / 40) * Math.PI * 2) * 4 * lift;
  const z = 110 * lift + bob;
  const landed = frame >= LAND;
  const press = interpolate(frame, [LAND - 4, LAND - 1, LAND], [1, 0.997, 1], clampOpt);
  // Shadow: key light from upper right -> shadow projects lower left, expanding and softening with elevation
  const shadow = `${-10 * lift}px ${10 * lift}px ${12 + 12 * lift}px rgba(10,8,6,${0.35 * lift}), ${-36 * lift}px ${48 * lift}px ${90 * lift}px rgba(10,8,6,${0.42 * lift})`;

  const slotVis = Math.min(1, rise * 2) * (1 - reseat);
  const landPulse = interpolate(frame, [LAND - 4, LAND, LAND + 14], [0, 1, 0], clampOpt);
  const slotEdge = Math.min(1, 0.45 * (1 - reseat)) + landPulse * 0.5;

  // --- Dual contour light beam laps ---
  const beam1Prog = interpolate(frame, [68, 82], [0, 1], { ...clampOpt, easing: EASE.linear });
  const beam1On = frame >= 67 && frame <= 83;
  const beam2Prog = interpolate(frame, [88, 108], [0, 1], { ...clampOpt, easing: EASE.swift });
  const beam2On = frame >= 87 && frame <= 109;
  const beamTrail = interpolate(frame, [108, 122], [0.4, 0], clampOpt);
  const bw = CARD.w + 6;
  const bh = CARD.h + 6;

  const hiresIn = interpolate(frame, [PUSH0, PUSH0 + 6], [0, 1], clampOpt);
  const rimOn = 0.5 * Math.min(1, lift + ramp(frame, PUSH0, 16, EASE.linear));

  // --- Annotations ---
  const noteIn = ramp(frame, 70, 14, EASE.out);
  const noteSettle = interpolate(frame, [RESEAT0 - 4, LAND], [0, 1], { ...clampOpt, easing: RESEAT_EASE });
  const noteZ = 4 + (88 + Math.sin(((frame - 70) / 44) * Math.PI * 2) * 3) * (1 - noteSettle);
  const hl = ramp(frame, 84, 12, EASE.swift);

  // --- Volumetric light cone: source at upper right casting down to pool ---
  const px = (spotX / 100) * 1920;
  const py = (spotY / 100) * 1080;
  const sx = px + 420;
  const sy = -720;
  const coneW = poolRx * 0.6;
  const cone = `${sx - 26}px ${sy}px, ${sx + 26}px ${sy}px, ${px + coneW}px ${py}px, ${px - coneW}px ${py}px`;

  return (
    <AbsoluteFill style={{ backgroundColor: L.bg[2] }}>
      <PageCam2D src="textures/live/projects-full.png" pageH={PAGE_H} keys={CAM_KEYS} ease={PUSH_EASE} bg={L.bg[1]}>
        {/* Rim highlight along near edge of tilted plane */}
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 8, background: 'rgba(255,240,220,0.8)', filter: 'blur(6px)', opacity: rimOn, pointerEvents: 'none' }} />

        {/* Page-space dark field: full page dimmed with soft aperture at card position; translateZ(1) sits beneath card */}
        {cardLight > 0.001 ? (
          <svg width={1920} height={PAGE_H} style={{ position: 'absolute', left: 0, top: 0, transform: 'translateZ(1px)', opacity: cardLight, pointerEvents: 'none' }}>
            <defs>
              <filter id="shc-tight" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22" /></filter>
              <filter id="shc-wide" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="60" /></filter>
              <mask id="shc-hole" maskUnits="userSpaceOnUse" x={0} y={0} width={1920} height={PAGE_H}>
                <rect x={0} y={0} width={1920} height={PAGE_H} fill="white" />
                <rect x={CARD.x - 60} y={CARD.y - 50} width={CARD.w + 120} height={CARD.h + 100} rx={70} fill="#262626" filter="url(#shc-wide)" />
                <rect x={CARD.x - 14} y={CARD.y - 14} width={CARD.w + 28} height={CARD.h + 28} rx={RADIUS + 14} fill="black" filter="url(#shc-tight)" />
              </mask>
            </defs>
            <rect x={0} y={0} width={1920} height={PAGE_H} fill="rgb(14,12,10)" fillOpacity={Math.min(0.97, 0.94 * holdBreath)} mask="url(#shc-hole)" />
          </svg>
        ) : null}

        <div style={{ transformStyle: 'preserve-3d' }}>
          {/* Recessed card socket placeholder + champagne breathing outline */}
          {slotVis > 0.02 || landPulse > 0.02 ? (
            <div style={{
              position: 'absolute', left: CARD.x - 2, top: CARD.y - 2, width: CARD.w + 4, height: CARD.h + 4, transform: 'translateZ(1.5px)',
              background: slotVis > 0.02 ? PATCH : 'transparent', borderRadius: RADIUS,
              boxShadow: `inset 0 0 26px rgba(150,110,40,${(0.14 * slotEdge).toFixed(3)})`, opacity: Math.max(slotVis, landPulse),
            }}>
              <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, border: `1.5px solid ${GOLD}`, opacity: slotEdge, boxShadow: landPulse > 0.02 ? `0 0 ${(24 * landPulse).toFixed(1)}px ${alpha(GOLD, 0.8)}` : undefined }} />
            </div>
          ) : null}

          {/* Elevated hover card */}
          <div style={{
            position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h,
            transform: `translateZ(${(z + 2).toFixed(2)}px) scale(${press})`, transformOrigin: 'center center', transformStyle: 'preserve-3d',
          }}>
            <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, overflow: 'hidden', boxShadow: landed ? 'none' : shadow }}>
              <Img src={staticFile(`textures/live/${CARD.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }} />
              <Img src={staticFile('textures/live/card4-hires.png')} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', opacity: hiresIn }} />
              {/* Hover card surface lighting: warm top-right key -> soft falloff lower-left */}
              <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(200deg, rgba(${LAMP},0.35), rgba(${LAMP},0) 45%, rgba(20,16,10,0.08) 100%)`, opacity: lift, pointerEvents: 'none' }} />
            </div>
            <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, // Rim highlight: warm white hairline + subtle outer spill for edge definition against dark UI (lights post-lock)
              boxShadow: `inset 0 0 0 1px rgba(255,255,255,${(0.7 * lift).toFixed(3)}), 0 0 0 1.5px rgba(255,236,205,${(0.7 * cardLight).toFixed(3)}), 0 0 44px rgba(255,214,160,${(0.18 * cardLight).toFixed(3)})`, pointerEvents: 'none' }} />

            {/* Contour beam: SVG rounded rectangle tracing pathLength=1 traveling segment */}
            {(beam1On || beam2On) && lift > 0.4 ? (
              <svg width={bw} height={bh} viewBox={`0 0 ${bw} ${bh}`} style={{
                position: 'absolute', left: -3, top: -3, overflow: 'visible', pointerEvents: 'none', opacity: beam1On ? 1 : 0.62,
                filter: `drop-shadow(0 0 6px ${alpha(GOLD, 0.9)}) drop-shadow(0 0 18px rgba(255,236,200,0.55))`,
              }}>
                <rect x={2} y={2} width={bw - 4} height={bh - 4} rx={RADIUS} fill="none" stroke={GOLD} strokeWidth={beam1On ? 5 : 3.5} strokeLinecap="round"
                  pathLength={1} strokeDasharray="0.16 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
                <rect x={2} y={2} width={bw - 4} height={bh - 4} rx={RADIUS} fill="none" stroke={BEAM_CORE} strokeWidth={beam1On ? 2.5 : 1.75} strokeLinecap="round"
                  pathLength={1} strokeDasharray="0.16 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
              </svg>
            ) : null}
            {beamTrail > 0.01 ? (
              <div style={{ position: 'absolute', inset: -3, borderRadius: RADIUS + 3, border: `1.5px solid ${GOLD}`, opacity: beamTrail, pointerEvents: 'none' }} />
            ) : null}
          </div>
        </div>

      </PageCam2D>

      {/* —— Lighting (screen space) ——
          1. Darkness: multiply blend outside pool dims to ~14% ambient;
          2. Light pool: tungsten soft-light lifts midtones + gentle screen specular;
          3. Volumetric cone + suspended dust motes (screen blend). */}
      <AbsoluteFill style={{
        // Near-Gaussian falloff: transparent center -> 10% edge luminance; multi-stop gradient ensures soft organic vignette
        background: `radial-gradient(${(poolRx * 1.35).toFixed(1)}px ${(poolRy * 1.35).toFixed(1)}px at ${spotX}% ${spotY}%, rgba(14,12,10,0) 0%, rgba(14,12,10,0) 26%, rgba(14,12,10,${(dark * 0.25).toFixed(3)}) 44%, rgba(14,12,10,${(dark * 0.62).toFixed(3)}) 62%, rgba(14,12,10,${(dark * 0.9).toFixed(3)}) 80%, rgba(14,12,10,${dark.toFixed(3)}) 100%)`,
        mixBlendMode: 'multiply', pointerEvents: 'none', opacity: lamp * (1 - cardLight),
      }} />
      {/* Pre-strike dark mask: entire page dimmed before lamp ignition */}
      <AbsoluteFill style={{ background: 'rgba(14,12,10,1)', mixBlendMode: 'multiply', opacity: 0.84 * (1 - lamp), pointerEvents: 'none' }} />
      {/* Tungsten pool warm tone (soft-light, calibrated to preserve highlight detail) */}
      <AbsoluteFill style={{
        background: `radial-gradient(${(poolRx * 1.2).toFixed(1)}px ${(poolRy * 1.2).toFixed(1)}px at ${spotX}% ${spotY}%, rgba(${LAMP},0.24) 0%, rgba(${LAMP},0.12) 50%, rgba(${LAMP},0) 80%)`,
        mixBlendMode: 'soft-light', pointerEvents: 'none', opacity: lamp * (1 - cardLight), // Fades out post-lock: card retains native contrast
      }} />
      {/* Volumetric light cone: trapezoid + linear gradient + wide blur; softens during push-in */}
      <AbsoluteFill style={{ mixBlendMode: 'screen', pointerEvents: 'none', opacity: lamp * (1 - 0.45 * ramp(frame, PUSH0, 18, EASE.smooth)) }}>
        {/* Blur placed on outer layer, clipping on inner: ensures soft cone boundaries */}
        <div style={{ position: 'absolute', inset: 0, filter: 'blur(28px)' }}>
          <div style={{
            position: 'absolute', inset: 0, clipPath: `polygon(${cone})`,
            background: `linear-gradient(${(Math.atan2(py - sy, px - sx) * 180 / Math.PI - 90).toFixed(1)}deg, rgba(${LAMP},0.34) 0%, rgba(${LAMP},0.16) 60%, rgba(${LAMP},0.06) 100%)`,
          }} />
        </div>
        <div style={{ position: 'absolute', inset: 0, clipPath: `polygon(${cone})` }}>
          <Dust look={L} count={36} seed={4} drift={0.3} opacity={0.6} color="#fff1dc" />
        </div>
      </AbsoluteFill>
      {/* Annotation layer: shares camera geometry with page, rendered above lighting —
          treated as self-illuminated, immune to dark field multiply; dark backdrop masks underlying UI text */}
      <NoteCam frame={frame}>
          {/* 3D annotations: left of card, shared 3D camera; drops flush to page on reseat */}
          {frame >= 70 ? (
            <div style={{ transformStyle: 'preserve-3d', pointerEvents: 'none' }}>
              {/* Annotation soft shadow on page (retracts flush on landing) */}
              <div style={{
                position: 'absolute', left: 520, top: 760, width: 240, height: 70, transform: 'translateZ(2px)',
                background: 'radial-gradient(ellipse at 50% 50%, rgba(0,0,0,0.55), transparent 70%)', filter: 'blur(12px)',
                opacity: 0.5 * noteIn * (1 - noteSettle),
              }} />
              {/* Dark backdrop: isolates annotations from overlapping background UI text */}
              <div style={{
                position: 'absolute', left: 400, top: 600, width: 380, height: 240, // Right boundary stops before card left edge (x=781)
                transform: `translateZ(${(noteZ - 1).toFixed(2)}px) translateY(${((1 - noteIn) * 26).toFixed(2)}px)`,
                background: 'radial-gradient(ellipse 50% 50% at 52% 50%, rgba(16,14,12,0.97) 0%, rgba(16,14,12,0.9) 60%, rgba(16,14,12,0) 100%)',
                filter: 'blur(6px)', opacity: noteIn,
              }} />
              <div style={{
                position: 'absolute', left: 528, top: 662, width: 'max-content', whiteSpace: 'nowrap',
                transform: `translateZ(${noteZ.toFixed(2)}px) translateY(${((1 - noteIn) * 26).toFixed(2)}px)`,
                opacity: noteIn, filter: noteIn < 1 ? `blur(${((1 - noteIn) * 4).toFixed(2)}px)` : undefined,
                fontFamily: FONT.sans, letterSpacing: '-0.035em', lineHeight: 1.1,
              }}>
                <div style={{ fontSize: 34, fontWeight: 760, color: '#f6f3ec', textShadow: '0 2px 18px rgba(0,0,0,0.6)' }}>Your product,</div>
                <div style={{ position: 'relative', display: 'inline-block', marginTop: 2 }}>
                  <div style={{ position: 'absolute', left: -6, top: '8%', bottom: '2%', width: `calc(${hl.toFixed(4)} * (100% + 12px))`, background: GOLD, borderRadius: 4 }} />
                  <div style={{ position: 'relative', fontSize: 34, fontWeight: 760, color: hl > 0.55 ? '#14110c' : '#f6f3ec' }}>in motion.</div>
                </div>
              </div>
            </div>
          ) : null}
      </NoteCam>
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
