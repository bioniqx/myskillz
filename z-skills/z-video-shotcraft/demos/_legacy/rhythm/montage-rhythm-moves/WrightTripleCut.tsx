// Edgar Wright triple-cut (wright-triple-cut) — Shaun of the Dead style rapid 3-cut montage:
// Frames 0–24 wide shot hold (FakeDashboard A); followed by three 10f close-up hard cuts,
// each with 4f hold, 3f action, 3f settle: (1) 25–34 cursor presses button (dot shrinks + button darkens)
// (2) 35–44 toggle flips left-to-right (knob slides 3f + track G.mid -> G.ink) (3) 45–54 large digit rotateX flips 0 -> 1;
// Frame 55 whip pans back to wide: 6f whip translateX slide-in, high-speed phase uses 3 offset ghost layers for motion blur,
// top-center card brightens with glow + large "1" flags result; frame ~68 to 130 fully settled (true hold >=60f).
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard, G } from '../../_fixtures/Fixtures';

const HOLD_END = 25; // Wide shot hold ends
const C1 = 25; // Close-up 1: cursor press
const C2 = 35; // Close-up 2: toggle switch
const C3 = 45; // Close-up 3: digit flip
const WHIP = 55; // Whip back to wide shot

// Unified close-up stage: G.panel base + centered large white card, subject centered at consistent scale
const CloseupStage: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{ width: 1920, height: 1080, background: G.panel, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <div style={{
      width: 1400, height: 800, background: G.card, border: `4px solid ${G.border}`,
      borderRadius: 28, boxShadow: '0 6px 24px rgba(0,0,0,0.08)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {children}
    </div>
  </div>
);

// Result card geometry (top-center cell of 3x2 grid): sidebar 220 + padding 36, col width 524, row height 454
const RESULT = { left: 808, top: 108, w: 524, h: 454 };

export const WrightTripleCut: React.FC = () => {
  const f = useCurrentFrame();

  // ===== Frames 0–24: wide shot hold =====
  if (f < HOLD_END) {
    return <FakeDashboard variant="A" />;
  }

  // ===== Close-up 1 (25–34): cursor hovers then presses, button darkens =====
  if (f < C2) {
    const t = f - C1; // Local 0–9; action window 4–6
    const p = interpolate(t, [4, 7], [0, 1], {
      easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    const cursorScale = 1 - 0.3 * p; // 1 -> 0.7 shrink
    const btnBg = p < 0.5 ? G.bar : '#5c5c5a'; // Darkens on press
    const btnY = 8 * p; // Button pressed down by 8px
    return (
      <CloseupStage>
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            width: 620, height: 190, borderRadius: 40, background: btnBg,
            border: `5px solid ${G.mid}`, boxSizing: 'border-box',
            transform: `translateY(${btnY}px)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14,
          }}>
            <div style={{ width: 260, height: 30, borderRadius: 15, background: p < 0.5 ? G.card : G.line }} />
          </div>
          {/* Circular cursor dot: hovers at button center, shrinks on press */}
          <div style={{
            position: 'absolute', left: '50%', top: '50%',
            width: 96, height: 96, marginLeft: -48, marginTop: -48 + btnY,
            borderRadius: 48, background: G.ink, border: '8px solid #ffffff',
            boxSizing: 'border-box', transform: `scale(${cursorScale})`,
            boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
          }} />
        </div>
      </CloseupStage>
    );
  }

  // ===== Close-up 2 (35–44): toggle switch flips left to right =====
  if (f < C3) {
    const t = f - C2;
    const p = interpolate(t, [4, 7], [0, 1], {
      easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    const trackW = 560; const trackH = 240; const knob = 192; const pad = 24;
    const knobX = pad + p * (trackW - knob - pad * 2); // Left -> right
    const trackBg = p < 0.5 ? G.mid : G.ink;
    return (
      <CloseupStage>
        <div style={{
          position: 'relative', width: trackW, height: trackH, borderRadius: trackH / 2,
          background: trackBg, boxSizing: 'border-box',
        }}>
          <div style={{
            position: 'absolute', top: pad, left: knobX,
            width: knob, height: knob, borderRadius: knob / 2, background: G.card,
            boxShadow: '0 6px 18px rgba(0,0,0,0.35)',
          }} />
        </div>
      </CloseupStage>
    );
  }

  // ===== Close-up 3 (45–54): large digit flips 0 -> 1 (rotateX) =====
  if (f < WHIP) {
    const t = f - C3;
    const p = interpolate(t, [4, 7], [0, 1], {
      easing: Easing.inOut(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    });
    const showOne = p >= 0.5;
    const angle = showOne ? (1 - p) * 2 * 90 : -p * 2 * 90; // 0 -> -90 fold away, 90 -> 0 fold in
    const digit = showOne ? '1' : '0';
    return (
      <CloseupStage>
        <div style={{ perspective: 1200 }}>
          <div style={{
            width: 440, height: 560, borderRadius: 32, background: G.ink,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transform: `rotateX(${angle}deg)`, backfaceVisibility: 'hidden',
            boxShadow: '0 8px 28px rgba(0,0,0,0.25)',
          }}>
            <div style={{
              fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 800,
              fontSize: 420, color: '#ffffff', lineHeight: 1,
            }}>
              {digit}
            </div>
          </div>
        </div>
      </CloseupStage>
    );
  }

  // ===== Frame 55 onward: whip back to wide shot + result card lights up =====
  const t = f - WHIP;
  // Whip: 6f slides in at high speed from 900px right, poly(5) out sharp deceleration; t>=6 stays 0 (true hold)
  const whipX = t >= 6 ? 0 : interpolate(t, [0, 6], [900, 0], {
    easing: Easing.out(Easing.poly(5)), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const speeding = t < 4; // High-speed phase: 3 offset ghost layers simulate motion blur

  // Result card: glow ramps 57–84 then stays constant (true hold from frame 84); pops 57–64 then stays 1
  const glow = interpolate(f, [57, 84], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const pop = f >= 64 ? 1 : interpolate(f, [57, 60, 64], [1, 1.07, 1], {
    easing: Easing.out(Easing.cubic), extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  const dash = (x: number, opacity: number, key: string) => (
    <div key={key} style={{ position: 'absolute', left: 0, top: 0, transform: `translateX(${x}px)`, opacity }}>
      <FakeDashboard variant="A" />
    </div>
  );

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, overflow: 'hidden', position: 'relative' }}>
      {speeding && dash(whipX + 220, 0.18, 'echo2')}
      {speeding && dash(whipX + 110, 0.35, 'echo1')}
      {dash(whipX, 1, 'main')}
      {/* Result card glow highlight */}
      <div style={{
        position: 'absolute',
        left: RESULT.left, top: RESULT.top, width: RESULT.w, height: RESULT.h,
        transform: `translateX(${whipX}px) scale(${pop})`,
        borderRadius: 14, boxSizing: 'border-box',
        background: `rgba(255,255,255,${0.72 * glow})`,
        border: `5px solid rgba(47,47,47,${glow})`,
        boxShadow: `0 0 ${70 * glow}px rgba(255,255,255,${0.95 * glow}), 0 0 ${26 * glow}px rgba(47,47,47,${0.28 * glow})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        opacity: glow,
      }}>
        <div style={{
          fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 800,
          fontSize: 260, color: G.ink, lineHeight: 1,
        }}>
          1
        </div>
      </div>
    </div>
  );
};
