// card-flock-tumble — Three UI cards tumble in 3D from knife-edge profile into a stepped lineup along a Catmull-Rom spline (tack-sharp throughout),
// continue slow rotation without stopping, pull inward to center with 10f acceleration, burst into a single turbulent smoke ring, and finish with giant headline slam.
// User directives preserved: zero blur on cards; exactly one smoke ring with turbulent frayed edges and very slow decay; never stop after landing; fast collapse; no particles.
//
// Design Decisions:
// - look = aurora (violet-pink darkfield). Unified palette: card ambient glow, background text wall, smoke ring, and giant headline all stay
//   within violet -> pink -> peach ribbon, replacing rainbow scheme; intensity driven by brightness and motion rather than color count.
// - Background: Rainbow stroke wall replaced with two 300px monochrome stroked "CRAFT THE SHOT" lines drifting in opposing directions (light violet 0.16),
//   with an aurora key light behind cards lifting the flock; on collapse, text wall shrinks toward center and fades out cleanly without muddying cards.
// - Framing: Flock center of gravity shifted lower-center (previously upper-left); convergence point = ring center = headline center, unified along one eye line.
// - Pacing: Eliminated 72-84f black gap — collapse arrives (70f) with an instant white-hot core flash (6f decay), ring sprouts directly from flash;
//   headline slams in at 74f (1.22 -> 1, snappy 14f + kerning compression), then slowly expands without stopping; eyebrow / motto follow in staggered cadence.
// - Giant headline is solid: white-hot core -> pale violet vertical gradient fill + pink-purple glow (the sole glow hero element),
//   topped with video-shotcraft mark + wordmark eyebrow, bottomed with 44px motto, finishing as a release poster.
// - Card UI = video-shotcraft workbench (Inbox / Shots / Home), rasterized at layout zoom via CARD_ZOOM.
//
// Timeline (30fps, 135f):
//   0–22    Text wall illuminates (6–22f), first card edge-on already in frame
//   10–54   Tumble: knife-edge -> tumble -> stepped lineup (spline + out cubic)
//   46–62   Stationary idle rotation (ry +0.34°/f, never stopping)
//   62–72   Collapse: 10f ease-in suction to center while scaling down; text wall shrinks and fades
//   70–76   Flash core: white-hot core + full-screen micro-exposure, 6f decay
//   70–135  Smoke ring: decelerated expansion -> continuous slow growth, very slow decay
//   74–88   Headline slam (snappy) -> continuous slow push; 84f eyebrow, 92f motto rise word-by-word
//   106–135 Hold: ring keeps growing, headline pushes in slowly, end frame forms poster
import React, { useId } from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { EASE, Grain, Vignette, ramp, mix } from '../../_fixtures/Polish';
import { LOOKS, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

const L = LOOKS.aurora;
const DISPLAY = '"Avenir Next", "SF Pro Display", "Helvetica Neue", sans-serif';

// ---------- Timeline ----------
export const CARD_FLOCK_TUMBLE_DURATION = 135;
const WALL_UP = [6, 22] as const; // Text wall lights up
const FLIGHT = [10, 54] as const; // Edge-on -> flight -> lineup: single continuous spline
const CARD_OUT = [62, 72] as const; // Collapse (fast: 10 frames converging to center)
const RING_T0 = 70; // Smoke ring spreads from convergence point (= flash frame)
const TEXT_T0 = 74; // Headline slam
const CY_OFF = 30; // Downward offset of card flock / convergence point relative to center

// ---------- Background: Monochrome stroked text wall + aurora key light ----------
const Backdrop: React.FC<{ frame: number }> = ({ frame }) => {
  const up = interpolate(frame, [WALL_UP[0], WALL_UP[1]], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: EASE.out });
  const k = ramp(frame, CARD_OUT[0], CARD_OUT[1] - CARD_OUT[0] + 4, EASE.exit); // Collapse: centripetal pull + fade out
  const wallOp = up * (1 - k);
  const drift = frame * 2.4;
  // After collapse, aurora key light switches to an afterglow behind the ring
  const bloomA = mix(0.5, 0.32, ramp(frame, CARD_OUT[0], 14, EASE.smooth));
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${L.bg[0]} 0%, ${L.bg[1]} 55%, ${L.bg[2]} 100%)`, overflow: 'hidden' }}>
      <AbsoluteFill style={{
        background: `radial-gradient(ellipse 46% 52% at 50% ${50 + (CY_OFF / 10.8).toFixed(1)}%, ${alpha(L.light, bloomA)} 0%, ${alpha(L.accent2, bloomA * 0.28)} 40%, ${alpha(L.light, 0)} 72%)`,
      }} />
      {wallOp > 0.01 && (
        <AbsoluteFill style={{ opacity: wallOp, transform: `scale(${mix(1, 0.7, k).toFixed(4)})` }}>
          {[0, 1].map((row) => (
            <div key={row} style={{
              position: 'absolute', top: row === 0 ? 60 : 640, left: 0, whiteSpace: 'nowrap',
              fontFamily: DISPLAY, fontWeight: 900, fontStyle: 'italic', fontSize: 300, letterSpacing: '-0.02em', lineHeight: 1,
              transform: `translateX(${((row === 0 ? -1 : 1) * drift - (row === 0 ? 300 : 1400)).toFixed(1)}px)`,
              color: 'transparent', WebkitTextStroke: `2.5px ${alpha('#d9c8ff', row === 0 ? 0.18 : 0.12)}`,
            }}>
              {'CRAFT THE SHOT  ·  CRAFT THE SHOT  ·  CRAFT THE SHOT  ·  '}
            </div>
          ))}
        </AbsoluteFill>
      )}
      {/* Horizon glow */}
      <div style={{
        position: 'absolute', left: '-10%', right: '-10%', top: '74%', height: '30%',
        background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.12)} 0%, ${alpha(L.accent, 0)} 70%)`,
      }} />
    </AbsoluteFill>
  );
};

// ---------- video-shotcraft UI cards (Editorial mock content: sidebar nav + three pages: Inbox / Shots / Home) ----------
// Cards scaled 1.6-1.74x in 3D: layout-level enlargement via CARD_ZOOM (CSS zoom, rasterized at target resolution),
// then scaled down by outer scale(s / CARD_ZOOM) — keeps typography crisp without bitmap blur.
const CARD_ZOOM = 1.75;
const UI = {
  sans: '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Inter, Arial, sans-serif',
  ink: '#17132a', ink2: '#5d5873', ink3: '#9a95ad', line: 'rgba(40,24,80,0.08)', fill: '#f5f3fb',
  violet: '#7c5cf6', pink: '#ec5fae', sky: '#5b8cff', mint: '#2fbf9b', amber: '#f0a23b',
};
const AV_COLORS = [UI.violet, UI.pink, UI.sky, UI.mint, UI.amber];
const Av: React.FC<{ t: string; i: number; size?: number }> = ({ t, i, size = 22 }) => (
  <div style={{
    width: size, height: size, borderRadius: size / 2, flex: 'none', background: AV_COLORS[i % AV_COLORS.length],
    color: '#fff', fontSize: size * 0.4, fontWeight: 650, display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 0 0 1.5px #fff', letterSpacing: '0.02em',
  }}>{t}</div>
);
const Chip: React.FC<{ c: string; children: React.ReactNode }> = ({ c, children }) => (
  <div style={{
    height: 19, padding: '0 8px', borderRadius: 6, fontSize: 10, fontWeight: 650, display: 'flex', alignItems: 'center',
    gap: 4, color: c, background: `${c}1c`, whiteSpace: 'nowrap', flex: 'none',
  }}>
    <div style={{ width: 5, height: 5, borderRadius: 3, background: c }} />{children}
  </div>
);
const NAV = ['Home', 'Inbox', 'Shots', 'Renders', 'Gallery'];
const INBOX = [
  ['AK', 'Ana Kim', 'Approved shot 04 · crash zoom', '2m'],
  ['MR', 'Marco Ruiz', 'Can we render the launch film today?', '9m'],
  ['JL', 'Jamie Lee', 'Assigned you “Cursor flyover”', '24m'],
  ['SO', 'Sam Ortiz', 'Left a note on the storyboard', '1h'],
  ['TN', 'Tara Nair', 'Approved the sound design pass', '2h'],
];
const TASKS: [string, string, string][] = [
  ['Crash zoom punch', 'Done', UI.mint],
  ['Cursor flyover', 'Rendering', UI.violet],
  ['Logo sting', 'Rendering', UI.violet],
  ['Beat-synced cuts', 'To do', UI.amber],
  ['Sound design pass', 'To do', UI.amber],
];
const PageBody: React.FC<{ seed: number }> = ({ seed }) => {
  if (seed === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {INBOX.map(([t, n, m, ago], i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, height: 46, borderBottom: `1px solid ${UI.line}` }}>
            <Av t={t} i={i} size={27} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 650, color: UI.ink }}>{n}</div>
              <div style={{ fontSize: 11, color: UI.ink2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m}</div>
            </div>
            <div style={{ fontSize: 10, color: UI.ink3, fontVariantNumeric: 'tabular-nums' }}>{ago}</div>
            {i < 2 && <div style={{ width: 6, height: 6, borderRadius: 3, background: UI.violet }} />}
          </div>
        ))}
      </div>
    );
  }
  if (seed === 1) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', fontSize: 9, fontWeight: 650, color: UI.ink3, letterSpacing: '0.08em', height: 24, alignItems: 'center', borderBottom: `1px solid ${UI.line}` }}>
          <span style={{ flex: 1, paddingLeft: 25 }}>SHOT</span><span style={{ width: 96 }}>STATUS</span><span style={{ width: 28 }} />
        </div>
        {TASKS.map(([name, st, c], i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', height: 42, borderBottom: `1px solid ${UI.line}` }}>
            <div style={{
              width: 14, height: 14, borderRadius: 7, marginRight: 11, flex: 'none',
              border: st === 'Done' ? 'none' : `1.5px solid ${UI.ink3}`, background: st === 'Done' ? UI.mint : 'transparent',
            }} />
            <div style={{ flex: 1, fontSize: 12.5, fontWeight: 550, color: st === 'Done' ? UI.ink3 : UI.ink, whiteSpace: 'nowrap' }}>{name}</div>
            <div style={{ width: 96 }}><Chip c={c}>{st}</Chip></div>
            <Av t={INBOX[(i + 2) % 5][0]} i={i + 2} size={21} />
          </div>
        ))}
      </div>
    );
  }
  const bars = [0.42, 0.66, 0.5, 0.82, 0.58, 0.94, 0.72];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ flex: 1, background: UI.fill, borderRadius: 10, padding: '11px 13px', boxShadow: `inset 0 0 0 1px ${UI.line}` }}>
          <div style={{ fontSize: 10, color: UI.ink3, fontWeight: 650 }}>Rendered this week</div>
          <div style={{ fontSize: 30, fontWeight: 750, color: UI.ink, letterSpacing: '-0.035em', lineHeight: 1.15, fontVariantNumeric: 'tabular-nums' }}>12</div>
          <div style={{ fontSize: 10, color: UI.mint, fontWeight: 650 }}>4 ahead of plan</div>
        </div>
        <div style={{ flex: 1.4, background: UI.fill, borderRadius: 10, padding: '11px 13px', boxShadow: `inset 0 0 0 1px ${UI.line}` }}>
          <div style={{ fontSize: 10, color: UI.ink3, fontWeight: 650 }}>Renders</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 54, marginTop: 6 }}>
            {bars.map((h, i) => (
              <div key={i} style={{
                flex: 1, height: `${h * 100}%`, borderRadius: 3,
                background: i === 5 ? `linear-gradient(180deg, ${UI.pink}, ${UI.violet})` : 'rgba(124,92,246,0.2)',
              }} />
            ))}
          </div>
        </div>
      </div>
      {TASKS.slice(1, 4).map(([name, st, c], i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, height: 27 }}>
          <div style={{ width: 3, height: 18, borderRadius: 2, background: c }} />
          <div style={{ flex: 1, fontSize: 12.5, fontWeight: 550, color: UI.ink }}>{name}</div>
          <Chip c={c}>{st}</Chip>
        </div>
      ))}
    </div>
  );
};
const UiCard: React.FC<{ seed: number; title: string }> = ({ seed, title }) => (
  <div
    style={{
      width: 560, height: 400, borderRadius: 16, boxSizing: 'border-box', display: 'flex', overflow: 'hidden', fontFamily: UI.sans,
      background: 'linear-gradient(180deg, #ffffff 0%, #faf8ff 100%)',
      // Violet ambient glow for aurora look + drop shadow + top inner highlight + 1px hairline border
      boxShadow: `inset 0 1px 0 #ffffff, 0 0 0 1px ${alpha('#d6c4ff', 0.4)}, 0 0 70px ${alpha(L.light, 0.32)}, 0 26px 70px rgba(4,1,12,0.6)`,
    }}
  >
    <div style={{ width: 118, background: '#f4f2fa', padding: '15px 10px', display: 'flex', flexDirection: 'column', gap: 3, borderRight: `1px solid ${UI.line}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '0 4px 11px' }}>
        <ShotcraftMark size={17} tone="light" />
        <div style={{ fontSize: 12, fontWeight: 800, color: UI.ink, letterSpacing: '-0.02em' }}>{BRAND.short}</div>
      </div>
      {NAV.map((n, i) => {
        const on = n === title;
        return (
          <div key={n} style={{
            display: 'flex', alignItems: 'center', gap: 7, height: 25, padding: '0 6px', borderRadius: 6,
            background: on ? 'rgba(124,92,246,0.12)' : 'transparent', color: on ? UI.violet : UI.ink2,
            fontSize: 11, fontWeight: on ? 650 : 500,
          }}>
            <div style={{ width: 9, height: 9, borderRadius: i % 2 ? 5 : 2.5, border: `1.5px solid ${on ? UI.violet : UI.ink3}` }} />
            {n}
          </div>
        );
      })}
      <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 6, padding: '0 4px' }}>
        <Av t="JL" i={2} size={18} />
        <div style={{ fontSize: 10, color: UI.ink2 }}>Jamie Lee</div>
      </div>
    </div>
    <div style={{ flex: 1, padding: '17px 20px', display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ fontWeight: 800, fontSize: 27, color: UI.ink, letterSpacing: '-0.035em' }}>{title}</div>
        <div style={{ marginLeft: 'auto', display: 'flex' }}>
          {[0, 1, 2].map((j) => <div key={j} style={{ marginLeft: j ? -5 : 0 }}><Av t={INBOX[(j + seed) % 5][0]} i={j + seed} size={20} /></div>)}
        </div>
        <div style={{
          height: 23, padding: '0 10px', borderRadius: 7, background: UI.violet, color: '#fff', fontSize: 10.5, fontWeight: 650,
          display: 'flex', alignItems: 'center', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.25)',
        }}>+ New</div>
      </div>
      <div style={{ fontSize: 11, color: UI.ink3, marginTop: -6 }}>
        {seed === 0 ? '5 unread · Today' : seed === 1 ? 'Launch film · 5 shots' : 'Good morning, Jamie'}
      </div>
      <PageBody seed={seed} />
    </div>
  </div>
);

// ---------- Flash core: white-hot core on convergence frame + full-screen micro-exposure (6f decay; no geometric rings, no particles) ----------
const CoreFlash: React.FC<{ frame: number }> = ({ frame }) => {
  const t = frame - RING_T0;
  if (t < -1 || t > 14) return null;
  const a = t < 0 ? 0.4 : Math.exp(-t / 3.2);
  return (
    <AbsoluteFill style={{ pointerEvents: 'none', mixBlendMode: 'screen' }}>
      <div style={{
        position: 'absolute', left: 960 - 420, top: 540 + CY_OFF - 420, width: 840, height: 840, borderRadius: '50%',
        background: `radial-gradient(circle, rgba(255,250,255,${a.toFixed(3)}) 0%, rgba(255,226,246,${(0.85 * a).toFixed(3)}) 9%, ${alpha(L.accent2, 0.45 * a)} 22%, ${alpha(L.light, 0.22 * a)} 44%, ${alpha(L.light, 0)} 70%)`,
      }} />
      <AbsoluteFill style={{ background: alpha('#f3e6ff', 0.12 * a) }} />
    </AbsoluteFill>
  );
};

// ---------- Single Turbulent Smoke Ring ----------
// Form: single ring; frayed turbulent edges (displacement mapping), alternating bright/dark patches along ring body;
// predominantly purple-pink with peach top; expands with deceleration and continues slow growth throughout; very slow diffusion decay; no water surface reflection in center.
const SmokeRing: React.FC<{ frame: number }> = ({ frame }) => {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const t = frame - RING_T0;
  if (t < 0) return null;
  const grow = Easing.out(Easing.cubic)(Math.min(1, t / 52));
  const R = 46 + 330 * grow + Math.max(0, t - 52) * 1.6;
  const op = interpolate(t, [0, 4, 30, 60], [0, 1, 0.94, 0.76], { extrapolateRight: 'clamp' });
  const w = R * interpolate(t, [0, 52], [0.36, 0.27], { extrapolateRight: 'clamp' });
  const disp = 60 + grow * 90;
  const rot = t * 0.35;
  const cy = 540 + CY_OFF;
  return (
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', mixBlendMode: 'screen' }}>
      <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
        <defs>
          <filter id={`smokeA-${uid}`} x="-60%" y="-60%" width="220%" height="220%">
            <feTurbulence type="fractalNoise" baseFrequency="0.013 0.016" numOctaves={4} seed={11} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={disp} xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <filter id={`smokeB-${uid}`} x="-60%" y="-60%" width="220%" height="220%">
            <feTurbulence type="fractalNoise" baseFrequency="0.021 0.018" numOctaves={4} seed={37} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={disp * 0.85} xChannelSelector="R" yChannelSelector="G" />
          </filter>
          <filter id={`smokeC-${uid}`} x="-60%" y="-60%" width="220%" height="220%">
            <feTurbulence type="fractalNoise" baseFrequency="0.019 0.023" numOctaves={3} seed={73} result="n" />
            <feDisplacementMap in="SourceGraphic" in2="n" scale={disp * 1.1} xChannelSelector="R" yChannelSelector="G" />
          </filter>
          {/* Top peach -> pink -> purple gradient along ring body (aurora ribbon) */}
          <linearGradient id={`ringGrad-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsla(24 80% 82% / 0.92)" />
            <stop offset="38%" stopColor="hsla(322 78% 72% / 0.9)" />
            <stop offset="100%" stopColor="hsla(262 80% 66% / 0.9)" />
          </linearGradient>
        </defs>
        <g transform={`rotate(${rot} 960 ${cy})`} opacity={op}>
          <g style={{ filter: `url(#smokeA-${uid})` }}>
            <circle cx={960} cy={cy} r={R} fill="none" stroke="hsla(285 70% 62% / 0.3)" strokeWidth={w * 1.9} style={{ filter: 'blur(22px)' }} />
          </g>
          <g style={{ filter: `url(#smokeA-${uid})` }}>
            <circle cx={960} cy={cy} r={R} fill="none" stroke={`url(#ringGrad-${uid})`} strokeWidth={w} style={{ filter: 'blur(9px)' }} opacity={0.88} />
          </g>
          <g style={{ filter: `url(#smokeB-${uid})` }}>
            <circle cx={960} cy={cy} r={R * 0.99} fill="none" stroke="hsla(318 90% 90% / 0.62)" strokeWidth={w * 0.42} style={{ filter: 'blur(6px)' }} />
          </g>
          <g style={{ filter: `url(#smokeC-${uid})` }}>
            <circle cx={960} cy={cy} r={R * 1.005} fill="none" stroke="hsla(262 50% 8% / 0.4)" strokeWidth={w * 0.4} style={{ filter: 'blur(7px)' }} />
          </g>
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// ---------- Card poses: Catmull-Rom spline continuous interpolation (true 3D smooth rotation) ----------
type Pose = { x: number; y: number; rx: number; ry: number; rz: number; s: number };
const POSE_KEYS: (keyof Pose)[] = ['x', 'y', 'rx', 'ry', 'rz', 's'];

const catmull = (p0: number, p1: number, p2: number, p3: number, t: number): number => {
  const t2 = t * t;
  const t3 = t2 * t;
  return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
};
const splinePose = (keys: Pose[], u: number): Pose => {
  const seg = u < 0.55 ? 0 : 1;
  const lt = seg === 0 ? u / 0.55 : (u - 0.55) / 0.45;
  const out = {} as Pose;
  for (const k of POSE_KEYS) {
    out[k] = catmull(keys[Math.max(0, seg - 1)][k], keys[seg][k], keys[seg + 1][k], keys[Math.min(2, seg + 2)][k], lt);
  }
  return out;
};

// Three cards: k0 knife-edge (near 90° profile) -> k1 mid-flight -> k2 stepped lineup (overlapping stack, s 1.6-1.74)
const CARDS: { title: string; k: [Pose, Pose, Pose]; conv: Pose }[] = [
  {
    title: 'Inbox',
    k: [
      { x: -8, y: -16, rx: 9, ry: 88, rz: 12, s: 1.05 },
      { x: -135, y: -92, rx: 16, ry: 44, rz: -8, s: 1.38 },
      { x: -108, y: -76, rx: 4, ry: 13, rz: -2, s: 1.62 },
    ],
    conv: { x: -20, y: -12, rx: 0, ry: 55, rz: 4, s: 0.12 },
  },
  {
    title: 'Shots',
    k: [
      { x: 0, y: 0, rx: 8, ry: 89, rz: 12, s: 1.0 },
      { x: -16, y: -7, rx: 13, ry: 38, rz: -7, s: 1.42 },
      { x: -5, y: -2, rx: 3, ry: 11, rz: -2, s: 1.68 },
    ],
    conv: { x: 0, y: 0, rx: 0, ry: 60, rz: 4, s: 0.12 },
  },
  {
    title: 'Home',
    k: [
      { x: 8, y: 16, rx: 7, ry: 90, rz: 12, s: 0.95 },
      { x: 112, y: 78, rx: 11, ry: 34, rz: -6, s: 1.46 },
      { x: 90, y: 70, rx: 2, ry: 9, rz: -1, s: 1.74 },
    ],
    conv: { x: 15, y: 10, rx: 0, ry: 65, rz: 4, s: 0.12 },
  },
];
const lerpPose = (a: Pose, b: Pose, t: number): Pose => {
  const out = {} as Pose;
  for (const k of POSE_KEYS) out[k] = a[k] + (b[k] - a[k]) * t;
  return out;
};

// Slow idle rotation after landing (never stopping, quadratic ease-in to prevent seam with spline), collapse starts from drifted pose
const idleAt = (f: number) => {
  const t = Math.min(f, CARD_OUT[0]) - FLIGHT[1] * 0.86;
  if (t <= 0) return { ry: 0, rx: 0, rz: 0 };
  const r = Math.min(1, t / 14) ** 2;
  return { ry: t * 0.34 * r, rx: t * -0.1 * r, rz: t * 0.05 * r };
};

export const CardFlockTumble: React.FC = () => {
  const frame = useCurrentFrame();

  // Headline: 14f snappy slam from 1.22 to 1 with kerning compression, followed by subtle continuous expansion (no frozen frames)
  const st = frame - TEXT_T0;
  const slam = ramp(frame, TEXT_T0, 14, EASE.snappy);
  const textScale = mix(1.22, 1, slam) + Math.max(0, st - 14) * 0.0008;
  const textOp = ramp(frame, TEXT_T0, 5, EASE.out);
  const glowK = 0.6 + 0.4 * Math.exp(-Math.max(0, st) / 10); // Glow flares on impact, then settles
  const tracking = mix(0.06, -0.025, slam);

  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <Backdrop frame={frame} />

      {/* Card flock (crisp throughout: no blur) */}
      {frame < CARD_OUT[1] + 2 && (
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', perspective: 1400, transform: `translateY(${CY_OFF}px)` }}>
          {CARDS.map((c, i) => {
            let pose: Pose;
            let op = 1;
            const drift = idleAt(frame);
            if (frame < FLIGHT[0]) {
              pose = c.k[0];
            } else if (frame < CARD_OUT[0]) {
              const raw = Math.min(1, (frame - FLIGHT[0]) / (FLIGHT[1] - FLIGHT[0]));
              pose = splinePose(c.k, Easing.out(Easing.cubic)(raw));
              pose = { ...pose, ry: pose.ry + drift.ry, rx: pose.rx + drift.rx, rz: pose.rz + drift.rz };
            } else {
              // Collapse: 10f ease-in acceleration toward center while shrinking; opacity stays 100% for first 55%, keeping suction readable
              const r = Math.min(1, (frame - CARD_OUT[0]) / (CARD_OUT[1] - CARD_OUT[0]));
              const e = Easing.in(Easing.quad)(r);
              const from = { ...c.k[2], ry: c.k[2].ry + drift.ry, rx: c.k[2].rx + drift.rx, rz: c.k[2].rz + drift.rz };
              pose = lerpPose(from, c.conv, e);
              op = 1 - Easing.in(Easing.cubic)(Math.max(0, (r - 0.55) / 0.45));
            }
            return (
              <div key={i} style={{
                position: 'absolute', opacity: op, zIndex: 10 + i,
                transform: `translate3d(${pose.x}px, ${pose.y}px, 0) rotateX(${pose.rx}deg) rotateY(${pose.ry}deg) rotateZ(${pose.rz}deg) scale(${pose.s / CARD_ZOOM})`,
              }}>
                <div style={{ zoom: CARD_ZOOM, position: 'relative' }}>
                  <UiCard seed={i} title={c.title} />
                  {/* Layer depth: rear cards dimmed slightly */}
                  {i < 2 && (
                    <div style={{ position: 'absolute', inset: 0, borderRadius: 16, background: '#140b26', opacity: i === 0 ? 0.2 : 0.1, pointerEvents: 'none' }} />
                  )}
                </div>
              </div>
            );
          })}
        </AbsoluteFill>
      )}

      <SmokeRing frame={frame} />
      <CoreFlash frame={frame} />

      {/* Headline layout lockup: eyebrow / solid headline / motto */}
      {st >= 0 && (
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', transform: `translateY(${CY_OFF}px)` }}>
          {/* Eyebrow: brand mark + lowercase wordmark (wordmark is not uppercase) */}
          <div style={{ position: 'absolute', top: 540 - 262, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 18 }}>
            <ShotcraftMark size={50} tone="dark" frameProgress={ramp(frame, TEXT_T0 + 8, 12, EASE.out)} cutProgress={ramp(frame, TEXT_T0 + 14, 10, EASE.out)} />
            <div style={{ ...type(30, 700), fontFamily: BRAND.font, color: '#f1e9ff', letterSpacing: '0.12em' }}>
              <TextReveal text={BRAND.name} by="char" variant="blur" start={TEXT_T0 + 10} each={12} gap={0.9} />
            </div>
          </div>
          <div style={{
            fontFamily: DISPLAY, fontWeight: 900, fontStyle: 'italic', fontSize: 282, lineHeight: 1, whiteSpace: 'nowrap',
            letterSpacing: `${tracking.toFixed(4)}em`, opacity: textOp, transform: `scale(${textScale.toFixed(4)})`,
            backgroundImage: 'linear-gradient(180deg, #ffffff 0%, #fbf3ff 38%, #d8c2ff 72%, #b693ff 100%)',
            WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
            filter: `drop-shadow(0 0 ${(18 * glowK).toFixed(1)}px ${alpha(L.accent2, 0.55 * glowK)}) drop-shadow(0 0 ${(60 * glowK).toFixed(1)}px ${alpha(L.light, 0.5 * glowK)})`,
            paddingRight: '0.08em',
          }}>CINEMATIC</div>
          <div style={{ position: 'absolute', top: 540 + 200, left: 0, right: 0, textAlign: 'center', ...type(44, 500), color: alpha('#f3ecff', 0.82) }}>
            <TextReveal text={PITCH.en.motto} by="word" variant="rise" start={TEXT_T0 + 18} each={16} gap={3} />
          </div>
        </AbsoluteFill>
      )}
      <Vignette strength={0.5} inner={0.48} color={L.shadow} />
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
