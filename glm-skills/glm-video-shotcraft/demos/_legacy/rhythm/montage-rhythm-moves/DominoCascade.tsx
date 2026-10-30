// Domino cascade entrance (domino-cascade) — Rube Goldberg / OK Go MV style.
// Three-stage momentum chain, each stage startFrame = previous stage impact frame:
// 1. Frames 36–51: title "CHAIN REACTION" slams down from off-screen top into upper screen via ease-in(cubic),
//    impact frame 51 triggers a 1-beat vertical screen shake (4f decay);
// 2. From frame 51: 4 cards below are jolted sequentially (5f stagger) bouncing up 60px in a parabola and landing back (12f),
//    last card lands at frame 78 = second impact (another 1-beat shake + last card tilts 3° left to provide horizontal momentum);
// 3. Frames 78–100: dark sidebar on left is bumped and slides into view, Easing.out(cubic) with overshoot rebound; frames 100–150 completely static.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card, TitleBlock } from '../../_fixtures/Fixtures';

const easeInCubic = Easing.in(Easing.cubic);
const easeOutCubic = Easing.out(Easing.cubic);

// —— Keyframes ——
const TITLE_START = 36; // Slam starts (first 36f hold to establish scene)
const IMPACT_1 = 51; // Title landing = first impact
const CARD_STAGGER = 5;
const CARD_DUR = 12;
const IMPACT_2 = IMPACT_1 + 3 * CARD_STAGGER + CARD_DUR; // 78, last card lands
const SIDE_END = IMPACT_2 + 14; // 92 sidebar in position (overshoot peak)
const SIDE_SETTLE = SIDE_END + 8; // 100 rebound settled, completely static afterwards

// Impact shake: 1 beat, decays to zero within 4f
const shake = (f: number, at: number, amp: number) => {
  if (f < at || f > at + 4) return 0;
  const seq = [amp, -amp * 0.6, amp * 0.3, -amp * 0.12, 0];
  return seq[f - at];
};

// Card row geometry: content center 1080 (leaving room for left 240px sidebar)
const CARD_W = 340;
const CARD_H = 220;
const GAP = 40;
const ROW_W = 4 * CARD_W + 3 * GAP; // 1480
const ROW_LEFT = 1080 - ROW_W / 2; // 340
const CARD_TOP = 700; // Card bottom edge 920, rests on floor line

export const DominoCascade: React.FC = () => {
  const frame = useCurrentFrame();

  // 1. Title slam: off-screen top -> upper screen, ease-in acceleration reads as "slam"
  const titleTop = interpolate(frame, [TITLE_START, IMPACT_1], [-260, 240], {
    easing: easeInCubic,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // Full-screen vertical shake for the two impacts
  const shakeY = shake(frame, IMPACT_1, 10) + shake(frame, IMPACT_2, 6);

  // 2. Card bounce: parabolic 4t(1-t), staggered every 5f
  const cardDy = (i: number) => {
    const s = IMPACT_1 + i * CARD_STAGGER;
    const t = Math.min(1, Math.max(0, (frame - s) / CARD_DUR));
    return -60 * 4 * t * (1 - t);
  };
  // Last card tilts 3° left on landing (visible source of horizontal momentum), then straightens
  const lastCardRot = interpolate(
    frame,
    [IMPACT_2 - 9, IMPACT_2, SIDE_END],
    [0, -3, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );

  // 3. Sidebar lateral slide-in: slides in with initial velocity + overshoot rebound
  let sideX: number;
  if (frame < IMPACT_2) {
    sideX = -260;
  } else if (frame < SIDE_END) {
    const t = (frame - IMPACT_2) / (SIDE_END - IMPACT_2);
    sideX = -260 + 272 * easeOutCubic(t); // Shoots to +12 (~5% overshoot)
  } else if (frame < SIDE_SETTLE) {
    const t = (frame - SIDE_END) / (SIDE_SETTLE - SIDE_END);
    sideX = 12 * (1 - Easing.inOut(Easing.quad)(t));
  } else {
    sideX = 0;
  }

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
      {/* Full-screen shake container */}
      <div style={{ position: 'absolute', inset: 0, transform: `translateY(${shakeY}px)` }}>
        {/* Floor line: card landing base */}
        <div style={{ position: 'absolute', left: ROW_LEFT - 30, top: 928, width: ROW_W + 60, height: 6, background: G.bar, borderRadius: 3 }} />

        {/* 1. Slamming title */}
        <div style={{ position: 'absolute', left: 240, width: 1680, top: titleTop, display: 'flex', justifyContent: 'center' }}>
          <TitleBlock text="CHAIN REACTION" size={120} />
        </div>

        {/* 2. Four bounce-jolted cards */}
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: ROW_LEFT + i * (CARD_W + GAP),
              top: CARD_TOP,
              transform: `translateY(${cardDy(i)}px)${i === 3 ? ` rotate(${lastCardRot}deg)` : ''}`,
              transformOrigin: '50% 100%',
            }}
          >
            <Card w={CARD_W} h={CARD_H} seed={i + 2} />
          </div>
        ))}

        {/* 3. Bumped slide-in sidebar */}
        <div
          style={{
            position: 'absolute', left: 0, top: 0, width: 240, height: 1080,
            background: G.side, transform: `translateX(${sideX}px)`,
            padding: '32px 24px', boxSizing: 'border-box',
            display: 'flex', flexDirection: 'column', gap: 22,
          }}
        >
          <div style={{ width: 44, height: 44, borderRadius: 10, background: '#777775' }} />
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} style={{ height: 13, width: `${58 + ((i * 31) % 38)}%`, background: G.sideBar, borderRadius: 6 }} />
          ))}
        </div>
      </div>
    </div>
  );
};
