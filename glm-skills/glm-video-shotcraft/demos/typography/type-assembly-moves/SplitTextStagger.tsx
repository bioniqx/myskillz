// split-text-stagger — masked per-character split-rise entrance (GSAP SplitText style).
// Title "FRAME MOTION." split per character into spans inside overflow:hidden line-height boxes,
// rising from translateY(115%) to 0 over 14f Easing.out(cubic) with 10% overshoot
// then 6f settle. delay = charIndex * 2f.
// Bottom baseline grows left to right concurrently with first character launch.
// Keyframes: 0-12 empty hold -> 12 first char launches + baseline grows -> each char 12+i*2,
// 14f rise to -10% overshoot -> 6f settle to 0 -> last char settles at 56f ->
// 56-130 complete static hold (74f >= 40f).
//
// Polish pass: soft lighting backdrop; system font stack 700, font size 136px;
// vertical motion blur during rapid rise; accent colored baseline matching text width exactly,
// strong ease-out growth; total duration 130f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT as PFONT, ramp } from '../../_fixtures/Polish';

export const SPLIT_TEXT_STAGGER_DURATION = 130;

const TEXT = 'FRAME MOTION.'; // First half of brand motto Frame motion. Craft the shot. (13 chars)
const START = 12; // First character launch frame
const RISE = 14; // Rise duration
const SETTLE = 6; // Overshoot settle duration
const OVERSHOOT = -10; // Overshoot to -10%
const FONT = 136;
const LINE_H = 1.05; // Span line-height (translateY % basis)

// Character vertical displacement (%): 115 -> -10 (out cubic) -> 0 (out quad)
const charY = (f: number, idx: number): number => {
  const t0 = START + idx * 2;
  if (f < t0 + RISE) {
    return interpolate(f, [t0, t0 + RISE], [115, OVERSHOOT], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
  }
  return interpolate(f, [t0 + RISE, t0 + RISE + SETTLE], [OVERSHOOT, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
};

export const SplitTextStagger: React.FC = () => {
  const frame = useCurrentFrame();
  const chars = TEXT.split('');
  // Baseline: launches with first char, grows left-to-right to 100%
  const lineW = ramp(frame, START, 30, EASE.snappy) * 100;

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden' }}>
      <Backdrop tone="light" light={{ x: 0.42, y: 0.3 }} accent="#5b63d3" grain={0.045} vignette={0.12} />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {/* Line container: baseline matches text row width */}
        <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'stretch' }}>
          <div style={{ display: 'flex' }}>
            {chars.map((c, i) => {
              const y = charY(frame, i);
              // Vertical velocity (px/frame) -> y-axis blur
              const vy = Math.abs(charY(frame + 0.5, i) - charY(frame - 0.5, i)) * FONT * LINE_H * 0.01;
              const blur = Math.min(10, vy * 0.32);
              const id = `sts-vb-${i}`;
              return (
                <div
                  key={i}
                  style={{
                    // Mask box: 0.3em headroom for overshoot, bottom edge forms clip line
                    overflow: 'hidden',
                    height: FONT * 1.35,
                    display: 'flex',
                    alignItems: 'flex-end',
                  }}
                >
                  {blur > 0.3 && (
                    <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
                      <filter id={id} x="-10%" y="-50%" width="120%" height="200%">
                        <feGaussianBlur stdDeviation={`0 ${blur.toFixed(2)}`} />
                      </filter>
                    </svg>
                  )}
                  <span
                    style={{
                      display: 'inline-block',
                      fontFamily: PFONT.sans,
                      fontWeight: 700,
                      fontSize: FONT,
                      lineHeight: LINE_H,
                      color: G.ink1,
                      letterSpacing: '-0.015em',
                      transform: `translateY(${y.toFixed(3)}%)`,
                      filter: blur > 0.3 ? `url(#${id})` : undefined,
                    }}
                  >
                    {c === ' ' ? '\u00a0' : c}
                  </span>
                </div>
              );
            })}
          </div>
          {/* Baseline hairline: width grows from 0 to full line width (accent color) */}
          <div style={{ marginTop: 12, height: 3, display: 'flex' }}>
            <div
              style={{
                height: 3,
                width: `${lineW.toFixed(3)}%`,
                borderRadius: 2,
                background: `linear-gradient(90deg, ${G.accent}, #7c83e6)`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
