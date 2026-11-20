// lead-word-zoom-assemble - Lead word zooms in and locks into place to assemble the sentence
// The lead word occupies screen center at 2.3x font size, continuing to push in 6% during hold.
// A single curve then simultaneously handles shrinking to final size and sliding the full line
// left into its final layout, while subsequent words push in from 0.5em right of their slots;
// in the same window as the line lifts, the subline emerges, pauses for a beat, and the entire scene
// crash-zooms into blur before handing off to the next shot.
//
// Critical pivot: transform-origin is anchored horizontally at the **center of the lead word**
// and vertically at the **baseline** - these are the only two anchors that must never move,
// measured once on mount (baseline read via offsetTop of a zero-size inline-block),
// otherwise font scaling causes frame-by-frame baseline jitter.
// Calibrated for 1920x1080.
// Polish layer (revision): 4-color mesh refined into low-contrast "indigo key light + touch of warm ambient" + grain + vignette;
// Lead word enters with 8px -> 0 blur (synced with 6f fade-in); recede segment adds dynamic blur based on scale velocity (<= 3.5px, returning to 0 at rest),
// avoiding harsh snaps on large zooms; line lift moved up to f32-46, brand line holds steady for 26f before crash; accent color unified to batch indigo.
import React, { Fragment, useEffect, useRef, useState } from 'react';
import { Grain, Vignette } from '../../_fixtures/Polish';
import {
  AbsoluteFill,
  continueRender,
  delayRender,
  Easing,
  getRemotionEnvironment,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export const LEAD_WORD_ZOOM_ASSEMBLE_DURATION = 84; // 2.8s @30fps

// ---- Choreography constants ----
const TEXT = 'Introducing video-shotcraft';
const HIGHLIGHT_WORD = 'video-shotcraft'; // Exact matching word switches to accent color: brand word highlights upon settling
const FONT_SIZE = 96;
const INITIAL_SCALE = 2.3; // Initial scale factor for lead word
const INTRO_DURATION = 6; // frames: lead word fade-in
const HOLD_DURATION = 12; // frames: lead word peak hold (push-in happens here)
const PUSH_SCALE = 1.06; // Additional push-in scale multiplier during hold
const RECEDE_DURATION = 12; // frames: recede to final font size
const ASSEMBLE_DURATION = 24; // frames: full line slides left into place
const WORD_DELAY = 6; // frames: delay after recede begins before second word starts pushing in
const WORD_STAGGER = 4; // frames: stagger between subsequent words
const WORD_DURATION = 12; // frames: push-in travel duration per word
const WORD_PUSH = 0.5; // em: initial offset distance to the right of each slot
const WORD_FADE = 2; // frames: fade-in for subsequent words (intentionally brief - pushed in, not faded in)
const LETTER_SPACING = '-0.03em';

// ---- Scene layer ----
const LIFT: [number, number] = [32, 46]; // frames: line lifts + subline appears (overlaps last 4f of left-slide as a continuous gesture)
const LIFT_DISTANCE = -56; // px
const SUBLINE = 'One shot card, one motion recipe — copy, paste, render.';
const CRASH_FRAMES = 12; // frames: crash-zoom duration at scene end
const CRASH_SCALE = 0.2;
const CRASH_BLUR = 9;

const INK = '#1d1d1f';
const INK_DIM = '#6e6f76';
const ACCENT = '#5b63d3';
// System Display font stack first (-apple-system may not resolve in headless Chrome, falling back to PingFang)
const SANS = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", "PingFang SC", Inter, Arial, sans-serif';
const MESH_BG =
  'radial-gradient(56% 50% at 26% 24%, rgba(91,99,211,0.16) 0%, rgba(91,99,211,0) 72%),' +
  'radial-gradient(50% 46% at 80% 82%, rgba(255,180,120,0.10) 0%, rgba(255,180,120,0) 72%),' +
  'radial-gradient(70% 60% at 50% 46%, rgba(255,255,255,0.85) 0%, rgba(255,255,255,0) 70%),' +
  'linear-gradient(180deg, #f6f6f8 0%, #efeff2 100%)';

/** Lead word drifts toward viewer: fast start, soft stop, hangs at peak */
const PUSH_EASE = Easing.bezier(0.25, 1, 0.5, 1);
/** Recede and left slide share the same curve - both actions must read as a single motion */
const ZOOM_EASE = Easing.bezier(0.5, 0, 0.05, 1);
/** Subsequent words push into slots: snappy start, long soft landing */
const WORD_EASE = Easing.bezier(0.22, 0.8, 0.36, 1);

// Full line scale: hold push-in + recede combined smoothly without velocity discontinuities
const lineScale = (f: number) =>
  interpolate(f, [0, HOLD_DURATION], [INITIAL_SCALE, INITIAL_SCALE * PUSH_SCALE], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: PUSH_EASE,
  }) +
  interpolate(f, [HOLD_DURATION, HOLD_DURATION + RECEDE_DURATION], [0, 1 - INITIAL_SCALE * PUSH_SCALE], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ZOOM_EASE,
  });

const TextReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();

  // Full line width, lead word center ratio, baseline position: measured once on mount; delays render until ready
  const lineRef = useRef<HTMLSpanElement>(null);
  const leadRef = useRef<HTMLSpanElement>(null);
  const baselineRef = useRef<HTMLSpanElement>(null);
  const [handle] = useState(() => delayRender('lead-word-zoom-assemble: measure line'));
  const [metrics, setMetrics] = useState<{
    lineWidth: number;
    leadRatio: number;
    baseline: number;
  } | null>(null);

  useEffect(() => {
    const line = lineRef.current;
    const lead = leadRef.current;
    if (!line || !lead) {
      continueRender(handle);
      return;
    }
    setMetrics({
      lineWidth: line.offsetWidth,
      leadRatio: (lead.offsetLeft + lead.offsetWidth / 2) / line.offsetWidth,
      baseline: baselineRef.current?.offsetTop ?? line.offsetHeight * 0.8,
    });
  }, [handle]);

  useEffect(() => {
    if (metrics) continueRender(handle);
  }, [metrics, handle]);

  const words = TEXT.split(' ').filter(Boolean);
  const ready = metrics !== null;
  const leadRatio = metrics?.leadRatio ?? 0.14;
  const lineWidth = metrics?.lineWidth ?? width * 0.5;
  const baseline = metrics?.baseline ?? FONT_SIZE * 0.88;

  const zoomStart = HOLD_DURATION;
  // Lead word translates from screen center to in-line slot position by offset distance
  const slideDistance = lineWidth * (0.5 - leadRatio);
  // Lead word entrance blur: syncs with 6f fade-in 8px->0 (pre-scale units, magnified by 2.3x)
  const introBlur = interpolate(frame, [0, INTRO_DURATION], [8 / INITIAL_SCALE, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <span
        ref={lineRef}
        style={{
          position: 'relative',
          display: 'inline-block',
          fontSize: FONT_SIZE,
          fontWeight: 600,
          color: INK,
          letterSpacing: LETTER_SPACING,
          lineHeight: 1.1,
          whiteSpace: 'nowrap',
          fontFamily: SANS,
          transformOrigin: `${leadRatio * 100}% ${baseline}px`,
          scale: lineScale(frame),
          // Instantaneous defocus during scale recovery: proportional to scale velocity (peak ~0.3/f -> ~3px), 0 at rest
          filter: (() => {
            const v = Math.abs(lineScale(frame + 0.5) - lineScale(frame - 0.5));
            const b = Math.min(3.5, v * 10) + introBlur;
            return b > 0.05 ? `blur(${b.toFixed(2)}px)` : undefined;
          })(),
          translate: `${interpolate(
            frame,
            [zoomStart, zoomStart + ASSEMBLE_DURATION],
            [slideDistance, 0],
            { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ZOOM_EASE },
          )}px`,
          opacity: ready ? 1 : 0,
          textRendering: 'geometricPrecision',
          ...(getRemotionEnvironment().isRendering ? null : { willChange: 'transform' as const }),
        }}
      >
        {words.map((word, i) => {
          const isLead = i === 0;
          const pushStart = zoomStart + WORD_DELAY + (i - 1) * WORD_STAGGER;
          const opacity = isLead
            ? interpolate(frame, [0, INTRO_DURATION], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              })
            : interpolate(frame, [pushStart, pushStart + WORD_FADE], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              });
          return (
            <Fragment key={i}>
              <span
                ref={isLead ? leadRef : undefined}
                style={{
                  display: 'inline-block',
                  opacity,
                  color: word === HIGHLIGHT_WORD ? ACCENT : undefined,
                  translate: isLead
                    ? undefined
                    : `${interpolate(
                        frame,
                        [pushStart, pushStart + WORD_DURATION],
                        [WORD_PUSH * FONT_SIZE, 0],
                        { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: WORD_EASE },
                      )}px`,
                }}
              >
                {word}
              </span>
              {/* Inter-word spaces placed outside inline-block to prevent line-box clipping */}
              {i < words.length - 1 ? ' ' : null}
            </Fragment>
          );
        })}
        {/* Baseline ruler: zero-size inline-block whose offsetTop marks baseline */}
        <span ref={baselineRef} style={{ display: 'inline-block', width: 0, height: 0 }} />
      </span>
    </AbsoluteFill>
  );
};

export const LeadWordZoomAssemble: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const lift = interpolate(frame, LIFT, [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const crash = interpolate(
    frame,
    [durationInFrames - CRASH_FRAMES, durationInFrames - 1],
    [0, 1],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.quad) },
  );

  return (
    <AbsoluteFill style={{ background: MESH_BG, fontFamily: SANS }}>
      <AbsoluteFill
        style={{
          transform: `scale(${1 + crash * CRASH_SCALE})`,
          filter: crash > 0.01 ? `blur(${crash * CRASH_BLUR}px)` : undefined,
          opacity: 1 - crash * 0.55,
        }}
      >
        <AbsoluteFill style={{ transform: `translateY(${lift * LIFT_DISTANCE}px)` }}>
          <TextReveal />
        </AbsoluteFill>
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: '50%',
            marginTop: 62,
            textAlign: 'center',
            fontSize: 34,
            fontWeight: 400,
            letterSpacing: '-0.005em',
            color: INK_DIM,
            opacity: lift,
            transform: `translateY(${(1 - lift) * 16}px)`,
          }}
        >
          {SUBLINE}
        </div>
      </AbsoluteFill>
      <Vignette strength={0.12} inner={0.5} color="#2a2c36" />
      <Grain opacity={0.05} />
    </AbsoluteFill>
  );
};
