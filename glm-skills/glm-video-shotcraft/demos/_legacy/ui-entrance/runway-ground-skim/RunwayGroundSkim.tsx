// runway-ground-skim v5 — Source video clickup-30.mp4 ~46–50s (clickup10 screenshots, 5 frames):
// User v5 feedback (verbatim): "Remove the bounce after landing, and make the whole drop faster"
// Implementation: 1. Remove landing bounce/compression — stop on impact, zero rebound/zero compression (criterion: drop feel = crisp & clean);
// 2. Speed up overall fall — single card fall 15->9 frames, all settled f45->f33, rise phase moved earlier accordingly;
// 3. Keep unchanged: 3-frame staggered starts, UI layout order (row-major left->right), gravity acceleration
// (distance ∝ t^2), page stands upright after landing completion to finish.
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from 'remotion';

const FONT = 'Helvetica, Arial, sans-serif';
const INK = '#3c3c42';
const MID = '#8d8d94';
const FAINT = '#d2d2d5';

const easeRise = Easing.bezier(0.42, 0, 0.16, 1);

/* Seeded mulberry32 (launch timing jitter <= 1.5 frames < 3 frame stagger, preserving order) */
const mulberry32 = (seed: number) => () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

const CARD_W = 760;
const MiniCardFace: React.FC<{ title: string; sub: string }> = ({ title, sub }) => (
  <div style={{
    width: CARD_W, border: `4px solid ${FAINT}`, borderRadius: 22, padding: '30px 40px',
    background: '#fcfcfb', display: 'flex', flexDirection: 'column', gap: 14, boxSizing: 'border-box',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
      <div style={{ width: 40, height: 40, border: '6px solid #85858b', borderRadius: 8, flexShrink: 0 }} />
      <div style={{ fontFamily: FONT, fontSize: 46, color: INK, fontWeight: 650, whiteSpace: 'nowrap' }}>{title}</div>
    </div>
    <div style={{ fontFamily: FONT, fontSize: 36, color: MID, paddingLeft: 64, whiteSpace: 'nowrap' }}>{sub}</div>
  </div>
);

/* UI layout order = array order: first row left->right, then second row left->right */
const CARDS: { title: string; sub: string; col: number; row: number }[] = [
  { title: 'Creative Refresh', sub: 'New logo exploration', col: 0, row: 0 },
  { title: 'New Bugs Per Week', sub: 'Bug tracker Dashboard', col: 1, row: 0 },
  { title: 'Tiger Team Roadmap', sub: 'Roadmap Outline', col: 2, row: 0 },
  { title: 'Design System', sub: 'Design Handbook Inspo', col: 3, row: 0 },
  { title: 'Development Sprint Dashboard', sub: 'Dev Team Sprints', col: 0, row: 1 },
  { title: 'CSS Bug Tracker', sub: 'Query Reports', col: 1, row: 1 },
  { title: 'Platform', sub: 'System Health Monitor', col: 2, row: 1 },
];

/* Recent grid slots (panel content coordinates) */
const GRID_X = 1180, GRID_Y = 760, COL_GAP = 850, ROW_GAP = 250;
const slotPos = (col: number, row: number) => ({ x: GRID_X + col * COL_GAP, y: GRID_Y + row * ROW_GAP });

/* Flat ground: Home dashboard (card slots left empty for floating cards to land into) */
const Ground: React.FC = () => (
  <div style={{ width: 4600, height: 2600, background: '#f6f6f5', borderRadius: 60, position: 'relative', overflow: 'hidden' }}>
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left sidebar */}
      <div style={{ width: 860, borderRight: `4px solid ${FAINT}`, padding: '70px 60px 0', background: '#f1f1f0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
          <div style={{ width: 64, height: 64, borderRadius: 18, background: 'linear-gradient(135deg,#adadb3,#6b6b72)' }} />
          <div style={{ fontFamily: FONT, fontSize: 56, fontWeight: 800, color: INK }}>ClickUp</div>
        </div>
        <div style={{ height: 46 }} />
        {['Home', 'Inbox', 'Company', 'People & Teams', 'Goals', 'Docs', 'More'].map((t, i) => (
          <div key={t} style={{
            display: 'flex', alignItems: 'center', gap: 30, height: 108, paddingLeft: 32,
            background: i === 0 ? '#e6e6f0' : 'transparent', borderRadius: 20,
          }}>
            <div style={{ width: 36, height: 36, border: '6px solid #90909a', borderRadius: 9 }} />
            <div style={{ fontFamily: FONT, fontSize: 46, color: INK, fontWeight: i === 0 ? 650 : 400 }}>{t}</div>
          </div>
        ))}
        <div style={{ height: 60 }} />
        <div style={{ fontFamily: FONT, fontSize: 38, letterSpacing: 5, color: MID, fontWeight: 600, paddingLeft: 32 }}>SPACES</div>
        <div style={{ height: 16 }} />
        {['EPD', 'Product roadmap', 'Design', 'Designer handbook', '3.0', 'Design system'].map((t) => (
          <div key={t} style={{ display: 'flex', alignItems: 'center', gap: 30, height: 96, paddingLeft: 32 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: '#d6d6da' }} />
            <div style={{ fontFamily: FONT, fontSize: 42, color: INK }}>{t}</div>
          </div>
        ))}
      </div>
      {/* Main area */}
      <div style={{ flex: 1, padding: '70px 100px 0', position: 'relative' }}>
        {/* Top tab bar */}
        <div style={{ display: 'flex', gap: 110, fontFamily: FONT, fontSize: 42, color: MID, marginBottom: 60 }}>
          <div>Product analytics</div><div style={{ fontWeight: 700, color: INK }}>ClickUp 3.0</div>
          <div>Widget brainstorm</div><div>Design system</div><div>Design</div>
        </div>
        <div style={{ fontFamily: FONT, fontSize: 110, fontWeight: 750, color: INK }}>Home</div>
        <div style={{ height: 40 }} />
        <div style={{
          display: 'flex', alignItems: 'center', gap: 30, border: `4px solid ${FAINT}`,
          borderRadius: 24, padding: '28px 42px', background: '#fff', width: 1400,
        }}>
          <div style={{ width: 38, height: 38, borderRadius: 19, border: '6px solid #9a9aa0' }} />
          <div style={{ fontFamily: FONT, fontSize: 42, color: MID }}>Search by app, filetype, or keyword</div>
        </div>
        <div style={{ height: 66 }} />
        <div style={{ display: 'flex', gap: 70, fontFamily: FONT, fontSize: 46 }}>
          <div style={{ color: INK, fontWeight: 700 }}>Recent</div>
          <div style={{ color: MID }}>Favorites</div>
        </div>
        {/* ↑ Empty Recent grid slot area (cards fall from air into 2 rows x 4 columns starting at GRID_X/GRID_Y) */}
        <div style={{ height: 560 }} />
        <div style={{ display: 'flex', gap: 70, fontFamily: FONT, fontSize: 44 }}>
          <div style={{ color: INK, fontWeight: 700 }}>Todo</div>
          <div style={{ color: MID }}>Comments</div>
          <div style={{ color: MID }}>Done</div>
          <div style={{ color: MID }}>Delegated</div>
        </div>
        <div style={{ height: 36 }} />
        <div style={{
          display: 'inline-block', padding: '16px 40px', background: '#e4e4e3', borderRadius: 14,
          fontFamily: FONT, fontSize: 36, letterSpacing: 4, color: '#6f6f75', fontWeight: 600,
        }}>TODAY</div>
        <div style={{ height: 40 }} />
        {['New Bugs Per Week', 'Designer handbook', 'Mobile screens', 'Product roadmap'].map((t) => (
          <div key={t} style={{
            display: 'flex', alignItems: 'center', gap: 34, height: 118,
            borderBottom: '3px solid #e5e5e3', width: 2600,
          }}>
            <div style={{ width: 32, height: 32, borderRadius: 9, background: '#c04a6e' }} />
            <div style={{ fontFamily: FONT, fontSize: 46, color: INK, fontWeight: 550 }}>{t}</div>
            <div style={{ marginLeft: 'auto', width: 180, height: 16, background: '#e3e3e8', borderRadius: 8 }} />
          </div>
        ))}
      </div>
    </div>
  </div>
);

export const RunwayGroundSkim: React.FC = () => {
  const frame = useCurrentFrame();
  const rand = mulberry32(20260718);
  const jit = CARDS.map(() => rand() * 1.2); // <= 1.2 frame jitter < 3 frame stagger, order never disturbed

  /* ---- Rhythm (faster fall + stop-on-impact version, 118 frames) ----
   * f0–6    Opening: all cards suspended in black void
   * f6–33   Drop: card i launches at f = 6 + i*3 (3 frame stagger), falls for 9 frames
   *         => 9 >> 3, 3–4 cards falling concurrently in mid-air (overlapping parallel, not serial);
   *         Gravity acceleration (distance ∝ t^2), stop on impact — zero rebound, zero compression
   * f38–94  Page stands upright + perspective levels out (rotateX 66->0, camera pulls back to center)
   * f94–118 Final frontal view full page hold */
  // v6 (batch 15): User feedback: "reduce time difference between drops, don't wait for one to land
  // before starting the next" — start stagger 3->1.5 frames (6x overlap within 9-frame fall window,
  // 5–6 cards falling simultaneously at any instant, almost synchronous with ripple feel)
  const START0 = 6, GAP = 1.5, FALLF = 9;

  const lifts = CARDS.map((c, i) => {
    const t = frame - (START0 + i * GAP + jit[i]);
    const H = 560 + (i % 3) * 160; // Staggered initial floating heights
    if (t <= 0) return H;
    const p = t / FALLF;
    if (p < 1) return H * (1 - p * p); // Gravity acceleration: fall distance ∝ t^2
    return 0; // Stop on impact, no bounce
  });

  /* Rise phase progress */
  const riseP = interpolate(frame, [38, 94], [0, 1], { easing: easeRise, extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  /* Camera: subtle push-in during card fall (72->66 deg), levels out (->0 deg) and pulls back to center during rise */
  const landP = interpolate(frame, [0, 34], [0, 1], { easing: Easing.bezier(0.3, 0.1, 0.6, 0.9), extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const rx = interpolate(landP, [0, 1], [72, 66]) - 66 * riseP;
  const z = interpolate(landP, [0, 1], [-620, -320]) + riseP * (-1620 - -320);
  const bright = interpolate(frame, [0, 32, 86], [0.32, 0.8, 1.0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  /* Anchor / perspective origin centers during rise: final full page in frame, center ≈ screen center */
  const anchorTop = 58 - riseP * 6;           // %: 58 -> 52 (full page unclipped at bottom in final state)
  const perspY = 30 + riseP * 20;             // % : 30 -> 50

  const cam = (children: React.ReactNode, extra?: React.CSSProperties) => (
    <AbsoluteFill style={{ perspective: 1050, perspectiveOrigin: `50% ${perspY}%`, ...extra }}>
      <div style={{
        position: 'absolute', left: '50%', top: `${anchorTop}%`, width: 0, height: 0,
        transformStyle: 'preserve-3d',
        transform: `translateZ(${z}px) rotateX(${rx}deg)`,
      }}>
        {children}
      </div>
    </AbsoluteFill>
  );

  const scene = (
    <div style={{ position: 'absolute', transformStyle: 'preserve-3d', transform: 'translate(-2300px, -1500px)' }}>
      {/* Ground plane */}
      <div style={{ filter: `brightness(${bright})` }}>
        <Ground />
      </div>
      {/* Soft shadow on ground (z≈0, card-shaped, size/offset/density vary with elevation) */}
      {CARDS.map((c, i) => {
        const h = lifts[i];
        if (h < 2) return null;
        const s = slotPos(c.col, c.row);
        return (
          <div key={'sh' + i} style={{
            position: 'absolute', left: s.x + 20, top: s.y + 14, width: CARD_W - 40, height: 150,
            transform: `translateZ(1px) translate(${h * 0.08}px, ${h * 0.12}px) scale(${1 + h * 0.0004})`,
            background: 'rgba(10,8,16,0.9)', borderRadius: 24,
            filter: `blur(${10 + h * 0.03}px)`,
            opacity: Math.max(0.12, 0.38 - h * 0.0003),
          }} />
        );
      })}
      {/* Floating cards: lying flat parallel to ground, elevated via translateZ, landing back into slots.
          Lit by "spotlight" while airborne (brighter than dark ground), blending into ground brightness upon landing */}
      {CARDS.map((c, i) => {
        const h = lifts[i];
        const s = slotPos(c.col, c.row);
        const airLit = h > 2 ? Math.max(1.35, bright) : bright;
        return (
          <div key={'card' + i} style={{
            position: 'absolute', left: s.x, top: s.y,
            transform: `translateZ(${h}px)`,
            filter: `brightness(${airLit})`,
            boxShadow: h > 2 ? `0 0 ${30 + h * 0.05}px rgba(240,235,255,${Math.min(0.3, h * 0.0004)})` : 'none',
          }}>
            <MiniCardFace title={c.title} sub={c.sub} />
          </div>
        );
      })}
    </div>
  );

  /* Ambient layers recede during rise: dark sky void/horizon glow/foreground blur fade out as perspective levels */
  const airOp = 1 - riseP;

  return (
    <AbsoluteFill style={{ background: '#07060a' }}>
      {/* Horizon glow (fades out after leveling) */}
      <AbsoluteFill style={{
        background: `radial-gradient(ellipse 60% 14% at 50% 40%, rgba(190,170,255,${(0.16 + landP * 0.1) * airOp}), transparent 75%)`,
      }} />
      {cam(scene)}
      {/* Foreground subtle blur (fades out after leveling) */}
      {airOp > 0.02 && (
        <AbsoluteFill style={{
          filter: 'blur(10px) brightness(0.88)', opacity: airOp,
          WebkitMaskImage: 'linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.7) 84%, black 98%)',
          maskImage: 'linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.7) 84%, black 98%)',
        }}>
          {cam(scene)}
        </AbsoluteFill>
      )}
      {/* Upper sky vignette (fades out with rise) */}
      <AbsoluteFill style={{
        background: 'linear-gradient(180deg, rgba(4,3,8,0.9) 0%, rgba(4,3,8,0.35) 16%, transparent 32%)',
        opacity: airOp, pointerEvents: 'none',
      }} />
      {/* Vignette (diminishes after leveling but persists) */}
      <AbsoluteFill style={{
        background: 'radial-gradient(ellipse 95% 90% at 50% 55%, transparent 50%, rgba(3,2,7,0.55) 85%, rgba(2,1,5,0.88) 100%)',
        opacity: 1 - riseP * 0.55, pointerEvents: 'none',
      }} />
    </AbsoluteFill>
  );
};
