// Odometer digit roll big banner (odometer-digit-roll) — Audio-visual hook / Vercel Ship metrics section.
// Fullscreen giant "99.98%" (190px fw800 tabular-nums); four digits each form a vertical 0–9
// strip (overflow:hidden digit box), spinning rapidly before settling digit-by-digit: digit i starts decelerating
// at 20+i*7f (Easing.out(cubic)), overshooting by half a row then bouncing back to lock over 6f. During roll, each digit layers 2 offset ghost
// copies (translateY ±rowHeight*0.5, opacity 0.25/0.12), velocity-gated and unmounted upon settle.
// Decimal point and % do not roll, remaining static throughout.
// Keyframes: 0–20 all 4 digits roll full speed (0.85 row/frame) -> 20/27/34/41 digits decelerate in sequence (each 16f
// deceleration + 6f rebound, locking at 42/49/56/63) -> 63–71 overall darken pulse (ink->#000->ink,
// amplified with 1.035 micro-scale) -> 66–84 bottom label bar fades in -> 84–150 completely static (66f >= 45f).
import React from 'react';
import { useCurrentFrame, interpolate, interpolateColors, Easing } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

const ROW = 210; // Digit row height (overflow box height)
const DW = 126; // Digit box width
const FS = 190; // Font size
const SPIN = 0.85; // High-speed roll rate: rows/frame
const DIGITS = [9, 9, 9, 8]; // Target digits (the 4 rolling digits in "99.98")

// Strip position for digit i (unit: rows, continuous value). Pure frame function, naturally deterministic.
const posAt = (f: number, i: number): number => {
  const d = DIGITS[i];
  const s = 20 + i * 7; // Deceleration start frame
  const p0 = SPIN * s;
  // After traveling at least 6 more rows, land on nearest integer position where digit % 10 == d
  const T = Math.ceil((p0 + 6 - d) / 10) * 10 + d;
  if (f < s) return SPIN * Math.max(f, 0);
  if (f < s + 16)
    return interpolate(f, [s, s + 16], [p0, T + 0.5], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
  if (f < s + 22)
    return interpolate(f, [s + 16, s + 22], [T + 0.5, T], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    });
  return T;
};

// A single vertical 0–9 column strip (2 cycles of 20 cells to accommodate overshoot boundary crossing)
const Strip: React.FC<{ pos: number; color: string; opacity?: number; dy?: number }> = ({
  pos,
  color,
  opacity = 1,
  dy = 0,
}) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      top: 0,
      width: DW,
      transform: `translateY(${-(pos % 10) * ROW + dy}px)`,
      opacity,
    }}
  >
    {Array.from({ length: 20 }).map((_, k) => (
      <div
        key={k}
        style={{
          width: DW,
          height: ROW,
          lineHeight: `${ROW}px`,
          textAlign: 'center',
          fontSize: FS,
          fontWeight: 800,
          fontVariantNumeric: 'tabular-nums',
          color,
        }}
      >
        {k % 10}
      </div>
    ))}
  </div>
);

// Single digit box: main strip + 2 offset ghost trails during spin (velocity-gated, unmounted when settled)
const DigitReel: React.FC<{ frame: number; i: number; color: string }> = ({ frame, i, color }) => {
  const pos = posAt(frame, i);
  const speed = Math.abs(pos - posAt(frame - 1, i));
  const gate = interpolate(speed, [0.06, 0.5], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{ position: 'relative', width: DW, height: ROW, overflow: 'hidden' }}>
      {gate > 0.001 && (
        <>
          <Strip pos={pos} color={color} opacity={0.25 * gate} dy={ROW * 0.5} />
          <Strip pos={pos} color={color} opacity={0.12 * gate} dy={-ROW * 0.5} />
        </>
      )}
      <Strip pos={pos} color={color} />
    </div>
  );
};

// Static non-rolling glyphs (decimal point / %), persistent throughout
const StaticGlyph: React.FC<{ ch: string; color: string; w?: number }> = ({ ch, color, w }) => (
  <div
    style={{
      width: w,
      height: ROW,
      lineHeight: `${ROW}px`,
      textAlign: 'center',
      fontSize: FS,
      fontWeight: 800,
      fontVariantNumeric: 'tabular-nums',
      color,
    }}
  >
    {ch}
  </div>
);

export const OdometerDigitRoll: React.FC = () => {
  const frame = useCurrentFrame();
  // All digits locked at 63f: overall darken pulse ink->#000->ink (8f), reinforced with micro-scale for perceptibility
  const inkNow = interpolateColors(frame, [63, 67, 71], [G.ink, '#000000', G.ink]);
  const pulseScale = interpolate(frame, [63, 67, 71], [1, 1.035, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.quad),
  });
  const labelOp = interpolate(frame, [66, 84], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <TitleBlock text="ODOMETER DIGIT ROLL" size={54} />
      </div>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 400,
          width: 1920,
          display: 'flex',
          justifyContent: 'center',
          fontFamily: 'Helvetica, Arial, sans-serif',
          transform: `scale(${pulseScale})`,
          transformOrigin: '960px 105px',
        }}
      >
        <DigitReel frame={frame} i={0} color={inkNow} />
        <DigitReel frame={frame} i={1} color={inkNow} />
        <StaticGlyph ch="." color={inkNow} w={70} />
        <DigitReel frame={frame} i={2} color={inkNow} />
        <DigitReel frame={frame} i={3} color={inkNow} />
        <StaticGlyph ch="%" color={inkNow} />
      </div>
      {/* Bottom label bar: fades in after all digits lock */}
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 680,
          width: 1920,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 16,
          opacity: labelOp,
        }}
      >
        <div style={{ width: 520, height: 22, background: G.bar, borderRadius: 11 }} />
        <div style={{ width: 320, height: 14, background: G.line, borderRadius: 7 }} />
      </div>
    </div>
  );
};
