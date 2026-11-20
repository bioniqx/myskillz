// scramble — Scramble Decode text reveal (ported from motion-lab final to native Remotion)
// Each character rapidly cycles through random glyphs (seed-driven, reproducible) before locking into the real character from left to right;
// flashes a highlight glow at the moment of locking. Imparts a hacker/decryption feel distinct from standard typewriter animations.
// Design canvas 480×270 (DesignStage proportional scale); parameter values calibrated in this coordinate space.
import React from 'react';
import { DesignStage, rand, seg, useT } from '../../_fixtures/Motion';

export const SCRAMBLE_DURATION = 96; // 3200ms @30fps

const TEXT = 'TEMPLATE MOTION DEMO';
const POOL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&*+=<>/\\';
const CHARS = [...TEXT];

export const Scramble: React.FC = () => {
  const t = useT();
  const frame = Math.floor(t * 96);
  return (
    <DesignStage bg="#07080c">
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#07080c',
          fontFamily: '"SF Mono",Menlo,monospace',
          fontSize: 34,
          letterSpacing: 2,
        }}
      >
        {CHARS.map((ch, i) => {
          let content: string = ch;
          let color = '#3d4560';
          let textShadow = 'none';
          if (ch !== ' ') {
            // Lock-in timing: left-to-right base stagger + seed perturbation
            const lockAt = 0.25 + (i / CHARS.length) * 0.6 + rand(i * 7) * 0.06;
            if (t < 0.06) {
              content = ' '; // Brief initial blank
            } else if (t < lockAt) {
              // High-speed scramble: swaps random character every 2 frames
              content = POOL[Math.floor(rand(i * 131 + Math.floor(frame / 2)) * POOL.length)];
            } else {
              // Locks to true character, flashing bright glow at lock moment before settling
              const flash = 1 - seg(t, lockAt, lockAt + 0.1);
              color = flash > 0.4 ? '#dff3ff' : '#e8eaf0';
              textShadow = `0 0 ${flash * 18}px rgba(120,200,255,${flash})`;
            }
          }
          return (
            <span
              key={i}
              style={{ minWidth: '0.62em', textAlign: 'center', color, textShadow }}
            >
              {content === ' ' ? ' ' : content}
            </span>
          );
        })}
      </div>
    </DesignStage>
  );
};
