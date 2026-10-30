// Pop burst confirm (pop-burst-confirm) — Triple burst at the moment of confirmation
// Half-screen checkmark icon (circular base + check): shrinks to 0.6x wind-up 3f -> pops 1.35x overshoot -> settles to 1x,
// on release frame 10 line particles shoot radially outward from center (flying out and dissipating) + stroked ring expands
// from icon edge to 2.5x diameter and fades out; subsequently "Deployed" pill tag pops up.
// Timing: 0–20 rest (hollow circle awaiting confirmation) -> 20–23 shrinks to 0.6x -> 23–27 holds wind-up 3f ->
// 27 release (checkmark draws + particles + expanding ring) -> 27–44 overshoot settle -> 40–50 tag pop-in -> true rest 65f after 55.
// Frame-deterministic, no random sources (particle angle jitter uses sin hash).
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G } from '../../_fixtures/Fixtures';

const AMBER = '#b45309';
const POP = 27; // Release frame
const DUR = 120;

export const PopBurstConfirm: React.FC = () => {
  const f = useCurrentFrame();

  // Icon scale: wind-up -> overshoot -> settle
  const scale = (() => {
    if (f <= 20) return 1;
    if (f <= 23)
      return interpolate(f, [20, 23], [1, 0.6], { easing: Easing.in(Easing.quad) });
    if (f <= POP) return 0.6;
    if (f <= 33)
      return interpolate(f, [POP, 33], [0.6, 1.35], { easing: Easing.out(Easing.cubic) });
    return interpolate(f, [33, 44], [1.35, 1], {
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.back(2)),
    });
  })();

  // Checkmark: drawn within 8f of release frame (dashoffset sliding window)
  const checkT = interpolate(f, [POP, POP + 8], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  // Particles: shoot radially for 14f from release frame (boosted to 190px amplitude for half-screen impact)
  const pt = interpolate(f, [POP, POP + 14], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const pDist = 210 + 190 * Easing.out(Easing.cubic)(pt);
  const pLen = 46 * (1 - pt);

  // Ring: expands from icon edge to 2.5x diameter and fades over 20f from release frame
  const rt = interpolate(f, [POP, POP + 20], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const ringR = 200 + 300 * Easing.out(Easing.cubic)(rt);
  const ringO = 0.85 * (1 - rt);
  const ringW = 16 - 12 * rt;

  // Tag: pops in at 40f (overshoot via back easing)
  const tagT = interpolate(f, [40, 50], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(2.6)),
  });

  const CX = 960;
  const CY = 470;

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      {/* Expanding ring (does not scale with icon) */}
      {rt > 0 && rt < 1 && (
        <svg
          width={1400}
          height={1400}
          style={{ position: 'absolute', left: CX - 700, top: CY - 700 }}
        >
          <circle cx={700} cy={700} r={ringR} fill="none" stroke={AMBER} strokeWidth={ringW} opacity={ringO} />
        </svg>
      )}

      {/* Particles: 10 line segments shoot radially with sin-hash angle jitter */}
      {pt > 0 && pt < 1 && (
        <svg
          width={1400}
          height={1400}
          style={{ position: 'absolute', left: CX - 700, top: CY - 700 }}
        >
          {Array.from({ length: 10 }).map((_, i) => {
            const ang = ((i * 36 + 9 * Math.sin(i * 7.31)) * Math.PI) / 180;
            const x1 = 700 + Math.cos(ang) * pDist;
            const y1 = 700 + Math.sin(ang) * pDist;
            const x2 = 700 + Math.cos(ang) * (pDist + pLen);
            const y2 = 700 + Math.sin(ang) * (pDist + pLen);
            return (
              <line
                key={i}
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={i % 5 < 2 ? AMBER : G.ink}
                strokeWidth={12}
                strokeLinecap="round"
                opacity={1 - pt}
              />
            );
          })}
        </svg>
      )}

      {/* Main icon: circular base + checkmark (half-screen close-up ~480px) */}
      <svg
        width={480}
        height={480}
        viewBox="0 0 480 480"
        style={{
          position: 'absolute',
          left: CX - 240,
          top: CY - 240,
          transform: `scale(${scale})`,
          transformOrigin: '50% 50%',
        }}
      >
        <circle cx={240} cy={240} r={190} fill={G.card} stroke={G.ink} strokeWidth={22} />
        {checkT > 0 && (
          <path
            d="M 150 245 L 215 310 L 340 175"
            fill="none"
            stroke={AMBER}
            strokeWidth={34}
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - checkT}
          />
        )}
      </svg>

      {/* Deployed pill tag */}
      {tagT > 0 && (
        <div
          style={{
            position: 'absolute',
            left: CX - 130,
            top: CY + 300,
            width: 260,
            transform: `scale(${tagT})`,
            transformOrigin: '50% 0%',
            padding: '16px 0',
            borderRadius: 40,
            background: G.ink,
            color: '#ffffff',
            textAlign: 'center',
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: 40,
            letterSpacing: 1,
          }}
        >
          Deployed
        </div>
      )}
    </div>
  );
};
