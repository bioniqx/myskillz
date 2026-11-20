// neon-frame-forerun-orbit v5. Design intent:
// "All components and text should drop from the air and snap into place simultaneously"
// - Adjustment: changed staggered drop to all components and text dropping simultaneously from mid-air
// (same-frame lift/land, soft shadows converging in sync). Precedent: full-assembly reveal = simultaneous snap,
// staggered drop is tour syntax. Kept neon gradient frame + gray panel + background neon tube frames;
// camera rotateY continuous arc from left (+38 deg) to right (-26 deg).
// - Polish pass: upgraded workbench homepage (panel height 900 -> 790);
// isomorphic soft shadows: higher elevation = larger, softer, lighter; airborne body slightly enlarged; deep floor shadow;
// camera scale pulled back slightly; vignette + grain; total duration 140f.
// - Brand: video-shotcraft logo + wordmark, page content updated to shots/renders domain.
import React, { useId } from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { FONT, Grain, Vignette } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const NEON_FRAME_FORERUN_ORBIT_DURATION = 140; // Frame stroke 0.5s + orbit & simultaneous snap 3.8s + settle

const easeFall = Easing.bezier(0.5, 0.05, 0.6, 1); // Accelerated drop, soft landing at end

/* Float + isomorphic soft shadow: h = float height (px). Body lifts toward top-left (key light at top-left), leaving shadow in place:
 * higher = larger, softer, lighter; as h -> 0 shadow converges and disappears */
const FloatWrap: React.FC<{ h: number; children: React.ReactNode }> = ({ h, children }) => (
  <div style={{ position: 'relative' }}>
    {h > 1 && (
      <div style={{
        position: 'absolute', inset: 0,
        transform: `translate(${(h * 0.26).toFixed(2)}px, ${(h * 0.48).toFixed(2)}px) scale(${(1 + h * 0.0012).toFixed(4)})`,
        filter: `brightness(0) blur(${(1.5 + h * 0.11).toFixed(2)}px)`,
        opacity: Math.max(0.08, 0.3 - h * 0.0011),
        pointerEvents: 'none',
      }}>{children}</div>
    )}
    <div style={{ transform: `translate(${(-h * 0.36).toFixed(2)}px, ${(-h * 0.82).toFixed(2)}px) scale(${(1 + h * 0.0007).toFixed(4)})` }}>{children}</div>
  </div>
);

/* v5: All components and text drop from mid-air and snap simultaneously — unified LAND time,
 * same-frame departure (t=LAND-FALL), same-frame landing (t=LAND), shadows converging synchronously;
 * components differ only slightly in float height H (same window, velocity scales naturally with elevation) */
const LAND = 0.52;
const liftOf = (t: number, land: number, H: number) => {
  const FALL = 0.3;
  const p = Math.min(1, Math.max(0, (t - (LAND - FALL)) / FALL));
  return (1 - easeFall(p)) * H;
};

const mulberry32 = (a: number) => () => {
  let t = (a += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

const INK = '#1c1d22', INK2 = '#5d5f67', INK3 = '#9c9ea6';
const HAIR = 'rgba(20,22,28,0.08)';
const ACC = '#6a5ae0';

const PW = 1330;
const PH = 790;
const PL = 1000; // Normalized path length

// Rectangular path: starts from left edge midpoint (left edge lights first)
const FRAME_D = `M 0 ${PH / 2} L 0 0 L ${PW} 0 L ${PW} ${PH} L 0 ${PH} Z`;

// Linear micro-icons (18 viewBox)
const Glyph: React.FC<{ k: number; c?: string }> = ({ k, c = INK2 }) => {
  const p = { fill: 'none', stroke: c, strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg width={17} height={17} viewBox="0 0 18 18">
      {k === 0 && <path d="M3 8 L9 3 L15 8 V15 H3 Z M7.5 15 V11 H10.5 V15" {...p} />}
      {k === 1 && <path d="M2.5 10 L4.5 4 H13.5 L15.5 10 V14.5 H2.5 Z M2.5 10 H6.5 L7.5 11.5 H10.5 L11.5 10 H15.5" {...p} />}
      {k === 2 && <><circle cx={9} cy={9} r={6.2} {...p} /><path d="M6.2 9.2 L8.2 11.2 L12 7" {...p} /></>}
      {k === 3 && <path d="M4.5 2.5 H10.5 L14 6 V15.5 H4.5 Z M10.5 2.5 V6 H14 M7 9.5 H11.5 M7 12.5 H11.5" {...p} />}
      {k === 4 && <><rect x={2.5} y={2.5} width={13} height={13} rx={2} {...p} /><path d="M6 12.5 V9.5 M9 12.5 V6 M12 12.5 V8" {...p} /></>}
      {k === 5 && <><circle cx={9} cy={9} r={6.2} {...p} /><circle cx={9} cy={9} r={2.6} {...p} /></>}
    </svg>
  );
};

const NAV = ['Home', 'Inbox', 'My Shots', 'Recipes', 'Renders', 'Goals'];
const SPACES: [string, string][] = [['Launch film', '#8b7cf0'], ['Promo reel', '#e48aa8'], ['Explainers', '#5aa5e6'], ['Sound design', '#e8a35c'], ['Page captures', '#5bbf95']];
const RECENTS: [string, string, number][] = [
  ['Launch film v3', 'Storyboard · 2h ago', 3], ['Shot list', 'List · 4h ago', 2], ['Render queue', 'Dashboard · Yesterday', 4],
  ['Crash zoom recipe', 'Doc · Yesterday', 3], ['Beat grid', 'Board · Mon', 2], ['Hero frames', 'Whiteboard · Mon', 5], ['Ship the promo', 'Goal · Last week', 5],
];
const TASKS: [string, string, string, string][] = [
  ['Add shot: crash zoom on pricing', '#e05c5c', 'In review', 'Today'],
  ['Sync cuts to the soundtrack beat', '#e8a23c', 'In progress', 'Tomorrow'],
  ['Capture checkout page at 2x', '#e05c5c', 'Blocked', 'Today'],
  ['Tune the 2.5D camera move', '#5aa5e6', 'In progress', 'Fri'],
  ['Render launch film at 1080p', '#5aa5e6', 'To do', 'Mon'],
  ['Export JianYing project', '#9a9ca4', 'To do', 'Next week'],
];
const AV = ['#e4e1da', '#dde0e8', '#e8e2e8', '#dce6e1'];

const Chip: React.FC<{ w: number; i: number }> = ({ w, i }) => {
  const [title, meta, k] = RECENTS[i];
  return (
    <div style={{
      width: w, height: 74, background: '#ffffff', borderRadius: 10, padding: '13px 14px', boxSizing: 'border-box',
      boxShadow: `0 0 0 1px ${HAIR}, 0 1px 2px rgba(16,18,24,0.05), 0 6px 14px -8px rgba(16,18,24,0.12)`,
      display: 'flex', gap: 11, alignItems: 'flex-start',
    }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, background: '#f2f2f0', boxShadow: `inset 0 0 0 1px ${HAIR}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
        <Glyph k={k} c={i === 0 ? ACC : INK2} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: INK, letterSpacing: '-0.01em', whiteSpace: 'nowrap' }}>{title}</div>
        <div style={{ fontSize: 12.5, color: INK3, marginTop: 5, whiteSpace: 'nowrap' }}>{meta}</div>
      </div>
    </div>
  );
};

/* Workbench homepage; t=snap progress. All elements depart and land in the same frame */
const HomePage: React.FC<{ t?: number }> = ({ t = 1 }) => {
  const L = (land: number, H = 72) => liftOf(t, land, H * 1.7);
  return (
  <div style={{
    width: PW, height: PH, background: 'linear-gradient(180deg, #f8f8f7 0%, #f3f3f1 100%)', borderRadius: 6, display: 'flex',
    // No overflow clip: floating elements project beyond panel edge under perspective
    overflow: 'visible', boxSizing: 'border-box', fontFamily: FONT.sans,
  }}>
    <div style={{ width: 290, background: '#f0f0ee', borderRadius: '6px 0 0 6px', boxShadow: `inset -1px 0 0 ${HAIR}`, padding: '26px 22px', boxSizing: 'border-box' }}>
      <FloatWrap h={L(0.24, 84)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 26, padding: '0 4px' }}>
          {/* Brand: etched logo (light base) + video-shotcraft wordmark */}
          <ShotcraftMark size={30} tone="light" />
          <div style={{ fontFamily: BRAND.font, fontSize: 17, fontWeight: 700, color: INK, letterSpacing: '0.01em', whiteSpace: 'nowrap' }}>{BRAND.name}</div>
          <svg width={12} height={12} viewBox="0 0 12 12" style={{ marginLeft: 2 }}><path d="M3 4.5 L6 7.5 L9 4.5" fill="none" stroke={INK3} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" /></svg>
        </div>
      </FloatWrap>
      {NAV.map((n, i) => (
        <FloatWrap key={n} h={L(0.3 + i * 0.045, 66)}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 11, height: 36, padding: '0 10px', borderRadius: 8,
            background: i === 0 ? '#ffffff' : 'transparent', boxShadow: i === 0 ? `0 0 0 1px ${HAIR}, 0 1px 2px rgba(16,18,24,0.06)` : undefined,
          }}>
            <Glyph k={i} c={i === 0 ? ACC : INK2} />
            <div style={{ fontSize: 15, fontWeight: i === 0 ? 600 : 500, color: i === 0 ? INK : INK2 }}>{n}</div>
            {i === 1 && <div style={{ marginLeft: 'auto', fontSize: 11.5, fontWeight: 700, color: '#fff', background: ACC, borderRadius: 9, padding: '2px 7px', fontVariantNumeric: 'tabular-nums' }}>4</div>}
          </div>
        </FloatWrap>
      ))}
      <FloatWrap h={L(0.56, 62)}>
        <div style={{ fontSize: 11.5, fontWeight: 650, letterSpacing: '0.09em', color: INK3, margin: '26px 10px 10px' }}>SPACES</div>
      </FloatWrap>
      {SPACES.map(([n, c], i) => (
        <FloatWrap key={n} h={L(0.62 + i * 0.05, 66)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, height: 34, padding: '0 10px' }}>
            <div style={{ width: 18, height: 18, borderRadius: 5, background: c, boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)', color: '#fff', fontSize: 10.5, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{n[0]}</div>
            <div style={{ fontSize: 14.5, color: INK2 }}>{n}</div>
          </div>
        </FloatWrap>
      ))}
    </div>
    <div style={{ flex: 1, padding: '30px 40px', boxSizing: 'border-box' }}>
      <FloatWrap h={L(0.26, 90)}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 20 }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: INK, letterSpacing: '-0.025em' }}>Good morning, Dana</div>
          <div style={{ fontSize: 14, color: INK3 }}>Tuesday, Oct 14</div>
        </div>
      </FloatWrap>
      <FloatWrap h={L(0.34, 80)}>
        <div style={{
          height: 46, borderRadius: 12, marginBottom: 24, display: 'flex', alignItems: 'center', padding: '0 16px', background: '#ffffff',
          boxShadow: `0 0 0 1px rgba(20,22,28,0.11), 0 1px 2px rgba(16,18,24,0.05)`,
        }}>
          <svg width={17} height={17} viewBox="0 0 18 18"><circle cx={8} cy={8} r={5.2} fill="none" stroke={INK3} strokeWidth={1.8} /><path d="M12 12 L15.5 15.5" stroke={INK3} strokeWidth={1.8} strokeLinecap="round" /></svg>
          <div style={{ fontSize: 15, color: INK3, marginLeft: 12 }}>Search shots, recipes and renders…</div>
          <div style={{ marginLeft: 'auto', fontSize: 12, fontFamily: FONT.mono, color: INK3, background: '#f3f3f1', borderRadius: 6, padding: '3px 7px', boxShadow: `inset 0 0 0 1px ${HAIR}` }}>⌘K</div>
        </div>
      </FloatWrap>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 28 }}>
        {[0, 1, 2, 3, 4, 5, 6].map((i) => (
          <FloatWrap key={i} h={L(0.42 + i * 0.04, 76)}>
            <Chip w={228} i={i} />
          </FloatWrap>
        ))}
      </div>
      <FloatWrap h={L(0.72, 60)}>
        <div style={{ display: 'flex', gap: 26, marginBottom: 6, boxShadow: `inset 0 -1px 0 ${HAIR}` }}>
          {['My Work', 'Assigned', 'Comments', 'Done'].map((n, i) => (
            <div key={n} style={{ fontSize: 14.5, fontWeight: i === 0 ? 650 : 500, color: i === 0 ? INK : INK3, paddingBottom: 11, boxShadow: i === 0 ? `inset 0 -2px 0 ${ACC}` : undefined }}>{n}</div>
          ))}
        </div>
      </FloatWrap>
      {TASKS.map(([title, pri, status, due], i) => (
        <FloatWrap key={i} h={L(0.78 + i * 0.04, 64)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, height: 44, boxShadow: `inset 0 -1px 0 ${HAIR}` }}>
            <div style={{ width: 16, height: 16, borderRadius: 8, boxShadow: `inset 0 0 0 1.8px ${pri}` }} />
            <div style={{ fontSize: 15, color: INK, fontWeight: 500 }}>{title}</div>
            <div style={{ marginLeft: 'auto', fontSize: 12.5, fontWeight: 600, color: status === 'Blocked' ? '#b4453f' : INK2, background: status === 'Blocked' ? '#fbe8e6' : '#efefed', borderRadius: 6, padding: '3px 9px' }}>{status}</div>
            <div style={{ display: 'flex', width: 62, justifyContent: 'flex-end' }}>
              {[0, 1].map((k) => (
                <div key={k} style={{ width: 24, height: 24, borderRadius: 12, background: AV[(i + k) % 4], marginLeft: k ? -4 : 0, boxShadow: '0 0 0 2px #f6f6f5', fontSize: 9.5, fontWeight: 700, color: '#55575e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {['DW', 'MK', 'JS', 'AL'][(i + k) % 4]}
                </div>
              ))}
            </div>
            <div style={{ width: 78, textAlign: 'right', fontSize: 13, color: due === 'Today' ? '#c2453f' : INK3, fontVariantNumeric: 'tabular-nums' }}>{due}</div>
          </div>
        </FloatWrap>
      ))}
    </div>
  </div>
  );
};

type BgFrame = { x: number; y: number; w: number; h: number; hue: string; phase: number; period: number; skew: number };
const rng = mulberry32(20260718);
const HUES = ['#b06af0', '#e879c9', '#f0a35c', '#6a7df0', '#e0679a', '#8a5cf0', '#c06af0'];
const BG_FRAMES: BgFrame[] = Array.from({ length: 18 }).map(() => ({
  x: rng() * 2000 - 120, y: rng() * 1100 - 60,
  w: 160 + rng() * 480, h: 70 + rng() * 220,
  hue: HUES[Math.floor(rng() * HUES.length)],
  phase: rng() * 90, period: 55 + rng() * 70,
  skew: -14 + rng() * 10,
}));

export const NeonFrameForerunOrbit: React.FC = () => {
  const frame = useCurrentFrame();
  // Unique filter/gradient IDs per instance (sanitize useId colons for url())
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  // Rapid frame outline stroke at start (starts at left midpoint, splits in both directions, 14 frames)
  const trace = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.3, 0.1, 0.3, 1),
  });
  // Early panel illumination: hero motion is orbit + landing snap
  const lit = interpolate(frame, [8, 30], [0.25, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.35, 0, 0.3, 1),
  });
  const frameLine = interpolate(frame, [96, 130], [1, 0.35], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const rimGlow = interpolate(frame, [0, 20, 108, 138], [0.7, 1, 0.75, 0.5], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const bgLit = interpolate(frame, [0, 30, 100, 136], [0.3, 1, 0.85, 0.1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  // Camera angle arc: continuously rotates from left (+38 deg) to right (-26 deg), uninterrupted —
  // ease-in-out: gentle start/stop, steady rotation mid-flight
  const orbit = interpolate(frame, [0, 128], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.42, 0.05, 0.32, 1),
  });
  const rotY = 38 - 64 * orbit;             // +38° → -26°
  const rotX = 6 - 2.5 * orbit;
  const rotZ = 3 - 7.5 * orbit;             // Left view slight upward tilt -> right view slight downward tilt
  const scale = 0.8 + 0.08 * Math.sin(orbit * Math.PI) + 0.1 * orbit; // Mid-arc push-in, settles at 0.9
  // Perspective origin shifts horizontally with camera arc
  const pOrigin = 30 + 34 * orbit;
  const headP = trace * (PL / 2);
  // Snap progress: runs concurrently with rotation (frames 10-118)
  const drop = interpolate(frame, [10, 118], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ background: '#060509', overflow: 'hidden' }}>
      {/* Background neon tube frame group */}
      <svg width={1920} height={1080} style={{ position: 'absolute' }}>
        <defs>
          <filter id={`obgblur-${uid}`} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation={7} />
          </filter>
        </defs>
        {BG_FRAMES.map((b, i) => {
          const breath = 0.5 + 0.5 * Math.sin(((frame + b.phase) / b.period) * Math.PI * 2);
          const op = bgLit * (0.18 + 0.4 * breath);
          return (
            <g key={i} transform={`translate(${b.x} ${b.y}) skewY(${b.skew * 0.4}) skewX(${b.skew})`}>
              <rect width={b.w} height={b.h} rx={4} fill="none"
                stroke={b.hue} strokeWidth={7} filter={`url(#obgblur-${uid})`} opacity={op * 0.8} />
              <rect width={b.w} height={b.h} rx={4} fill="none"
                stroke={b.hue} strokeWidth={1.6} opacity={op} />
            </g>
          );
        })}
      </svg>
      {/* Main subject: frame and panel rotating along camera arc */}
      <div style={{ position: 'absolute', inset: 0, perspective: 1500, perspectiveOrigin: `${pOrigin}% 44%` }}>
        <div style={{
          position: 'absolute', left: (1920 - PW) / 2, top: (1080 - PH) / 2 - 10,
          transform: `scale(${scale}) rotateY(${rotY}deg) rotateX(${rotX}deg) rotateZ(${rotZ}deg)`,
          transformStyle: 'preserve-3d',
        }}>
          <div style={{ opacity: trace > 0.4 ? 1 : 0, filter: `brightness(${Math.max(0.05, lit)})` }}>
            <HomePage t={drop} />
            <div style={{
              position: 'absolute', inset: 0, borderRadius: 6,
              background: 'linear-gradient(150deg, rgba(30,20,60,0.5), rgba(0,0,0,0.78))',
              opacity: 1 - lit,
            }} />
          </div>
          {/* Panel floor shadow: deep, broad, soft, elevating panel above background tubes */}
          <div style={{
            position: 'absolute', left: 0, top: 0, width: PW, height: PH, borderRadius: 6, pointerEvents: 'none',
            boxShadow: '0 30px 90px -10px rgba(0,0,0,0.75), 0 8px 24px rgba(0,0,0,0.45)', opacity: Math.min(1, trace * 1.4),
            transform: 'translateZ(-1px)',
          }} />
          <div style={{
            position: 'absolute', left: -10, top: -10, width: PW + 20, height: PH + 20,
            borderRadius: 12, opacity: rimGlow * Math.min(1, trace * 1.6),
            boxShadow: '-18px -8px 42px 6px rgba(185,95,240,0.42), 22px 24px 56px 12px rgba(240,150,90,0.30), 0 14px 80px 22px rgba(200,100,220,0.20)',
          }} />
          <svg width={PW + 80} height={PH + 80} viewBox={`-40 -40 ${PW + 80} ${PH + 80}`}
            style={{ position: 'absolute', left: -40, top: -40 }}>
            <defs>
              <linearGradient id={`omainfg-${uid}`} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={PW} y2={PH}>
                <stop offset="0%" stopColor="#c07af5" />
                <stop offset="38%" stopColor="#e58bd8" />
                <stop offset="72%" stopColor="#f0b06a" />
                <stop offset="100%" stopColor="#e8925c" />
              </linearGradient>
              <filter id={`ofblur-${uid}`} x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation={10} />
              </filter>
              <filter id={`ofblur2-${uid}`} x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation={3} />
              </filter>
            </defs>
            {[1, -1].map((dir) => (
              <g key={dir}>
                <path d={FRAME_D} pathLength={PL} fill="none" stroke={`url(#omainfg-${uid})`}
                  strokeWidth={14} strokeLinecap="butt" filter={`url(#ofblur-${uid})`}
                  strokeDasharray={`${headP} ${PL}`}
                  strokeDashoffset={dir === 1 ? 0 : -(PL - headP)}
                  opacity={0.6 * rimGlow} />
                <path d={FRAME_D} pathLength={PL} fill="none" stroke={`url(#omainfg-${uid})`}
                  strokeWidth={3.5} strokeLinecap="butt"
                  strokeDasharray={`${headP} ${PL}`}
                  strokeDashoffset={dir === 1 ? 0 : -(PL - headP)}
                  opacity={0.95 * frameLine} />
                {trace < 1 && (
                  <path d={FRAME_D} pathLength={PL} fill="none" stroke="#ffffff"
                    strokeWidth={6} strokeLinecap="round" filter={`url(#ofblur2-${uid})`}
                    strokeDasharray={`8 ${PL}`}
                    strokeDashoffset={dir === 1 ? -(Math.max(0, headP - 8)) : -(PL - headP)}
                    opacity={0.95} />
                )}
              </g>
            ))}
          </svg>
        </div>
      </div>
      <Vignette strength={0.5} inner={0.45} color="#030206" />
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};
