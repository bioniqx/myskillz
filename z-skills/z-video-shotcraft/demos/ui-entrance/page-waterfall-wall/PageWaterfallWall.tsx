// page-waterfall-wall — Page Waterfall Wall: Real page screenshot slices arranged into 3 columns, infinitely scrolling in alternating directions at differential speeds on a tilted wall,
// with outer camera slow push-in, offering an overview of "endlessly flowing content".
// Polish layer (revision):
// · Assets use only card-level slices (card1–10, no inter-column reuse); previously mixed full-page blank screenshot projects-empty and
//   2032x88 search bar slivers (which read as blank cards / fragmented strips on the wall) have been removed
// · 3 columns of 420px width, fitting entire wall within frame (original 560px width x 1.2 cut side columns in half, heavily distorting perspective on outer text)
// · Wall scaling and slow push-in rely on CSS zoom (layout-level scaling), rasterizing card text at display size (Q2), preventing blurry upscaling
// · Solid #101014 + opaque gradient mask replaced with: cool-toned dark soft-light backdrop (subtle indigo afterglow behind wall) + top/bottom feathering
//   (gradients match actual edge colors of background) + slight darkening at top distant edge (aerial perspective) + vignette + grain
// · Card slices gain hairline border and top specular edge, shadows upgraded to two tiers (contact shadow + ambient shadow)
// Asset paths standardized to textures/live/ (matching workbench / template public).
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { Backdrop, Grain } from '../../_fixtures/Polish';
import { VerticalTicker, TickerColumn } from './VerticalTicker';

export const PAGE_WATERFALL_WALL_DURATION = 150; // 5s (infinite loop, trim according to section needs)

const BG = '#0d0e13';
const ZOOM = 1.2; // Baseline zoom compensating for perspective foreshortening (recipe scale 1.2)
const PUSH = 0.06; // Camera slow push 1→1.06

const shot = (file: string) => (
  <div
    style={{
      position: 'relative',
      borderRadius: 20,
      overflow: 'hidden',
      background: '#fefcf9',
      boxShadow: '0 2px 4px rgba(0,0,0,0.35), 0 22px 48px -12px rgba(0,0,0,0.6)',
    }}
  >
    <Img src={staticFile(`textures/live/${file}`)} style={{ width: '100%', display: 'block' }} />
    {/* Hairline border + top specular edge (clipped within rounded corners) */}
    <div
      style={{
        position: 'absolute', inset: 0, borderRadius: 20, pointerEvents: 'none',
        boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.10), inset 0 1px 0 rgba(255,255,255,0.9)',
      }}
    />
  </div>
);

// 3 columns at differential speeds in alternating directions (recipe card params: loop 12/9/14s, center column reversed); 10 card slices distributed 4/3/3, no reuse across columns
export const buildColumns = (loops: [number, number, number]): TickerColumn[] => [
  {
    items: ['card1.png', 'card2.png', 'card3.png', 'card10.png'].map(shot),
    durationInSeconds: loops[0],
    direction: -1,
  },
  {
    items: ['card4.png', 'card5.png', 'card6.png'].map(shot),
    durationInSeconds: loops[1],
    direction: 1,
  },
  {
    items: ['card7.png', 'card8.png', 'card9.png'].map(shot),
    durationInSeconds: loops[2],
    direction: -1,
  },
];

// Top/bottom feathering: gradients sample actual colors at stage top/bottom edges (longer feathering on distant top edge), soft row enter/exit
const FADE_TOP = 'linear-gradient(to bottom, #111319 0%, rgba(17,19,25,0.85) 10%, rgba(17,19,25,0) 30%)';
const FADE_BOTTOM = 'linear-gradient(to top, #08090c 0%, rgba(8,9,12,0.8) 8%, rgba(8,9,12,0) 22%)';

const Wall: React.FC<{ loops: [number, number, number]; zoom: number }> = ({ loops, zoom }) => (
  <AbsoluteFill>
    {/* zoom ensures wall is laid out and rasterized at display resolution; internal 1920/zoom CSS canvas centers 3 columns */}
    <div style={{ position: 'absolute', left: 0, top: 0, width: 1920 / zoom, height: 1080 / zoom, zoom }}>
      <VerticalTicker columns={buildColumns(loops)} backgroundColor="transparent" maskHeight={0} scale={1} columnWidth={420} gap={26} />
    </div>
    {/* Aerial perspective: subtle darkening at distant wall edge (upper frame) */}
    <AbsoluteFill style={{ background: 'linear-gradient(to bottom, rgba(13,14,19,0.5) 0%, rgba(13,14,19,0) 50%)', pointerEvents: 'none' }} />
    <AbsoluteFill style={{ background: FADE_TOP, pointerEvents: 'none' }} />
    <AbsoluteFill style={{ background: FADE_BOTTOM, pointerEvents: 'none' }} />
  </AbsoluteFill>
);

export const PageWaterfallWall: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // Camera push-in hosted on outer layer: wall loops continuously, camera moves monotonically (linear span across entire shot, recipe definition)
  const push = interpolate(frame, [0, durationInFrames], [1, 1 + PUSH], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: BG }}>
      <Backdrop tone="dark" light={{ x: 0.5, y: 0.42 }} accent="#5b63d3" grain={0} vignette={0} />
      <Wall loops={[12, 9, 14]} zoom={ZOOM * push} />
      <AbsoluteFill style={{ background: 'radial-gradient(ellipse 75% 70% at 50% 50%, rgba(5,6,10,0) 55%, rgba(5,6,10,0.55) 100%)', pointerEvents: 'none' }} />
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};

// Seam self-test: short loop (3s=90f), no camera push; f0 and f90 should match pixel-for-pixel
export const SeamTest: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: BG }}>
    <Wall loops={[3, 3, 3]} zoom={ZOOM} />
  </AbsoluteFill>
);
