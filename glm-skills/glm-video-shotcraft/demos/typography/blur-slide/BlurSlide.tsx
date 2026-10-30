// blur-slide — Blur Slide word-by-word reveal (Round 2 redesign: editorial typography poster)
// Same technique: headline reveals word-by-word; y-translation + blur + opacity share the same progress p and converge synchronously along the same easing curve
// — words "surface from defocus" rather than "slide in and fade"; subtitle staggers in before the headline finishes, overlapping to read as one continuous sentence.
//
// Design decisions:
// - look: paper (warm white paper, ink, vermilion). Editorial typography context: magazine masthead + large serif headline + sans-serif subtitle,
//   left-aligned to the 168px safe margin grid, leaving negative space on the right for the headline to breathe.
// - Hierarchy: masthead 24px all-caps (texture level) -> section kicker 30px vermilion all-caps -> headline 170px serif two lines ->
//   subtitle 46px sans-serif. 3.7x size ratio between title and subtitle; font family distinguishes weight-400 serif from weight-400 sans-serif.
// - Accent color reserved for one word: italic "cinematic." on the second line is vermilion; it settles last with an extended entrance window (the hero element).
// - Copy: headline 5 words "Make every launch / feel cinematic.", subtitle 9 words (video-shotcraft tagline); masthead uses the video-shotcraft wordmark.
//
// Schedule (30fps, 120f)
//   0–24   Masthead and hairline rule present on frame 0 (no empty first frame); hairline draws left-to-right (snappy 24f)
//   4–22   Section kicker blur-slide entrance (shares technique family, acts as "prep")
//   10–40  Headline line 1: 3 words, 4f stagger, 22f duration each
//   26–58  Line 2: 6f breath pause first, "feel" 22f, "cinematic." 30f (settles last, tracking tightens with p)
//   34–80  Subtitle: 9 words, 2.4f stagger, 20f duration each, smaller displacement/blur — hierarchy by amplitude, not duration; overlaps 24f with headline
//   72–98  Footer hairline draws right-to-left + page number fades in (aftermath of hold phase, framing layout into a complete page)
//   80–119 Settled hold 40f: subtle push-in 1->1.03 (smooth, zero start/end velocity) + subtle key light breathing on paper
// Curves: all 3 channels share EASE.out (quint-out grade), fast attack with long tail so words "float" in rather than "bounce" in.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { LOOKS, SERIF, Stage, alpha } from '../../_fixtures/Look';
import { EASE, FONT, ramp } from '../../_fixtures/Polish';
import { ShotcraftWordmark } from '../../_fixtures/Brand';

export const BLUR_SLIDE_DURATION = 120; // 4000ms @30fps

const L = LOOKS.paper;
const LEFT = 168; // Left safe margin / grid origin

// Word: start frame, dur entrance duration, dy offset (px), blur max blur (px).
// opacity / translateY / blur (and optional tracking) are all bound to the same p — core mechanism of this card; do not split into separate easings.
type Word = { text: string; start: number; dur: number; style?: React.CSSProperties; track?: [number, number] };

const Words: React.FC<{ words: Word[]; dy: number; blur: number; gap: string; style: React.CSSProperties }> = ({ words, dy, blur, gap, style }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap, whiteSpace: 'nowrap', ...style }}>
      {words.map((w, i) => {
        const p = ramp(frame, w.start, w.dur, EASE.out);
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              opacity: p,
              transform: `translateY(${((1 - p) * dy).toFixed(2)}px)`,
              filter: p >= 0.999 ? undefined : `blur(${((1 - p) * blur).toFixed(2)}px)`,
              letterSpacing: w.track ? `${(w.track[0] + (w.track[1] - w.track[0]) * p).toFixed(4)}em` : undefined,
              ...w.style,
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};

// Headline: line 1 has 3 words staggered at 4f; line 2 pauses 6f to breathe, hero word has longer entrance window and tracking tightens with p
const H1_A: Word[] = ['Make', 'every', 'launch'].map((text, i) => ({ text, start: 10 + i * 4, dur: 22 }));
const H1_B: Word[] = [
  { text: 'feel', start: 26, dur: 22 },
  {
    text: 'cinematic.', start: 30, dur: 30, track: [0.03, -0.025],
    style: { fontStyle: 'italic', color: L.accent },
  },
];
// Subtitle: 9 words, 2.4f stagger (more words than draft, gap compacted per card rules)
const H2: Word[] = 'Shot recipes and camera moves, crafted by your agent.'.split(' ').map((text, i) => ({ text, start: 34 + i * 2.4, dur: 20 }));

export const BlurSlide: React.FC = () => {
  const frame = useCurrentFrame();
  // Ultra-slow push-in of entire group: origin at text block left edge, smooth throughout with zero ending velocity
  const push = 1 + 0.03 * ramp(frame, 0, 119, EASE.smooth);
  // Masthead hairline rule: draws left to right
  const rule = ramp(frame, 0, 24, EASE.snappy);
  // Section kicker: same blur-slide family, unit = full line
  const kick = ramp(frame, 4, 18, EASE.out);
  // Background issue number: slowly develops from defocus (much slower than headline, establishes spatial depth)
  const folio = ramp(frame, 0, 48, EASE.out);
  // Footer: starts drawing at subtitle tail (72f), 26f snappy
  const foot = ramp(frame, 72, 26, EASE.snappy);
  const headline: React.CSSProperties = {
    fontFamily: SERIF, fontSize: 170, fontWeight: 400, lineHeight: 1, letterSpacing: '-0.035em', color: L.ink,
  };
  return (
    <Stage look={L} keyLight={{ x: 0.3, y: 0.18 }} fill={null} breathe={0.6} grain={0.06} vignette={0.1}>
      {/* Faint warmth of vermilion at bottom-right of paper, preventing warm white from looking flat */}
      <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 40% 50% at 96% 100%, ${alpha(L.accent, 0.06)}, ${alpha(L.accent, 0)} 70%)` }} />

      {/* Background: large issue number (5% ink), pushes slower than text layer with counter-drift -> foreground/background parallax */}
      <div
        style={{
          position: 'absolute', right: 120, top: 150, fontFamily: SERIF, fontSize: 760, fontWeight: 400, lineHeight: 1, letterSpacing: '-0.06em',
          color: alpha(L.ink, 0.045 * folio), filter: folio >= 0.999 ? undefined : `blur(${((1 - folio) * 24).toFixed(2)}px)`,
          transform: `translateX(${(-24 * ramp(frame, 0, 119, EASE.smooth)).toFixed(2)}px)`,
        }}
      >
        07
      </div>
        {/* Masthead: texture-level small text (not meant to be read), present on frame 0; static furniture does not push with text */}
        <div style={{ position: 'absolute', left: LEFT, right: LEFT, top: 92, display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontFamily: FONT.sans, fontSize: 24, fontWeight: 600, letterSpacing: '0.2em', color: L.ink2, opacity: 0.4 + 0.6 * rule }}>
          {/* Masthead wordmark: video-shotcraft (lowercase, wordmark omits caps tracking) */}
          <ShotcraftWordmark size={24} markScale={1.5} gap={12} tone="light" color={L.ink2} />
          <span style={{ color: L.ink3 }}>N° 07 — OCTOBER 2026</span>
        </div>
        <div style={{ position: 'absolute', left: LEFT, top: 140, width: 1920 - LEFT * 2, height: 1.5, background: alpha(L.ink, 0.22), transform: `scaleX(${rule.toFixed(4)})`, transformOrigin: '0 50%' }} />

        {/* Footer: right-to-left hairline rule + page number after subtitle settles, closing hold phase and framing page into a complete spread */}
        <div style={{ position: 'absolute', left: LEFT, top: 972, width: 1920 - LEFT * 2, height: 1.5, background: alpha(L.ink, 0.18), transform: `scaleX(${foot.toFixed(4)})`, transformOrigin: '100% 50%' }} />
        <div style={{ position: 'absolute', right: LEFT, top: 994, fontFamily: FONT.sans, fontSize: 24, fontWeight: 600, letterSpacing: '0.2em', color: L.ink3, opacity: foot }}>
          PAGE 07
        </div>

      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push.toFixed(5)})`, transformOrigin: `${LEFT}px 560px` }}>
        {/* Section kicker */}
        <div
          style={{
            position: 'absolute', left: LEFT, top: 318, display: 'flex', alignItems: 'center', gap: 18,
            fontFamily: FONT.sans, fontSize: 30, fontWeight: 650, letterSpacing: '0.16em', color: L.accent,
            opacity: kick, transform: `translateY(${((1 - kick) * 18).toFixed(2)}px)`, filter: kick >= 0.999 ? undefined : `blur(${((1 - kick) * 6).toFixed(2)}px)`,
          }}
        >
          <span style={{ width: 14, height: 14, background: L.accent, display: 'inline-block' }} />
          RELEASE NOTES
        </div>

        {/* Headline two lines: serif 170px, negative tracking */}
        <Words words={H1_A} dy={64} blur={18} gap="0.24em" style={{ ...headline, position: 'absolute', left: LEFT - 6, top: 384 }} />
        <Words words={H1_B} dy={64} blur={18} gap="0.24em" style={{ ...headline, position: 'absolute', left: LEFT - 6, top: 556 }} />

        {/* Subtitle: sans-serif 46px, one step lower displacement and blur than headline */}
        <Words
          words={H2}
          dy={26}
          blur={9}
          gap="0.26em"
          style={{ position: 'absolute', left: LEFT, top: 800, fontFamily: FONT.sans, fontSize: 46, fontWeight: 400, letterSpacing: '-0.012em', color: L.ink2, lineHeight: 1.2 }}
        />
      </div>
    </Stage>
  );
};
