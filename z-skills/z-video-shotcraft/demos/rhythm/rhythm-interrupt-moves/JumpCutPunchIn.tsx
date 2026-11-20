// Three-stage jump-cut punch-in — Rhythmic editing | Godard jump cut / documentary punch-in.
// FakeDashboard A fixed framing, zoom center pinned to center of row 2 middle card (Deploys)
// (1071px, 817px). Three hard cuts without interpolation step up magnification: cuts deliberately avoid tweening,
// landing in a single frame. Each cut overlays a 2f full-frame brightness 0.92 pulse as a tick mark.
// Keyframes: 0–34 scale 1.0 -> frame 35 jump cut to 1.6 (35–36 dimming pulse) -> frame 70 jump cut to 2.6
// (70–71 dimming pulse) -> final stage 86–134 completely static (49f >= 45f).
// Texture: magnification uses CSS zoom (layout-level scaling; Chromium rasterizes at target size, keeping typography sharp at 2.6x);
// first two stages feature subtle 0.8% in-stage drift push-in (in-out, no velocity jumps) to keep frames alive while cuts remain hard;
// final stage settles over 16f ease-out into true static hold. Target card uses real UI selected state (accent ring + soft halo);
// ring intensifies on the third jump ("that's the one"); vignette tightens per stage drawing focus to target, with 4.5% film grain.
import React from 'react';
import { AbsoluteFill, Freeze, useCurrentFrame } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';
import { EASE, Grain, Vignette, mix, ramp } from '../../_fixtures/Polish';

export const JUMP_CUT_PUNCH_IN_DURATION = 135; // 35f wide + 35f medium + 65f close (including 49f static hold)

// Target card (3x2 grid row 2 middle card) geometry:
// Sidebar 220 + padding 36; card width (1920-220-72-56)/3 = 524.67, card height (1080-72-72-28)/2 = 454
const CARD_L = 220 + 36 + 524.67 + 28; // ≈808.67
const CARD_T = 72 + 36 + 454 + 28; // 590
const CARD_W = 524.67;
const CARD_H = 454;
const ORIGIN_X = CARD_L + CARD_W / 2; // ≈1071
const ORIGIN_Y = CARD_T + CARD_H / 2; // 817

const JUMP_1 = 35;
const JUMP_2 = 70;
const STEPS = [1.0, 1.6, 2.6]; // Step ratio >=1.5x to avoid looking like camera shake

// Three hard cut stages (zero interpolation)
const stepAt = (f: number): number => (f < JUMP_1 ? 0 : f < JUMP_2 ? 1 : 2);

// Intra-stage drift: first two stages push 0.8% in-out over 35f (live camera); final stage pushes 0.8% ease-out over 16f then holds static
const driftAt = (f: number): number => {
  const st = stepAt(f);
  if (st === 0) return mix(1, 1.008, ramp(f, 0, JUMP_1, EASE.smooth));
  if (st === 1) return mix(1, 1.008, ramp(f, JUMP_1, JUMP_2 - JUMP_1, EASE.smooth));
  return mix(1, 1.008, ramp(f, JUMP_2, 16, EASE.out));
};

// 2f dimming pulse on cut frame (full-screen brightness 0.92)
const pulseAt = (f: number): number =>
  (f >= JUMP_1 && f <= JUMP_1 + 1) || (f >= JUMP_2 && f <= JUMP_2 + 1) ? 0.92 : 1;

export const JumpCutPunchIn: React.FC = () => {
  const frame = useCurrentFrame();
  const st = stepAt(frame);
  const s = STEPS[st]; // Stage zoom: layout-level CSS zoom (updates once per stage)
  const drift = driftAt(frame); // Intra-stage drift: transform scale (subpixel smooth, no reflow)
  const b = pulseAt(frame);

  // Selection ring: rests quietly during first two stages; intensifies over 8f ease-out on third jump ("that's the one")
  const lock = ramp(frame, JUMP_2, 8, EASE.out);
  const ringA = mix(0.42, 0.85, lock);
  const haloA = mix(0.07, 0.14, lock);

  return (
    <AbsoluteFill style={{ background: G.canvas, overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          filter: b < 1 ? `brightness(${b})` : undefined,
          transform: `scale(${drift})`,
          transformOrigin: `${ORIGIN_X}px ${ORIGIN_Y}px`,
        }}
      >
        <div
          style={{
            position: 'absolute',
            // zoom scales left/top as well: left = O/s - O => focal center O stays stationary on screen (same-origin jump cut)
            left: ORIGIN_X / s - ORIGIN_X,
            top: ORIGIN_Y / s - ORIGIN_Y,
            width: 1920,
            height: 1080,
            zoom: s,
          }}
        >
          <FakeDashboard variant="A" />
          {/* Target card selected state: 1.5px accent ring + soft halo, scales with composition */}
          <div
            style={{
              position: 'absolute',
              left: CARD_L - 5,
              top: CARD_T - 5,
              width: CARD_W + 10,
              height: CARD_H + 10,
              borderRadius: 19,
              border: `1.5px solid rgba(91,99,211,${ringA.toFixed(3)})`,
              boxShadow: `0 0 0 5px rgba(91,99,211,${haloA.toFixed(3)}), 0 18px 48px -18px rgba(91,99,211,${(haloA * 1.6).toFixed(3)})`,
              boxSizing: 'border-box',
              pointerEvents: 'none',
            }}
          />
        </div>
      </div>
      {/* Vignette: tightens with closer stages to direct focus toward target card */}
      <Vignette strength={[0.1, 0.14, 0.18][st]} inner={0.52} color="#1a1c24" cx={ORIGIN_X / 1920} cy={0.56} />
      {/* Grain freezes once final push completes (86f), ensuring pixel-perfect static hold in tail */}
      <Freeze frame={JUMP_2 + 16} active={frame >= JUMP_2 + 16}>
        <Grain opacity={0.045} />
      </Freeze>
    </AbsoluteFill>
  );
};
