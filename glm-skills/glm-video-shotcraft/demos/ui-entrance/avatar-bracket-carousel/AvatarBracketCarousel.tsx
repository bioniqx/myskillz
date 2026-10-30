// avatar-bracket-carousel — Bracket Carousel avatar rotation in focus frame
// "Your ___ agent" layout (video-shotcraft agent crew: Director / Editor / Motion / Audio): 4-corner bracket locks active avatar, vertical spring carousel,
// scale up and sharpen into frame, scale down and fade out; role label updates in sync while flanking text stays fixed.
// Design coordinates 480x270 (DesignStage proportional scaling). Parameter table calibrated to this coordinate space.
// Polish pass: dark soft-light base + grain at full resolution; illuminated gradient discs + line icons for avatars;
// brackets lock inward on entrance; flanking text floats up staggered; role tag styled as backed chip scrolling with pos.
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DesignStage, E, seg, useT } from '../../_fixtures/Motion';
import { Backdrop, EASE, FONT, Grain } from '../../_fixtures/Polish';

export const AVATAR_BRACKET_CAROUSEL_DURATION = 156; // 5200ms @30fps

// Accent color: indigo boosted for dark mode (matching fixture G.accent hue)
const ACCENT = '#7b83f2';

// Neutral gray avatar bases to differentiate queue items; accent color reserved for focus brackets
const AV = [
  { c: '#4a4e5c', icon: 'clapper', role: 'Director' },
  { c: '#565b6b', icon: 'scissors', role: 'Editor' },
  { c: '#62687a', icon: 'curve', role: 'Animator' },
  { c: '#6f7588', icon: 'wave', role: 'Sound' },
];

// Line icons (24 viewBox, white stroke) replacing emojis to keep avatars neutral
const ICON: Record<string, React.ReactNode> = {
  // Clapperboard: Director
  clapper: (
    <>
      <path d="M4.5 10h15v8.3c0 .7-.5 1.2-1.2 1.2H5.7c-.7 0-1.2-.5-1.2-1.2Z" />
      <path d="M4.3 10 3.8 7.3c-.1-.6.3-1.2.9-1.3l12.6-2.3c.6-.1 1.2.3 1.3.9l.4 2.2Z" />
      <path d="M8.4 5.2l2 3.3M12.8 4.4l2 3.3" />
    </>
  ),
  // Scissors: Editor
  scissors: (
    <>
      <circle cx="6.6" cy="6.8" r="2.5" />
      <circle cx="6.6" cy="17.2" r="2.5" />
      <path d="M8.7 8.3 19.5 17.6M8.7 15.7 19.5 6.4" />
    </>
  ),
  // Motion curve + keyframe: Motion
  curve: (
    <>
      <path d="M4.5 18.5C10 18.5 9.5 5.5 19.5 5.5" />
      <rect x="2.9" y="16.9" width="3.2" height="3.2" transform="rotate(45 4.5 18.5)" fill="currentColor" stroke="none" />
      <rect x="17.9" y="3.9" width="3.2" height="3.2" transform="rotate(45 19.5 5.5)" fill="currentColor" stroke="none" />
    </>
  ),
  // Audio waveform: Sound
  wave: <path d="M4.5 12h.01M8 9.2v5.6M11.2 5.8v12.4M14.4 8.4v7.2M17.6 10.4v3.2M20 12h.01" />,
};

// 4-corner bracket corner paths (92x92 viewBox)
const CORNERS = ['M4,26 L4,4 L26,4', 'M66,4 L88,4 L88,26', 'M88,66 L88,88 L66,88', 'M26,88 L4,88 L4,66'];
// Corner outward offset direction during entrance lock (TL / TR / BR / BL)
const CORNER_DIR = [[-1, -1], [1, -1], [1, 1], [-1, 1]];

const STEP = 76;
const SWITCHES = [0.24, 0.46, 0.68]; // Three transition start points

export const AvatarBracketCarousel: React.FC = () => {
  const t = useT();

  // Three transitions: 0.24 / 0.46 / 0.68 with spring physics
  const posAt = (tt: number) => {
    let p = 0;
    SWITCHES.forEach((s0) => {
      p += seg(tt, s0, s0 + 0.14, (k) => E.spring(k, 0.25));
    });
    return p;
  };
  const pos = posAt(t);
  // Carousel velocity (slots/frame): used for directional smear stretch, 0 at rest
  const dt = 1 / 155;
  const vel = (posAt(t + dt * 0.5) - posAt(t - dt * 0.5));

  // Bracket pulse breathing on transition
  let breath = 0;
  SWITCHES.forEach((s0) => {
    breath += Math.sin(seg(t, s0, s0 + 0.1) * Math.PI);
  });

  // Entrance: brackets converge inward 14px to lock (0.03->0.17); text floats up staggered
  const lock = seg(t, 0.03, 0.17, EASE.snappy);
  const lockOp = seg(t, 0.03, 0.09, EASE.out);
  const wordIn = (t0: number) => seg(t, t0, t0 + 0.13, EASE.snappy);
  const wl = wordIn(0.0);
  const wr = wordIn(0.035);

  const word: React.CSSProperties = {
    color: '#eef0f6',
    fontWeight: 700,
    fontSize: 34,
    letterSpacing: '-0.035em',
    lineHeight: 1,
    fontKerning: 'normal',
  };

  return (
    <AbsoluteFill>
      {/* Full resolution background: cool dark base + key light spot above slot + subtle accent glow */}
      <Backdrop tone="dark" light={{ x: 0.42, y: 0.34 }} accent={ACCENT} grain={0} vignette={0.55} />
      <DesignStage bg="transparent">
        <div
          style={{
            position: 'absolute',
            inset: 0,
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 22,
            fontFamily: FONT.sans,
          }}
        >
          <div style={{ ...word, opacity: wl, transform: `translateY(${(1 - wl) * 10}px)`, filter: `blur(${(1 - wl) * 2}px)` }}>
            Your
          </div>

          {/* Center focus brackets + avatar column */}
          <div style={{ position: 'relative', width: 92, height: 92, flex: 'none' }}>
            {/* Subtle accent underglow inside slot giving spatial presence to focus point */}
            <div
              style={{
                position: 'absolute',
                inset: -18,
                borderRadius: '50%',
                background: `radial-gradient(circle, rgba(123,131,242,0.16) 0%, rgba(123,131,242,0) 62%)`,
                opacity: lockOp,
              }}
            />
            <div style={{ position: 'absolute', left: '50%', top: '50%', width: 0, height: 0 }}>
              {AV.map((a, k) => {
                const d = Math.abs(k - pos);
                const sc = Math.max(0.5, 1 - d * 0.38);
                const op = Math.max(0, 1 - d * 0.62);
                // Entrance: staggered by 0.03, floats in 12px from below along carousel direction
                const enter = seg(t, 0.02 + k * 0.03, 0.12 + k * 0.03, EASE.out);
                // Smear: +6% vertical at 0.25 slots/frame velocity with equal-volume horizontal contraction
                const smear = Math.min(0.08, Math.abs(vel) * 0.24);
                return (
                  <div
                    key={k}
                    style={{
                      position: 'absolute',
                      left: -29,
                      top: -29,
                      width: 58,
                      height: 58,
                      borderRadius: '50%',
                      // Top-lit gradient disc + 1px hairline stroke + inner highlight + dual drop shadow
                      background: `radial-gradient(120% 100% at 32% 18%, ${lighten(a.c, 0.22)} 0%, ${a.c} 55%, ${lighten(a.c, -0.18)} 100%)`,
                      border: '0.5px solid rgba(255,255,255,0.14)',
                      boxSizing: 'border-box',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'rgba(255,255,255,0.94)',
                      boxShadow:
                        'inset 0 0.75px 0 rgba(255,255,255,0.22), 0 1px 2px rgba(0,0,0,0.35), 0 8px 18px -4px rgba(0,0,0,0.55)',
                      transform: `translateY(${(k - pos) * STEP + (1 - enter) * 12}px) scale(${sc * (1 - smear * 0.5)}, ${sc * (1 + smear)})`,
                      opacity: op * enter,
                      filter: `blur(${Math.min(3, d * 2.4)}px)`,
                    }}
                  >
                    <svg
                      width={26}
                      height={26}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.7}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      {ICON[a.icon]}
                    </svg>
                  </div>
                );
              })}
            </div>

            <div
              style={{
                position: 'absolute',
                inset: 0,
                zIndex: 3,
                opacity: lockOp,
                transform: `scale(${1 + Math.min(1, breath) * 0.07})`,
              }}
            >
              <svg width={92} height={92} viewBox="0 0 92 92" style={{ overflow: 'visible' }}>
                {CORNERS.map((d, i) => (
                  <path
                    key={i}
                    d={d}
                    fill="none"
                    stroke={ACCENT}
                    strokeWidth={3.2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    transform={`translate(${CORNER_DIR[i][0] * (1 - lock) * 14} ${CORNER_DIR[i][1] * (1 - lock) * 14})`}
                    style={{ filter: 'drop-shadow(0 0 3px rgba(123,131,242,0.45))' }}
                  />
                ))}
              </svg>
            </div>

            {/* Role chip: backed chip over next avatar (static pos), text scrolls in sync with pos */}
            <div
              style={{
                position: 'absolute',
                left: '50%',
                top: '50%',
                zIndex: 4,
                transform: `translate(-50%, 58px) translateY(${(1 - lockOp) * 6}px)`,
                opacity: lockOp,
                height: 20,
                width: 78,
                borderRadius: 10,
                background: 'linear-gradient(180deg, rgba(30,32,40,0.96), rgba(20,21,27,0.96))',
                border: '0.5px solid rgba(255,255,255,0.10)',
                boxShadow: 'inset 0 0.5px 0 rgba(255,255,255,0.08), 0 4px 10px -2px rgba(0,0,0,0.6)',
                overflow: 'hidden',
              }}
            >
              {AV.map((a, k) => (
                <div
                  key={k}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 5,
                    color: '#c9cde0',
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.02em',
                    transform: `translateY(${(k - pos) * 14}px)`,
                    opacity: Math.max(0, 1 - Math.abs(k - pos) * 2.2),
                  }}
                >
                  <span style={{ width: 4, height: 4, borderRadius: 2, background: ACCENT, flex: 'none' }} />
                  {a.role}
                </div>
              ))}
            </div>
          </div>

          <div style={{ ...word, opacity: wr, transform: `translateY(${(1 - wr) * 10}px)`, filter: `blur(${(1 - wr) * 2}px)` }}>
            agent
          </div>
        </div>
      </DesignStage>
      <Grain opacity={0.07} blend="soft-light" />
    </AbsoluteFill>
  );
};

// Adjust hex color lightness: brighten (amt > 0) / darken (amt < 0)
function lighten(hex: string, amt: number) {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) =>
    Math.round(amt >= 0 ? c + (255 - c) * amt : c * (1 + amt)),
  );
  return `rgb(${ch.join(',')})`;
}
