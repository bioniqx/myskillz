// command-palette-summon — Command palette descent
// FakeDashboard rests → full screen dims + blurs → ⌘K palette drops from 20px above center with overshoot
// → 5 candidate rows stagger in → simulated input of 2 letters (gray blocks as chars) narrows candidates 5→3→2
// → highlights first item. Fully static after f=110 (40f). Cursor blinks when f<104, then stays solid.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';

const CL = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// Timeline
const DIM0 = 12; // Dimming starts (first 12f initial rest)
const DIM1 = 22;
const PANEL_IN = 18; // Palette begins drop
const ROWS_START = 32; // Candidate rows begin staggered entrance
const KEY1 = 62; // First letter
const KEY2 = 78; // Second letter
const HL = 94; // Highlight first item
const BLINK_END = 104; // Cursor stops blinking (stays solid)

const PANEL_W = 780;
const PANEL_X = (1920 - PANEL_W) / 2;
const PANEL_Y = 290;
const ROW_H = 72;
const ROW_GAP = 8;
const EXIT_DUR = 10;

// exitAt: 0=retained until end, 1=exits after first keystroke, 2=exits after second keystroke
const ROWS = [
  { titleW: 52, exitAt: 0 },
  { titleW: 38, exitAt: 0 },
  { titleW: 61, exitAt: 2 },
  { titleW: 45, exitAt: 1 },
  { titleW: 56, exitAt: 1 },
];

const PaletteRow: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const { titleW, exitAt } = ROWS[i];
  const inStart = ROWS_START + i * 4;
  const exitStart = exitAt === 1 ? KEY1 + 3 : exitAt === 2 ? KEY2 + 3 : null;

  if (exitStart !== null && frame >= exitStart + EXIT_DUR) return null; // Conditional unmount, not opacity 0

  const inOp = interpolate(frame, [inStart, inStart + 8], [0, 1], CL);
  const inY = interpolate(frame, [inStart, inStart + 8], [12, 0], {
    easing: Easing.out(Easing.cubic),
    ...CL,
  });
  const exitT =
    exitStart === null
      ? 1
      : interpolate(frame, [exitStart, exitStart + EXIT_DUR], [1, 0], {
          easing: Easing.inOut(Easing.cubic),
          ...CL,
        });

  // Highlight first item
  const hl = i === 0 ? interpolate(frame, [HL, HL + 10], [0, 1], CL) : 0;

  return (
    <div
      style={{
        height: (ROW_H + ROW_GAP) * exitT,
        opacity: inOp * exitT,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: ROW_H,
          borderRadius: 12,
          background: hl > 0 ? `rgba(228,228,226,${hl})` : 'transparent',
          boxShadow: hl > 0 ? `inset 4px 0 0 rgba(47,47,47,${hl})` : 'none',
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          padding: '0 22px',
          boxSizing: 'border-box',
          transform: `translateY(${inY}px)`,
        }}
      >
        <div style={{ width: 36, height: 36, borderRadius: 9, background: G.mid }} />
        <div style={{ height: 14, width: `${titleW}%`, background: G.bar, borderRadius: 7 }} />
        <div style={{ marginLeft: 'auto', width: 58, height: 24, borderRadius: 6, background: G.line }} />
      </div>
    </div>
  );
};

export const CommandPaletteSummon: React.FC = () => {
  const frame = useCurrentFrame();

  // Background dim + blur
  const dim = interpolate(frame, [DIM0, DIM1], [0, 0.45], CL);
  const blur = interpolate(frame, [DIM0, DIM1], [0, 10], CL);

  // Palette drop: 20px above → overshoot +8px → settle to 0
  const panelY =
    frame < PANEL_IN + 9
      ? interpolate(frame, [PANEL_IN, PANEL_IN + 9], [-20, 8], {
          easing: Easing.out(Easing.cubic),
          ...CL,
        })
      : interpolate(frame, [PANEL_IN + 9, PANEL_IN + 15], [8, 0], {
          easing: Easing.inOut(Easing.cubic),
          ...CL,
        });
  const panelOp = interpolate(frame, [PANEL_IN, PANEL_IN + 7], [0, 1], CL);

  // Simulated typing: typed character count
  const typed = (frame >= KEY1 ? 1 : 0) + (frame >= KEY2 ? 1 : 0);
  // Cursor blink (16f period), stays solid after BLINK_END to guarantee final stillness
  const cursorOn = frame >= BLINK_END ? true : (frame - PANEL_IN) % 16 < 8;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ filter: frame < DIM0 ? undefined : `blur(${blur}px)` }}>
        <FakeDashboard variant="A" />
      </div>
      <div style={{ position: 'absolute', inset: 0, background: `rgba(20,20,20,${dim})` }} />

      {frame >= PANEL_IN && (
        <div
          style={{
            position: 'absolute',
            left: PANEL_X,
            top: PANEL_Y,
            width: PANEL_W,
            transform: `translateY(${panelY}px)`,
            opacity: panelOp,
            background: G.card,
            borderRadius: 18,
            border: `2px solid ${G.border}`,
            boxShadow: '0 28px 90px rgba(0,0,0,0.4)',
            padding: 20,
            boxSizing: 'border-box',
          }}
        >
          {/* Input field */}
          <div
            style={{
              height: 76,
              borderBottom: `2px solid ${G.line}`,
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              padding: '0 10px 14px 10px',
              boxSizing: 'border-box',
            }}
          >
            <div style={{ width: 32, height: 32, borderRadius: 8, background: G.bar }} />
            {/* Typed character gray blocks */}
            {Array.from({ length: typed }).map((_, c) => (
              <div key={c} style={{ width: 28, height: 38, borderRadius: 6, background: '#4a4a48' }} />
            ))}
            {/* Cursor */}
            {cursorOn && <div style={{ width: 4, height: 42, background: G.ink, borderRadius: 2 }} />}
            {/* Placeholder hint bar: unmounted on first letter typed */}
            {typed === 0 && (
              <div style={{ width: 260, height: 14, borderRadius: 7, background: G.line, opacity: 0.8 }} />
            )}
          </div>
          {/* Candidate rows */}
          <div style={{ paddingTop: 14 }}>
            {ROWS.map((_, i) => (
              <PaletteRow key={i} i={i} frame={frame} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
