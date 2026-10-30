// icon-flip-bloom-logo — Icon flips on Y-axis flattening into vertical line, blooming into brand mark + wordmark sweep
// Source: perplexity-promo 88–91.5s. Smiley laptop icon anticipatory wobble ->
// flips on Y-axis flattening into a vertical line (motion blur / trailing ghosts) -> blooms past thinnest point into mark (petals opening) ->
// wordmark letters settle scaling down from large to small (blurred when large, sharp when settled, coupled scale + blur).
// Polish: soft-light bright field + grounded contact shadow (adapts with wobble and flip).
// Brand cycle: final logo is video-shotcraft mark — past the thinnest point, mark expands from vertical line using overshoot spring
// (viewfinder frame), followed by amber diagonal cut sliding in at 45° (replacing the original second beat of blooming petals);
// video-shotcraft wordmark in lowercase brand font, letters settling large-to-small; only accent color is the mark's amber cut.
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing, spring, useVideoConfig } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, ramp } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const ICON_FLIP_BLOOM_LOGO_DURATION = 130;
const MARK = 300; // Mark size (viewBox 128 -> visible viewfinder frame approx 244×225)

const SmileLaptop: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 40 40">
    <rect x={7} y={6} width={26} height={20} rx={3.5} fill="#fff" stroke={G.ink} strokeWidth={3} />
    <circle cx={15.5} cy={13.5} r={2} fill={G.ink} />
    <circle cx={24.5} cy={13.5} r={2} fill={G.ink} />
    <path d="M14 18.5 Q20 23.5 26 18.5" stroke={G.ink} strokeWidth={2.8} fill="none" strokeLinecap="round" />
    <path d="M3.5 31.5 L36.5 31.5" stroke={G.ink} strokeWidth={3.6} strokeLinecap="round" />
  </svg>
);

const WORD = BRAND.name;

export const IconFlipBloomLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ---- Timeline ----
  // 0–10: Icon entrance (fade-in with slight spring)
  // 12–34: Anticipation tilt wobble
  // 34–46: Y-axis flip flattens to vertical line (scaleX -> 0.04, with trails)
  // 46–62: Past thinnest point mark expands (bloom 0->1 with overshoot); amber cut slides in from 53
  // 64–100: Mark shifts left + wordmark directional blur sweep
  const FLIP_START = 34;
  const FLIP_MID = 46;
  const BLOOM_END = 62;
  const WORD_START = 66;

  // Entrance
  const inT = spring({ frame, fps, config: { damping: 13, stiffness: 140, mass: 0.8 } });

  // Anticipation: two tilt wobbles with increasing amplitude (-10° / +14°), leaning back to build tension
  const wobble =
    interpolate(frame, [12, 18, 24, 30, FLIP_START], [0, -12, 14, -18, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.inOut(Easing.sin),
    });

  // First half of flip: scaleX 1 -> 0.04 (accelerated entry), accompanied by ghost trails
  const flipIn = interpolate(frame, [FLIP_START, FLIP_MID], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  const iconScaleX = interpolate(flipIn, [0, 1], [1, 0.04]);

  // Bloom: spring overshoot
  const bloomSpring = spring({
    frame: frame - FLIP_MID,
    fps,
    config: { damping: 11, stiffness: 130, mass: 0.9 },
  });
  const bloom = frame < FLIP_MID ? 0 : bloomSpring;
  // Mark expands from line width: scaleX 0.04 -> 1
  const markScaleX = interpolate(bloom, [0, 1], [0.04, 1]);
  // Second beat: amber cut slides in along its 45° angle (starts after viewfinder expands past halfway)
  const cut = frame < FLIP_MID + 7 ? 0 : spring({ frame: frame - FLIP_MID - 7, fps, config: { damping: 16, stiffness: 170 } });

  // Mark shifts left to make room (as wordmark enters)
  const shift = interpolate(frame, [WORD_START - 2, WORD_START + 16], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const markX = interpolate(shift, [0, 1], [0, -471]); // Coupled with wordmark start +187: visually centers lockup group

  const showIcon = frame < FLIP_MID;

  // Ghost trail frames (draws 2 ghost frames during flip)
  const ghosts = frame >= FLIP_START && frame < FLIP_MID ? [0.12, 0.24] : [];

  return (
    <AbsoluteFill style={{ background: G.bg, alignItems: 'center', justifyContent: 'center' }}>
      <Backdrop tone="light" light={{ x: 0.5, y: 0.36 }} accent={BRAND.amber} />
      {/* Contact soft shadow: offsets with wobble, narrows during flip, fades after bloom (flat logo needs no contact shadow) */}
      <div style={{
        position: 'absolute', left: 960 + markX - 150 * (showIcon ? iconScaleX : markScaleX) + wobble * 2.2, top: 540 + 150,
        width: 300 * (showIcon ? iconScaleX : markScaleX), height: 26, borderRadius: '50%',
        background: 'radial-gradient(ellipse at center, rgba(20,22,28,0.22) 0%, rgba(20,22,28,0) 70%)',
        opacity: inT * (1 - ramp(frame, FLIP_MID, 14, EASE.out)),
      }} />
      <div style={{ position: 'relative', width: 1920, height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {/* Icon / mark container */}
        <div
          style={{
            position: 'absolute',
            left: 960 + markX,
            top: 200,
            transform: 'translate(-50%, -50%)',
          }}
        >
          {showIcon ? (
            <>
              {ghosts.map((g, i) => {
                const gs = Math.min(1, iconScaleX + g);
                return (
                  <div
                    key={i}
                    style={{
                      position: 'absolute',
                      left: '50%',
                      top: '50%',
                      transform: `translate(-50%, -50%) scaleX(${gs})`,
                      opacity: 0.22 - i * 0.08,
                      filter: 'blur(6px)',
                    }}
                  >
                    <SmileLaptop size={340} />
                  </div>
                );
              })}
              <div
                style={{
                  transform: `scale(${inT}) rotate(${wobble}deg) scaleX(${iconScaleX})`,
                  transformOrigin: 'center 78%',
                  filter: flipIn > 0.3 ? `blur(${flipIn * 5}px)` : 'none',
                  opacity: inT,
                }}
              >
                <SmileLaptop size={340} />
              </div>
            </>
          ) : (
            <div style={{ transform: `scaleX(${markScaleX})` }}>
              <ShotcraftMark size={MARK} tone="light" cutProgress={cut} />
            </div>
          )}
        </div>

        {/* Wordmark: letters scale down from large to small — blurred when large, sharp when settled (scale + blur coupled), anchored at baseline */}
        <div
          style={{
            position: 'absolute',
            left: 960 + markX + 187,
            top: 200,
            transform: 'translateY(-50%)',
            display: 'flex',
            fontFamily: BRAND.font,
            fontWeight: 700,
            fontSize: 112,
            lineHeight: 1,
            color: BRAND.ink,
            letterSpacing: '0.03em',
            whiteSpace: 'nowrap',
          }}
        >
          {WORD.split('').map((ch, i) => {
            const st = WORD_START + i * 2.6; // Independent scale-down per letter, staggered by 2.6f for legibility
            const cT = ramp(frame, st, 12, EASE.snappy);
            const op = ramp(frame, st, 5, EASE.out);
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  opacity: op,
                  transform: `scale(${(1.9 - 0.9 * cT).toFixed(4)})`,
                  transformOrigin: '50% 78%',
                  filter: cT < 0.995 ? `blur(${((1 - cT) * 14).toFixed(2)}px)` : undefined,
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
