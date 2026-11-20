// line-unfold-panel — Line-to-panel reveal (Jarvis / FUI motif)
// Dark background. Two-beat entrance: 3px hairline expands rapidly outward from center (5f) ->
// unfolds vertically to full Card panel height (9f, out easing) -> content delayed fade-in.
// Static hold then reverse exit: collapses into line (7f) -> shrinks to dot -> turns off like an old CRT.
// f0–12 empty hold; entrance f12–34; hold panel to f78; exit f78–98; final static hold >= 42f (140f total).
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, Card } from '../../_fixtures/Fixtures';

const PANEL_W = 760;
const PANEL_H = 460;
const CX = 960;
const CY = 540;

// —— Entrance schedule ——
const T0 = 12; // Ignition start
const LINE_END = T0 + 5; // Line expansion complete f17
const UNFOLD_END = LINE_END + 9; // Panel vertical unfold complete f26
const CONTENT_END = UNFOLD_END + 8; // Content fade-in complete f34

// —— Exit schedule ——
const OUT0 = 78; // Collapse start
const COLLAPSE_END = OUT0 + 7; // Collapsed into line f85
const SHRINK_END = COLLAPSE_END + 6; // Line shrunk into dot f91
const OFF = SHRINK_END + 4; // Dot extinguished f95

const clamp = { extrapolateLeft: 'clamp' as const, extrapolateRight: 'clamp' as const };

export const LineUnfoldPanel: React.FC = () => {
  const frame = useCurrentFrame();

  // Entrance: scaleX (line expansion) fast attack and stop, stays 1 after entrance
  const inSX = interpolate(frame, [T0, LINE_END], [0.004, 1], {
    easing: Easing.out(Easing.poly(4)),
    ...clamp,
  });
  // Entrance: scaleY (vertical unfold), clamped at 3px during line phase
  const inSY = interpolate(frame, [LINE_END, UNFOLD_END], [3 / PANEL_H, 1], {
    easing: Easing.out(Easing.cubic),
    ...clamp,
  });
  // Content fade-in (begins after panel unfolds past halfway)
  const contentOp = interpolate(frame, [UNFOLD_END - 3, CONTENT_END], [0, 1], {
    easing: Easing.out(Easing.quad),
    ...clamp,
  });

  // Exit: collapse Y back to line, then shrink X back to dot
  const outSY = interpolate(frame, [OUT0, COLLAPSE_END], [1, 3 / PANEL_H], {
    easing: Easing.in(Easing.cubic),
    ...clamp,
  });
  const outSX = interpolate(frame, [COLLAPSE_END, SHRINK_END], [1, 0.004], {
    easing: Easing.in(Easing.poly(4)),
    ...clamp,
  });
  // Content retreats before collapse
  const contentOutOp = interpolate(frame, [OUT0 - 4, OUT0 + 2], [1, 0], clamp);

  const sx = frame < OUT0 ? inSX : outSX;
  const sy = frame < OUT0 ? inSY : outSY;

  // Final dot extinguish: opacity drops quickly. Conditional unmount when f >= OFF -> true static hold
  const dotOp = interpolate(frame, [SHRINK_END, OFF], [1, 0], {
    easing: Easing.in(Easing.quad),
    ...clamp,
  });

  const alive = frame >= T0 && frame < OFF;
  // Panel phase (sy large enough) shows card content; line/dot phase shows glowing beam
  const isPanel = sy > 0.15;

  return (
    <div style={{ width: 1920, height: 1080, background: '#1c1c1b', overflow: 'hidden', position: 'relative' }}>
      <div
        style={{
          position: 'absolute',
          top: 120,
          width: '100%',
          textAlign: 'center',
          fontFamily: 'Helvetica, Arial, sans-serif',
          fontWeight: 800,
          fontSize: 52,
          color: G.mid,
          letterSpacing: 2,
        }}
      >
        LINE UNFOLD PANEL
      </div>
      {alive && (
        <div
          style={{
            position: 'absolute',
            left: CX - PANEL_W / 2,
            top: CY - PANEL_H / 2,
            width: PANEL_W,
            height: PANEL_H,
            transform: `scaleX(${sx}) scaleY(${sy})`,
            transformOrigin: '50% 50%',
            opacity: dotOp,
          }}
        >
          {isPanel ? (
            <>
              <Card w={PANEL_W} h={PANEL_H} seed={3} style={{ border: `2px solid ${G.mid}`, boxShadow: '0 0 40px rgba(255,255,255,0.18)' }} />
              {/* Content layer individual opacity: dark overlay simulates "unlit content" */}
              <div
                style={{
                  position: 'absolute',
                  inset: 2,
                  borderRadius: 12,
                  background: G.card,
                  opacity: 1 - Math.min(contentOp, contentOutOp),
                }}
              />
            </>
          ) : (
            // Line/dot phase: white glowing bar fills container (compressed to line by scale)
            <div style={{ width: '100%', height: '100%', background: '#ffffff', boxShadow: '0 0 60px rgba(255,255,255,0.9)', borderRadius: 2 }} />
          )}
        </div>
      )}
    </div>
  );
};
