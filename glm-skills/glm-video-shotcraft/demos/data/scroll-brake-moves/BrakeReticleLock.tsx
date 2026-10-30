// Combo: scroll brake x reticle lock (brake-reticle-lock)
// Changelog list rushes upward at high speed (accelerating sprint -> 9f sharp deceleration with 30px overshoot rebound).
// On the hard brake frame (BRAKE=59), four L-shaped corner brackets fly in from off-screen in four directions, locking onto
// the four corners of the target row with back-out overshoot; target row simultaneously highlights + side badge pops out on the right.
// Critical sync: reticle lock frame and list hard brake frame must resonate on the exact same frame (both trigger at f=59); any offset breaks the punch.
// Keyframes: 0–12 initial rest -> 12–50 accelerating sprint (speed-dependent blur) -> 50–59 sharp deceleration overshoot ->
// 59 hard brake + corner brackets fly in -> 59–72 lock rebound / highlight / tag -> 75–150 true freeze for 75f.
// Deterministic across frames, no randomness.
//
// Polish upgrade: gray skeleton rows replaced with realistic changelog (type icon / title / description / version / date, chronological top-down),
// target row v2.41 publication-grade content; top bar wireframe replaced with realistic app header; isotropic blur replaced with vertical SpeedBlur along scroll direction;
// corner reticles updated from 8px black thick brackets to 6px rounded accent L-brackets, with directional motion blur proportional to flight speed; target row gains accent border +
// elevated shadow, while remaining rows dim to 0.38; badge pops out from 0.6->1 with pulsing dot; soft light background + top/bottom fade mask + grain.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, FONT, Grain, SpeedBlur, innerHighlight, softShadow, tracking } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

const SCROLL_START = 12;
const BRAKE = 59;
const DUR = 150;
export const BRAKE_RETICLE_LOCK_DURATION = DUR;

const PITCH = 156; // Row height 120 + gap 36
const ROW_H = 120;
const TARGET_ROW = 30;
const FINAL_SCROLL = TARGET_ROW * PITCH - 480; // Target item top rests at screen y=480
const LIST_X = 360;
const LIST_W = 1200;

// Scroll position: 12–50 accelerating sprint (sin-in, rolling faster) -> 50–59 sharp deceleration overshooting 30px ->
// 59–63 rebound settle. Frame 59 is the hard brake frame (first stop/reversal).
const scrollAt = (f: number): number => {
  if (f <= SCROLL_START) return 0;
  if (f <= 50) {
    return interpolate(f, [SCROLL_START, 50], [0, FINAL_SCROLL - 430], {
      easing: Easing.in(Easing.sin),
    });
  }
  if (f <= BRAKE) {
    return interpolate(f, [50, BRAKE], [FINAL_SCROLL - 430, FINAL_SCROLL + 30], {
      easing: Easing.out(Easing.cubic),
    });
  }
  return interpolate(f, [BRAKE, BRAKE + 4], [FINAL_SCROLL + 30, FINAL_SCROLL], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
};

// Mock content: video-shotcraft chronological release history, row 30 = v2.41 Motion workbench
const TITLES = [
  'Crash zoom shot card', 'Faster Remotion renders', 'Audio drift on long renders', 'Beat grid from any BGM',
  'Dolly zoom shot card', 'Real page captures', 'Caption timing at 60 fps', 'Gallery style filters', 'Whip pans',
  'Ink Press template', 'Improved SFX ducking', 'Blur seam on 4K export', 'Storyboard from a prompt', 'Inline shot previews',
  'Poster frame picker', 'Parallax depth layers', 'Font fallback in titles', 'Beat-synced flash cuts', 'Film grain overlay',
  'Lower thirds', 'Faster cold render', 'Mask edge on Safari', 'Showcase gallery', 'Light leaks', 'Per-shot color looks',
  'Offline asset cache', 'Cursor path smoothing', 'Timeline markers', 'Typing code block card', 'JianYing export',
  'Motion workbench', 'Vertical 9:16 cuts', 'Brand kit import', 'Shot A/B compare', 'Multi-track SFX',
  'Batch renders', 'Review links', 'Voiceover sync',
];
const DESCS = [
  'Rolled out to every project.', 'Now 3× faster on long films.', 'Fixed for macOS and Linux.', 'Ships with the skill today.',
];
// Types: icon color + glyph
const KIND = [
  { name: 'Feature', tint: 'rgba(91,99,211,0.12)', ink: '#4a51b8', glyph: '✦' },
  { name: 'Improved', tint: 'rgba(22,150,110,0.12)', ink: '#137a5a', glyph: '↗' },
  { name: 'Fix', tint: 'rgba(20,22,28,0.06)', ink: '#5d5f66', glyph: '✓' },
];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'];

const Row: React.FC<{ i: number; highlight: number; dim: number }> = ({ i, highlight, dim }) => {
  const isTarget = i === TARGET_ROW;
  const k = KIND[isTarget ? 0 : (i * 7) % 3];
  const later = i > TARGET_ROW;
  return (
    <div
      style={{
        position: 'absolute',
        top: i * PITCH,
        left: 0,
        width: LIST_W,
        height: ROW_H,
        background: '#ffffff',
        border: `1px solid ${G.hairline}`,
        borderRadius: 16,
        display: 'flex',
        alignItems: 'center',
        gap: 26,
        padding: '0 32px',
        boxSizing: 'border-box',
        boxShadow:
          `${innerHighlight(0.9)}, ${softShadow(3 + 20 * highlight, { strength: 1 + 0.6 * highlight })}` +
          (highlight > 0 ? `, 0 0 0 ${(2 * highlight).toFixed(2)}px rgba(91,99,211,${(0.85 * highlight).toFixed(3)})` : ''),
        opacity: 1 - 0.62 * dim,
        fontFamily: FONT.sans,
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          flexShrink: 0,
          borderRadius: 14,
          background: isTarget ? `linear-gradient(180deg, #7178e6, ${G.accent})` : k.tint,
          color: isTarget ? '#fff' : k.ink,
          display: 'grid',
          placeItems: 'center',
          fontSize: 26,
          fontWeight: 700,
          boxShadow: isTarget ? 'inset 0 1px 0 rgba(255,255,255,0.35)' : 'none',
        }}
      >
        {k.glyph}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: isTarget ? 36 : 30, fontWeight: isTarget ? 700 : 600, color: later ? G.ink3 : G.ink1, letterSpacing: tracking(30), whiteSpace: 'nowrap' }}>
          {TITLES[i % TITLES.length]}
        </div>
        <div style={{ marginTop: 6, fontSize: 24, color: G.ink2, whiteSpace: 'nowrap' }}>
          {isTarget ? 'Every shot, tuned in one place.' : later ? 'Planned for Q4.' : DESCS[i % DESCS.length]}
        </div>
      </div>
      <div style={{ flexShrink: 0, fontFamily: FONT.mono, fontSize: 22, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>
        {later ? '—' : `v2.${11 + i}`}
      </div>
      <div style={{ flexShrink: 0, width: 96, textAlign: 'right', fontSize: 22, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>
        {isTarget ? 'Today' : later ? 'Q4' : `${MONTHS[Math.floor((i / TARGET_ROW) * 9)]} ${1 + ((i * 11) % 27)}`}
      </div>
    </div>
  );
};

// L-corner bracket: right angle formed by two rounded accent lines
const Corner: React.FC<{ flip: [number, number]; style: React.CSSProperties }> = ({ flip, style }) => (
  <div style={{ position: 'absolute', width: 46, height: 46, transform: `scale(${flip[0]}, ${flip[1]})`, ...style }}>
    <div style={{ position: 'absolute', left: 0, top: 0, width: 46, height: 6, background: G.accent, borderRadius: 3 }} />
    <div style={{ position: 'absolute', left: 0, top: 0, width: 6, height: 46, background: G.accent, borderRadius: 3 }} />
  </div>
);

// Reticle lock progress (back-out overshoot)
const lockAt = (f: number) =>
  interpolate(f, [BRAKE, BRAKE + 9], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.4)),
  });

// List top/bottom gradient fade (below top bar / screen bottom)
const LIST_MASK = 'linear-gradient(180deg, transparent 72px, #000 170px, #000 960px, transparent 1080px)';

export const BrakeReticleLock: React.FC = () => {
  const f = useCurrentFrame();
  const scroll = scrollAt(f);

  // Speed-dependent vertical blur: driven by adjacent-frame delta (px/f), streaked during sprint, crisp when braked
  const v = scroll - scrollAt(Math.max(0, f - 1));

  // From hard brake frame: highlight 0->1 (6f), remaining rows dim (12f)
  const highlight = interpolate(f, [BRAKE, BRAKE + 6], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const dim = interpolate(f, [BRAKE + 2, BRAKE + 14], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // Target item screen coordinates (settles at top=480)
  const rowTopAt = (fr: number) => TARGET_ROW * PITCH - scrollAt(fr);
  const GAP = 10; // Lock position: corners offset outward by 10px
  const rect = (fr: number) => ({ x: LIST_X - GAP, y: rowTopAt(fr) - GAP, w: LIST_W + GAP * 2, h: ROW_H + GAP * 2 });

  const corners: Array<{ ax: 0 | 1; ay: 0 | 1; fromX: number; fromY: number; flip: [number, number] }> = [
    { ax: 0, ay: 0, fromX: -620, fromY: -320, flip: [1, 1] },
    { ax: 1, ay: 0, fromX: 620, fromY: -320, flip: [-1, 1] },
    { ax: 0, ay: 1, fromX: -620, fromY: 320, flip: [1, -1] },
    { ax: 1, ay: 1, fromX: 620, fromY: 320, flip: [-1, -1] },
  ];
  const cornerPos = (c: (typeof corners)[number], fr: number) => {
    const r = rect(fr);
    const fly = 1 - lockAt(fr); // 1 = off-screen, 0 = locked in place
    return { x: r.x + c.ax * r.w - 23 + c.fromX * fly, y: r.y + c.ay * r.h - 23 + c.fromY * fly };
  };

  // Side badge: pops out from right of row at 63f (with overshoot)
  const tagT = interpolate(f, [BRAKE + 4, BRAKE + 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.6)),
  });
  const tagOp = interpolate(f, [BRAKE + 4, BRAKE + 7], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const r = rect(f);

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden', fontFamily: FONT.sans }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.25 }} vignette={0.16} grain={0} />

      {/* Changelog long list: rushes upward as a whole, vertically blurred during speed phase */}
      <div style={{ position: 'absolute', inset: 0, WebkitMaskImage: LIST_MASK, maskImage: LIST_MASK }}>
        <SpeedBlur vx={0} vy={v} amount={0.15} max={32}>
          <div style={{ position: 'absolute', left: LIST_X, top: 0, width: LIST_W, height: 1080 }}>
            <div style={{ position: 'absolute', top: -scroll, left: 0, width: LIST_W, height: 40 * PITCH }}>
              {Array.from({ length: 38 }).map((_, i) => (
                <Row key={i} i={i} highlight={i === TARGET_ROW ? highlight : 0} dim={i === TARGET_ROW ? 0 : dim} />
              ))}
            </div>
          </div>
        </SpeedBlur>
      </div>

      {/* Top bar (fixed, does not scroll) */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 72,
          background: 'rgba(250,250,249,0.92)',
          borderBottom: `1px solid ${G.hairline}`,
          display: 'flex',
          alignItems: 'center',
          padding: '0 40px',
          gap: 16,
          boxSizing: 'border-box',
          zIndex: 3,
        }}
      >
        <ShotcraftMark size={32} tone="light" />
        <div style={{ fontFamily: BRAND.font, fontSize: 24, fontWeight: 700, color: G.ink1, letterSpacing: '0.03em' }}>{BRAND.name}</div>
        <div style={{ fontSize: 24, color: G.ink3 }}>/</div>
        <div style={{ fontSize: 24, fontWeight: 550, color: G.ink2 }}>Changelog</div>
        <div
          style={{
            marginLeft: 'auto',
            width: 38,
            height: 38,
            borderRadius: 19,
            background: '#e4e5ea',
            color: G.ink2,
            fontSize: 15,
            fontWeight: 700,
            display: 'grid',
            placeItems: 'center',
          }}
        >
          JL
        </div>
      </div>

      {/* Reticle corner brackets: mount on the exact hard brake frame (critical: resonates with brake); directional motion blur during fly-in */}
      {f >= BRAKE &&
        corners.map((c, i) => {
          const p = cornerPos(c, f);
          const q = cornerPos(c, f - 1);
          return (
            <SpeedBlur key={i} vx={p.x - q.x} vy={p.y - q.y} amount={0.1} max={18}>
              <Corner
                flip={c.flip}
                style={{ left: p.x, top: p.y, opacity: Math.min(1, lockAt(f) * 3 + 0.35) }}
              />
            </SpeedBlur>
          );
        })}

      {/* Side popup badge */}
      {f >= BRAKE + 4 && (
        <div
          style={{
            position: 'absolute',
            left: r.x + r.w + 28,
            top: r.y + r.h / 2 - 28,
            height: 56,
            transform: `scale(${(0.6 + 0.4 * tagT).toFixed(4)})`,
            transformOrigin: 'left center',
            opacity: tagOp,
            padding: '0 24px 0 22px',
            borderRadius: 28,
            background: G.ink1,
            boxShadow: softShadow(12, { strength: 1.4 }),
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontWeight: 650,
            fontSize: 26,
            letterSpacing: tracking(26),
          }}
        >
          <div style={{ width: 10, height: 10, borderRadius: 5, background: '#67d17c', boxShadow: '0 0 0 4px rgba(103,209,124,0.22)' }} />
          Just shipped
        </div>
      )}
      <Grain opacity={0.05} />
    </div>
  );
};
      {f >= BRAKE + 4 && (
        <div
          style={{
            position: 'absolute',
            left: r.x + r.w + 28,
            top: r.y + r.h / 2 - 28,
            height: 56,
            transform: `scale(${(0.6 + 0.4 * tagT).toFixed(4)})`,
            transformOrigin: 'left center',
            opacity: tagOp,
            padding: '0 24px 0 22px',
            borderRadius: 28,
            background: G.ink1,
            boxShadow: softShadow(12, { strength: 1.4 }),
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            fontWeight: 650,
            fontSize: 26,
            letterSpacing: tracking(26),
          }}
        >
          <div style={{ width: 10, height: 10, borderRadius: 5, background: '#67d17c', boxShadow: '0 0 0 4px rgba(103,209,124,0.22)' }} />
          Just shipped
        </div>
      )}
      <Grain opacity={0.05} />
    </div>
  );
};
