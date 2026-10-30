// overhead-tabletop-drop (Round 2 redesign)
// Core technique preserved: three page cards lie flat in a tabletop grid; camera cranes horizontally in top-down view (translateX only, angle locked),
// pauses for a beat after sliding past target, then plunges downward — rotateX / scale / translateX run concurrently, leveling out into full-screen.
//
// Design decisions
// - look: graphite (near-monochrome dark field · white · touch of champagne gold). Tabletop is a deep graphite matte surface with three ceiling spotlights casting
//   individual light pools; pages look like fresh print proofs laid out on a review table — dark table, white paper, contrast creates depth. Table has hairline grid +
//   printed label below each proof (01 SHOTS / 02 HOME / 03 CHANGELOG), serving as motion references for the lateral slide.
// - Content: three pages from video-shotcraft official site — shot catalog, homepage, changelog. Each page redesigned specifically for camera moves: large typography, minimal elements,
//   realistic copy. Target is the center homepage, settling full-screen into a poster: 150px two-line brand statement + right storyboard product visual.
// - Pacing: pan inspection (50f ease-in-out) → target selection (8f hold: target proof lifts 16px off table, its overhead spotlight brightens while other two dim) →
//   plunge (28f, zero-velocity start asymmetric curve, scale incorporates ~5% anticipation pull-back) → soft return to full-screen (8f) → product visual in page completes
//   a micro-action: golden "Hero shot" block slides into storyboard empty slot, seating with subtle overshoot → hold.
// - Q2: cards laid out at 2x settling resolution and scaled down to 0.5 on the table plane; text remains at native resolution when diving into full-screen.
//
// Timeline (30fps, 140f total)
//   0–50    Lateral pan inspection: translateX +760→−360 (smooth, slides past target by ~1/3 width), angle locked at 62°
//   44–60   Selection: target proof lifts 16px off table, shadow expands and diffuses; left/right overhead lights dim to 35%, target light +25%
//   58–86   Plunge dive: rotateX 62→−1.6, scale 1→2.04 (~5% anticipation pull-back), translateX −360→0 all run concurrently across three channels
//   86–94   Soft return to 0° / 2.0 front-facing full-screen; target proof simultaneously settles back onto tabletop
//   98–118  In-page action: golden shot block slides into empty slot from right (snappy + single overshoot), block in same column yields downward
//   94–140  Hold: ultra-slow creep in 1→1.012, ending on video-shotcraft homepage poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { LOOKS, alpha, type } from '../../_fixtures/Look';
import { EASE, FONT, Grain, Vignette, bezier, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const OVERHEAD_TABLETOP_DROP_DURATION = 140;

const L = LOOKS.graphite;
const PAPER = '#f4f1ea'; // Proof paper tone (warm white, avoiding pure white)
const INK = '#141414';
const INK2 = '#5f5c56';
const INK3 = '#9b968c';
const RULE = 'rgba(20,20,20,0.1)';
const GOLD = '#b8893a'; // Gold on paper (one stop darker than look's champagne gold, legible on white)
const SERIF_STACK = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif';

const CARD_W = 996;
const CARD_H = 560;
const GAP = 150;
const PITCH = CARD_W + GAP;
const RES = 2; // Cards laid out at final settling scale (1992×1120), then scaled to 0.5 in plane
const INNER = (CARD_H * RES) / 1080; // 1.037: 1920×1080 design fits full inside 2x card

const PAN_END = 50;
const DROP = 58;
const DROP_END = 86;
const SETTLE_END = 94;

const DIVE = bezier(0.36, 0, 0.12, 1); // Zero initial velocity, rapid acceleration, long deceleration settling
const DIVE_SCALE = bezier(0.45, -0.18, 0.12, 1); // Pulls back ~5% first (camera lifts slightly) before plunging

// ───────────── Three Proof Pages (1920×1080 design coordinates) ─────────────

const Nav: React.FC<{ active: string }> = ({ active }) => (
  <div style={{ position: 'absolute', left: 150, right: 150, top: 60, height: 64, display: 'flex', alignItems: 'center', fontFamily: FONT.sans }}>
    <ShotcraftMark size={44} tone="light" style={{ marginRight: 14, flex: 'none' }} />
    <div style={{ ...type(32, 700), fontFamily: BRAND.font, letterSpacing: '0.03em', color: INK }}>{BRAND.name}</div>
    <div style={{ display: 'flex', gap: 46, marginLeft: 90, ...type(26, 550), color: INK2 }}>
      {['Product', 'Shots', 'Changelog', 'Docs'].map((n) => (
        <span key={n} style={{ color: n === active ? INK : INK2, fontWeight: n === active ? 700 : 550 }}>{n}</span>
      ))}
    </div>
    <div style={{ marginLeft: 'auto', padding: '16px 30px', borderRadius: 999, background: INK, color: PAPER, ...type(24, 650) }}>View on GitHub</div>
  </div>
);

// Homepage right-hand product visual: launch film storyboard (5 acts × shot blocks); slot = slide-in progress of golden "Hero shot" block
const DAYS = ['Open', 'Hook', 'Demo', 'Proof', 'Outro'];
const BLOCKS: { d: number; y: number; h: number; t: string }[] = [
  { d: 0, y: 40, h: 120, t: 'Tilt reveal' },
  { d: 1, y: 190, h: 150, t: 'Crash zoom' },
  { d: 2, y: 60, h: 100, t: 'Whip pan' },
  { d: 3, y: 230, h: 120, t: 'Drone dive' },
  { d: 4, y: 40, h: 140, t: 'Logo sting' },
  { d: 0, y: 300, h: 110, t: 'Title card' },
  { d: 4, y: 290, h: 110, t: 'End card' },
];
const Planner: React.FC<{ slot: number }> = ({ slot }) => {
  const colW = 126;
  const x0 = 38;
  const s = Math.max(0, slot);
  return (
    <div style={{
      position: 'absolute', left: 1080, top: 250, width: 690, height: 600, borderRadius: 28, background: '#1a1a1c',
      boxShadow: '0 40px 80px -30px rgba(20,16,8,0.55), 0 0 0 1px rgba(0,0,0,0.2)', overflow: 'hidden', fontFamily: FONT.sans,
    }}>
      <div style={{ position: 'absolute', left: 40, top: 32, ...type(30, 700), color: '#f4f4f2' }}>Launch film</div>
      <div style={{ position: 'absolute', right: 40, top: 36, ...type(24, 550), color: '#8f8c86' }}>0:42 · 30 fps</div>
      {DAYS.map((d, i) => (
        <div key={d} style={{ position: 'absolute', left: x0 + i * colW, top: 96, width: colW - 12, ...type(22, 650, { caps: true }), color: '#8f8c86', letterSpacing: '0.12em' }}>{d}</div>
      ))}
      <div style={{ position: 'absolute', left: 40, right: 40, top: 132, height: 1, background: 'rgba(255,255,255,0.1)' }} />
      <div style={{ position: 'absolute', left: 0, top: 150, width: 700, height: 440 }}>
        {BLOCKS.map((b, i) => {
          // Demo column (d=2) blocks yield downward when golden block seats
          const push = b.d === 2 ? 150 * s : 0;
          return (
            <div key={i} style={{
              position: 'absolute', left: x0 + b.d * colW, top: b.y + push, width: colW - 12, height: b.h, borderRadius: 14,
              background: '#2a2a2d', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.06)', padding: '14px 14px', boxSizing: 'border-box',
              ...type(22, 600), color: '#c9c6bf', lineHeight: 1.18,
            }}>{b.t}</div>
          );
        })}
        {/* Golden shot block: slides from off-screen right into Demo column empty slot */}
        <div style={{
          position: 'absolute', left: mix(760, x0 + 2 * colW, slot), top: 60, width: colW - 12, height: 136, borderRadius: 14,
          background: 'linear-gradient(180deg, #e8c983 0%, #d4a85a 100%)', padding: '14px 14px', boxSizing: 'border-box',
          boxShadow: `0 ${12 + 18 * (1 - s)}px ${26 + 20 * (1 - s)}px -8px rgba(212,168,90,0.45), inset 0 1px 0 rgba(255,255,255,0.5)`,
          ...type(22, 750), color: '#2a1e08', lineHeight: 1.18,
        }}>Hero shot<div style={{ ...type(19, 650), color: 'rgba(42,30,8,0.65)', marginTop: 8 }}>120f</div></div>
      </div>
    </div>
  );
};

const HomePage: React.FC<{ slot: number }> = ({ slot }) => (
  <div style={{ position: 'absolute', inset: 0, background: PAPER, fontFamily: FONT.sans }}>
    <Nav active="Product" />
    <div style={{ position: 'absolute', left: 150, top: 290 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, ...type(24, 700, { caps: true }), color: GOLD, letterSpacing: '0.18em' }}>
        <div style={{ width: 36, height: 2, background: GOLD }} />For Claude Code &amp; Codex
      </div>
      <div style={{ ...type(148, 800), color: INK, marginTop: 34, lineHeight: 0.98, letterSpacing: '-0.05em' }}>
        Frame motion.<br /><span style={{ fontFamily: SERIF_STACK, fontStyle: 'italic', fontWeight: 400, letterSpacing: '-0.03em' }}>Craft the shot.</span>
      </div>
      <div style={{ ...type(34, 450), color: INK2, marginTop: 44, width: 860, lineHeight: 1.4 }}>
        Cinematic product videos, crafted by your agent. From screenshot to showreel.
      </div>
      <div style={{ display: 'flex', gap: 22, marginTop: 52 }}>
        <div style={{ padding: '22px 40px', borderRadius: 999, background: INK, color: PAPER, ...type(28, 650) }}>Get the skill</div>
        <div style={{ padding: '22px 40px', borderRadius: 999, boxShadow: `inset 0 0 0 2px ${RULE}`, color: INK, ...type(28, 600) }}>Watch the film →</div>
      </div>
    </div>
    <Planner slot={slot} />
  </div>
);

// Shot catalog page: three shot recipe cards (name / duration / one-liner), follows 3-column card layout
const PLANS = [
  { n: 'Crash zoom', p: '2s', u: '60 frames', d: 'Punch in on the one number that matters.' },
  { n: 'Drone dive', p: '4s', u: '120 frames', d: 'Fall from the overview straight into the hero.', hi: true },
  { n: 'Whip pan', p: '1s', u: '30 frames', d: 'Cut between pages at full speed.' },
];
const ShotsPage: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: PAPER, fontFamily: FONT.sans }}>
    <Nav active="Shots" />
    <div style={{ position: 'absolute', left: 0, right: 0, top: 200, textAlign: 'center', ...type(104, 800), color: INK, letterSpacing: '-0.045em' }}>Pick a shot.</div>
    <div style={{ position: 'absolute', left: 0, right: 0, top: 336, textAlign: 'center', ...type(32, 450), color: INK2 }}>Shot recipes for cinematic product films.</div>
    <div style={{ position: 'absolute', left: 200, right: 200, top: 450, display: 'flex', gap: 40 }}>
      {PLANS.map((pl) => (
        <div key={pl.n} style={{
          flex: 1, height: 500, borderRadius: 28, padding: '44px 44px', boxSizing: 'border-box',
          background: pl.hi ? INK : '#fbf9f4', color: pl.hi ? PAPER : INK,
          boxShadow: pl.hi ? '0 30px 60px -24px rgba(20,16,8,0.5)' : `inset 0 0 0 2px ${RULE}`,
        }}>
          <div style={{ ...type(30, 650), color: pl.hi ? '#e4c58a' : INK2 }}>{pl.n}</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 30 }}>
            <div style={{ ...type(120, 800), letterSpacing: '-0.05em' }}>{pl.p}</div>
            <div style={{ ...type(26, 500), opacity: 0.6 }}>/ {pl.u}</div>
          </div>
          <div style={{ ...type(28, 450), opacity: 0.72, marginTop: 30, lineHeight: 1.4 }}>{pl.d}</div>
        </div>
      ))}
    </div>
  </div>
);

const LOG = [
  { v: '2.4', d: 'Sep 12', t: 'Motion workbench', b: 'Tune every shot on a timeline, then render in one click.' },
  { v: '2.3', d: 'Aug 28', t: 'JianYing export', b: 'Hand the finished cut to your editor as a native draft.' },
  { v: '2.2', d: 'Aug 09', t: 'Beat-synced cuts', b: 'Every cut lands on the music, frame-accurate.' },
];
const ChangelogPage: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: PAPER, fontFamily: FONT.sans }}>
    <Nav active="Changelog" />
    <div style={{ position: 'absolute', left: 150, top: 200, ...type(104, 800), color: INK, letterSpacing: '-0.045em' }}>Changelog</div>
    <div style={{ position: 'absolute', left: 150, right: 150, top: 380 }}>
      {LOG.map((e) => (
        <div key={e.v} style={{ display: 'flex', gap: 60, padding: '38px 0', borderTop: `2px solid ${RULE}` }}>
          <div style={{ width: 260 }}>
            <div style={{ display: 'inline-block', padding: '8px 18px', borderRadius: 999, background: INK, color: PAPER, ...type(24, 700) }}>v{e.v}</div>
            <div style={{ ...type(26, 500), color: INK3, marginTop: 14 }}>{e.d}</div>
          </div>
          <div>
            <div style={{ ...type(48, 750), color: INK }}>{e.t}</div>
            <div style={{ ...type(28, 450), color: INK2, marginTop: 12 }}>{e.b}</div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

// ───────────── Tabletop ─────────────

// Single proof page: lying flat on table; lift = elevation off tabletop (px, along table normal)
const PageCard: React.FC<{ x: number; lift?: number; children: React.ReactNode }> = ({ x, lift = 0, children }) => (
  <div style={{
    position: 'absolute', left: x - (CARD_W * RES) / 2, top: -(CARD_H * RES) / 2, width: CARD_W * RES, height: CARD_H * RES,
    borderRadius: 10 * RES, overflow: 'hidden', boxSizing: 'border-box', background: PAPER,
    boxShadow: `${softShadow((4 + lift * 1.6) * RES, { strength: 3.2, color: '#000000' })}, inset 0 ${RES}px 0 rgba(255,255,255,0.7)`,
    backfaceVisibility: 'hidden', transform: `translateZ(${4 + lift}px) scale(${1 / RES})`,
  }}>
    <div style={{ width: 1920, height: 1080, zoom: INNER, position: 'relative' }}>{children}</div>
  </div>
);

// Printed labels on tabletop: index + page name (monospace, all-caps), placed outside proof bottom edge
const DeskTag: React.FC<{ x: number; n: string; label: string; on: number }> = ({ x, n, label, on }) => (
  <div style={{
    position: 'absolute', left: x - CARD_W / 2, top: CARD_H / 2 + 34, width: CARD_W, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18,
    fontFamily: FONT.mono, fontSize: 30, letterSpacing: '0.16em', color: alpha(L.ink, 0.42 + 0.5 * on), transform: 'translateZ(1px)',
  }}>
    <span style={{ color: on > 0.5 ? L.accent2 : alpha(L.ink, 0.5) }}>{n}</span>
    <span style={{ flex: 'none', width: 40, height: 2, background: alpha(L.ink, 0.25) }} />
    <span>{label}</span>
  </div>
);

export const OverheadTabletopDrop: React.FC = () => {
  const f = useCurrentFrame();

  // Lateral pan: translateX only (angle locked — inspection is pure tracking)
  const panX = mix(760, -360, ramp(f, 0, PAN_END, EASE.smooth));
  // Plunge dive: three channels start and stop in sync
  const d = ramp(f, DROP, DROP_END - DROP, DIVE);
  const ds = ramp(f, DROP, DROP_END - DROP, DIVE_SCALE);
  const rotX = f < DROP_END
    ? mix(62, -1.6, d)
    : f < 90
      ? mix(-1.6, 0.5, ramp(f, DROP_END, 4, EASE.smooth))
      : mix(0.5, 0, ramp(f, 90, 4, EASE.smooth));
  const push = mix(1, 1.012, ramp(f, SETTLE_END, 46, EASE.smooth)); // Ultra-slow push-in after settling
  const scale = (f < DROP_END ? mix(1, 2.04, ds) : mix(2.04, 2.0, ramp(f, DROP_END, SETTLE_END - DROP_END, EASE.smooth))) * push;
  const tx = f <= DROP ? panX : mix(-360, 0, d);

  // Selection: target proof lifts off table, spotlight intensity shifts
  const pick = ramp(f, 44, 16, EASE.out);
  const lift = 16 * (pick - ramp(f, 70, 18, EASE.smooth));
  const tilt = Math.max(0, Math.min(1, rotX / 62));
  // In-page micro-action: golden schedule block seats (snappy translation + overshoot settle)
  const slot = ramp(f, 98, 20, EASE.overshoot);

  // Spotlight pools (world coordinates, cast onto each proof): left/right lights dim after selection
  const pool = (x: number, k: number) =>
    `radial-gradient(ellipse 820px 620px at ${2800 + x}px 3200px, ${alpha('#f2efe6', 0.2 * k)} 0%, ${alpha('#f2efe6', 0.07 * k)} 45%, ${alpha('#f2efe6', 0)} 75%)`;
  const side = 1 - 0.65 * pick;
  const hero = 1 + 0.25 * pick;

  return (
    <AbsoluteFill style={{ background: L.bg[2], overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, perspective: 1600, perspectiveOrigin: '50% 42%' }}>
        {/* World origin = screen center; in-plane scale first, then rotateX, finally translateX */}
        <div style={{
          position: 'absolute', left: '50%', top: '50%', width: 0, height: 0, transformStyle: 'preserve-3d',
          transform: `translateX(${tx}px) rotateX(${rotX}deg) scale(${scale})`,
        }}>
          {/* Tabletop: deep graphite + 3 spotlight pools + hairline grid (fine 80 / coarse 400) */}
          <div style={{
            position: 'absolute', left: -2800, top: -3200, width: 5600, height: 4100, backfaceVisibility: 'hidden',
            background: [
              pool(-PITCH, side), pool(0, hero), pool(PITCH, side),
              'repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1.5px, transparent 1.5px, transparent 400px)',
              'repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0px, rgba(255,255,255,0.05) 1.5px, transparent 1.5px, transparent 400px)',
              'repeating-linear-gradient(90deg, rgba(255,255,255,0.022) 0px, rgba(255,255,255,0.022) 1px, transparent 1px, transparent 80px)',
              'repeating-linear-gradient(0deg, rgba(255,255,255,0.022) 0px, rgba(255,255,255,0.022) 1px, transparent 1px, transparent 80px)',
              `linear-gradient(180deg, ${L.bg[0]}, ${L.bg[1]})`,
            ].join(', '),
          }} />
          <DeskTag x={-PITCH} n="01" label="SHOTS" on={0} />
          <DeskTag x={0} n="02" label="HOME" on={pick} />
          <DeskTag x={PITCH} n="03" label="CHANGELOG" on={0} />
          <PageCard x={-PITCH}><ShotsPage /></PageCard>
          <PageCard x={0} lift={lift}><HomePage slot={slot} /></PageCard>
          <PageCard x={PITCH}><ChangelogPage /></PageCard>
          {/* Left/right proofs dim with spotlights: overlay with tabletop tone */}
          {[-PITCH, PITCH].map((x) => (
            <div key={x} style={{
              position: 'absolute', left: x - CARD_W / 2, top: -CARD_H / 2, width: CARD_W, height: CARD_H, borderRadius: 10,
              background: L.bg[1], opacity: 0.08 + 0.34 * pick, transform: 'translateZ(5px)', pointerEvents: 'none',
            }} />
          ))}
        </div>
      </div>
      {/* Spotlight volumetric beams (screen space): three beams cast diagonally onto proofs, tracking lateral card movement; dissipate with tilt during dive */}
      {[-PITCH, 0, PITCH].map((x, i) => {
        const k = (i === 1 ? hero : side) * tilt;
        if (k < 0.02) return null;
        const cx = 960 + tx + x * 0.92; // Card array centerline → screen x (slightly compressed under perspective)
        return (
          <div key={x} style={{
            position: 'absolute', left: cx - 560, top: -60, width: 1120, height: 560, pointerEvents: 'none', opacity: k,
            filter: 'blur(26px)', mixBlendMode: 'screen',
          }}>
            <div style={{
              position: 'absolute', inset: 0, clipPath: 'polygon(44% 0, 56% 0, 90% 100%, 10% 100%)',
              background: `linear-gradient(180deg, ${alpha('#f2efe6', 0.22)} 0%, ${alpha('#f2efe6', 0.09)} 60%, ${alpha('#f2efe6', 0.0)} 100%)`,
            }} />
          </div>
        );
      })}
      {/* Screen space: far field (upper screen) fades into night, recedes with tilt; vignette + grain */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: `linear-gradient(180deg, ${alpha(L.bg[2], 0.95 * tilt)} 0%, ${alpha(L.bg[2], 0.55 * tilt)} 24%, ${alpha(L.bg[2], 0)} 48%)`,
      }} />
      <Vignette strength={0.12 + 0.45 * tilt} inner={0.45} color="#000000" />
      <Grain opacity={0.04 + 0.05 * tilt} blend="soft-light" />
    </AbsoluteFill>
  );
};
