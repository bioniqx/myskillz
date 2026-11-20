// trailer-bumper — Fast-cut teaser bumper
// Structure is everything: triple 9f fast cuts (full page A / full page B / 2.2x close-up on middle column Top pages card of A) -> 6f pure black breath
// -> main title fades in + subtle rise over 16f and holds. Each fast cut shot includes internal 1->1.04 slow push-in.
// True static finish: letter spacing tightens over 30f (ends at 63f) completing all animations, followed by 77f (>40f) pure hold.
// Texture: wide shot variety (full view / alternate page full view / close-up); close-up uses CSS zoom to rasterize at target resolution;
// all three shots share vignette + grain as if captured by the same camera; black frame is a true silent beat;
// opening title card is production-grade: soft light background + kicker + main title (lowercase video-shotcraft wordmark) + subtitle (brand tagline);
// main title tracking closes from 0.05em to -0.012em during fade-in/rise (trailer title "breathing"); subtitle follows 6f later, entire frame freezing after 63f.
import React from 'react';
import { AbsoluteFill, Freeze, useCurrentFrame, interpolate, Easing } from 'remotion';
import { G, FakeDashboard } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, Grain, Vignette, mix, ramp, tracking } from '../../_fixtures/Polish';
import { BRAND, PITCH } from '../../_fixtures/Brand';

export const TRAILER_BUMPER_DURATION = 140; // Fast cuts 27f + black silence 6f + title intro 30f + static hold 77f

// Timeline (frames)
const CUT_1 = 0; // Shot 1: variant A full page
const CUT_2 = 9; // Shot 2: variant B full page
const CUT_3 = 18; // Shot 3: variant A middle card 2.2x close-up
const BLACK = 27; // Pure black silence
const TITLE = 33; // Main title opening
const TITLE_IN = 16; // Title fade-in and rise duration
const SETTLED = TITLE + 30; // Tracking settle completes = last animation frame

// Slow push-in within fast cuts: local 0->9f, scale 1->1.04 (linear constant creep over 9f, maintaining momentum across cuts)
const push = (frame: number, start: number) =>
  interpolate(frame, [start, start + 9], [1, 1.04], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

// Shot 3 focal point: center of top card in middle column (Top pages) -> pushed to screen center
const FOCUS_X = 1071;
const FOCUS_Y = 335;
const CLOSE = 2.2;

const Shot: React.FC<{ children: React.ReactNode; s: number }> = ({ children, s }) => (
  <AbsoluteFill style={{ background: G.canvas, overflow: 'hidden' }}>
    <AbsoluteFill style={{ transform: `scale(${s})`, transformOrigin: '50% 50%' }}>{children}</AbsoluteFill>
    <Vignette strength={0.18} inner={0.5} color="#1a1c24" />
    <Grain opacity={0.05} />
  </AbsoluteFill>
);

export const TrailerBumper: React.FC = () => {
  const frame = useCurrentFrame();

  // —— Sections 1–3: Triple fast cut ——
  if (frame < BLACK) {
    if (frame < CUT_2) {
      // Shot 1: Variant A full page + slow push-in
      return (
        <Shot s={push(frame, CUT_1)}>
          <FakeDashboard variant="A" />
        </Shot>
      );
    }
    if (frame < CUT_3) {
      // Shot 2: Variant B full page + slow push-in
      return (
        <Shot s={push(frame, CUT_2)}>
          <FakeDashboard variant="B" />
        </Shot>
      );
    }
    // Shot 3: Variant A middle card 2.2x close-up (layout-level CSS zoom) + same slow push-in
    return (
      <Shot s={push(frame, CUT_3)}>
        <div
          style={{
            position: 'absolute',
            // zoom scales left/top as well: left = 960/s - cx => focal point aligns to screen center
            left: 960 / CLOSE - FOCUS_X,
            top: 540 / CLOSE - FOCUS_Y,
            width: 1920,
            height: 1080,
            zoom: CLOSE,
          }}
        >
          <FakeDashboard variant="A" />
        </div>
      </Shot>
    );
  }

  // —— Section 4: Pure black silence for 6f, completely empty ——
  if (frame < TITLE) {
    return <AbsoluteFill style={{ background: '#000000' }} />;
  }

  // —— Section 5: Main opening — title card fades in + rises over 16f, tracking settles over 30f then holds ——
  const opacity = interpolate(frame, [TITLE, TITLE + TITLE_IN], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  const rise = interpolate(frame, [TITLE, TITLE + TITLE_IN], [44, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const track = mix(0.05, -0.012, ramp(frame, TITLE, SETTLED - TITLE, EASE.out));
  const eyebrow = ramp(frame, TITLE + 2, 16, EASE.out);
  const sub = ramp(frame, TITLE + 6, 18, EASE.out);
  // Title background lights up from black: fades from black to soft light over 12f (avoiding abrupt jump to white after black frame)
  const lightUp = ramp(frame, TITLE, 12, EASE.out);

  return (
    <AbsoluteFill style={{ background: '#000000', overflow: 'hidden', fontFamily: FONT.sans }}>
      <Freeze frame={SETTLED} active={frame >= SETTLED}>
        <AbsoluteFill style={{ opacity: lightUp }}>
          <Backdrop tone="light" light={{ x: 0.5, y: 0.36 }} vignette={0.2} />
        </AbsoluteFill>
      </Freeze>
      <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            transform: `translateY(${rise}px)`,
          }}
        >
          <div
            style={{
              opacity: eyebrow,
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: '0.18em',
              color: G.accent,
              marginBottom: 30,
            }}
          >
            INTRODUCING
          </div>
          <div
            style={{
              opacity,
              fontFamily: BRAND.font,
              fontWeight: 800,
              fontSize: 176,
              lineHeight: 1,
              color: G.ink1,
              letterSpacing: `${track.toFixed(4)}em`,
              textAlign: 'center',
              whiteSpace: 'nowrap',
            }}
          >
            {BRAND.name}
          </div>
          <div
            style={{
              opacity: sub,
              marginTop: 38,
              fontSize: 40,
              fontWeight: 500,
              color: G.ink2,
              letterSpacing: tracking(40),
            }}
          >
            {PITCH.en.taglines[1]}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
