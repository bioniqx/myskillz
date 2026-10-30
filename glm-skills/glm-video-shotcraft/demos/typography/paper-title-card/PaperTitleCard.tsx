// paper-title-card — word-by-word letterpress title card on paper
// Section transition / value proposition breath: single sentence letterpress entrance (large scale -> 1 + blur -> 0),
// exactly one accent-colored italic keyword per line, accent underline scaleX resolve, full card fade out at tail.
// Uniform 50-55f card duration across video; warm paper background with central light matching editorial palette.
// Parameterized: words/sub/subDigits customizable; subDigits driven by DigitRoll
// odometer roll (settles prior to card fade). Ready to copy into project.
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from 'remotion';

export const PAPER_TITLE_CARD_DURATION = 55; // ≈1.8s @30fps

const SERIF = 'ui-serif, Georgia, "Times New Roman", serif';
const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';

// Exactly one accent keyword per sentence: feature name / value proposition (C2)
// br: forced line break after keyword to balance line lengths and avoid orphans
const WORDS: { text: string; accent?: boolean; br?: boolean }[] = [
  { text: 'Direct' },
  { text: 'the' },
  { text: 'film.', br: true },
  { text: 'Let' },
  { text: 'the' },
  { text: 'agent' },
  { text: 'shoot', accent: true },
  { text: 'it.' },
];
// Subtitle: video-shotcraft render queue context (mock demo data)
const SUB = 'shots rendered today';
const SUB_DIGITS = '12';

// Odometer digit roller column (duplicated strips ensure smooth scroll to any target digit;
// tabular-nums prevents horizontal jitter)
const DIGITS = '0123456789';
const DigitColumn: React.FC<{ ch: string; delay: number; lineH: number; color: string }> = ({ ch, delay, lineH, color }) => {
  const frame = useCurrentFrame();
  if (ch < '0' || ch > '9') {
    return <span style={{ fontSize: 26, lineHeight: `${lineH}px`, color }}>{ch}</span>;
  }
  const target = DIGITS.indexOf(ch);
  const t = interpolate(frame, [delay, delay + 22], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.25, 0.8, 0.25, 1),
  });
  const offset = (10 + target) * t * lineH;
  return (
    <span style={{ display: 'inline-block', height: lineH }}>
      <span style={{ display: 'block', transform: `translateY(${-offset}px)` }}>
        {(DIGITS + DIGITS).split('').map((d, j) => (
          <span
            key={j}
            style={{
              display: 'block',
              fontSize: 26,
              lineHeight: `${lineH}px`,
              color,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {d}
          </span>
        ))}
      </span>
    </span>
  );
};

const DigitRoll: React.FC<{ value: string; delay: number; color: string }> = ({ value, delay, color }) => {
  const lineH = 26 * 1.15;
  return (
    <span style={{ display: 'inline-flex', overflow: 'hidden', height: lineH, verticalAlign: 'bottom' }}>
      {value.split('').map((c, i) => (
        <DigitColumn key={i} ch={c} delay={delay + i * 4} lineH={lineH} color={color} />
      ))}
    </span>
  );
};

export const PaperTitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const duration = PAPER_TITLE_CARD_DURATION;
  const fadeOut = interpolate(frame, [duration - 8, duration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const underline = interpolate(frame, [16, 34], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const subT = interpolate(frame, [10, 22], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: 'oklch(97.5% 0.008 82)',
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeOut,
        backgroundImage:
          'radial-gradient(1100px 750px at 50% 42%, oklch(99.3% 0.014 88 / 0.85), transparent 65%)',
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 1500 }}>
        <div
          style={{
            fontFamily: SERIF,
            fontSize: 116,
            fontWeight: 600,
            lineHeight: 1.14,
            color: 'oklch(18% 0.006 82)',
            letterSpacing: '-0.012em',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            columnGap: '0.26em',
          }}
        >
          {WORDS.map((w, i) => {
            const delay = 4 + i * 4;
            const t = interpolate(frame, [delay, delay + 9], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: Easing.bezier(0.2, 0.75, 0.3, 1),
            });
            return (
              <React.Fragment key={i}>
                <span
                  style={{
                    opacity: t,
                    transform: `scale(${1.28 - 0.28 * t})`,
                    filter: `blur(${(1 - t) * 7}px)`,
                    display: 'inline-block',
                    fontStyle: w.accent ? 'italic' : 'normal',
                    color: w.accent ? 'oklch(52% 0.115 65)' : undefined,
                  }}
                >
                  {w.text}
                </span>
                {w.br && <span style={{ flexBasis: '100%', height: 0 }} />}
              </React.Fragment>
            );
          })}
        </div>
        <div
          style={{
            height: 6,
            width: 220,
            margin: '38px auto 0',
            borderRadius: 3,
            background: 'oklch(52% 0.115 65)',
            transform: `scaleX(${underline})`,
          }}
        />
        <div
          style={{
            fontFamily: MONO,
            fontSize: 26,
            letterSpacing: '0.12em',
            color: 'oklch(50% 0.006 82)',
            marginTop: 34,
            opacity: subT,
            textTransform: 'uppercase',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'baseline',
            gap: '0.5em',
          }}
        >
          <DigitRoll value={SUB_DIGITS} delay={12} color="oklch(52% 0.115 65)" />
          <span>{SUB}</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
