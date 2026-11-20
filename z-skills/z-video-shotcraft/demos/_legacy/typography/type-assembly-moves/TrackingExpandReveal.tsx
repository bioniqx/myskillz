// tracking-expand-reveal — Cinematic title letter-spacing entrance
// Title "BREATHE" (150px) begins with characters tightly overlapping (equivalent to letter-spacing -0.42em),
// expanding to 0.14em over 50 frames, synchronized with blur 10px -> 0, opacity 0.6 -> 1, scaleX 0.92 -> 1.
// Letter-spacing itself is kept constant (avoiding per-frame reflow jitter): container sets constant letterSpacing 0.14em for end state,
// while individual character spans interpolate translateX manually — char i start offset = (i - center) * gap delta 84px,
// all converging toward word center; offset depends strictly on gap delta, not glyph width, naturally centered.
// Keyframes: 0–50 expansion (Easing.out(poly(5))) + deblur/brighten -> 35–58 subtitle fades in (~70% through title expansion)
// -> 58–130 fully static (>=72f, filters completely removed).
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, TitleBlock } from '../../_fixtures/Fixtures';

const WORD = 'BREATHE';
const FS = 150; // Main word font size
// Start-to-end delta per character gap: (-0.42em) - (0.14em) = -0.56em = -84px @150px
const GAP_DELTA = -0.56 * FS;

export const TrackingExpandReveal: React.FC = () => {
  const frame = useCurrentFrame();
  // Expansion progress 0 -> 1 (0–50f, out poly(5))
  const p = interpolate(frame, [0, 50], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.poly(5)),
  });
  const blur = 10 * (1 - p);
  const op = interpolate(p, [0, 1], [0.6, 1]);
  const sx = interpolate(p, [0, 1], [0.92, 1]);
  // Subtitle: fades in starting at 70% of main word timeline (frame 35)
  const subOp = interpolate(frame, [35, 58], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });

  const N = WORD.length;
  const center = (N - 1) / 2;
  const settled = frame >= 50; // Remove all filters/transforms after expansion to guarantee identical frames

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 120, top: 96 }}>
        <TitleBlock text="TRACKING EXPAND REVEAL" size={54} />
      </div>

      {/* Main word: container letterSpacing stays constant at 0.14em (end state), chars only translateX */}
      <div
        style={{
          position: 'absolute',
          top: 430,
          left: 0,
          width: 1920,
          display: 'flex',
          justifyContent: 'center',
          transform: settled ? undefined : `scaleX(${sx})`,
          filter: settled ? undefined : `blur(${blur}px)`,
          opacity: settled ? 1 : op,
        }}
      >
        <div
          style={{
            fontFamily: 'Helvetica, Arial, sans-serif',
            fontWeight: 800,
            fontSize: FS,
            color: G.ink,
            letterSpacing: '0.14em',
            whiteSpace: 'pre',
            // letter-spacing is trailing-only; shift whole block left by half gap to restore visual centering
            marginLeft: 0.14 * FS * 0.5,
          }}
        >
          {WORD.split('').map((ch, i) => {
            const tx = (1 - p) * (i - center) * GAP_DELTA;
            return (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  transform: settled ? undefined : `translateX(${tx}px)`,
                }}
              >
                {ch}
              </span>
            );
          })}
        </div>
      </div>

      {/* Subtitle: fades in at 70% mark of main word expansion */}
      <div
        style={{
          position: 'absolute',
          top: 630,
          left: 0,
          width: 1920,
          textAlign: 'center',
          fontFamily: 'Helvetica, Arial, sans-serif',
          fontWeight: 500,
          fontSize: 34,
          color: G.mid,
          letterSpacing: '0.32em',
          opacity: frame >= 58 ? 1 : subOp,
        }}
      >
        A CINEMATIC TITLE ENTRANCE
      </div>
    </div>
  );
};
