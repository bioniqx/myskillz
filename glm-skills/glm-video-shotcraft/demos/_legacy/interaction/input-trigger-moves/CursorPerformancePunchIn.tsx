// cursor-performance-punch-in — Anthropomorphic cursor performance + click-following punch-in
// Scaled-up cursor slides in along a Bezier curve from bottom-left (wrist flick overshoot at tail) -> hover button subtle glow response ->
// Click: button depresses + ripple expands + entire canvas punches in 1->1.4 centered on click point -> hold -> ease back.
// "Round-trip" punch-in distinguishes from crash-zoom. Ending true rest ≥35f. Entirely grayscale.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard, G } from '../../_fixtures/Fixtures';

// Timeline (30fps, 150f total)
const T = {
  cursorInEnd: 30, // 0–30f cursor Bezier slide-in (f24 overshoot peak, f24–30 hook back & settle)
  click: 40,       // 30–40f hover response 10f; f40 click
  punchEnd: 52,    // 40–52f punch-in 1->1.4 (out-cubic)
  holdEnd: 72,     // 52–72f hold 20f
  backEnd: 90,     // 72–90f ease back to 1.0 (inOut-cubic)
  total: 150,      // 90–150f true rest 60f
};

// Button and click point (canvas coordinates)
const BTN = { x: 1560, y: 130, w: 200, h: 64 };
const CLICK = { x: 1665, y: 168 };

// Cursor Bezier curve: enters from bottom-left, dips then swoops up with character
const P0 = { x: 180, y: 1000 };
const P1 = { x: 820, y: 1075 };
const P2 = { x: 1795, y: 560 };
const P3 = { x: CLICK.x, y: CLICK.y };
const bez = (t: number) => {
  const u = 1 - t;
  return {
    x: u * u * u * P0.x + 3 * u * u * t * P1.x + 3 * u * t * t * P2.x + t * t * t * P3.x,
    y: u * u * u * P0.y + 3 * u * u * t * P1.y + 3 * u * t * t * P2.y + t * t * t * P3.y,
  };
};

const Cursor: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <svg
    width={48}
    height={48}
    viewBox="0 0 28 28"
    style={{
      position: 'absolute',
      left: x - 3.4,
      top: y - 1.7,
      filter: 'drop-shadow(0 4px 7px rgba(0,0,0,0.4))',
    }}
  >
    <path
      d="M2 1 L2 23 L8 17.5 L11.5 25 L15.5 23.2 L12 15.8 L20 15 Z"
      fill="#ffffff"
      stroke="#2f2f2f"
      strokeWidth={1.6}
      strokeLinejoin="round"
    />
  </svg>
);

export const CursorPerformancePunchIn: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Cursor: path parameter t, overshooting to 1.05 at f24 (flicks past button along tangent), hooking back to 1.0 across f24–30 ——
  const t =
    frame < 24
      ? interpolate(frame, [0, 24], [0, 1.05], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.out(Easing.cubic),
        })
      : interpolate(frame, [24, T.cursorInEnd], [1.05, 1], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.quad),
        });
  const cur = bez(t);
  // On click frame cursor dips 3px with button (f40–42 down, f42–46 return)
  const dip = interpolate(frame, [T.click, T.click + 2, T.click + 6], [0, 3, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // —— Hover response: f30–34 button brightens (visible contrast on dark) + subtle scale-up ——
  const lift = interpolate(frame, [T.cursorInEnd, T.cursorInEnd + 4], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const c = Math.round(47 + 38 * lift); // #2f2f2f -> #555553 approx
  const hoverScale = 1 + 0.05 * lift;

  // —— Click depression: f40–42 scale->0.94, f42–46 rebound ——
  const press = interpolate(frame, [T.click, T.click + 2, T.click + 6], [1, 0.94, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // —— Punch-in round-trip: 40–52f 1->1.4 (out-cubic); 72–90f 1.4->1 (inOut) ——
  const zoom =
    frame < T.holdEnd
      ? interpolate(frame, [T.click, T.punchEnd], [1, 1.4], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.out(Easing.cubic),
        })
      : interpolate(frame, [T.holdEnd, T.backEnd], [1.4, 1], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.cubic),
        });

  // —— Ripple: expansion out-cubic (40–62f, diameter 60->380), fade linear (40–66f) frame timing decoupled ——
  const rippleAlive = frame >= T.click && frame < T.click + 26;
  const rippleD = interpolate(frame, [T.click, T.click + 22], [60, 380], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const rippleOp = interpolate(frame, [T.click, T.click + 26], [0.9, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const rippleBw = interpolate(frame, [T.click, T.click + 22], [9, 3], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
      {/* Entire canvas punches in centered on click point */}
      <div style={{
        position: 'absolute', inset: 0,
        transform: `scale(${zoom})`,
        transformOrigin: `${CLICK.x}px ${CLICK.y}px`,
      }}>
        <FakeDashboard variant="A" />

        {/* Custom Deploy button in top right (overlaid on page) */}
        <div style={{
          position: 'absolute', left: BTN.x, top: BTN.y, width: BTN.w, height: BTN.h,
          borderRadius: 14, background: `rgb(${c},${c},${c - 2})`,
          boxShadow: '0 6px 18px rgba(0,0,0,0.28)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transform: `scale(${hoverScale * press})`,
          fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 700,
          fontSize: 27, color: '#ffffff', letterSpacing: 0.5,
        }}>
          Deploy
        </div>

        {/* Ripple ring: conditionally mounted, unmounted after f66 */}
        {rippleAlive && (
          <div style={{
            position: 'absolute',
            left: CLICK.x - rippleD / 2, top: CLICK.y - rippleD / 2,
            width: rippleD, height: rippleD, borderRadius: '50%',
            border: `${rippleBw}px solid ${G.ink}`,
            opacity: rippleOp,
          }} />
        )}

        {/* Enlarged cursor (punches in with canvas, pinned to button) */}
        <Cursor x={cur.x} y={cur.y + dip} />
      </div>
    </div>
  );
};
