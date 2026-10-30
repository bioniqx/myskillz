// D-Style Black Card Transition (black-card) — Previous shot fades into black, title card reveals word-by-word with letterpress stamp
// (dark-mode variant of paper-title-card), then hands off to next shot. Combines chapter divider + breathing room; <= 2 uses per 30s video.
// Reference implementation (realistic textures): Scene A = projects-full board (ends with **8f** fade to black,
// adhering to 6–10 frame spec); dark title card = "weekly brief, every project linked" word-by-word letterpress
// (dark ground + page light-tone text, no accent color for body text — avoids feeling like an error alert modal), monospace secondary line;
// once full title is revealed, **hold ~15 frames** before exit to avoid "fading out immediately as last word lands";
// Scene B = wbr-full weekly report page fades in from black over 8f handoff.
// Beats: 0–8 A fade-out -> 8–20 black hold -> 20–47 title word-by-word stamp -> 47–62 full title hold ->
// 62–70 title exit -> 70–78 fade into Scene B -> 78–120 Scene B hold.
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';

export const BLACKCARD_DUR = 120;

const A_VIEW_Y = -180;
const SERIF = 'ui-serif, Georgia, "Times New Roman", serif';
const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';

// Body text on dark card uses page ground tone (light); accent color reserved for key words
const PAPER_LIGHT = 'oklch(92% 0.01 82)';
const AMBER = 'oklch(68% 0.12 65)';
const DIM = 'oklch(72% 0.01 82)';

const WORDS: { text: string; accent?: boolean }[] = [
  { text: 'Every' },
  { text: 'project,' },
  { text: 'linked' },
  { text: 'to' },
  { text: 'your', accent: true },
  { text: 'weekly' },
  { text: 'report.' },
];

const Scene: React.FC = () => {
  const frame = useCurrentFrame();

  // Scene A outro: 0->8 fade out to black (spec requires 6–10 frames, here 8)
  const aOut = interpolate(frame, [0, 8], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.5, 0, 0.4, 1),
  });

  // Title card: word-by-word letterpress from 20 (delay = 20 + i*3, last word i=6 delay=38 completes at 47)
  const cardOpacity = interpolate(frame, [18, 26], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.7, 0.3, 1),
  });
  // Full title settles at 47f, holds until 62 before exit (~15 frames full presentation)
  const cardOut = interpolate(frame, [62, 70], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.5, 1),
  });

  // Scene B fade-in: 70->78 (hands off after title completely fades out across 62->70)
  const bIn = interpolate(frame, [70, 78], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1),
  });

  return (
    <AbsoluteFill style={{ backgroundColor: '#0c0c10', overflow: 'hidden' }}>
      {/* Scene A */}
      {frame < 14 ? (
        <div style={{ position: 'absolute', opacity: aOut }}>
          <Img
            src={staticFile('legacy-textures/projects-full.png')}
            style={{ position: 'absolute', left: 0, top: A_VIEW_Y, width: 1920 }}
          />
        </div>
      ) : null}

      {/* Black title card (18–74) */}
      {frame >= 18 && frame < 74 ? (
        <AbsoluteFill
          style={{
            justifyContent: 'center', alignItems: 'center',
            opacity: cardOpacity * (1 - cardOut), pointerEvents: 'none',
          }}
        >
          <div style={{ textAlign: 'center', maxWidth: 1500 }}>
            <div
              style={{
                fontFamily: SERIF, fontSize: 96, fontWeight: 600, lineHeight: 1.16,
                color: PAPER_LIGHT, letterSpacing: '-0.012em',
                display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: '0.26em',
              }}
            >
              {WORDS.map((w, i) => {
                const delay = 20 + i * 3;
                const t = interpolate(frame, [delay, delay + 9], [0, 1], {
                  extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.75, 0.3, 1),
                });
                return (
                  <span
                    key={i}
                    style={{
                      opacity: t, transform: `scale(${1.3 - 0.3 * t})`,
                      filter: `blur(${(1 - t) * 7}px)`, display: 'inline-block',
                      fontStyle: w.accent ? 'italic' : 'normal',
                      color: w.accent ? AMBER : undefined,
                    }}
                  >
                    {w.text}
                  </span>
                );
              })}
            </div>
            <div
              style={{
                height: 4, width: 180, margin: '30px auto 0', borderRadius: 2,
                background: AMBER, transform: `scaleX(${interpolate(frame, [32, 44], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) })})`,
              }}
            />
            <div
              style={{
                fontFamily: MONO, fontSize: 20, letterSpacing: '0.14em', color: DIM,
                marginTop: 26, textTransform: 'uppercase',
                opacity: interpolate(frame, [26, 36], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
              }}
            >
              Weekly Brief · 2026-W28
            </div>
          </div>
        </AbsoluteFill>
      ) : null}

      {/* Scene B (fades in from 70) */}
      {frame >= 70 ? (
        <div style={{ position: 'absolute', opacity: bIn }}>
          <Img
            src={staticFile('legacy-textures/wbr-full.png')}
            style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080 }}
          />
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

export const BlackCardTransition: React.FC = () => (
  <Scene />
);
