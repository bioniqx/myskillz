// terminal-typewriter — Terminal typewriter trigger
// Dark terminal window centered, types "$ acme deploy --prod" char by char (2f/char, frame-deterministic
// substring), block cursor blinks in 12f square wave -> 12f hold after typing -> Enter key frame: 6f
// Easing.in(cubic) snap-push scale 1 -> 3.2 into command line (last 2f adds blur) hard-cutting to
// full-screen FakeDashboard A, settles 1.06 -> 1 over 4f. Settle phase true hold >=40f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';

const CMD = 'acme deploy --prod';

// Timeline (30fps, 145f total)
const T = {
  typeStart: 10,                       // Typing starts
  typeEnd: 10 + CMD.length * 2,        // 46: 18 characters x 2f
  enter: 58,                           // Enter pressed after 12f pause
  pushEnd: 64,                         // 6f snap-push ends, hard-cut frame
  settleEnd: 68,                       // Dashboard settles 1.06 -> 1 over 4f
  total: 145,                          // True hold 77f from f68
};

// Terminal window geometry
const TW = 1100;
const TH = 620;
const TL = (1920 - TW) / 2; // 410
const TT = (1080 - TH) / 2; // 230
const TITLEBAR = 52;
const PAD = 34;
// Command-line baseline (push focus): center of second text line below titlebar
const FOCUS_X = 960;
const FOCUS_Y = TT + TITLEBAR + PAD + 92; // ≈ 408

const TerminalWindow: React.FC<{ chars: number; cursorOn: boolean }> = ({ chars, cursorOn }) => (
  <div style={{
    width: TW, height: TH, background: '#1e1e1c', borderRadius: 14,
    boxShadow: '0 24px 64px rgba(0,0,0,0.35)',
    overflow: 'hidden', boxSizing: 'border-box',
  }}>
    {/* Titlebar: 3 window control dots (grayscale) */}
    <div style={{
      height: TITLEBAR, background: '#2a2a28', borderBottom: '1px solid #3a3a38',
      display: 'flex', alignItems: 'center', gap: 12, padding: '0 22px',
      boxSizing: 'border-box',
    }}>
      {['#6a6a68', '#8f8f8d', '#b5b5b3'].map((c, i) => (
        <div key={i} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />
      ))}
      <div style={{ margin: '0 auto', height: 10, width: 200, background: '#4a4a48', borderRadius: 5 }} />
      <div style={{ width: 72 }} />
    </div>
    {/* Content area */}
    <div style={{
      padding: PAD, fontFamily: 'Menlo, Consolas, monospace', fontSize: 40,
      color: '#d8d8d6', lineHeight: 1.5,
    }}>
      {/* Single-line historical output for context */}
      <div style={{ color: '#7a7a78', fontSize: 32, marginBottom: 18 }}>~/acme-app (main)</div>
      <div style={{ display: 'flex', alignItems: 'center', whiteSpace: 'pre' }}>
        <span style={{ color: '#9f9f9d' }}>{'$ '}</span>
        <span>{CMD.substring(0, chars)}</span>
        <span style={{
          display: 'inline-block', width: 24, height: 48, marginLeft: 4,
          background: '#d8d8d6', opacity: cursorOn ? 1 : 0,
        }} />
      </div>
    </div>
  </div>
);

export const TerminalTypewriter: React.FC = () => {
  const frame = useCurrentFrame();

  // Frame-deterministic typing: 2f/character
  const chars = Math.min(CMD.length, Math.max(0, Math.floor((frame - T.typeStart) / 2)));

  // Block cursor 12f square-wave blink (throughout)
  const cursorOn = frame % 12 < 6;

  // Enter snap push: entire scene scale 1 -> 3.2, 6f Easing.in(cubic), pushes toward command line
  const pushScale = interpolate(frame, [T.enter, T.pushEnd], [1, 3.2], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.in(Easing.cubic),
  });
  // Last 2f motion blur (f62–f64), unmounted after hard cut
  const pushBlur = interpolate(frame, [T.pushEnd - 2, T.pushEnd], [0, 10], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });

  // Hard cut: terminal unmounts and dashboard mounts from f64
  const cut = frame >= T.pushEnd;

  // Dashboard settle: 1.06 -> 1 stabilization over 4f
  const dashScale = interpolate(frame, [T.pushEnd, T.settleEnd], [1.06, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  return (
    <div style={{ width: 1920, height: 1080, background: G.bg, position: 'relative', overflow: 'hidden' }}>
      {!cut ? (
        <div style={{
          width: 1920, height: 1080,
          transform: `scale(${pushScale})`,
          transformOrigin: `${FOCUS_X}px ${FOCUS_Y}px`,
          ...(pushBlur > 0 ? { filter: `blur(${pushBlur}px)` } : {}),
        }}>
          <div style={{ position: 'absolute', left: TL, top: TT }}>
            <TerminalWindow chars={chars} cursorOn={cursorOn} />
          </div>
        </div>
      ) : (
        <div style={{
          width: 1920, height: 1080,
          transform: `scale(${dashScale})`,
          transformOrigin: '960px 540px',
        }}>
          <FakeDashboard variant="A" />
        </div>
      )}
    </div>
  );
};
