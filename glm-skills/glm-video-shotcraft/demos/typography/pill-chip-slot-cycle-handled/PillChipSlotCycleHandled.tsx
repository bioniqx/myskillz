// pill-chip-slot-cycle-handled — Chip Slot Cycle roller displacement (Remotion)
// White-base layout "Your [chip] Handled": vertical word cycle inside dark capsule (Shots->Camera->Sound->Renders,
// four workflow milestones handled by video-shotcraft: Shots / Camera / Sound / Renders),
// revealing gray ghost items above and below; capsule width animates smoothly with word length, naturally displacing flanking text.
// Design coordinates 480x270 (DesignStage proportional scale). Parameter values calibrated to this space.
import React, { useLayoutEffect, useRef, useState } from 'react';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';

export const PILL_CHIP_SLOT_CYCLE_HANDLED_DURATION = 150; // 5000ms @30fps

const WORDS = [
  { w: 'Shots', e: '🎬' },
  { w: 'Camera', e: '🎥' },
  { w: 'Sound', e: '🔊' },
  { w: 'Renders', e: '🎞️' },
];
const FONT = '700 22px -apple-system,system-ui,sans-serif';
// Fallback word width (pre-mount estimate: charCount * 13 + 74 padding);
// measured via offsetWidth in useLayoutEffect on first frame for pixel precision
const FALLBACK_WIDTHS = WORDS.map((o) => o.w.length * 13 + 74);

// Static flanking text ("Your" / "Handled")
const SIDE: React.CSSProperties = {
  color: '#15171d',
  fontWeight: 800,
  fontSize: 30,
  letterSpacing: -0.5,
  flex: 'none',
};

export const PillChipSlotCycleHandled: React.FC = () => {
  const t = useT();

  // Width measurement: measures offsetWidth per word (+74 capsule padding) using hidden span,
  // measured on first layout; fallback estimate prevents first-frame layout jump
  const measRef = useRef<HTMLDivElement>(null);
  const [widths, setWidths] = useState<number[]>(FALLBACK_WIDTHS);
  useLayoutEffect(() => {
    const spans = measRef.current?.children;
    if (!spans) return;
    setWidths(
      WORDS.map((o, i) => ((spans[i] as HTMLElement).offsetWidth || o.w.length * 13) + 74),
    );
  }, []);

  // Three transitions: 0.25 / 0.47 / 0.69, advancing one slot using 0.12 inOutCubic
  let pos = 0;
  for (const s0 of [0.25, 0.47, 0.69]) pos += seg(t, s0, s0 + 0.12, E.inOutCubic);
  const ci = Math.min(WORDS.length - 1, Math.floor(pos));
  const frac = pos - ci;
  // Capsule width interpolates between current and next word, smoothly displacing flanking text
  const chipW = lerp(frac, widths[ci], widths[Math.min(ci + 1, WORDS.length - 1)]);

  // Ghost items: preceding and following neighbors moving subtly with scroll, settling to baseline opacity
  const near = Math.round(pos);
  const roll = (pos - near) * 48 * 0.5;
  const settle = 1 - Math.min(1, Math.abs(pos - near) * 3);
  const ghost = (top: number): React.CSSProperties => ({
    position: 'absolute',
    left: '50%',
    top,
    font: FONT,
    color: '#15171d',
    whiteSpace: 'nowrap',
    transform: `translateX(-50%) translateY(${-roll}px)`,
    opacity: 0.13 * (0.4 + settle * 0.6),
  });

  return (
    <DesignStage bg="#fbfbfd">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontFamily: '-apple-system,system-ui,sans-serif',
        }}
      >
        {/* Hidden measurement span */} 
        <div ref={measRef} style={{ position: 'absolute', visibility: 'hidden' }}>
          {WORDS.map((o) => (
            <span key={o.w} style={{ whiteSpace: 'nowrap', font: FONT }}>
              {o.w}
            </span>
          ))}
        </div>
        <div style={SIDE}>Your</div>
        <div style={{ position: 'relative', flex: 'none' }}>
          {/* Dark capsule: overflow hidden housing 4-row word roller column */}
          <div
            style={{
              position: 'relative',
              height: 48,
              width: chipW,
              margin: '0 14px',
              flex: 'none',
              borderRadius: 99,
              background: '#1a1c24',
              boxShadow: '0 8px 24px rgba(20,22,40,.22)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: 0,
                transform: `translateY(${-pos * 48}px)`,
              }}
            >
              {WORDS.map(({ w, e }) => (
                <div
                  key={w}
                  style={{
                    height: 48,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 9,
                    paddingLeft: 18,
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span style={{ fontSize: 18 }}>{e}</span>
                  <span style={{ font: FONT, color: '#fff' }}>{w}</span>
                </div>
              ))}
            </div>
          </div>
          {/* Gray ghost items above and below capsule */}
          <div style={ghost(-38)}>{near > 0 ? WORDS[near - 1].w : ''}</div>
          <div style={ghost(58)}>{near < WORDS.length - 1 ? WORDS[near + 1].w : ''}</div>
        </div>
        <div style={SIDE}>Handled</div>
      </div>
    </DesignStage>
  );
};
