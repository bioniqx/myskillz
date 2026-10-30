// changelog-scroll-brake — Changelog scroll brake
// ~34 rows (staggered row heights) rush upward at high speed (fast start + exponential long-tail deceleration).
// High-speed phase overlays vertical motion blur (driven by velocity delta, blurred into color streaks); after precise braking stop, target row elevates
// (scale 1.03 + deepened shadow) + accent border, while remaining rows dim. Full freeze after f=84 (66f).
//
// Polish upgrade: gray skeleton rows replaced with a full year of realistic changelog (version / type badge / title / description / date,
// chronologically ordered top to bottom, with Planned roadmap items following the stop point); target row has v2.41 publication-grade content + NEW badge;
// start transition changed from "instant full speed at frame 14" to cubic-bezier(0.45,0,0.06,1) (ramps to peak in ~5f before long-tail brake); isotropic blur replaced with
// vertical SpeedBlur along the scroll direction (horizontal glyphs stay sharp, yielding authentic motion blur); fixed header at top + vertical gradient fade masks; soft light + grain.
import React from 'react';
import { useCurrentFrame, interpolate } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, Grain, SpeedBlur, bezier, innerHighlight, softShadow, tracking } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CHANGELOG_SCROLL_BRAKE_DURATION = 150; // Rest 14f + scroll 50f + elevation 14f + hold 66f

const CL = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// Timeline
const SCROLL0 = 14; // Initial rest for 14f (stopped at top of scroll)
const SCROLL1 = 64; // Hard brake stop frame
const LIFT0 = 68; // Target row lift start
const LIFT1 = 82;

const COL_W = 1000;
const COL_X = (1920 - COL_W) / 2;
const GAP = 20;
const N = 34;
const TARGET = 28;

// Staggered row heights (frame-deterministic: derived solely from i)
const rowH = (i: number) => 72 + ((i * 29) % 3) * 22; // 72 / 94 / 116

// Precompute y for each row
const rowY: number[] = [];
{
  let y = 0;
  for (let i = 0; i < N; i++) {
    rowY.push(y);
    y += rowH(i) + GAP;
  }
}
const TARGET_CY = rowY[TARGET] + rowH(TARGET) / 2;
const END_T = 540 - TARGET_CY; // Target row stops at screen center
const START_T = 200; // Initial: top of scroll below header

// Fast launch (~5f to peak speed) + exponential long-tail deceleration: explosive start with gradual taper
const BRAKE_EASE = bezier(0.45, 0, 0.06, 1);
const scrollAt = (f: number): number =>
  interpolate(f, [SCROLL0, SCROLL1], [START_T, END_T], { easing: BRAKE_EASE, ...CL });

// Mock content: video-shotcraft full-year release log (chronological top-down), stop point = Motion workbench, followed by roadmap
const TITLES = [
  'Crash zoom shot card', 'Faster Remotion renders', 'Fix: audio drift on long renders',
  'Beat grid from any BGM', 'Dolly zoom shot card', 'Real page captures', 'Fix: caption timing at 60 fps',
  'Gallery style filters', 'Whip pans', 'Ink Press template', 'Improved SFX ducking', 'Fix: blur seam on 4K export',
  'Storyboard from a prompt', 'Inline shot previews', 'Poster frame picker', 'Parallax depth layers', 'Fix: font fallback in titles',
  'Beat-synced flash cuts', 'Film grain overlay', 'Lower thirds', 'Faster cold render', 'Fix: mask edge on Safari',
  'Showcase gallery', 'Light leaks', 'Per-shot color looks', 'Offline asset cache', 'Fix: cursor path smoothing', 'JianYing export',
];
const KINDS = ['Feature', 'Improved', 'Fix'] as const;
const KIND_STYLE: Record<string, { bg: string; fg: string }> = {
  Feature: { bg: 'rgba(91,99,211,0.11)', fg: '#4a51b8' },
  Improved: { bg: 'rgba(22,150,110,0.11)', fg: '#137a5a' },
  Fix: { bg: 'rgba(20,22,28,0.06)', fg: '#5d5f66' },
  Planned: { bg: 'transparent', fg: '#9b9da3' },
  Launch: { bg: G.accent, fg: '#ffffff' },
};
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];
const entry = (i: number) => {
  if (i === TARGET)
    return {
      v: 'v2.41', kind: 'Launch', title: 'Motion workbench',
      desc: 'Every shot, tuned in one place.', date: 'Today',
    };
  if (i > TARGET)
    return { v: '—', kind: 'Planned', title: ['Vertical 9:16 cuts', 'Brand kit import', 'Shot A/B compare', 'Multi-track SFX', 'Batch renders'][(i - TARGET - 1) % 5], desc: 'On the roadmap for Q4.', date: 'Q4' };
  const kind = TITLES[i].startsWith('Fix') ? 'Fix' : KINDS[i % 2];
  return {
    v: `v2.${13 + i}`,
    kind,
    title: TITLES[i].replace(/^Fix: (.)/, (_, c: string) => c.toUpperCase()),
    desc: 'Rolled out to every project with no action required.',
    date: `${MONTHS[Math.min(8, Math.floor((i / TARGET) * 9))]} ${1 + ((i * 11) % 27)}`,
  };
};

const Row: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const isTarget = i === TARGET;
  const h = rowH(i);
  const e = entry(i);
  const k = KIND_STYLE[e.kind];
  const tall = h >= 94;
  const planned = e.kind === 'Planned';

  // Target row elevates + highlights; remaining rows dim
  const t = interpolate(frame, [LIFT0, LIFT1], [0, 1], { easing: EASE.out, ...CL });
  const lift = isTarget ? t : 0;
  const dim = isTarget ? 0 : t;

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: rowY[i],
        width: COL_W,
        height: h,
        background: planned ? 'rgba(255,255,255,0.55)' : '#ffffff',
        border: planned ? '1px dashed rgba(20,22,28,0.14)' : `1px solid ${G.hairline}`,
        borderRadius: 14,
        display: 'flex',
        alignItems: 'center',
        gap: 22,
        padding: '0 30px',
        boxSizing: 'border-box',
        transform: `scale(${1 + 0.03 * lift})`,
        boxShadow: planned
          ? 'none'
          : `${innerHighlight(0.9)}, ${softShadow(2 + 26 * lift, { strength: 1 + 0.6 * lift })}` +
            (lift > 0 ? `, 0 0 0 ${(2 * lift).toFixed(2)}px rgba(91,99,211,${(0.9 * lift).toFixed(3)})` : ''),
        opacity: 1 - 0.62 * dim,
        zIndex: isTarget ? 2 : 1,
        fontFamily: FONT.sans,
      }}
    >
      <div style={{ width: 82, flexShrink: 0, fontFamily: FONT.mono, fontSize: 22, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>
        {e.v}
      </div>
      <div
        style={{
          flexShrink: 0,
          height: 34,
          padding: '0 14px',
          borderRadius: 17,
          background: k.bg,
          border: planned ? '1px solid rgba(20,22,28,0.12)' : 'none',
          color: k.fg,
          fontSize: 20,
          fontWeight: 650,
          lineHeight: '34px',
          letterSpacing: '0.01em',
        }}
      >
        {e.kind}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div
          style={{
            fontSize: isTarget ? 36 : 28,
            fontWeight: isTarget ? 700 : 600,
            color: planned ? G.ink3 : G.ink1,
            letterSpacing: tracking(isTarget ? 36 : 28),
            whiteSpace: 'nowrap',
          }}
        >
          {e.title}
        </div>
        {tall && (
          <div style={{ marginTop: 4, fontSize: isTarget ? 26 : 22, color: G.ink2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {e.desc}
          </div>
        )}
      </div>
      {isTarget && (
        <div
          style={{
            flexShrink: 0,
            height: 30,
            padding: '0 12px',
            borderRadius: 8,
            background: 'rgba(91,99,211,0.11)',
            color: G.accent,
            fontSize: 18,
            fontWeight: 750,
            lineHeight: '30px',
            letterSpacing: '0.08em',
            opacity: lift,
            transform: `translateX(${((1 - lift) * 8).toFixed(2)}px)`,
          }}
        >
          NEW
        </div>
      )}
      <div style={{ flexShrink: 0, width: 92, textAlign: 'right', fontSize: 22, color: G.ink3, fontVariantNumeric: 'tabular-nums' }}>
        {e.date}
      </div>
    </div>
  );
};

// Top/bottom gradient fade for list: regions below header and at bottom of screen
const LIST_MASK = 'linear-gradient(180deg, transparent 150px, #000 250px, #000 930px, transparent 1060px)';

export const ChangelogScrollBrake: React.FC = () => {
  const frame = useCurrentFrame();
  const T = scrollAt(frame);
  // Velocity delta (px/f) -> vertical motion blur
  const v = scrollAt(frame + 0.5) - scrollAt(frame - 0.5);

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden', fontFamily: FONT.sans }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.2 }} vignette={0.16} grain={0} />
      <div style={{ position: 'absolute', inset: 0, WebkitMaskImage: LIST_MASK, maskImage: LIST_MASK }}>
        <SpeedBlur vx={0} vy={v} amount={0.32} max={30}>
          <div
            style={{
              position: 'absolute',
              left: COL_X,
              top: 0,
              width: COL_W,
              height: 1080,
              transform: `translateY(${T.toFixed(2)}px)`,
            }}
          >
            {Array.from({ length: N }).map((_, i) => (
              <Row key={i} i={i} frame={frame} />
            ))}
          </div>
        </SpeedBlur>
      </div>
      {/* Fixed header: brand mark + Changelog + brand name */}
      <div style={{ position: 'absolute', left: COL_X, top: 64, width: COL_W, display: 'flex', alignItems: 'baseline', gap: 22 }}>
        <ShotcraftMark size={50} tone="light" style={{ alignSelf: 'center', marginRight: -4 }} />
        <div style={{ fontSize: 52, fontWeight: 720, letterSpacing: tracking(52), color: G.ink1 }}>Changelog</div>
        <div style={{ fontFamily: BRAND.font, fontSize: 30, fontWeight: 600, color: G.ink3, letterSpacing: '0.03em' }}>{BRAND.name}</div>
      </div>
      <Grain opacity={0.05} />
    </div>
  );
};
