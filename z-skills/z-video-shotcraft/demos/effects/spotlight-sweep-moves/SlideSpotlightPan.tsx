// slide-spotlight-pan v2 — referenced from clickup03:
// Purple streak hugs UI panel perimeter (up left vertical edge, then along top horizontal edge),
// spotlight head moves linearly rightward; panel slides linearly leftward (camera right pan feel).
// Streak hugs UI edge, spotlight moves with constant linear velocity.
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate } from 'remotion';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

const ink = '#3c3c3a';
const mid = '#98989a';
const line = '#e4e4e2';

const PW = 3000;
const PH = 1400;
const TOP = 150;   // Panel top edge screen y
const CR = 60;     // Panel corner radius

const SideRow: React.FC<{ w: number }> = ({ w }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 16, height: 44 }}>
    <div style={{ width: 26, height: 26, borderRadius: 7, background: mid }} />
    <div style={{ height: 15, width: w, background: '#c6c6c4', borderRadius: 7 }} />
  </div>
);

const Task: React.FC<{ seed: number }> = ({ seed }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 13, padding: '26px 0' }}>
    <div style={{ height: 13, width: 210 + (seed % 3) * 30, background: line, borderRadius: 6 }} />
    <div style={{ height: 17, width: 260 + ((seed * 7) % 4) * 26, background: '#aeaeac', borderRadius: 8 }} />
    <div style={{ width: 22, height: 16, background: '#d6d6d4', borderRadius: 3 }} />
  </div>
);

const Col: React.FC<{ accent: string; seed: number; w: number }> = ({ accent, seed, w }) => (
  <div style={{ width: w, flexShrink: 0 }}>
    <div style={{ borderTop: `6px solid ${accent}`, paddingTop: 24, display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ height: 20, width: 120, background: '#525250', borderRadius: 9 }} />
      <div style={{ width: 32, height: 32, borderRadius: 16, border: `3px solid ${line}` }} />
      <div style={{ marginLeft: 'auto', width: 22, height: 22, background: line, borderRadius: 4 }} />
    </div>
    {[0, 1].map((i) => <Task key={i} seed={seed + i} />)}
  </div>
);

// Extra-wide panel content: sidebar (ShotcraftMark + wordmark) + header + 3-column board
const WidePanel: React.FC = () => (
  <div style={{
    width: PW, height: PH, background: '#f4f4f3',
    display: 'flex', boxSizing: 'border-box',
    borderRadius: `${CR}px ${CR}px 0 0`,
  }}>
    <div style={{ width: 560, borderRight: `3px solid ${line}`, padding: '52px 48px', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 56 }}>
        {/* Sidebar brand position: ShotcraftMark + wordmark */}
        <ShotcraftMark size={46} tone="light" />
        <div style={{ fontFamily: BRAND.font, fontSize: 27, fontWeight: 700, letterSpacing: '0.03em', lineHeight: 1, color: ink, whiteSpace: 'nowrap' }}>{BRAND.name}</div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <SideRow w={110} /><SideRow w={200} /><SideRow w={100} />
      </div>
      <div style={{ height: 20, width: 130, background: '#adadab', borderRadius: 9, margin: '58px 0 24px' }} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <SideRow w={180} /><SideRow w={220} /><SideRow w={170} />
      </div>
    </div>
    <div style={{ flex: 1, padding: '52px 64px', boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 22, marginBottom: 48 }}>
        <div style={{ width: 36, height: 30, background: mid, borderRadius: 6 }} />
        <div style={{ height: 26, width: 400, background: '#606060', borderRadius: 11 }} />
        <div style={{ height: 18, width: 150, background: line, borderRadius: 8, marginLeft: 64 }} />
        <div style={{ height: 18, width: 120, background: line, borderRadius: 8 }} />
        <div style={{ height: 18, width: 90, background: line, borderRadius: 8 }} />
      </div>
      <div style={{ display: 'flex', gap: 84 }}>
        <Col accent="#c4ad45" seed={1} w={620} />
        <Col accent="#6b5bd6" seed={4} w={620} />
        <Col accent="#4f8f6f" seed={7} w={620} />
      </div>
    </div>
  </div>
);

export const SlideSpotlightPan: React.FC = () => {
  const frame = useCurrentFrame();
  // Panel slides linearly leftward (camera pan right) — strictly linear
  const slide = interpolate(frame, [0, 132], [180, -1100]);
  // Spotlight head moves linearly rightward in panel local coordinates — strictly linear
  // Origin at top-left vertical edge (negative = vertical phase), turns corner along top edge
  const head = interpolate(frame, [0, 132], [-360, 2600]);
  const onTop = Math.max(0, head);            // Top edge phase progress
  const cornerT = Math.min(1, Math.max(0, (head + 360) / 360)); // Vertical edge phase 0->1
  const vertHeadY = TOP + 620 - cornerT * 620; // Vertical head ascends toward corner

  // Spotlight head position in screen coordinates
  const headScreenX = slide + onTop;
  // Head hugs panel left edge during vertical phase
  const leftEdgeX = slide;

  // Vertical streak intensity: full before corner, decays after turn
  const vGlow = head < 0 ? 1 : Math.max(0, 1 - head / 900);
  // Top streak intensity: full after turning corner
  const hGlow = Math.min(1, Math.max(0, (head + 120) / 240));

  const grad = (dir: string, c: string) =>
    `linear-gradient(${dir}, rgba(0,0,0,0) 0%, ${c} 42%, ${c} 58%, rgba(0,0,0,0) 100%)`;

  return (
    <AbsoluteFill style={{ background: '#050409', overflow: 'hidden' }}>
      {/* Panel layer: revealed within spotlight mask */}
      <div style={{ position: 'absolute', left: 0, top: TOP, transform: `translateX(${slide}px)` }}>
        <WidePanel />
        {/* Edge bloom: violet glow spilling into UI top edge below head */}
        <div style={{
          position: 'absolute', left: onTop - 620, top: -30, width: 1240, height: 380,
          background: 'radial-gradient(ellipse 620px 190px at 50% 0%, rgba(168,95,245,0.5), rgba(140,75,235,0.16) 55%, rgba(0,0,0,0) 78%)',
          filter: 'blur(6px)', opacity: hGlow,
        }} />
        {/* Left edge bloom (vertical phase) */}
        <div style={{
          position: 'absolute', left: -30, top: vertHeadY - TOP - 320, width: 340, height: 780,
          background: 'radial-gradient(ellipse 170px 390px at 0% 50%, rgba(168,95,245,0.45), rgba(140,75,235,0.14) 55%, rgba(0,0,0,0) 78%)',
          filter: 'blur(6px)', opacity: vGlow,
        }} />
        {/* Spotlight reveal mask centered at light head */}
        <div style={{
          position: 'absolute', inset: -60,
          background: `radial-gradient(ellipse 1350px 1000px at ${onTop + 60}px ${(head < 0 ? vertHeadY - TOP : 40) + 260}px, rgba(0,0,0,0) 26%, rgba(0,0,0,0.55) 60%, rgba(5,4,9,0.96) 100%)`,
        }} />
      </div>

      {/* ===== Edge-hugging purple streak (screen layer along panel edge) ===== */}
      {/* Top horizontal streak: 3 glow layers + bright core */}
      <div style={{ opacity: hGlow }}>
        <div style={{
          position: 'absolute', left: headScreenX - 640, top: TOP - 56, width: 1280, height: 112,
          background: grad('90deg', 'rgba(150,82,238,0.55)'), filter: 'blur(30px)',
        }} />
        <div style={{
          position: 'absolute', left: headScreenX - 470, top: TOP - 17, width: 940, height: 34,
          background: grad('90deg', 'rgba(196,126,255,0.9)'), filter: 'blur(10px)',
        }} />
        <div style={{
          position: 'absolute', left: headScreenX - 330, top: TOP - 8, width: 660, height: 16,
          background: grad('90deg', 'rgba(240,155,235,0.85)'), filter: 'blur(5px)',
        }} />
        <div style={{
          position: 'absolute', left: headScreenX - 300, top: TOP - 3, width: 600, height: 6,
          background: grad('90deg', '#f6e8ff'), filter: 'blur(1.5px)',
        }} />
      </div>
      {/* Top-left vertical streak (initial phase along left edge) */}
      <div style={{ opacity: vGlow }}>
        <div style={{
          position: 'absolute', left: leftEdgeX - 52, top: vertHeadY - 420, width: 104, height: 840,
          background: grad('180deg', 'rgba(150,82,238,0.5)'), filter: 'blur(28px)',
        }} />
        <div style={{
          position: 'absolute', left: leftEdgeX - 14, top: vertHeadY - 330, width: 28, height: 660,
          background: grad('180deg', 'rgba(196,126,255,0.9)'), filter: 'blur(9px)',
        }} />
        <div style={{
          position: 'absolute', left: leftEdgeX - 3, top: vertHeadY - 260, width: 6, height: 520,
          background: grad('180deg', '#f6e8ff'), filter: 'blur(1.5px)',
        }} />
      </div>

      {/* Top black margin above light band */}
      <div style={{
        position: 'absolute', left: 0, top: 0, width: 1920, height: TOP - 4,
        background: 'linear-gradient(180deg, #050409 78%, rgba(5,4,9,0) 100%)',
      }} />
    </AbsoluteFill>
  );
};

export const SLIDE_SPOTLIGHT_PAN_DURATION = 132;
