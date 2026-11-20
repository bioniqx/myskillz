// origin: vibe-motion/skills remotion-3d-ticker assets/VerticalTicker.tsx
//         (Scanned 2026-07-13; items generalized to ReactNode,
//          mask height/perspective/scale/column width/gap exposed as props)
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';

export interface TickerColumn {
  /** Column content — any ReactNode (screenshot-slice divs, <Img>, text cards…) */
  items: React.ReactNode[];
  /** Seconds for one full loop (one copy of items scrolling its own height) */
  durationInSeconds: number;
  /** -1 scrolls up, 1 scrolls down */
  direction: -1 | 1;
}

export interface VerticalTickerProps {
  columns: TickerColumn[];
  /** Background color, also used by the top/bottom fade masks */
  backgroundColor?: string;
  /** Height of each fade mask in px */
  maskHeight?: number;
  /** rotateX tilt of the whole wall, degrees */
  tiltDeg?: number;
  /** CSS perspective distance in px */
  perspective?: number;
  /** Overall scale of the tilted wall (compensates perspective shrink) */
  scale?: number;
  /** Column width in px */
  columnWidth?: number;
  /** Gap between columns and between items within a column, px */
  gap?: number;
}

/**
 * 3D perspective multi-column infinite vertical scrolling ticker wall.
 * Duplicates [...items, ...items] with progress modulo translateY 0 -> -50%.
 * Uses marginBottom = gap on each item for seamless loop alignment.
 */
export const VerticalTicker: React.FC<VerticalTickerProps> = ({
  columns,
  backgroundColor = '#000',
  maskHeight = 200,
  tiltDeg = 20,
  perspective = 1000,
  scale = 1.2,
  columnWidth = 400,
  gap = 30,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor, overflow: 'hidden' }}>
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          justifyContent: 'center',
          gap,
          transform: `perspective(${perspective}px) rotateX(${tiltDeg}deg) scale(${scale})`,
          transformOrigin: 'center center',
        }}
      >
        {columns.map((col, idx) => (
          <Column key={idx} {...col} width={columnWidth} gap={gap} />
        ))}
      </div>
      {/* Fade masks sit above the wall so rows enter/exit softly */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: maskHeight,
          background: `linear-gradient(to bottom, ${backgroundColor} 0%, transparent 100%)`,
          zIndex: 10,
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: maskHeight,
          background: `linear-gradient(to top, ${backgroundColor} 0%, transparent 100%)`,
          zIndex: 10,
        }}
      />
    </AbsoluteFill>
  );
};

const Column: React.FC<TickerColumn & { width: number; gap: number }> = ({
  items,
  durationInSeconds,
  direction,
  width,
  gap,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const loopFrames = durationInSeconds * fps;
  const progress = (frame % loopFrames) / loopFrames;
  // up: 0 -> -50%; down: -50% -> 0 (starts offset by half cycle, no first-frame blank)
  const translateY = direction === -1 ? progress * -50 : -50 + progress * 50;

  return (
    <div style={{ width, height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          transform: `translateY(${translateY}%)`,
          willChange: 'transform',
        }}
      >
        {[...items, ...items].map((node, i) => (
          <div key={i} style={{ marginBottom: gap }}>
            {node}
          </div>
        ))}
      </div>
    </div>
  );
};
