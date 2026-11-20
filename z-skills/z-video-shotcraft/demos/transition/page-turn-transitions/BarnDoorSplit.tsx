// Barn door split reveal: The old page splits down the center into two doors accelerating outward, revealing the new page emerging from the gap.
//
// Redesign (Ember - Release version upgrade):
// - look = ember (warm dark / orange). Semantic: "succession of old and new":
//   Old page = current release "Shotcraft 3" (placeholder version),
//   cool gray, no accent color, like an extinguished metal plate;
//   New page = "Shotcraft 4" release poster, warm dark stage + ember orange, with branded mark above kicker.
//   Both pages share identical layout and slots (kicker / 220px mark / subhead / 3 stat metrics);
//   when the doors open, "4" stands right where "3" stood, making the replacement instantly readable.
// - Doors are solid slabs with depth: 10px inner edge bevels catch light from the gap (orange rim light),
//   and the door surfaces warm up near the seam; light from the new page shines through the gap—
//   first a hairline bright streak traces out vertically from center (crack preview), then widens into a slit of light;
//   as doors slide away, the new page develops with an overexposed beam of light (screen blend, fading with distance).
// - Motion: Gap pre-opening ease-in (anticipation) flows into ease-in door acceleration of 1000px ("parting" not "pushed away"),
//   with horizontal motion blur tied to velocity;
//   New page emerges 1.08 -> 1 (snappy, starts 2f after doors); once settled, subhead rises word-by-word
//   and 3 metrics count from old to new values
//   (render 64s -> 11.8s, manual keyframes 12 -> 0: numbers tell the story "new version saves effort", placeholder values).
//
// Timeline (30fps, 150f total):
//   0–24    Old page established: cool gray poster, camera extremely slow push 1 -> 1.015; full frame at frame 0
//   20–30   Anticipation: center hairline traces up/down from midpoint (snappy 10f), doors warmed by light
//   30–40   Preparation: gap widens ease-in 0 -> 16px, light slit brightens
//   40–64   Main action: both doors translateX ∓1000 (ease-in 24f) + horizontal motion blur
//   42–78   New page emerges 1.08 -> 1 (snappy 36f); overexposed beam fades 40–74
//   64–110  Follow-through: subhead rises word-by-word (64), 3 metrics stagger-roll to new values (72–104)
//   110–150 Hold: embers slowly drift up, wordmark breathes light, camera slow push 1.8%, ending on full release poster
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, bezier, mix, ramp, velocity } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, TextReveal, alpha, glow, stagger, type } from '../../_fixtures/Look';
import { ShotcraftMark } from '../../_fixtures/Brand';

export const BARN_DOOR_SPLIT_DURATION = 150;

const L = LOOKS.ember;
// Old page: cool gray metal plate (deliberately no accent color)
const OLD = { bg0: '#1d1f23', bg1: '#141518', ink: '#9a9ea7', ink2: '#6f737b', ink3: '#4a4d54', line: 'rgba(255,255,255,0.07)' };

const CRACK = 20; // Hairline streak starts
const GAP = 30; // Gap pre-opening starts
const SLIDE = 40; // Doors begin accelerating
const SLIDE_D = 24;
const SLIDE_EASE = bezier(0.42, 0, 0.8, 0.25); // ease-in (~aggressive cubic-in): starts visibly, accelerates continuously, not vanishing only at the last frame

const gapAt = (f: number) => 16 * ramp(f, GAP, 10, EASE.exit);
const slideAt = (f: number) => 1000 * ramp(f, SLIDE, SLIDE_D, SLIDE_EASE);
const doorAt = (f: number) => gapAt(f) / 2 + slideAt(f); // Single door offset

// Three metrics: old value -> new value (illustrative)
const STATS = [
  { from: 64, to: 11.8, dec: 1, unit: 's', label: 'Median render' },
  { from: 12, to: 0, dec: 0, unit: '', label: 'Manual keyframes' },
  { from: 6, to: 30, dec: 0, unit: '', label: 'Preview fps' },
];

// Shared layout skeleton: kicker / mark / subhead / stat row (same slots = replacement semantics)
const Layout: React.FC<{
  kicker: React.ReactNode; mark: React.ReactNode; sub: React.ReactNode; stats: React.ReactNode;
}> = ({ kicker, mark, sub, stats }) => (
  <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', fontFamily: FONT.sans }}>
    <div style={{ marginTop: 214, height: 40 }}>{kicker}</div>
    <div style={{ marginTop: 26, height: 230, display: 'flex', alignItems: 'center' }}>{mark}</div>
    <div style={{ marginTop: 34, height: 60 }}>{sub}</div>
    <div style={{ marginTop: 92 }}>{stats}</div>
  </div>
);

const StatRow: React.FC<{ cells: { value: string; label: string; color: string; labelColor: string; line: string; o?: number; y?: number }[] }> = ({ cells }) => (
  <div style={{ display: 'flex', gap: 56 }}>
    {cells.map((c, k) => (
      <div key={k} style={{ width: 300, borderTop: `1px solid ${c.line}`, paddingTop: 26, opacity: c.o ?? 1, transform: `translateY(${(c.y ?? 0).toFixed(2)}px)` }}>
        <div style={{ ...type(72, 700), color: c.color, letterSpacing: '-0.04em' }}>{c.value}</div>
        <div style={{ ...type(30, 500), color: c.labelColor, marginTop: 10 }}>{c.label}</div>
      </div>
    ))}
  </div>
);

// Old page: Shotcraft 3 (cool gray poster)
const OldPage: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 70% 60% at 50% 30%, #25272c 0%, ${OLD.bg0} 45%, ${OLD.bg1} 100%)` }}>
    {/* Subtle horizontal streaks: brushed metal texture (very faint) */}
    <div style={{ position: 'absolute', inset: 0, opacity: 0.5, background: 'repeating-linear-gradient(180deg, rgba(255,255,255,0.012) 0px, rgba(255,255,255,0.012) 1px, transparent 1px, transparent 4px)' }} />
    <Layout
      kicker={<span style={{ ...type(30, 650, { caps: true }), letterSpacing: '0.22em', color: OLD.ink3 }}>Current release</span>}
      mark={<span style={{ ...type(220, 760), color: OLD.ink, letterSpacing: '-0.055em' }}>Shotcraft 3</span>}
      sub={<span style={{ ...type(48, 450), color: OLD.ink2 }}>Shot recipes for product films.</span>}
      stats={<StatRow cells={STATS.map((s) => ({
        value: `${s.from.toFixed(s.dec)}${s.unit}`, label: s.label, color: OLD.ink, labelColor: OLD.ink3, line: OLD.line,
      }))} />}
    />
  </div>
);

// New page: Shotcraft 4 (release poster on ember stage)
const NewPage: React.FC<{ frame: number }> = ({ frame }) => {
  const statP = (k: number) => ramp(frame, 72 + stagger(k, 3, 12, EASE.out), 26, EASE.snappy);
  const breath = 0.85 + 0.15 * Math.sin(frame / 16);
  return (
    <>
      <Layout
        kicker={
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 18 }}>
            <ShotcraftMark size={44} tone="dark" />
            <span style={{ ...type(30, 700, { caps: true }), letterSpacing: '0.22em', color: L.accent }}>Introducing</span>
          </span>
        }
        mark={
          <span style={{ ...type(220, 800), letterSpacing: '-0.055em', color: L.ink, position: 'relative' }}>
            Shotcraft{' '}
            <span style={{
              backgroundImage: `linear-gradient(180deg, ${L.accent2} 0%, ${L.accent} 70%, #e0471a 100%)`,
              WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
              filter: `drop-shadow(0 0 ${(30 * breath).toFixed(1)}px ${alpha(L.accent, 0.55)})`,
            }}>4</span>
          </span>
        }
        sub={
          <span style={{ ...type(48, 450), color: L.ink2 }}>
            <TextReveal text="One prompt to a finished promo." start={64} by="word" variant="rise" each={18} gap={3} />
          </span>
        }
        stats={<StatRow cells={STATS.map((s, k) => {
          const p = statP(k);
          const v = mix(s.from, s.to, p);
          return {
            value: `${v.toFixed(s.dec)}${s.unit}`, label: s.label,
            color: L.ink,
            labelColor: L.ink2, line: alpha(L.accent, 0.35),
            o: ramp(frame, 66 + k * 4, 12, EASE.out), y: mix(18, 0, ramp(frame, 66 + k * 4, 18, EASE.snappy)),
          };
        })} />}
      />
    </>
  );
};

// Door: 960px viewport containing full old page (right door inner layer shifted left 960px for alignment) + inner edge bevel + seam glow
// (Doors cast no shadow onto new page: light comes from behind doors, casting shadows toward camera; shadow in the gap would only muddy the light)
const Door: React.FC<{ side: 'left' | 'right'; offset: number; light: number; edge: number }> = ({ side, offset, light, edge }) => {
  const inner = side === 'left' ? 'right' : 'left';
  const toward = side === 'left' ? 'to left' : 'to right';
  return (
    <div style={{
      position: 'absolute', top: 0, left: side === 'left' ? 0 : 960, width: 960, height: 1080, overflow: 'hidden',
      transform: `translateX(${side === 'left' ? -offset : offset}px)`,
    }}>
      <div style={{ position: 'absolute', top: 0, left: side === 'left' ? 0 : -960, width: 1920, height: 1080 }}>
        <OldPage />
      </div>
      {/* Door surface warmed by slit light: brightest near seam, decaying over 520px outward */}
      {light > 0.01 && (
        <div style={{
          position: 'absolute', top: 0, bottom: 0, [inner]: 0, width: 620, mixBlendMode: 'screen', opacity: light,
          background: `linear-gradient(${toward}, ${alpha(L.light, 0.5)} 0%, ${alpha(L.light, 0.14)} 30%, ${alpha(L.light, 0)} 100%)`,
        }} />
      )}
      {/* Slab bevel: 10px thickness strip illuminated by seam light (bright -> warm -> dark) */}
      {edge > 0.01 && (
        <div style={{
          position: 'absolute', top: 0, bottom: 0, [inner]: 0, width: 10, opacity: edge,
          background: `linear-gradient(${toward}, #ffe2c2 0%, ${L.accent} 35%, #5a2410 100%)`,
        }} />
      )}
    </div>
  );
};

export const BarnDoorSplit: React.FC = () => {
  const frame = useCurrentFrame();
  const door = doorAt(frame);
  const vx = velocity(doorAt, frame);

  // Preview hairline: traces vertically from center; merges into light slit as gap opens
  const crack = ramp(frame, CRACK, 10, EASE.snappy);
  const seamLight = ramp(frame, CRACK, 12, EASE.out); // Door face glow / edge brightness
  const edge = frame >= GAP ? 1 : 0;
  // Overexposed light beam: fades as doors slide away
  const flash = ramp(frame, GAP, 12, EASE.exit) * (1 - ramp(frame, SLIDE + 6, 30, EASE.out));
  const bP = ramp(frame, SLIDE + 2, 36, EASE.snappy);
  const bScale = mix(1.08, 1, bP) * mix(1, 1.018, ramp(frame, 78, 72, EASE.smooth)); // Very slow push after settling to keep hold phase alive
  const push = mix(1, 1.015, ramp(frame, 0, SLIDE, EASE.smooth));
  const doorsGone = frame > SLIDE + SLIDE_D;
  const showNew = frame >= GAP;
  // Door face glow: fades as doors slide open (darker as doors move away from light source)
  const doorLight = seamLight * (1 - ramp(frame, SLIDE, 14, EASE.out) * 0.6);

  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: L.bg[2] }}>
      {/* New page: single Stage backdrop; mounted only when gap opens */}
      {showNew && (
        <div style={{ position: 'absolute', inset: 0, transform: `scale(${bScale.toFixed(5)})`, transformOrigin: '50% 46%' }}>
          <Stage look={L} keyLight={{ x: 0.5, y: 0.12 }} fill={{ x: 0.5, y: 1.08 }} breathe={0.6}>
            <Dust look={L} count={28} seed={4} drift={0.35} opacity={0.55} color={L.accent2} />
          </Stage>
          {/* Warm glow behind wordmark */}
          <div style={{
            position: 'absolute', left: 960 - 700, top: 366 - 260, width: 1400, height: 520,
            background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.16)} 0%, ${alpha(L.accent, 0)} 70%)`,
          }} />
          <NewPage frame={frame} />
          {/* Overexposed beam: light bursting through door gap */}
          {flash > 0.01 && (
            <div style={{
              position: 'absolute', top: 0, bottom: 0, left: 960 - (door + 160), width: 2 * (door + 160), mixBlendMode: 'screen', opacity: flash,
              background: `linear-gradient(90deg, ${alpha(L.light, 0)} 0%, ${alpha(L.light, 0.55)} 40%, ${alpha('#ffe6cc', 0.85)} 50%, ${alpha(L.light, 0.55)} 60%, ${alpha(L.light, 0)} 100%)`,
            }} />
          )}
        </div>
      )}

      {!doorsGone && (
        <div style={{ position: 'absolute', inset: 0, transform: `scale(${push.toFixed(5)})`, transformOrigin: '50% 50%' }}>
          <SpeedBlur vx={-vx} amount={0.09} max={22}>
            <Door side="left" offset={door} light={doorLight} edge={edge} />
          </SpeedBlur>
          <SpeedBlur vx={vx} amount={0.09} max={22}>
            <Door side="right" offset={door} light={doorLight} edge={edge} />
          </SpeedBlur>
          {/* Crack preview: hairline bright streak + bloom, tracing up and down from center */}
          {crack > 0 && frame < SLIDE + 4 && (
            <div style={{
              position: 'absolute', left: 960 - 1, top: 0, width: 2, height: 1080, transform: `scaleY(${crack.toFixed(4)})`,
              background: 'linear-gradient(180deg, rgba(255,226,194,0) 0%, #ffe2c2 22%, #fff6ec 50%, #ffe2c2 78%, rgba(255,226,194,0) 100%)',
              boxShadow: glow(L.accent, 0.9), opacity: 1 - ramp(frame, SLIDE, 4, EASE.out),
            }} />
          )}
        </div>
      )}
    </div>
  );
};
