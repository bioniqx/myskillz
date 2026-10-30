// typing-code-block — Code Block Reveal (motion-lab finalized to native Remotion)
// Side-by-side comparison of two reveal styles for the same syntax-highlighted code:
// Left: line-by-line fade-in and float (line stagger);
// Right: character-by-character typing with preserved token coloring; current character highlighted with block cursor background.
// Design coordinates 480x270 (uniformly scaled via DesignStage); parameters are calibrated to this coordinate space.
import React from 'react';
import { DesignStage, E, seg, useT } from '../../_fixtures/Motion';

export const TYPING_CODE_BLOCK_DURATION = 138; // 4600ms @30fps

// Token colors: keyword / identifier / function / string / punctuation / comment
const K = '#c792ea';
const ID = '#e8eaf0';
const FN = '#82aaff';
const ST = '#c3e88d';
const PU = '#89ddff';
const CM = '#546e7a';
// Each line is a sequence of [text, color] tokens
const LINES: [string, string][][] = [
  [['const ', K], ['app', ID], [' = ', PU], ['createApp', FN], ['();', ID]],
  [['app', ID], ['.', PU], ['use', FN], ['(', ID], ['router', ID], [');', ID]],
  [['app', ID], ['.', PU], ['mount', FN], ['(', ID], ["'#root'", ST], [');', ID]],
  [['// ready', CM]],
];
// Flat character sequence for right-side typing (preserves token color + line index)
const FLAT: { ch: string; color: string; row: number }[] = [];
LINES.forEach((line, row) => {
  for (const [txt, color] of line) for (const ch of txt) FLAT.push({ ch, color, row });
});

// Code panel container: shared wrapper frame + top label for both panels
const Panel: React.FC<{ x: number; label: string; children: React.ReactNode }> = ({
  x,
  label,
  children,
}) => (
  <div
    style={{
      position: 'absolute',
      left: `${x}%`,
      top: '14%',
      width: '45%',
      height: '72%',
      background: '#10121a',
      border: '1px solid #1c2030',
      borderRadius: 8,
      padding: '10px 12px',
      boxSizing: 'border-box',
      fontFamily: '"SF Mono",Menlo,monospace',
      fontSize: 12,
      lineHeight: 1.9,
    }}
  >
    <div style={{ fontSize: 8, letterSpacing: 2, color: '#4a5270', marginBottom: 6 }}>{label}</div>
    {children}
  </div>
);

export const TypingCodeBlock: React.FC = () => {
  const t = useT();
  // Right typing progress: t in [0.08, 0.9] advances linearly through all characters
  const typed = Math.floor(seg(t, 0.08, 0.9) * FLAT.length);
  return (
    <DesignStage bg="#0a0b10">
      {/* Left: line-by-line fade-in and float (line stagger) */}
      <Panel x={3.5} label="LINE FADE-IN">
        {LINES.map((line, i) => {
          const k = seg(t, 0.08 + i * 0.14, 0.08 + i * 0.14 + 0.3, E.outCubic);
          return (
            <div key={i} style={{ opacity: k, transform: `translateY(${(1 - k) * 8}px)` }}>
              {line.map(([txt, color], j) => (
                <span key={j} style={{ color }}>
                  {txt}
                </span>
              ))}
            </div>
          );
        })}
      </Panel>
      {/* Right: character-by-character typing (colored tokens), cursor block background on active char */}
      <Panel x={51.5} label="CHAR TYPING">
        {LINES.map((_, row) => (
          <div key={row} style={{ minHeight: '1.9em' }}>
            {FLAT.map((c, i) =>
              c.row === row ? (
                <span
                  key={i}
                  style={{
                    color: c.color,
                    // Active character rendered with block background as cursor (remains visible)
                    opacity: i < typed || i === typed ? 1 : 0,
                    background: i === typed && typed < FLAT.length ? '#3a4468' : 'transparent',
                  }}
                >
                  {c.ch}
                </span>
              ) : null,
            )}
          </div>
        ))}
      </Panel>
    </DesignStage>
  );
};
