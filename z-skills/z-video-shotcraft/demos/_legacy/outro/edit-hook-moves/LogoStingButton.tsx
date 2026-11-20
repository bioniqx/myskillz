// logo-sting-button — Button ending outro sequence
// Previous shot fades to black -> black hold -> LOGO enters and holds (viewer assumes end) -> 12f UI closeup easter egg jump cut ->
// jump cuts back to black LOGO lockup freeze. Rhythm is everything: easter egg beat is blink-and-you-miss-it. True static hold >= 40f.
import React from 'react';
import { useCurrentFrame, interpolate, Easing } from 'remotion';
import { FakeDashboard } from '../../_fixtures/Fixtures';

// Timeline (30fps, 142f total)
const T = {
  shotAEnd: 24,     // 0–24f Previous shot (B), f14–24 darkens to black
  darkenStart: 14,
  blackEnd: 30,     // 24–30f Black hold 6f
  logoInEnd: 40,    // 30–40f LOGO entrance 10f
  holdEnd: 70,      // 40–70f Hold 30f (viewer assumes end)
  eggEnd: 82,       // 70–82f Easter egg jump cut 12f
  total: 142,       // 82–142f Black LOGO true static hold 60f
};

const LogoLockup: React.FC<{ opacity: number; scale: number }> = ({ opacity, scale }) => (
  <div style={{
    width: 1920, height: 1080, background: '#000',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  }}>
    <div style={{
      display: 'flex', alignItems: 'center', gap: 44,
      opacity, transform: `scale(${scale})`,
    }}>
      <div style={{
        width: 120, height: 120, borderRadius: 28, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* Small black mark inside square to avoid empty white box */}
        <div style={{ width: 44, height: 44, borderRadius: 12, background: '#000' }} />
      </div>
      <div style={{
        fontFamily: 'Helvetica, Arial, sans-serif', fontWeight: 800,
        fontSize: 90, color: '#fff', letterSpacing: 2,
      }}>
        ACME
      </div>
    </div>
  </div>
);

export const LogoStingButton: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Phase 1: Previous shot (FakeDashboard B) darkens to black ——
  if (frame < T.shotAEnd) {
    const dark = interpolate(frame, [T.darkenStart, T.shotAEnd - 1], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.in(Easing.cubic),
    });
    return (
      <div style={{ width: 1920, height: 1080, background: '#000', position: 'relative', overflow: 'hidden' }}>
        <FakeDashboard variant="B" />
        <div style={{ position: 'absolute', inset: 0, background: '#000', opacity: dark }} />
      </div>
    );
  }

  // —— Phase 2: Black hold 6f ——
  if (frame < T.blackEnd) {
    return <div style={{ width: 1920, height: 1080, background: '#000' }} />;
  }

  // —— Phase 4: Easter egg jump cut 12f (variant A button region 2.4x crop + corner tick dot flashes 2f) ——
  if (frame >= T.holdEnd && frame < T.eggEnd) {
    const egg = frame - T.holdEnd; // 0..11
    // Tick dot: lights for 2f at frame 4–5, like a blink
    const tickOn = egg >= 4 && egg < 6;
    return (
      <div style={{ width: 1920, height: 1080, background: '#ececea', position: 'relative', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', inset: 0,
          // 2.4x zoom: translate first card bottom "button row" (avatar circle + text bar) to screen center
          // Original coords (839, 531) (col 2 card bottom avatar + text) -> screen center (960, 540)
          // Cropping col 2 card pushes dark sidebar completely off-screen for a cleaner closeup
          transform: 'translate(-1054px, -734px) scale(2.4)', transformOrigin: '0 0',
        }}>
          <FakeDashboard variant="A" />
        </div>
        {tickOn && (
          <div style={{
            position: 'absolute', right: 90, bottom: 80,
            width: 56, height: 56, borderRadius: 28, background: '#2f2f2f',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{ width: 20, height: 20, borderRadius: 10, background: '#fff' }} />
          </div>
        )}
      </div>
    );
  }

  // —— Phase 3 + Phase 5: Black LOGO (entrance -> hold -> post-egg freeze ending, true static hold) ——
  const opacity = interpolate(frame, [T.blackEnd, T.logoInEnd], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const scale = interpolate(frame, [T.blackEnd, T.logoInEnd], [0.96, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  return <LogoLockup opacity={opacity} scale={scale} />;
};
