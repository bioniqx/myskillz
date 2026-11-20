// multiplane parallax (Round 2 redesign) — Real page split into 3 depth layers for lateral travel: a single drive displacement multiplied by layer coefficients
// (background 0.35x / midground 0.7x / foreground 1.4x); the velocity gradient turns a lateral slide into "gliding through space".
//
// Design decisions
// - look: sand (beige + terracotta, warm, paper feel). The real projects page itself is warm white paper, naturally unified with sand —
//   this shot feels like a camera on a slider skimming across a set of physical product still lifes on a warm-lit tabletop, rather than a 2D webpage panning.
// - Three layers each provide clear depth cues:
//   Background: full-page screenshot scaled down one stop, defocused by 5px, desaturated, with a warm atmospheric haze darker at the top (receding into the environment);
//   Midground: 10 real project cards (440px, primary reading layer, pin-sharp, two tiers of soft warm shadows falling onto the "tabletop");
//   Foreground: 5 enlarged terracotta / ink tag pills (sampled from real tags on cards) sweeping past the lens, with depth-of-field blur + velocity-based horizontal motion blur.
// - Text pinned to the frame (0x layer): top-left kicker (video-shotcraft logo + name) + 120px headline "Your page, in depth." + subtitle, serving as the stationary reference for the whole shot —
//   with text still and the world moving, parallax reads much more clearly.
// - Slider has an end stop: when the drive settles, card4 lands right in the screen center, then lifts (elevation 6→26, 1.035x) + terracotta border +
//   "In focus" badge; the final frame is a complete poster.
//
// Timeline (30fps, 165f)
//   0–6     Opening: all 3 layers already on screen; headline starts rising word-by-word (frame 1 is not blank)
//   6–136   Slider 130f: asymmetric in-out (gentle start, uniform mid-section, very soft settle), midground total displacement 1020px
//   4–40    Headline: kicker letter-spacing tightens (4) → headline rises word-by-word (8) → subtitle (26)
//   122–144 Hero lift: card4 rises + border + badge (out curve, settling ~8f later than position)
//   144–164 Hold 20f: background drifts ultra-slowly by 4px to keep the frame alive
import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from 'remotion';
import layout from '../../_textures/live-layout.json';
import { EASE, SpeedBlur, bezier, mix, ramp, softShadow, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const MULTIPLANE_DUR = 165;

const L = LOOKS.sand;
const CARDS = layout.projects.cards;
const DRIVE_EASE = bezier(0.45, 0, 0.18, 1);
const HERO = 3; // card4
const MID_W = 440;
const GAP = 500; // Midground card pitch
const ROW_X = 260; // Card 0 left edge (midground layer coordinates)
const ROW_Y = 410;
// Total drive: midground (0.7x) brings card4 center exactly to screen center at settle
const MID_END = 960 - (ROW_X + HERO * GAP + MID_W / 2);
const DRIVE = -MID_END / 0.7;
const driveAt = (f: number) => DRIVE * ramp(f, 6, 130, DRIVE_EASE) + 4 * ramp(f, 136, 29, EASE.smooth);

// Foreground pills: tags taken from real card tags; x is foreground layer coordinates, y is screen coordinates.
// At settle (foreground displacement -2040), only EdgeAI / ASR remain near the bottom edge framing the shot; the rest have slid off-screen
const PILLS = [
  { t: 'Calibration', x: 1200, y: 880, tone: 'accent' },
  { t: 'Routing', x: 1640, y: 296, tone: 'ink' },
  { t: 'EdgeAI', x: 2600, y: 905, tone: 'paper' },
  { t: 'Benchmark', x: 4300, y: 300, tone: 'ink' },
  { t: 'ASR', x: 3720, y: 860, tone: 'accent' },
] as const;

export const MultiplaneReal: React.FC = () => {
  const frame = useCurrentFrame();
  const drive = driveAt(frame);
  const vFg = -1.4 * velocity(driveAt, frame); // Foreground screen velocity (px/frame)
  const lift = ramp(frame, 122, 22, EASE.out);
  const ring = ramp(frame, 128, 16, EASE.snappy);
  const kick = ramp(frame, 4, 20, EASE.snappy);
  const sub = ramp(frame, 26, 18, EASE.out);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.0 }} fill={{ x: 0.85, y: 1 }} grain={0.06}>
        {/* Background 0.35x: full page scaled down one stop, defocused, desaturated (page background matches canvas, so lateral move shows no seams) */}
        <div style={{ position: 'absolute', left: 0, top: 0, transform: `translateX(${(-drive * 0.35).toFixed(2)}px)`, filter: 'blur(5px) saturate(0.7)', opacity: 0.75 }}>
          <Img src={staticFile('textures/live/projects-full.png')} style={{ position: 'absolute', left: -40, top: -170, width: 2100 }} />
        </div>
        {/* Aerial perspective: warm thin haze over background, denser at the top */}
        <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(180deg, ${alpha(L.bg[0], 0.82)} 0%, ${alpha(L.bg[1], 0.62)} 50%, ${alpha(L.bg[2], 0.55)} 100%)` }} />
        {/* Tabletop: supporting surface for midground card shadows, with a faint horizon light */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: ROW_Y + 330, height: 340, background: `linear-gradient(180deg, ${alpha(L.shadow, 0)}, ${alpha(L.shadow, 0.06)} 40%, ${alpha(L.shadow, 0.02)})` }} />
      </Stage>

      {/* Midground 0.7x: horizontal row of real cards (primary reading layer, no blur) */}
      <div style={{ position: 'absolute', left: 0, top: ROW_Y, transform: `translateX(${(-drive * 0.7).toFixed(2)}px)` }}>
        {CARDS.map((c, k) => {
          const hero = k === HERO;
          const h = (MID_W * c.h) / c.w;
          const e = hero ? mix(6, 26, lift) : 6;
          return (
            <div key={c.file} style={{
              position: 'absolute', left: ROW_X + k * GAP, top: (312 - c.h) * (MID_W / c.w) * 0.5, width: MID_W, height: h, borderRadius: 12, overflow: 'hidden',
              transform: hero ? `translateY(${(-14 * lift).toFixed(2)}px) scale(${(1 + 0.035 * lift).toFixed(4)})` : undefined,
              boxShadow: `0 0 0 ${hero ? (2.5 * ring).toFixed(2) : 0}px ${alpha(L.accent, 0.9)}, ${softShadow(e, { color: L.shadow, strength: 1.2 })}`,
            }}>
              <Img src={staticFile(`textures/live/${hero ? 'card4-hires.png' : c.file}`)} style={{ width: '100%', height: '100%' }} />
            </div>
          );
        })}
        {/* Hero badge: drops from card top edge after lifting */}
        <div style={{
          position: 'absolute', left: ROW_X + HERO * GAP + 2, top: -64, height: 44, padding: '0 18px', borderRadius: 22, display: 'flex', alignItems: 'center', gap: 10,
          background: L.accent, color: L.onAccent, ...type(22, 700, { caps: true }), letterSpacing: '0.14em', whiteSpace: 'nowrap',
          opacity: ring, transform: `translateY(${((1 - ring) * 14 - 14 * lift).toFixed(2)}px)`,
          boxShadow: softShadow(8, { color: L.shadow }),
        }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: L.onAccent }} />
          In focus
        </div>
      </div>

      {/* Foreground 1.4x: enlarged tag pills sweep past lens (defocused, deeper and further shadows), horizontal motion blur only during fast section */}
      <SpeedBlur vx={vFg} amount={0.2} max={10}>
        <div style={{ position: 'absolute', inset: 0, transform: `translateX(${(-drive * 1.4).toFixed(2)}px)` }}>
          {PILLS.map((p) => {
            const bg = p.tone === 'accent' ? L.accent : p.tone === 'ink' ? L.ink : L.surface;
            const fg = p.tone === 'paper' ? L.ink : L.onAccent;
            return (
              <div key={p.t} style={{
                position: 'absolute', left: p.x, top: p.y, height: 128, padding: '0 56px', borderRadius: 64, display: 'flex', alignItems: 'center',
                background: bg, color: fg, ...type(60, 650), filter: 'blur(7px)', opacity: 0.92,
                boxShadow: `0 40px 70px -10px ${alpha(L.shadow, 0.35)}`,
              }}>{p.t}</div>
            );
          })}
        </div>
      </SpeedBlur>

      {/* 0x layer: headline pinned to frame */}
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, ...type(22, 700, { caps: true }), letterSpacing: `${mix(0.5, 0.18, kick).toFixed(3)}em`, color: L.accent, opacity: kick }}>
          <ShotcraftMark size={34} tone="light" />
          <span style={{ textTransform: 'none', fontFamily: BRAND.font, fontSize: 26, fontWeight: 700, letterSpacing: '0.03em', color: L.ink }}>{BRAND.name}</span>
          <span style={{ width: 28, height: 2, background: L.accent }} />
          2.5D camera moves
        </div>
        <div style={{ marginTop: 18, ...type(120, 760), color: L.ink }}>
          <TextReveal text="Your page, in depth." by="word" variant="rise" start={8} each={20} gap={4} />
        </div>
      </div>
      <div style={{ position: 'absolute', right: 120, top: 196, width: 520, textAlign: 'right', ...type(34, 450), lineHeight: 1.35, color: L.ink2, opacity: sub, transform: `translateY(${((1 - sub) * 14).toFixed(1)}px)` }}>
        Screenshots, split into layers and flown in 2.5D.
      </div>
    </AbsoluteFill>
  );
};
