// list-stack-press — List cards fly up and stack from bottom one by one, each landing presses and rebounds the stack, counter ticks in sync
// "Stacking has weight": As each new card lands, the settled stack is pressed down then rebounds — physical feedback conveys
// "these are tangibly accumulated items". Reference implementation extracted from template ScenePapers:
// Anticipation beat (counter illuminates and micro-scales 4–6f before first card, drawing eyes to stack area); 5 cards in 12f equidistant tempo
// rise 600px from bottom (alternating ±2° tilt settling flat + scale 1.06→1); entire stack presses down 6px when subsequent card arrives,
// rebounding over 8f (stackPress pulse — the crucial touch of "weight"); highlight bar sprouts 2–4f after landing;
// trailing glaze sweep passes over the entire stack; screen-space DigitRoll counter rolls one digit per card.
// Orthographic perspective (stack/list shots require orthographic view, Q6), camera tracks stack downwards.
// Polish layer (revision):
// · Camera changed from 5 segmented keyframes (each with own ease-in/out, velocity hitting zero at keyframes) to a continuous curve fed per-frame to PageCam2D
// · Flying cards gain vertical motion blur proportional to velocity; shadows revised to two tiers varying with elevation (contact shadow + ambient shadow)
// · Highlight bar precisely aligned to the measured "project-related" title line, blended with multiply beneath text (highlighter), no longer covering copy
// · Glaze sweep repositioned to trigger after the last card settles, clipped within each card's rounded corners (Q4)
// · Counter digits explicitly set to system sans-serif + tabular-nums (previously fell back to browser default serif), with vertical motion blur during roll
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam2D, CamKey2D } from '../../_fixtures/PageCam2D';
import { FONT, SpeedBlur, bezier, softShadow, velocity } from '../../_fixtures/Polish';
import layout from '../../_textures/live-layout.json';

export const LIST_STACK_PRESS_DURATION = 88; // 18–88f falls within shot offset 0

const cards = layout.papers.cards;
const PAGE_H = layout.papers.pageH;
const MONO = FONT.mono;
const AMBER = 'oklch(52% 0.115 65)';
const FILES = ['paper1.png', 'paper2.png', 'paper3.png', 'paper4.png', 'paper5.png'];
// Measured from screenshot: project name line in each card (page px, card-local coordinates) — highlight bar covers only this line
const HL_TOP = 156, HL_H = 20, HL_LEFT = 16;
const HL_W = [187, 244, 247, 240, 191];

const CUES = [6, 18, 30, 42, 54]; // Reserve 6f before first card for counter anticipation beat
const DUR = 22;
const FLY_EASE = Easing.bezier(0.45, 0.05, 0.25, 1.12);
const TILTS = [2, -2, 2, -2, 2];

// Anticipation beat: counter lights up + micro-scales (0.96→1) ahead of first card, drawing eye to stack area (once per sequence)
const ANTICIPATE_START = 0;
const ANTICIPATE_END = 6;

// Camera: Continuous curve (page header closeup 1.35 → full stack panorama 0.86), tracking stack vertically;
// Vertical position leads, zoom settles slightly later, resting after 82f for glaze and counter settlement
const CAM_END = 82;
const CY_EASE = bezier(0.42, 0, 0.2, 1);
const Z_EASE = bezier(0.3, 0, 0.18, 1);
const camAt = (f: number) => {
  const u = Math.min(1, Math.max(0, f / CAM_END));
  return { cx: 960, cy: 270 + (815 - 270) * CY_EASE(u), zoom: 1.35 + (0.86 - 1.35) * Z_EASE(u) };
};
// Per-frame keyframes + linear interpolation = passes continuous curve intact to PageCam2D (its segmented easing pauses at keyframes)
const CAM_KEYS: CamKey2D[] = Array.from({ length: LIST_STACK_PRESS_DURATION }, (_, f) => ({ frame: f, ...camAt(f) }));
const LINEAR = (t: number) => t;

// odometer digit column — continuous odometer without re-mounting: `pos` is continuous position on digit tape
// (0→5); each card landing advances pos by one digit. Single tick roll must be shorter than 12f card interval,
// and the last digit must settle before shot ends — re-mounting key to roll 22f from 0 violates both rules
// (previous digit never finishes, ending frame stalls at 4).
const DIGITS = '0123456789';
const ROLL_DUR = 8; // Single digit roll duration (frames), < 12f card interval
const ROLL_EASE = Easing.bezier(0.25, 0.8, 0.25, 1);
const rollAt = (frame: number) => {
  let pos = 0;
  for (const c of CUES) {
    pos += interpolate(frame, [c + DUR, c + DUR + ROLL_DUR], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ROLL_EASE,
    });
  }
  return pos;
};
const DigitRoll: React.FC<{ pos: number; lineH: number; color: string; blur: number }> = ({ pos, lineH, color, blur }) => (
  <span style={{ display: 'inline-flex', overflow: 'hidden', height: lineH, verticalAlign: 'bottom' }}>
    <span style={{ display: 'inline-block', height: lineH }}>
      <span style={{ display: 'block', transform: `translateY(${-pos * lineH}px)`, filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : undefined }}>
        {(DIGITS + DIGITS).split('').map((d, j) => (
          <span
            key={j}
            style={{
              display: 'block', fontFamily: FONT.sans, fontWeight: 500, fontSize: 104, letterSpacing: '-0.04em',
              lineHeight: `${lineH}px`, color, fontVariantNumeric: 'tabular-nums',
            }}
          >
            {d}
          </span>
        ))}
      </span>
    </span>
  </span>
);

// Flight progress (with overshoot) and vertical translation as pure functions of frame — motion blur requires sampling adjacent frames
const flyT = (i: number, f: number) =>
  interpolate(f, [CUES[i], CUES[i] + DUR], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: FLY_EASE });
const flyY = (i: number, f: number) => 600 * (1 - flyT(i, f));

export const ListStackPress: React.FC = () => {
  const frame = useCurrentFrame();
  // Continuous counter position: rolls forward 1 digit as each card lands (cue+DUR), settling in 8f.
  // Last card lands at f76, settles at f84, well before shot ends at f88.
  const rollPos = rollAt(frame);
  const rollV = Math.abs(velocity(rollAt, frame)); // digits/frame

  // Anticipation: counter 0→6f scales 0.96→1 and lights up, drawing eyes to stack area
  const antT = interpolate(frame, [ANTICIPATE_START, ANTICIPATE_END], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad),
  });
  const counterScale = 0.96 + 0.04 * antT;
  const counterOpacity = 0.3 + 0.7 * antT;

  // when a *later* card enters, the settled stack gets pressed down 6px then
  // springs back over ~8 frames
  const stackPress = (settledIndex: number) => {
    let press = 0;
    for (let j = settledIndex + 1; j < CUES.length; j++) {
      const cue = CUES[j];
      const p = interpolate(frame, [cue, cue + 4, cue + 8], [0, 6, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.sin),
      });
      press = Math.max(press, p);
    }
    return press;
  };

  // glaze: sweeps across entire stack from top-left after last card settles at f76 (page coordinates), visible only within card rounded corners
  const glazeX = interpolate(frame, [74, 87], [-500, 2300], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.45, 0, 0.35, 1),
  });
  const glazeVis = interpolate(frame, [74, 77, 84, 87], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#faf7f2' }}>
      <PageCam2D src="textures/live/papers-full.png" pageH={PAGE_H} keys={CAM_KEYS} ease={LINEAR}>
        {/* cover the printed cards so blank slots stack in */}
        {cards.map((c, i) => (
          <div
            key={`slot-${i}`}
            style={{
              position: 'absolute', left: c.x - 12, top: c.y - 10,
              width: c.w + 24, height: c.h + 20, background: '#faf7f2',
              opacity: frame >= CUES[i] + DUR - 2 ? 0 : 1,
            }}
          />
        ))}

        {cards.map((c, i) => {
          const cue = CUES[i];
          const t = flyT(i, frame);
          if (t <= 0) return null;
          const settled = t >= 0.999;
          const dy = flyY(i, frame) + (settled ? stackPress(i) : 0);
          const rot = TILTS[i] * (1 - t);
          const scale = 1.06 - 0.06 * t;
          // Elevation: flight phase maps 0–56px by remaining travel, settles at 3px (closer to ground when pressed)
          const elev = settled ? 3 - stackPress(i) * 0.3 : 3 + 53 * Math.min(1, Math.max(0, 1 - t));
          const vy = settled ? 0 : velocity((f) => flyY(i, f), frame);

          // Highlight bar: sprouts 3f after landing; last card has only 12f before cut, compressed to 5f grow + 4f fade
          const lastCard = i === CUES.length - 1;
          const hlStart = cue + DUR + (lastCard ? 2 : 3);
          const hlLen = lastCard ? 5 : 7;
          const hlGrow = interpolate(frame, [hlStart, hlStart + hlLen], [0, 1], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1),
          });
          const hlFade = interpolate(frame, [hlStart + hlLen, hlStart + hlLen + (lastCard ? 4 : 5)], [1, 0], {
            extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          });

          const card = (
            <div
              style={{
                position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h,
                transform: `translateY(${dy.toFixed(3)}px) rotate(${rot.toFixed(4)}deg) scale(${scale.toFixed(5)})`,
                transformOrigin: 'center center', borderRadius: 12,
                boxShadow: softShadow(elev, { color: '#3c2d1e', strength: 1.15 }),
              }}
            >
              <div style={{ position: 'absolute', inset: 0, borderRadius: 12, overflow: 'hidden' }}>
                <Img src={staticFile(`textures/live/${FILES[i]}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }} />
                {hlGrow > 0 && hlFade > 0 ? (
                  // Highlighter: multiply blended under text, preserving original font depth
                  <div
                    style={{
                      position: 'absolute', left: HL_LEFT, top: HL_TOP, height: HL_H,
                      width: HL_W[i] * hlGrow, borderRadius: 3,
                      background: 'oklch(90% 0.075 82)', mixBlendMode: 'multiply', opacity: 0.85 * hlFade,
                      pointerEvents: 'none',
                    }}
                  />
                ) : null}
                {/* glaze: diagonal soft light sweeping continuously across stack in page coordinates, clipped by card rounded corners */}
                {glazeVis > 0 && (
                  <div
                    style={{
                      position: 'absolute', top: -200, height: c.h + 400, left: glazeX - c.x - (c.y - 200) * 0.25, width: 360,
                      transform: 'rotate(14deg)', opacity: glazeVis * 0.55, mixBlendMode: 'soft-light',
                      background: 'linear-gradient(90deg, rgba(255,236,200,0), rgba(255,226,170,0.95) 45%, rgba(255,226,170,0.95) 55%, rgba(255,236,200,0))',
                      pointerEvents: 'none',
                    }}
                  />
                )}
              </div>
              {/* Top 1px highlight edge + hairline (screenshot cards have subtle borders, supplementing specular edge here) */}
              <div style={{ position: 'absolute', inset: 0, borderRadius: 12, boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.9)', pointerEvents: 'none' }} />
            </div>
          );
          return Math.abs(vy) > 1 ? (
            <SpeedBlur key={FILES[i]} vx={0} vy={vy} amount={0.22} max={14}>
              {card}
            </SpeedBlur>
          ) : (
            <React.Fragment key={FILES[i]}>{card}</React.Fragment>
          );
        })}
      </PageCam2D>

      {/* screen-space counter, top-right — lands one digit per card */}
      <div
        style={{
          position: 'absolute', top: 70, right: 96, textAlign: 'right',
          pointerEvents: 'none', opacity: counterOpacity,
          transform: `scale(${counterScale})`, transformOrigin: 'top right',
        }}
      >
        <div style={{ fontFamily: MONO, fontSize: 22, fontWeight: 500, letterSpacing: '0.18em', color: 'oklch(48% 0.008 82)', textTransform: 'uppercase' }}>
          Paper Radar
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
          <DigitRoll pos={rollPos} lineH={104 * 1.12} color={AMBER} blur={Math.min(6, rollV * 30)} />
        </div>
        <div style={{ height: 1, background: 'oklch(80% 0.01 82)', margin: '8px 0 10px auto', width: 220 }} />
        <div style={{ fontFamily: MONO, fontSize: 19, letterSpacing: '0.14em', color: 'oklch(52% 0.008 82)', textTransform: 'uppercase' }}>
          Of 31 Fetched Today
        </div>
      </div>
    </AbsoluteFill>
  );
};
