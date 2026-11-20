// grid-flash-mosaic — 3x3 grid flash cut
// Light background -> from frame 25, 3x3 grid snaps in cell-by-cell on 16th notes (every 2f) in shuffled order (h(i)),
// each cell = cropped section of FakeDashboard or gray card; on entry 3f scale 1.18 -> 1 + 2f darken pulse.
// Once filled, holds for 14f (subtle wall breathing 1.008) -> center cell zooms over 14f with Easing.in(cubic) to fill screen
// becoming full-screen page. Settle phase true hold >=40f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, FakeDashboard } from '../../_fixtures/Fixtures';

const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

const CELL_W = 600;
const CELL_H = 340;
const GAP = 12;
const GRID_X = (1920 - (CELL_W * 3 + GAP * 2)) / 2; // 48
const GRID_Y = (1080 - (CELL_H * 3 + GAP * 2)) / 2; // 18

const FILL_START = 25; // First cell drops in
const STEP = 2; // 16th notes: 1 cell every 2f
// Shuffled order: index sorted by h(i+1)
const ORDER = Array.from({ length: 9 }, (_, i) => i).sort(
  (a, b) => h(a + 1) - h(b + 1)
);
const RANK: number[] = [];
ORDER.forEach((cell, k) => (RANK[cell] = k));

const LAST_IN = FILL_START + 8 * STEP + 3; // Last cell entry animation ends at f44
const HOLD_END = LAST_IN + 14; // Full wall breathing phase ends at f58
const ZOOM_DUR = 14;
const ZOOM_END = HOLD_END + ZOOM_DUR; // f72, true hold thereafter

// Center cell contains miniature full-page FakeDashboard (0.3125), zooms to exactly full screen
const MINI_SCALE = CELL_W / 1920; // 0.3125
// 3.2 fills exactly; 3.28 pushes dark cell border off-screen for clean full-page settle
const ZOOM_SCALE = 3.28;

// Non-center cells: FakeDashboard crop offset (x, y, variant) or gray card (null)
const CROPS: Array<{ x: number; y: number; v: 'A' | 'B' } | null> = [
  { x: -120, y: -60, v: 'A' },
  null, // Gray card
  { x: -1260, y: -120, v: 'B' },
  { x: -60, y: -520, v: 'B' },
  null, // Center cell (handled separately, placeholder)
  { x: -1300, y: -640, v: 'A' },
  { x: -420, y: -300, v: 'B' },
  null, // Gray card
  { x: -900, y: -680, v: 'A' },
];

const CellContent: React.FC<{ i: number }> = ({ i }) => {
  if (i === 4) {
    // Center cell: full-page dashboard scaled inside cell
    return (
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: (CELL_H - 1080 * MINI_SCALE) / 2,
          transform: `scale(${MINI_SCALE})`,
          transformOrigin: 'top left',
        }}
      >
        <FakeDashboard variant="A" />
      </div>
    );
  }
  const crop = CROPS[i];
  if (crop === null) {
    // Gray card cell
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          background: G.panel,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Card w={430} h={240} seed={i * 3 + 2} />
      </div>
    );
  }
  // Crop slice: full-page dashboard clipped into cell with offset (varying background position)
  return (
    <div style={{ position: 'absolute', left: crop.x, top: crop.y }}>
      <FakeDashboard variant={crop.v} />
    </div>
  );
};

export const GridFlashMosaic: React.FC = () => {
  const f = useCurrentFrame();

  // Full wall subtle breathing: only during 14f hold after filled, sine cycle 1 -> 1.008 -> 1
  const breath =
    f >= LAST_IN && f < HOLD_END
      ? 1 + 0.008 * Math.sin((Math.PI * (f - LAST_IN)) / 14)
      : 1;

  // Center cell zoom: 14f Easing.in(cubic), expands to cover screen
  const zoom = interpolate(f, [HOLD_END, ZOOM_END], [1, ZOOM_SCALE], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.bg,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${breath})`,
          transformOrigin: '960px 540px',
        }}
      >
        {Array.from({ length: 9 }).map((_, i) => {
          const start = FILL_START + RANK[i] * STEP;
          if (f < start) return null; // Hard entry: not rendered before beat, no fade
          const row = Math.floor(i / 3);
          const col = i % 3;
          // Cell entry: 3f scale 1.18 -> 1
          const popScale = interpolate(f, [start, start + 3], [1.18, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          // 2f darken pulse
          const darken = interpolate(f, [start, start + 2], [0.45, 0], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          const isCenter = i === 4;
          const cellScale = isCenter ? popScale * zoom : popScale;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: GRID_X + col * (CELL_W + GAP),
                top: GRID_Y + row * (CELL_H + GAP),
                width: CELL_W,
                height: CELL_H,
                overflow: 'hidden',
                background: G.card,
                border: `3px solid ${G.ink}`,
                boxSizing: 'border-box',
                transform: `scale(${cellScale})`,
                transformOrigin: 'center',
                zIndex: isCenter ? 10 : 1,
              }}
            >
              <CellContent i={i} />
              {darken > 0.001 && (
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    background: '#000',
                    opacity: darken,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
