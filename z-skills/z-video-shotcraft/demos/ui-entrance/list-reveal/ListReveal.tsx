// list-reveal — itemized menu entrance + continuous drift (two decoupled motion layers)
//
// Redesign (graphite dark field: sidebar poster layout):
// - look = graphite (near monochrome dark field, white as accent, champagne gold as highlight). Subject is a column of 700x92 sidebar items
//   (Home / Shots / Renders / Reviews / Settings / Sign out — video-shotcraft workbench sidebar), 46px text, 34px line icons,
//   26px monospace shortcuts; active item Home is a lit solid porcelain bar (sole highlight), unread badge in champagne gold.
//   Right side features a 120px headline "Every shot, within reach." + 36px subhead, creating a launch poster composition.
// - Core motion technique: two decoupled layers —
//   1. Item entrance: 24f per item, scale 0.82->1 + translateY 44->0 + focus blur 8px->0, soft overshoot (~1.5%),
//      staggered by 10f, 2-3 items in motion simultaneously;
//      icons settle +2f later, shortcuts +4f later (follow-through).
//   2. Continuous drift: list container moves upward at steady velocity 96px (~0.8px/f),
//      reading as ambient breathing rather than upward motion. End frame stays offset.
// - Headline enters halfway through list reveal (single focal point at opening), lines rise from baseline.
//
// Timeline (30fps, total 120f):
//   0-2     Stage light established, container starts drifting
//   2-26    Home item enters (porcelain bar, beat 1)
//   12-86   Remaining 5 items enter staggered by 10f (divider before Sign out reveals)
//   46-80   Headline rises line by line, subhead fades in
//   86-120  Hold: drift continues, light breathes, tail frame settles as poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, bezier, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Sheen, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';

export const LIST_REVEAL_DURATION = 120;

const L = LOOKS.graphite;

const ITEMS = [
  { label: 'Home', key: '⌘1' },
  { label: 'Shots', key: '⌘2' },
  { label: 'Renders', key: '⌘3' },
  { label: 'Reviews', key: '' },
  { label: 'Settings', key: '⌘,' },
  { label: 'Sign out', key: '' },
];

const ROW_W = 700;
const ROW_H = 92;
const GAP = 14;
const LIST_X = 170;
const LIST_Y = 236; // List top at drift midpoint
const DRIFT = 96; // Total drift distance (+48 -> -48)

const START = 2; // First item start frame
const STAGGER = 10;
const EACH = 24;
const softBack = bezier(0.3, 1.18, 0.5, 1); // Soft overshoot ~1.5%

const Icon: React.FC<{ i: number; color: string }> = ({ i, color }) => {
  const p = { fill: 'none', stroke: color, strokeWidth: 1.7, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg width={34} height={34} viewBox="0 0 24 24">
      {i === 0 && (<><path d="M4 10.5 12 4l8 6.5V19a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19Z" {...p} /><path d="M9.5 20.5v-6h5v6" {...p} /></>)}
      {i === 1 && <path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z" {...p} />}
      {i === 2 && (<><rect x={3.5} y={5} width={17} height={14} rx={2.5} {...p} /><path d="M10.2 9.2v5.6l4.6-2.8Z" {...p} /></>)}
      {i === 3 && <path d="M4 6.5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2V14a2 2 0 0 1-2 2h-7l-4.5 3.5V16H6a2 2 0 0 1-2-2Z" {...p} />}
      {i === 4 && (<><circle cx={12} cy={12} r={3} {...p} /><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8" {...p} /></>)}
      {i === 5 && (<><path d="M14 4h3.5A1.5 1.5 0 0 1 19 5.5v13a1.5 1.5 0 0 1-1.5 1.5H14" {...p} /><path d="M10 8l-4 4 4 4M6 12h9" {...p} /></>)}
    </svg>
  );
};

export const ListReveal: React.FC = () => {
  const frame = useCurrentFrame();
  // Overall drift: constant velocity throughout (ambient layer, linear, decoupled from item ease)
  const drift = DRIFT / 2 - (DRIFT * frame) / (LIST_REVEAL_DURATION - 1);

  return (
    <AbsoluteFill style={{ background: L.bg[2], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.26, y: 0.02 }} fill={{ x: 0.85, y: 0.9 }} intensity={0.5} breathe={0.5} grain={0.09} vignette={0.6}>
        <Dust look={L} count={22} seed={7} drift={0.12} opacity={0.3} />
      </Stage>

      {/* List: overall drift layer */}
      <div style={{ position: 'absolute', left: LIST_X, top: LIST_Y, width: ROW_W, transform: `translateY(${drift.toFixed(3)}px)` }}>
        {ITEMS.map((it, i) => {
          const t0 = START + i * STAGGER;
          const lin = ramp(frame, t0, EACH, EASE.linear);
          const p = softBack(lin);
          const pIcon = softBack(ramp(frame, t0 + 2, EACH, EASE.linear));
          const pKey = ramp(frame, t0 + 4, EACH - 4, EASE.out);
          const active = i === 0;
          const last = i === ITEMS.length - 1;
          const y = i * (ROW_H + GAP) + (last ? 22 : 0);
          const blur = (1 - EASE.out(lin)) * 8;
          return (
            <React.Fragment key={i}>
              {last && (
                <div style={{
                  position: 'absolute', left: 24, right: 24, top: y - 18, height: 1, background: alpha('#ffffff', 0.1),
                  transform: `scaleX(${ramp(frame, t0, EACH, EASE.snappy).toFixed(4)})`, transformOrigin: '0 50%',
                }} />
              )}
              <div style={{
                position: 'absolute', left: 0, top: y, width: ROW_W, height: ROW_H, borderRadius: 24, boxSizing: 'border-box',
                display: 'flex', alignItems: 'center', gap: 26, padding: '0 34px 0 30px',
                background: active ? 'linear-gradient(180deg, #f7f6f2 0%, #e9e8e3 100%)' : 'linear-gradient(180deg, #1c1d21 0%, #161719 100%)',
                boxShadow: active
                  ? `inset 0 1px 0 #ffffff, 0 18px 40px -14px rgba(0,0,0,0.75), 0 0 60px -10px ${alpha('#ffffff', 0.16)}`
                  : `inset 0 0 0 1px ${alpha('#ffffff', 0.07)}, inset 0 1px 0 ${alpha('#ffffff', 0.06)}, 0 14px 30px -14px rgba(0,0,0,0.8)`,
                opacity: Math.min(1, lin * 2.2),
                filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : undefined,
                transform: `translateY(${((1 - p) * 44).toFixed(2)}px) scale(${(0.82 + 0.18 * p).toFixed(4)})`,
                transformOrigin: '30% 50%', overflow: 'hidden',
              }}>
                {/* Single sheen sweep after active item settles (clipped to rounded corners) */}
                {active && <Sheen progress={ramp(frame, 22, 26, EASE.swift)} strength={0.6} width={0.18} />}
                <div style={{
                  width: 56, height: 56, borderRadius: 16, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: active ? alpha('#000000', 0.06) : alpha('#ffffff', 0.05),
                  transform: `scale(${(0.72 + 0.28 * pIcon).toFixed(4)})`, opacity: Math.min(1, Math.max(0, pIcon) * 2),
                }}>
                  <Icon i={i} color={active ? '#141416' : last ? L.ink3 : L.ink2} />
                </div>
                <div style={{ ...type(46, active ? 680 : 560), color: active ? '#0f0f11' : last ? L.ink3 : L.ink, whiteSpace: 'nowrap' }}>{it.label}</div>
                <div style={{ marginLeft: 'auto', opacity: pKey, transform: `translateX(${((1 - pKey) * 14).toFixed(2)}px)` }}>
                  {i === 3 ? (
                    <div style={{
                      minWidth: 50, height: 40, padding: '0 14px', boxSizing: 'border-box', borderRadius: 20, background: L.accent2,
                      color: '#1a1408', display: 'flex', alignItems: 'center', justifyContent: 'center', ...type(26, 750),
                      boxShadow: `0 0 24px -4px ${alpha(L.accent2, 0.7)}`,
                    }}>3</div>
                  ) : it.key ? (
                    <div style={{ ...type(26, 500, { mono: true }), color: active ? alpha('#000000', 0.45) : L.ink3 }}>{it.key}</div>
                  ) : null}
                </div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Right headline: enters after list is halfway revealed */}
      <div style={{ position: 'absolute', left: 1010, top: 336, width: 780 }}>
        <div style={{ ...type(24, 600, { mono: true }), letterSpacing: '0.16em', color: L.accent2, opacity: ramp(frame, 40, 16, EASE.out) }}>
          video-shotcraft · workbench
        </div>
        <div style={{ ...type(120, 760), color: L.ink, marginTop: 26 }}>
          <TextReveal text={'Every shot,\nwithin reach.'} by="line" start={46} each={22} gap={7} />
        </div>
        <div style={{
          ...type(36, 450), color: L.ink2, marginTop: 34, lineHeight: 1.35, maxWidth: 760, whiteSpace: 'pre-line',
          opacity: ramp(frame, 66, 18, EASE.out), transform: `translateY(${((1 - ramp(frame, 66, 18, EASE.snappy)) * 16).toFixed(2)}px)`,
        }}>
          {'Every recipe, render and storyboard,\none keystroke away.'}
        </div>
      </div>
    </AbsoluteFill>
  );
};
