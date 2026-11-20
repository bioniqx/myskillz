// glow-orb-ambient — ambient glow orbs breathing: three large orbs drift organically, central card rim glows as nearest orb approaches.
//
// Redesign (deep sea tides: frosted glass card):
// - look = custom "abyss": deep sea black with cyan tint; three orbs = tidal cyan (key) / deep sea blue / coral accent.
//   Orbs rendered via 1200/1000/760px multi-stop radial gradients (screen blend without runtime blur).
// - Hero is a 1100x600 frosted glass card (backdrop-filter blur + saturation): as orbs drift behind card, color filters
//   through glass into card surface. Outer rim glow takes color and distance of nearest orb, plus hairline directional rim light
//   oriented toward dominant orb.
// - Content: video-shotcraft video preview card (ShotcraftMark + wordmark, 160px title "Launch film",
//   36px value copy, 64 undulating audio waveform bars + 64px mono remaining time).
//   Organic breathing in graceful slow motion.
// - Rhythm: snappy entrance, extended breath, gentle convergence. Card rises 8-34f (snappy), text follows line-by-line;
//   orbs and waveform share tidal clock, decelerating 115-145f via out-sine into 25f static hold.
//
// Timeline (30fps, total 170f):
//   0-24     Orbs illuminate from dark field (ambient glow from frame 0)
//   8-34     Card rises: translateY 48->0, scale 0.96->1, fade in
//   18-56    Card typography: title unblurs (18f+) -> subtitle (32f) -> waveform bars grow left-to-right (36-60f)
//   0-115    Normal drift (staggered periods 96-150f, total amplitude >= 260px)
//   115-145  Tidal clock out-sine convergence to freeze; camera push 1->1.03 settles in sync
//   145-170  Static hold
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, Grain, Vignette, ramp } from '../../_fixtures/Polish';
import { TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const GLOW_ORB_AMBIENT_DURATION = 170; // ~5.7s: light up -> drift -> 115-145f converge -> last 25f static hold

// Custom look "abyss": deep sea cyan-black + tidal cyan / deep sea blue / coral
const C = {
  bg: ['#071a1e', '#041114', '#02090b'],
  ink: '#eefaf7', ink2: '#a3c2bd', ink3: '#5f807b',
  teal: '#1fd1b2', blue: '#2f6bff', coral: '#ff7059',
};

const W = 1920;
const H = 1080;
const CX = W / 2;
const CY = H / 2 + 10;
const CARD_W = 1100;
const CARD_H = 600;

const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};
const TAU = Math.PI * 2;

type Orb = { size: number; peak: number; c: string; bx: number; by: number; p1: number; p2: number; ax: number; ay: number; seed: number };
const ORBS: Orb[] = [
  { size: 1200, peak: 0.55, c: C.teal, bx: 560, by: 360, p1: 118, p2: 150, ax: 300, ay: 200, seed: 1 },
  { size: 1000, peak: 0.5, c: C.blue, bx: 1420, by: 660, p1: 132, p2: 96, ax: 280, ay: 190, seed: 2 },
  { size: 760, peak: 0.42, c: C.coral, bx: 1240, by: 220, p1: 104, p2: 142, ax: 300, ay: 160, seed: 3 },
];

const orbPos = (o: Orb, t: number) => {
  const f1 = h(o.seed * 7 + 1) * TAU, f2 = h(o.seed * 7 + 2) * TAU, f3 = h(o.seed * 7 + 3) * TAU, f4 = h(o.seed * 7 + 4) * TAU;
  return {
    x: o.bx + o.ax * (0.62 * Math.sin((TAU * t) / o.p1 + f1) + 0.38 * Math.sin((TAU * t) / o.p2 + f2)),
    y: o.by + o.ay * (0.6 * Math.sin((TAU * t) / o.p2 + f3) + 0.4 * Math.sin((TAU * t) / o.p1 + f4)),
  };
};

// Tidal clock: 0-115 real-time; 115-145 out-sine deceleration (A = 60/pi for continuous velocity); frozen thereafter
const T0 = 115, TS = 30;
const tide = (f: number) => (f <= T0 ? f : T0 + (2 * TS / Math.PI) * Math.sin((Math.PI / 2) * Math.min(1, (f - T0) / TS)));

// Waveform bar height (pure function of tidal clock, freezes in sync)
const BARS = 64;
const barH = (i: number, t: number) => {
  const x = i / (BARS - 1);
  const env = 0.35 + 0.65 * Math.sin(Math.PI * Math.min(1, x * 1.05)) ** 0.8;
  const w = 0.5 + 0.28 * Math.sin(i * 0.42 + t / 9) + 0.16 * Math.sin(i * 1.13 - t / 14) + 0.06 * Math.sin(i * 2.7 + t / 5);
  return Math.max(0.08, env * w);
};


export const GlowOrbAmbient: React.FC = () => {
  const f = useCurrentFrame();
  const t = tide(f);

  const orbIn = 0.35 + 0.65 * ramp(f, 0, 24, EASE.out);
  const cardIn = ramp(f, 8, 26, EASE.snappy);
  const cam = 1 + 0.03 * ramp(f, 0, 145, EASE.smooth);

  const pos = ORBS.map((o) => orbPos(o, t));

  // Card rim: nearest orb distance -> glow intensity; dominant orb sets rim light angle and color
  let glowK = 0, lead = 0;
  ORBS.forEach((o, i) => {
    const d = Math.hypot(pos[i].x - CX, pos[i].y - CY);
    const p = Math.min(1, Math.max(0, (760 - d) / 520));
    const g = p * (o.peak / 0.55);
    if (g > glowK) { glowK = g; lead = i; }
  });
  const leadC = ORBS[lead].c;
  const lp = pos[lead];
  const ang = (Math.atan2(lp.x - CX, -(lp.y - CY)) * 180) / Math.PI;
  const gAng = (ang + 180).toFixed(1); // Gradient 0% on illuminated side

  // Remaining time counter: updates once per second (settles at 00:38)
  const secs = 42 - Math.floor(Math.min(f, 145) / 30);
  const mm = String(Math.floor(secs / 60)).padStart(2, '0');
  const ss = String(secs % 60).padStart(2, '0');

  const barsIn = (i: number) => ramp(f, 36 + i * 0.36, 14, EASE.snappy);

  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${C.bg[0]} 0%, ${C.bg[1]} 55%, ${C.bg[2]} 100%)`, overflow: 'hidden' }}>
      <AbsoluteFill style={{ transform: `scale(${cam})`, transformOrigin: `${CX}px ${CY}px` }}>
        {/* Ambient orbs: multi-stop radial gradients (screen blend without runtime blur) */} 
        {ORBS.map((o, i) => (
          <div key={i} style={{
            position: 'absolute', left: pos[i].x - o.size / 2, top: pos[i].y - o.size / 2, width: o.size, height: o.size, borderRadius: '50%',
            background: `radial-gradient(circle closest-side, ${alpha(o.c, o.peak)} 0%, ${alpha(o.c, o.peak * 0.62)} 22%, ${alpha(o.c, o.peak * 0.3)} 48%, ${alpha(o.c, o.peak * 0.1)} 72%, ${alpha(o.c, 0)} 100%)`,
            opacity: orbIn, mixBlendMode: 'screen',
          }} />
        ))}
        {/* Distant dot grid providing depth reference */} 
        <div style={{
          position: 'absolute', inset: -40, opacity: 0.5,
          backgroundImage: `radial-gradient(circle, ${alpha('#cffff4', 0.12)} 1.2px, transparent 1.6px)`, backgroundSize: '40px 40px',
          WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at 50% 50%, #000 20%, transparent 85%)', maskImage: 'radial-gradient(ellipse 70% 70% at 50% 50%, #000 20%, transparent 85%)',
        }} />

        {/* Hero: frosted glass card */} 
        <div style={{
          position: 'absolute', left: CX - CARD_W / 2, top: CY - CARD_H / 2, width: CARD_W, height: CARD_H, borderRadius: 44,
          // Note: card ancestors must omit filter/opacity<1 to preserve backdrop-filter root —
          // entrance opacity applied directly on glass layer, outer wrapper applies transform only
          transform: `translateY(${(1 - cardIn) * 48}px) scale(${0.96 + 0.04 * cardIn})`,
          boxShadow: `0 0 ${(90 * glowK).toFixed(1)}px ${(8 * glowK).toFixed(1)}px ${alpha(leadC, 0.32 * glowK)}, 0 50px 120px -30px rgba(0,0,0,0.85)`,
        }}>
          <div style={{
            position: 'absolute', inset: 0, borderRadius: 44, overflow: 'hidden', opacity: Math.min(1, cardIn * 1.3),
            background: 'linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.035) 45%, rgba(255,255,255,0.05) 100%)',
            backdropFilter: 'blur(44px) saturate(1.5)', WebkitBackdropFilter: 'blur(44px) saturate(1.5)',
            boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.10), inset 0 1.5px 0 rgba(255,255,255,0.18)',
          }}>
            {/* Surface rim glow along dominant orb direction */} 
            <div style={{ position: 'absolute', inset: 0, opacity: 0.7 * glowK, background: `linear-gradient(${gAng}deg, ${alpha(leadC, 0.16)} 0%, ${alpha(leadC, 0)} 55%)` }} />

            {/* Header */} 
            <div style={{ position: 'absolute', left: 64, right: 64, top: 56, display: 'flex', alignItems: 'center', gap: 18, opacity: ramp(f, 14, 14, EASE.out) }}>
              <ShotcraftMark size={56} tone="dark" />
              <div style={{ ...type(36, 650), fontFamily: BRAND.font, letterSpacing: '0.03em', color: C.ink }}>{BRAND.name}</div>
              <div style={{
                marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12, padding: '10px 22px', borderRadius: 40,
                background: 'rgba(255,255,255,0.07)', boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.1)', ...type(32, 550), color: C.ink2,
              }}>
                <div style={{ width: 12, height: 12, borderRadius: 6, background: C.teal, boxShadow: `0 0 12px ${C.teal}` }} />
                Now playing
              </div>
            </div>

            {/* Title + description */} 
            <div style={{ position: 'absolute', left: 60, top: 150 }}>
              <TextReveal text="Launch film" by="char" variant="blur" start={18} each={20} gap={2.2} style={{ ...type(160, 650), letterSpacing: '-0.045em', color: C.ink }} />
            </div>
            <div style={{ position: 'absolute', left: 66, top: 334 }}>
              <TextReveal text="Beat-synced cuts · film-grade SFX" by="word" variant="blur" start={32} each={16} gap={2.5} style={{ ...type(36, 450), color: C.ink2 }} />
            </div>

            {/* Audio waveform + remaining time */} 
            <div style={{ position: 'absolute', left: 66, bottom: 64, width: 700, height: 96, display: 'flex', alignItems: 'center', gap: 5 }}>
              {Array.from({ length: BARS }, (_, i) => {
                const k = barsIn(i);
                const played = i < 22;
                return (
                  <div key={i} style={{
                    width: 6, height: Math.max(6, 96 * barH(i, t) * k), borderRadius: 3,
                    background: played ? C.ink : alpha(C.ink, 0.28), opacity: k,
                  }} />
                );
              })}
            </div>
            <div style={{ position: 'absolute', right: 64, bottom: 58, textAlign: 'right', opacity: ramp(f, 40, 16, EASE.out) }}>
              <div style={{ fontFamily: FONT.mono, fontSize: 64, fontWeight: 500, color: C.ink, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums', lineHeight: 1 }}>
                {mm}:{ss}
              </div>
              <div style={{ ...type(28, 500, { caps: true }), letterSpacing: '0.14em', color: C.ink3, marginTop: 12 }}>Remaining</div>
            </div>
          </div>
          {/* Directional rim light: hairline gradient edge illuminated on side facing dominant orb */} 
          <div style={{
            position: 'absolute', inset: 0, borderRadius: 44, padding: 1.5, boxSizing: 'border-box', pointerEvents: 'none', opacity: cardIn,
            background: `linear-gradient(${gAng}deg, ${alpha(leadC, 0.2 + 0.75 * glowK)} 0%, rgba(255,255,255,${(0.14 * glowK).toFixed(3)}) 35%, rgba(255,255,255,0) 62%)`,
            WebkitMask: 'linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)', WebkitMaskComposite: 'xor', maskComposite: 'exclude',
          }} />
        </div>
      </AbsoluteFill>
      <Vignette strength={0.5} inner={0.4} color="#010506" />
      <Grain opacity={0.1} blend="soft-light" />
    </AbsoluteFill>
  );
};
