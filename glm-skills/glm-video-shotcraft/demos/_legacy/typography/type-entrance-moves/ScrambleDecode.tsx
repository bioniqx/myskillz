// scramble-decode — Hacker-terminal text entrance
// Title "DECODE SPEED" has each character rapidly cycling through random letters/numbers (every 2f, hashed from seed),
// locking in sequence from left to right: character i locks to target glyph at frame 20+i*6; on lock, char flashes inverted
// (G.ink block with white text for 2f) then settles. Scrambling characters use G.mid, locked use G.ink.
// Keyframes: 0–20f full scramble -> 20–86f sequential lock from left to right -> 87–130f fully static ending.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { G } from '../../_fixtures/Fixtures';

const TEXT = 'DECODE SPEED';
const CHARSET = 'ABCDEF0123456789#$%&';
const LOCK_START = 20; // Lock frame for character 0
const LOCK_STEP = 6; // Interval between adjacent character locks
const FLASH_LEN = 2; // Lock invert flash duration in frames

// Frame-deterministic pseudorandom generator
const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

export const ScrambleDecode: React.FC = () => {
  const frame = useCurrentFrame();
  const chars = TEXT.split('');
  const lockedCount = chars.filter((c, i) => c === ' ' || frame >= LOCK_START + i * LOCK_STEP).length;
  const allLocked = lockedCount === chars.length;

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.bg,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 48,
      }}
    >
      <div
        style={{
          fontFamily: 'ui-monospace, Menlo, Monaco, monospace',
          fontWeight: 800,
          fontSize: 120,
          letterSpacing: 2,
          display: 'flex',
        }}
      >
        {chars.map((ch, i) => {
          if (ch === ' ') {
            return <span key={i} style={{ display: 'inline-block', width: '0.7em' }} />;
          }
          const lockFrame = LOCK_START + i * LOCK_STEP;
          const locked = frame >= lockFrame;
          const flashing = locked && frame < lockFrame + FLASH_LEN;
          // Scramble phase: changes pseudorandom character every 2 frames
          const tick = Math.floor(frame / 2);
          const scrambleChar = CHARSET[Math.floor(h(i * 101 + tick * 7 + 13) * CHARSET.length)];
          const shown = locked ? ch : scrambleChar;
          return (
            <span
              key={i}
              style={{
                display: 'inline-block',
                width: '1ch',
                textAlign: 'center',
                color: flashing ? G.card : locked ? G.ink : G.mid,
                background: flashing ? G.ink : 'transparent',
              }}
            >
              {shown}
            </span>
          );
        })}
      </div>
      {/* Bottom progress bar: ratio of locked characters, reinforcing the left-to-right sweep feel */}
      <div style={{ width: 900, height: 10, background: G.line, borderRadius: 5, overflow: 'hidden' }}>
        <div
          style={{
            width: `${(lockedCount / chars.length) * 100}%`,
            height: '100%',
            background: allLocked ? G.ink : G.mid,
            borderRadius: 5,
          }}
        />
      </div>
    </div>
  );
};
