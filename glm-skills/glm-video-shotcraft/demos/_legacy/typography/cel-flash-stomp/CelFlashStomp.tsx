// Background cel-flash stomp (cel-flash-stomp) — A hybrid combination of stomp-typography (word-by-word rhythmic stomping)
// and background-cel-flash (solid background flashing). Three giant words hard-cut on the beat filling the screen,
// each stamping down tilted like a seal (scale 1.18->0.98->1 bounce + alternating ±2.5° rotate);
// From the settle frame of each word, the background layer alternates every 2f between G.bg and a deeper gray — the text layer
// sits motionless above, and flashing only the background is the core mechanic (anime special-move title card feel). The third word doubles flash duration and widens contrast.
// Keyframes: 0 "SHIP" hard cuts in (rot+2.5°) -> 0–6 bounce-drop -> 6–11 background flash (#cfcfca, 2f alternation across 6f)
// -> 30 "FASTER" hard cut (rot−2.5°) -> 30–36 bounce-drop -> 36–41 background flash
// -> 60 "TODAY" hard cut (rot 0°) -> 60–66 bounce-drop -> 66–73 background flash doubled (8f, #c4c4c0)
// + 66–80 bottom label bar fades in -> 80–144 complete rest (≥45f, no frame-by-frame noise layer).
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

type Word = {
  text: string;
  start: number; // Hard-cut entrance frame
  end: number; // Visible until this frame (when next word hard-cuts)
  rot: number; // Stamp tilt angle
  flashLen: number; // Total background flash duration after settling
  flashDark: string; // Darker gray for flash alternation
};

const LAND = 6; // Entrance bounce duration: settles at start+6, starts flashing on same frame
const WORDS: Word[] = [
  { text: 'SHIP', start: 0, end: 30, rot: 2.5, flashLen: 6, flashDark: '#cfcfca' },
  { text: 'FASTER', start: 30, end: 60, rot: -2.5, flashLen: 6, flashDark: '#cfcfca' },
  { text: 'TODAY', start: 60, end: 9999, rot: 0, flashLen: 8, flashDark: '#c4c4c0' },
];

export const CelFlashStomp: React.FC = () => {
  const frame = useCurrentFrame();
  const word = WORDS.find((w) => frame >= w.start && frame < w.end)!;
  const t = frame - word.start;

  // Bounce-drop: scale 1.18 -> 0.98 (2% overshoot) -> 1 within 6f, poly(5) ease-out
  const scale =
    t < 4
      ? interpolate(t, [0, 4], [1.18, 0.98], {
          extrapolateRight: 'clamp',
          easing: Easing.out(Easing.poly(5)),
        })
      : interpolate(t, [4, LAND], [0.98, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.out(Easing.quad),
        });

  // Background flash: starting on settle frame (start+LAND), alternates every 2f between deeper gray and G.bg, lasting flashLen frames
  const ft = t - LAND;
  const flashing = ft >= 0 && ft < word.flashLen;
  const bg = flashing && Math.floor(ft / 2) % 2 === 0 ? word.flashDark : G.bg;

  // Bottom label bar fades in starting on the same frame third word settles (66–80)
  const labelOp = interpolate(frame, [66, 80], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

  return (
    <div style={{ width: 1920, height: 1080, background: bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <TitleBlock text="CEL FLASH STOMP" size={54} />
      </div>
      {/* Text layer sits independently above background: stays perfectly motionless during background flashes */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: 210,
            color: G.ink,
            letterSpacing: -4,
            transform: `scale(${scale}) rotate(${word.rot}deg)`,
          }}
        >
          {word.text}
        </div>
      </div>
      {/* Bottom label bar: fades in on the same frame third word settles */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 96,
          background: G.ink,
          opacity: labelOp,
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          padding: '0 120px',
          boxSizing: 'border-box',
        }}
      >
        <div style={{ width: 40, height: 40, borderRadius: 10, background: G.sideBar }} />
        <div style={{ height: 16, width: 320, background: G.mid, borderRadius: 8 }} />
        <div style={{ marginLeft: 'auto', height: 16, width: 180, background: G.sideBar, borderRadius: 8 }} />
      </div>
    </div>
  );
};
