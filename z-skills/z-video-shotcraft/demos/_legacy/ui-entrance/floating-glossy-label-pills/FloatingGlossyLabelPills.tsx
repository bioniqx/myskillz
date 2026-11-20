// floating-glossy-label-pills — Glossy Pills Carousel (ported from motion-lab final to native Remotion)
// White background with accent-colored haze at four corners; four light-gray dashboard placeholder mockups
// (three-column cards / line-chart dashboard / list table / form + toggle list) queued horizontally,
// each topped with a glossy accent pill label (Feature A–D);
// Circular loop track, ensuring adjacent panel edges peek out on left and right at any beat. Starts with residual motion
// from the previous beat (drifting 11px left, gently settling), followed by a 3-beat track shift to the right
// (t≈0.20/0.483/0.688, inOutCubic, beat 1 with a long tail) — centered panel scales up sharp, flanking panels scale down to 0.62,
// sink, dim, and slightly blur; at t≈0.717 a black cursor with white outline hard-cuts in top-right, decelerates diagonally
// toward bottom-left, settling at t≈0.90 at the right end of the last pill.
// ACCENT and its shades are the sole hue source across the card; reskin by swapping with project brand colors.
// Design coordinates 480×270 (DesignStage scales proportionally); parameter table values calibrated to this system.
import React from 'react';
import { DesignStage, E, lerp, rand, seg, useT } from '../../_fixtures/Motion';

export const FLOATING_GLOSSY_LABEL_PILLS_DURATION = 120; // 4000ms @30fps

// ── Template accent colors: replace this group with project brand colors for production use ──
const ACCENT = '#7a8699'; // Neutral blue-gray as default demo color
const ACCENT_LIGHT = '#a8b2c0', ACCENT_DEEP = '#4c5666';
const A_RGB = '122,134,153', AL_RGB = '168,178,192', AD_RGB = '76,86,102';
const F = '-apple-system,BlinkMacSystemFont,sans-serif';

// Frame-by-frame measurements (480×270 crop system):
//   Center panel x 105–357 (W≈252), top=75, bottom edge precisely flush with frame bottom -> true height H≈195
//   Neighboring (resting) panel x -70..86 (scaled to 0.62), top=126 -> scaled + sunk by 51px
//   Center-to-center distance between adjacent panels SP≈232
// Internal UI authored in 330×255 content coordinates, then scaled proportionally to 252×195
const CW = 330, CH = 255, CS = 252 / CW;
const W = Math.round(CW * CS), H = Math.round(CH * CS), SP = 232;
const PANEL_TOP = 75;

// ── Generic placeholder (wireframe / skeleton) parts: purely gray bars + color blocks, no specific copy ──
const TITLE = '#a8adb5', TEXT = '#d4d7dd', FAINT = '#e3e5ea', LINE = '#eceef1';

// Skeleton bar: default border-radius min(h/2, 3)
const Skel: React.FC<{ x: number; y: number; w: number; h: number; col: string; r?: number }> = ({ x, y, w, h, col, r }) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      borderRadius: r === undefined ? Math.min(h / 2, 3) : r,
      background: col,
    }}
  />
);

// Window title bar: accent square + logotype gray bar + two dots on right (shared chrome across pages)
const Topbar: React.FC = () => (
  <div style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: 16, background: '#fff', borderBottom: '1px solid #eceef1', zIndex: 1 }}>
    <Skel x={8} y={4} w={8} h={8} col={ACCENT} r={2} />
    <Skel x={20} y={6} w={28} h={5} col="#b9bec6" />
    <div style={{ position: 'absolute', right: 8, top: 5.5, width: 5, height: 5, borderRadius: '50%', background: '#d8dbe0' }} />
    <div style={{ position: 'absolute', right: 18, top: 5.5, width: 5, height: 5, borderRadius: '50%', background: '#d8dbe0' }} />
  </div>
);

// Left sidebar: one active item + several gray bars
const Sidebar: React.FC = () => (
  <div style={{ position: 'absolute', left: 0, top: 16, width: 70, height: 'calc(100% - 16px)', background: '#f7f8f9', borderRight: '1px solid #eceef1' }}>
    <Skel x={8} y={8} w={36} h={8} col={ACCENT} />
    {Array.from({ length: 8 }, (_, i) => (
      <Skel key={i} x={8} y={26 + i * 11} w={30 + rand(i + 9) * 22} h={4} col={i === 1 ? ACCENT_LIGHT : '#d8dbe0'} />
    ))}
  </div>
);

// 1) Three-column cards placeholder (centered header + 3 cards: header bar / large metric block / text skeleton / button block)
const BCards: React.FC = () => (
  <>
    <Topbar />
    <Skel x={CW / 2 - 46} y={30} w={92} h={9} col={TITLE} />
    <Skel x={CW / 2 - 70} y={46} w={140} h={5} col={FAINT} />
    {Array.from({ length: 3 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: 16 + i * 104, top: 64, width: 92, height: 170, border: `1px solid ${LINE}`, borderRadius: 6, background: '#fff' }}>
        <Skel x={10} y={12} w={38} h={6} col="#b9bec6" />
        <Skel x={10} y={26} w={52} h={14} col={TITLE} r={4} />
        {Array.from({ length: 5 }, (_, k) => (
          <Skel key={k} x={10} y={52 + k * 13} w={44 + rand(i * 7 + k) * 26} h={4} col={FAINT} />
        ))}
        <Skel x={10} y={142} w={72} h={16} col={ACCENT} r={4} />
      </div>
    ))}
  </>
);

// 2) Dashboard placeholder (four metric cards + line chart placeholder)
const BDash: React.FC = () => (
  <>
    <Topbar />
    <Sidebar />
    <Skel x={84} y={26} w={64} h={9} col={TITLE} />
    {Array.from({ length: 4 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: 84 + i * 60, top: 44, width: 54, height: 32, border: `1px solid ${LINE}`, borderRadius: 6, background: '#fff' }}>
        <Skel x={7} y={7} w={34} h={8} col={TITLE} />
        <Skel x={7} y={20} w={22} h={3} col={FAINT} />
      </div>
    ))}
    <div style={{ position: 'absolute', left: 84, top: 86, width: 232, height: 146, border: `1px solid ${LINE}`, borderRadius: 6, background: '#fff' }}>
      <Skel x={8} y={8} w={56} h={5} col={TEXT} />
      <svg viewBox="0 0 232 146" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        <path d="M8 116 C 40 112, 56 62, 84 64 S 128 120, 152 116 S 196 50, 224 56 L224 134 L8 134 Z" fill={`rgba(${A_RGB},.18)`} />
        <path d="M8 116 C 40 112, 56 62, 84 64 S 128 120, 152 116 S 196 50, 224 56" fill="none" stroke={ACCENT} strokeWidth={2} />
      </svg>
      {Array.from({ length: 5 }, (_, i) => (
        <Skel key={i} x={12 + i * 44} y={138} w={22} h={3} col={FAINT} />
      ))}
    </div>
  </>
);

// 3) List / table placeholder (compact stat bar + multiline skeleton + status color blocks)
const BTable: React.FC = () => (
  <>
    <Topbar />
    <Sidebar />
    <Skel x={84} y={26} w={76} h={9} col={TITLE} />
    {Array.from({ length: 4 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: 84 + i * 60, top: 44, width: 54, height: 22, border: `1px solid ${LINE}`, borderRadius: 6, background: '#fff' }}>
        <Skel x={7} y={7} w={26 + rand(i + 3) * 14} h={8} col={TITLE} />
      </div>
    ))}
    {Array.from({ length: 7 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: 84, top: 78 + i * 22, width: 232, height: 18, borderBottom: '1px solid #f0f1f4' }}>
        <Skel x={0} y={6} w={70 + rand(i + 21) * 60} h={5} col={TEXT} />
        {/* Status blocks preserve functional colors (error light red / normal light green) */}
        <Skel x={172} y={4} w={26} h={9} col={i % 2 ? '#f2d6d6' : '#cdeccf'} r={4} />
        <div style={{ position: 'absolute', left: 226, top: 6, width: 6, height: 6, borderRadius: '50%', background: '#28c06a' }} />
      </div>
    ))}
  </>
);

// 4) Form + switch list placeholder (input fields on left, avatar color blocks + toggles on right)
const BForm: React.FC = () => (
  <>
    <Topbar />
    <Sidebar />
    <Skel x={84} y={26} w={96} h={9} col={TITLE} />
    <Skel x={84} y={44} w={44} h={5} col="#b9bec6" />
    {Array.from({ length: 3 }, (_, i) => (
      <React.Fragment key={i}>
        <Skel x={84} y={56 + i * 26} w={34 + rand(i + 51) * 30} h={4} col={TEXT} />
        <div style={{ position: 'absolute', left: 84, top: 64 + i * 26, width: 120, height: 13, border: '1px solid #dcdfe4', borderRadius: 4, background: '#fff' }} />
      </React.Fragment>
    ))}
    <Skel x={84} y={140} w={120} h={15} col="#26282d" r={8} />
    <Skel x={84} y={168} w={60} h={5} col="#b9bec6" />
    {Array.from({ length: 3 }, (_, i) => (
      <Skel key={i} x={84} y={180 + i * 9} w={110 + rand(i + 71) * 60} h={3} col={FAINT} />
    ))}
    <Skel x={218} y={44} w={40} h={5} col="#b9bec6" />
    <Skel x={218} y={122} w={52} h={5} col="#b9bec6" />
    {Array.from({ length: 4 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: 218, top: 56 + i * 30 + (i > 1 ? 22 : 0), width: 100, height: 22 }}>
        <div style={{ position: 'absolute', left: 0, top: 3, width: 13, height: 13, borderRadius: '50%', background: `hsl(${212 + i * 4},14%,${56 + i * 5}%)` }} />
        <Skel x={19} y={3} w={48} h={4} col="#c2c6cc" />
        <Skel x={19} y={11} w={32} h={4} col={FAINT} />
        {/* Switches preserve functional colors (active=blue / inactive=gray) */}
        <div style={{ position: 'absolute', right: 0, top: 4, width: 18, height: 10, borderRadius: 6, background: i % 2 ? '#d6d9de' : '#2f7de1' }}>
          <div style={{ position: 'absolute', top: 1.5, ...(i % 2 ? { left: 1.5 } : { right: 1.5 }), width: 7, height: 7, borderRadius: '50%', background: '#fff' }} />
        </div>
      </div>
    ))}
  </>
);

// 4 sets: pill + placeholder mockup queued horizontally (higher i is further left, enters center later), looping track
const GROUPS: { txt: string; Body: React.FC }[] = [
  { txt: 'Feature A', Body: BCards },
  { txt: 'Feature B', Body: BDash },
  { txt: 'Feature C', Body: BTable },
  { txt: 'Feature D', Body: BForm },
];

// Mist patch static parameters (position / color)
const FOGS = [
  { left: '68%', top: '8%', rgb: AD_RGB },
  { left: '4%', top: '60%', rgb: A_RGB },
  { left: '40%', top: '82%', rgb: AL_RGB },
];

// Track 3 beats: start t≈0.20 / 0.483 / 0.688, inOutCubic ease-in -> mid-surge -> ease-out;
// Beat 1 is noticeably slower with a long tail (settles fully at t≈0.48), beats 2 & 3 are snappier.
const BEATS = [
  { b: 0.200, d: 0.185, tail: 0.28 }, // Slot 1 -> Slot 2
  { b: 0.483, d: 0.150, tail: 0 },    // Slot 2 -> Slot 3
  { b: 0.688, d: 0.150, tail: 0 },    // Slot 3 -> Slot 4
];

export const FloatingGlossyLabelPills: React.FC = () => {
  const t = useT();
  // Residual tail from previous beat at intro: at t=0 track offset 11px left, settles at t≈0.19
  let trackX = -11 * (1 - seg(t, 0, 0.19, E.outQuart));
  for (const B of BEATS) {
    const p = B.tail
      ? 0.85 * seg(t, B.b, B.b + B.d, E.inOutCubic) + 0.15 * seg(t, B.b, B.b + B.tail, E.outCubic)
      : seg(t, B.b, B.b + B.d, E.inOutCubic);
    trackX += p * SP;
  }
  const N = GROUPS.length, RING = N * SP;
  // Cursor: hard-cuts in at t≈0.717 top-right (x≈403, y≈36), decelerates diagonally down-left,
  // arriving near the right end of the last pill (x≈281, y≈56) by t≈0.90 and holding near-static
  const cp = seg(t, 0.717, 0.90, E.outQuart);
  return (
    <DesignStage bg="#fbfbfc">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
          background: `radial-gradient(55% 75% at 106% 42%, rgba(${A_RGB},.55), transparent 70%),
      radial-gradient(42% 50% at -6% 88%, rgba(${AD_RGB},.42), transparent 70%),
      radial-gradient(48% 40% at 12% -10%, rgba(${AL_RGB},.5), transparent 70%),
      #fbfbfc`,
        }}
      >
        {/* Drifting mist patches */}
        {FOGS.map(({ left, top, rgb }, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left,
              top,
              width: 240,
              height: 160,
              borderRadius: '50%',
              filter: 'blur(50px)',
              background: `rgba(${rgb},.14)`,
              transform: `translate(${Math.sin(t * Math.PI * 2 * 0.5 + i * 2.1) * 18}px,${Math.cos(t * Math.PI * 2 * 0.4 + i) * 12}px)`,
            }}
          />
        ))}

        {GROUPS.map(({ txt, Body }, i) => {
          // Circular track: panels loop around 4 positions, ensuring adjacent panels peek out on both edges at any beat
          let wx = trackX - i * SP;
          wx = ((wx % RING) + RING * 1.5) % RING - RING / 2;
          const d = Math.min(1, Math.abs(wx) / SP); // 0=dead center, 1=at neighbor position
          const close = 1 - d;
          const sc = lerp(close, 0.62, 1);          // Measured neighbor scale down to 0.62
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: '50%',
                top: 0,
                width: W,
                height: 270,
                marginLeft: -W / 2,
                transform: `translateX(${wx}px)`,
                // Neighboring position (d=1) must stay clearly visible — reference film keeps adjacent panel edges exposed
                opacity: lerp(Math.min(1, close * 2.4), 0.78, 1),
                filter: `blur(${d * 1.3}px)`,
                zIndex: close > 0.5 ? 2 : 1,
              }}
            >
              {/* Panel: proportional downscale + top edge sinking linearly with d (slope ≈80px) */}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: PANEL_TOP,
                  width: W,
                  height: H,
                  borderRadius: 8,
                  transformOrigin: '50% 0',
                  boxShadow: `0 0 0 1.5px rgba(${A_RGB},.6), 0 14px 34px rgba(${AD_RGB},.22)`,
                  transform: `translateY(${d * 80}px) scale(${sc})`,
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    width: CW,
                    height: CH,
                    borderRadius: 10,
                    background: '#fff',
                    overflow: 'hidden',
                    transform: `scale(${CS})`,
                    transformOrigin: '0 0',
                    fontFamily: F,
                  }}
                >
                  <Body />
                </div>
              </div>
              {/* Pill: center y sinks from 45 (center) to 102 (neighbor), sinking more than panel,
                  hugging panel top edge when off-center — separate steeper sink curve */}
              <div
                style={{
                  position: 'absolute',
                  left: '50%',
                  top: 28,
                  transformOrigin: '50% 50%',
                  padding: '4px 13px',
                  borderRadius: 999,
                  whiteSpace: 'nowrap',
                  // Original cssText had font shorthand after line-height:1, effectively yielding line-height: normal
                  font: `700 14px ${F}`,
                  color: '#fff',
                  background: `linear-gradient(180deg,${ACCENT_LIGHT} 0%,${ACCENT} 45%,${ACCENT_DEEP} 100%)`,
                  boxShadow: `inset 0 2px 3px rgba(255,255,255,.65), inset 0 -4px 8px rgba(34,39,47,.5),
          0 12px 28px rgba(${AD_RGB},.35)`,
                  transform: `translateX(-50%) translateY(${d * 92}px) scale(${sc})`,
                }}
              >
                {txt}
                <div
                  style={{
                    position: 'absolute',
                    left: '12%',
                    top: 3,
                    width: '76%',
                    height: '38%',
                    borderRadius: 999,
                    background: 'linear-gradient(180deg,rgba(255,255,255,.75),rgba(255,255,255,0))',
                    pointerEvents: 'none',
                  }}
                />
              </div>
            </div>
          );
        })}

        {/* Black cursor with white outline (swipes toward last pill near end, macOS pointer style) */}
        <div
          style={{
            position: 'absolute',
            width: 0,
            height: 0,
            borderLeft: '8px solid #0d0d11',
            borderRight: '4px solid transparent',
            borderBottom: '14px solid transparent',
            filter: 'drop-shadow(0 0 1px #fff) drop-shadow(0 0 1px #fff) drop-shadow(0 2px 3px rgba(0,0,0,.3))',
            transform: 'rotate(-16deg)',
            opacity: seg(t, 0.717, 0.725),
            zIndex: 5,
            left: `${(lerp(cp, 403, 281) / 480) * 100}%`,
            top: `${(lerp(cp, 36, 56) / 270) * 100}%`,
          }}
        />
      </div>
    </DesignStage>
  );
};
