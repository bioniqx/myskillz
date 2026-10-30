// neon-triple-marquee — Three-row counter-directional neon marquee recap (technique inspired by clickup-30 61–64.5s)
//
// Second redesign (Night sign wall · oblique angle + wet pavement reflection):
// - look = custom "neon": blue-black brick wall + tri-color neon tubes (ice cyan / magenta / sodium amber). Rather than flat outlined text,
//   this models a physical neon sign wall: oblique camera angle (wall rotateY -17° -> -9° slow pan-in, perspective adds depth to word streams);
//   below the wall lies wet ground where active rows cast reflections and color pools.
// - Three tube layers: unlit glass tube (matching color, dim, persistent — keeping 3-row structure visible) -> energized colored tube + dual bloom -> near-white hot core;
//   light spills onto the brick wall behind (revealing mortar seams), grounding "tubes on a wall" rather than "text on a screen".
// - Typography: bold condensed font (Avenir Next Condensed Heavy), repeating FRAME / CRAFT / SHIP (video-shotcraft's
//   "Frame -> Craft -> Ship", adapted from brand motto "Frame motion. Craft the shot." as recap);
//   spacing measured via canvas text width, delimited by hollow diamonds (◇).
// - Round-robin cycle: 42f period, 14f phase offset, one lit and two dim; each activation strikes a 2-frame ignition flicker (authentic neon strike), followed by cosine envelope.
//   Three rows ignite sequentially at 0/5/10f; from 124f onward, rows power off top-to-bottom (two flickers then off),
//   settling into an unlit sign poster showing dark glass tubes against the wall, avoiding fade to black.
//
// Schedule (30fps, 150f total):
//   0–18     Ignition: three rows strike sequentially (from 0/5/10f), unlit glass tubes glow
//   18–124   Round-robin: 42f period, 14f phase offset, odd/even rows scroll in opposite directions at constant speed
//   124–142  Power down: rows power off top-to-bottom staggered by 6f with dual flickers
//   142–150  Dark hold: unlit glass tubes + wall ambient glow
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, Grain, Vignette, ramp, mix } from '../../_fixtures/Polish';
import { alpha } from '../../_fixtures/Look';

export const NEON_TRIPLE_MARQUEE_DURATION = 150;

const FONT = '"Avenir Next Condensed", "DIN Condensed", "Arial Narrow", Impact, sans-serif';
const WEIGHT = 800;
const SIZE = 286;
const GAP = SIZE * 0.36;
const PLANE_W = 2900; // Wall width (avoids exposing edges during oblique perspective shot)
const FLOOR_Y = 900; // Baseboard / floor line (wall coordinates)
const ROW_Y = [28, 318, 608];

const WALL = '#0a0b14';
// Brick texture: two-row running bond pattern (tiled SVG), subtle mortar lines revealed under illumination
const BRICK = `url("data:image/svg+xml;utf8,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='300' height='120'>" +
  "<rect width='300' height='120' fill='none'/>" +
  "<g stroke='rgba(255,255,255,0.04)' stroke-width='3'>" +
  "<line x1='0' y1='1.5' x2='300' y2='1.5'/><line x1='0' y1='61.5' x2='300' y2='61.5'/>" +
  "<line x1='1.5' y1='0' x2='1.5' y2='60'/><line x1='151.5' y1='0' x2='151.5' y2='60'/>" +
  "<line x1='76.5' y1='60' x2='76.5' y2='120'/><line x1='226.5' y1='60' x2='226.5' y2='120'/></g></svg>",
)}")`;

// Measured text width (deterministic across same font/size); falls back to estimation when DOM unavailable
const widthCache = new Map<string, number>();
const measure = (text: string) => {
  const hit = widthCache.get(text);
  if (hit !== undefined) return hit;
  let w = text.length * SIZE * 0.6;
  if (typeof document !== 'undefined') {
    const ctx = document.createElement('canvas').getContext('2d');
    if (ctx) {
      ctx.font = `${WEIGHT} ${SIZE}px ${FONT}`;
      w = ctx.measureText(text).width + text.length * SIZE * 0.02; // letterSpacing 0.02em
    }
  }
  widthCache.set(text, w);
  return w;
};

type Row = { word: string; color: string; core: string; dir: 1 | -1; speed: number };
const ROWS: Row[] = [
  { word: 'FRAME', color: '#38d9ff', core: '#e9fbff', dir: 1, speed: 9 },
  { word: 'CRAFT', color: '#ff3d9a', core: '#ffe6f3', dir: -1, speed: 11 },
  { word: 'SHIP', color: '#ffae34', core: '#fff3dc', dir: 1, speed: 9 },
];

// Ignition flicker sequence (deterministic): 0/1 gating, holds at 1 after 6 frames
const IGNITE = [0, 1, 0.15, 0, 0.9, 0.6];
const ignite = (f: number, at: number) => {
  const k = Math.floor(f - at);
  if (k < 0) return 0;
  return k < IGNITE.length ? IGNITE[k] : 1;
};
// Power-down sequence: two flickers then off
const KILL = [1, 0.2, 0.85, 0.1, 0.5, 0];
const kill = (f: number, at: number) => {
  const k = Math.floor(f - at);
  if (k < 0) return 1;
  return k < KILL.length ? KILL[k] : 0;
};

const PERIOD = 42;
const SLOT = PERIOD / 3; // 14f per row
// Round-robin brightness: each row illuminates in its 14f slot — 2f ignition flicker, 3f rise, plateau, 4f ease-in extinction
// overlapping 2f with next row (at least one row remains active, avoiding dark pauses)
const pulse = (f: number, i: number) => {
  if (f < 18) return 0;
  const ph = ((((f - 18) - i * SLOT) % PERIOD) + PERIOD) % PERIOD;
  const len = SLOT + 2;
  if (ph >= len) return 0;
  const fl = ph < 1 ? 0.6 : ph < 2 ? 0.25 : 1; // Ignition strike
  const up = ramp(ph, 1, 3, EASE.out);
  const down = 1 - ramp(ph, len - 5, 5, EASE.exit);
  return Math.max(up * down, 0) * fl;
};

const MarqueeRow: React.FC<{ row: Row; f: number; y: number; lit: number; glass: number; cheap?: boolean }> = ({ row, f, y, lit, glass, cheap }) => {
  const wordW = measure(row.word);
  const dotW = SIZE * 0.42;
  const unitW = wordW + GAP + dotW + GAP;
  const copies = Math.ceil(PLANE_W / unitW) + 3;
  const raw = (f * row.speed) % unitW;
  const offset = row.dir === 1 ? -unitW * 1.5 + raw : -unitW * 0.5 - raw;
  const base: React.CSSProperties = {
    position: 'absolute', top: y, left: 0, width: PLANE_W, height: SIZE * 1.05,
    transform: `translateX(${offset.toFixed(2)}px)`,
    fontFamily: FONT, fontWeight: WEIGHT, fontSize: SIZE, letterSpacing: '0.02em', lineHeight: 1, color: 'transparent',
  };
  // Delimiter: hollow diamond (border color/width match tube layer, glyphs stroked without fill)
  const text = (sep: string, bw: number) => Array.from({ length: copies }).map((_, i) => (
    <span key={i} style={{ position: 'absolute', left: i * unitW, top: 0, whiteSpace: 'nowrap' }}>
      {row.word}
      <span style={{
        position: 'absolute', left: wordW + GAP + dotW * 0.2, top: SIZE * 0.34, width: dotW * 0.6, height: dotW * 0.6,
        transform: 'rotate(45deg)', boxSizing: 'border-box', border: `${bw.toFixed(2)}px solid ${sep}`, borderRadius: 6,
      }} />
    </span>
  ));
  const tube = 6 + lit * 4;
  const core = 2 + lit * 1.8;
  return (
    <>
      {/* Unlit glass tube: matching dim color, keeps 3-row layout visible */}
      <div style={{ ...base, WebkitTextStroke: `6px ${alpha(row.color, 0.3 * glass)}` }}>{text(alpha(row.color, 0.3 * glass), 6)}</div>
      {lit > 0.02 && (
        <>
          {/* Energized tube body + dual bloom */}
          <div style={{
            ...base, WebkitTextStroke: `${tube.toFixed(2)}px ${row.color}`, opacity: Math.min(1, lit * 1.1),
            filter: cheap ? undefined : `drop-shadow(0 0 ${(3 + lit * 6).toFixed(1)}px ${row.color}) drop-shadow(0 0 ${(14 + lit * 22).toFixed(1)}px ${row.color}) drop-shadow(0 0 ${(40 + lit * 50).toFixed(1)}px ${alpha(row.color, 0.9)})`,
          }}>{text(row.color, tube)}</div>
          {/* Hot core: near-white thin line illuminated only when energized — key to authentic neon look */}
          <div style={{ ...base, WebkitTextStroke: `${core.toFixed(2)}px ${row.core}`, opacity: Math.min(1, lit * 1.3), filter: cheap ? undefined : `drop-shadow(0 0 2px ${alpha(row.core, 0.9)})` }}>
            {text(row.core, core)}
          </div>
        </>
      )}
    </>
  );
};

export const NeonTripleMarquee: React.FC = () => {
  const f = useCurrentFrame();

  // Power per row: ignition * shutdown
  const power = ROWS.map((_, i) => ignite(f, i * 5) * kill(f, 124 + i * 6));
  // Unlit glass: persistent after ignition, retains 0.6 after shutdown (unlit sign poster: tubes remain visible)
  const glass = ROWS.map((_, i) => Math.max(ignite(f, i * 5), f >= 124 ? 1 : 0) * (1 - 0.25 * ramp(f, 124 + i * 6 + 4, 8, EASE.out)));
  // Brightness: all rows flash on boot (0.7) -> round-robin cycle
  const lit = ROWS.map((_, i) => {
    const boot = f < 18 ? 0.7 * ignite(f, i * 5) * (1 - ramp(f, 12, 6, EASE.out)) : 0;
    const killFlash = f >= 124 ? 0.55 * kill(f, 124 + i * 6) * (f < 124 + i * 6 ? 0 : 1) : 0;
    return Math.max(boot, pulse(f, i) * power[i], killFlash);
  });

  // Camera: oblique angle on wall, rotateY -17° -> -9° slow pan-in (smooth), subtle overall push
  const cam = ramp(f, 0, 150, EASE.smooth);
  const rotY = mix(-17, -9, cam);
  const scale = mix(1.0, 1.05, cam);

  return (
    <AbsoluteFill style={{ background: '#05050a', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, perspective: 1700, perspectiveOrigin: '50% 45%' }}>
        <div style={{
          position: 'absolute', left: (1920 - PLANE_W) / 2, top: 40, width: PLANE_W, height: 1200,
          transform: `rotateY(${rotY.toFixed(3)}deg) scale(${scale.toFixed(4)})`, transformOrigin: '50% 40%',
        }}>
          {/* Brick wall: base color + subtle mortar lines (illuminated by light spill) */}
          <div style={{
            position: 'absolute', left: 0, top: -40, width: PLANE_W, height: FLOOR_Y + 40, background: WALL,
            backgroundImage: BRICK, backgroundSize: '300px 120px',
          }} />
          {/* Wall light spill: soft colored band behind each row, breathing with intensity (screen blend on brick) */}
          {ROWS.map((r, i) => (
            <div key={`spill${i}`} style={{
              position: 'absolute', left: 0, right: 0, top: ROW_Y[i] - 200, height: SIZE + 400, mixBlendMode: 'screen',
              background: `radial-gradient(ellipse 50% 44% at 50% 50%, ${alpha(r.color, 0.6)} 0%, ${alpha(r.color, 0.12)} 45%, ${alpha(r.color, 0)} 72%)`,
              opacity: 0.05 * glass[i] + lit[i] * 0.55,
            }} />
          ))}
          {ROWS.map((r, i) => (
            <MarqueeRow key={r.word} row={r} f={f} y={ROW_Y[i]} lit={lit[i]} glass={glass[i]} />
          ))}
          {/* Wet pavement: dark reflective plane below wall base, reflecting bottom row (flipped, blurred, faded) */}
          <div style={{ position: 'absolute', left: 0, top: FLOOR_Y, width: PLANE_W, height: 300, background: 'linear-gradient(180deg, #08080e 0%, #040407 100%)' }} />
          <div style={{
            position: 'absolute', left: 0, top: FLOOR_Y, width: PLANE_W, height: 300, overflow: 'hidden',
            WebkitMaskImage: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 70%)',
            maskImage: 'linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 70%)',
            filter: 'blur(3px)',
          }}>
            {/* Mirror: point y_w on wall reflects below floor at (FLOOR_Y - y_w); inner layer 600px tall flipped on center -> row at y_w - 300 */}
            <div style={{ position: 'absolute', left: 0, top: 0, width: PLANE_W, height: 600, transform: 'scaleY(-1)', transformOrigin: '50% 50%' }}>
              <MarqueeRow row={ROWS[2]} f={f} y={ROW_Y[2] - 300} lit={lit[2]} glass={glass[2]} cheap />
            </div>
          </div>
          {/* Floor color pool: light pool on pavement for each row (dimmer for distant rows) */}
          {ROWS.map((r, i) => (
            <div key={`pool${i}`} style={{
              position: 'absolute', left: 0, right: 0, top: FLOOR_Y - 40, height: 220, mixBlendMode: 'screen',
              background: `radial-gradient(ellipse 46% 40% at 50% 30%, ${alpha(r.color, 0.55)} 0%, ${alpha(r.color, 0)} 70%)`,
              opacity: lit[i] * [0.18, 0.28, 0.5][i],
            }} />
          ))}
          {/* Baseboard seam: hairline highlight separating wall and floor */}
          <div style={{ position: 'absolute', left: 0, top: FLOOR_Y, width: PLANE_W, height: 2, background: 'rgba(255,255,255,0.06)' }} />
          <div style={{ position: 'absolute', left: 0, top: FLOOR_Y, width: PLANE_W, height: 2, background: 'rgba(255,255,255,0.06)' }} />
        </div>
      </div>
      <Vignette strength={0.62} inner={0.36} color="#020205" />
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
