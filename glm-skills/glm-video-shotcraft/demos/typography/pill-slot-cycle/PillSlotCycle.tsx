// pill-slot-cycle — In-sentence slot cycling: fixed stem + slot-machine rolling pill at end
// Source: notion-ai 4.5–8.5s. Old pill flies up and fades out; new pill slides in from below with motion blur.
// After 6 cycles, the pill disappears and the sentence resolves into "One skill to do it all." (the six steps of video-shotcraft).
//
// Polish upgrades:
// - Pill flips in/out around a cylinder: enter rotateX -38°→0 + scale 0.94→1, exit 0→34° + 1→0.94 (perspective 1400),
//   vertical motion blur calculated from instantaneous velocity (SVG blur on y-axis only), 0 when static.
// - Pill material: white face + hairline border + top inner highlight + two-tier soft shadow varying with lift height;
//   linear SVG icons on a light accent rounded badge (replacing fallback Unicode glyphs like ▲ ☰).
// - System font stack + negative tracking; soft-lit Backdrop replacing flat #ececea.
// - Finale: after final sentence lands, the full line smoothly centers (stem stays stationary during cycling), then holds ≥45f.
import React, { useLayoutEffect, useRef, useState } from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT as PFONT, mix, ramp, softShadow, innerHighlight } from '../../_fixtures/Polish';

const FONT = PFONT.sans;

// Six verb phrases in the slot = six steps of video-shotcraft (storyboard -> capture -> camera -> beat -> sound -> render)
type IconKey = 'board' | 'capture' | 'camera' | 'beat' | 'sound' | 'render';
const PILLS: { label: string; icon: IconKey }[] = [
  { label: 'Storyboard it', icon: 'board' },
  { label: 'Capture the page', icon: 'capture' },
  { label: 'Move the camera', icon: 'camera' },
  { label: 'Cut on the beat', icon: 'beat' },
  { label: 'Design the sound', icon: 'sound' },
  { label: 'Render the film', icon: 'render' },
];
const STEM = 'One skill to'; // Sentence stem (conclusion = STEM + "do it all.")

const BEAT = 21; // ~0.7s @30fps
const INTRO = 12; // Stem intro
const CYCLES = PILLS.length;
const SWAP = 8; // Swap completes in first 8f of each beat
const FIN = 14; // Finale landing duration
const CENTER = 26; // Smooth centering after landing
// 12f intro + 6×21f cycles + 14f finale + 48f hold
export const PILL_SLOT_CYCLE_DURATION = INTRO + CYCLES * BEAT + FIN + 48; // 200f ≈ 6.7s

const STEM_LEFT = 300; // Stem left anchor (remains static during cycling)
const STEM_GAP = 36;
const WORD_GAP = 18; // Standard word spacing between "to" and "do" in finale, not slot gap

// Linear icons (24px viewBox, stroke inherits currentColor)
const Icon: React.FC<{ k: IconKey }> = ({ k }) => {
  const p = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <svg width={34} height={34} viewBox="0 0 24 24" style={{ display: 'block' }}>
      {k === 'board' && (
        <>
          <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" {...p} />
          <path d="M12 4.5v15M3.5 12h17" {...p} />
        </>
      )}
      {k === 'capture' && (
        <>
          <path d="M4 8.5V5.5A1.5 1.5 0 0 1 5.5 4h3M15.5 4h3A1.5 1.5 0 0 1 20 5.5v3M20 15.5v3a1.5 1.5 0 0 1-1.5 1.5h-3M8.5 20h-3A1.5 1.5 0 0 1 4 18.5v-3" {...p} />
          <rect x="8" y="9" width="8" height="6" rx="1" {...p} />
        </>
      )}
      {k === 'camera' && (
        <>
          <rect x="3" y="7" width="12" height="10" rx="2" {...p} />
          <path d="M15 10.5l5.5-3v9l-5.5-3z" {...p} />
        </>
      )}
      {k === 'beat' && <path d="M5 10v4M8.5 7v10M12 4v16M15.5 8v8M19 10.5v3" {...p} />}
      {k === 'sound' && (
        <>
          <path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" {...p} />
          <path d="M15.5 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11" {...p} />
        </>
      )}
      {k === 'render' && (
        <>
          <rect x="3.5" y="5" width="17" height="14" rx="2.5" {...p} />
          <path d="M10 9.2v5.6l4.8-2.8z" {...p} />
        </>
      )}
    </svg>
  );
};

// Pill component; lift = height off slot (0 in slot -> 1 in flight), driving shadow size and softness
const Pill: React.FC<{ label: string; icon: IconKey; lift?: number; style?: React.CSSProperties }> = ({
  label,
  icon,
  lift = 0,
  style,
}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 18,
      padding: '14px 38px 14px 18px',
      borderRadius: 999,
      background: 'linear-gradient(180deg, #ffffff 0%, #fafafb 100%)',
      border: '1px solid rgba(20,22,28,0.10)',
      boxShadow: `${innerHighlight(0.95)}, ${softShadow(6 + lift * 30)}`,
      fontFamily: FONT,
      fontWeight: 700,
      fontSize: 64,
      letterSpacing: '-0.025em',
      color: G.ink1,
      whiteSpace: 'nowrap',
      ...style,
    }}
  >
    <span
      style={{
        width: 62,
        height: 62,
        borderRadius: 18,
        background: G.accentSoft,
        boxShadow: 'inset 0 0 0 1px rgba(91,99,211,0.14)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: G.accent,
        flexShrink: 0,
      }}
    >
      <Icon k={icon} />
    </span>
    {label}
  </div>
);

// Vertical motion blur filter (y-axis only; omitted when std < 0.3)
const VBlur: React.FC<{ id: string; std: number }> = ({ id, std }) => (
  <svg width={0} height={0} style={{ position: 'absolute' }} aria-hidden>
    <filter id={id} x="-10%" y="-60%" width="120%" height="220%">
      <feGaussianBlur stdDeviation={`0 ${std.toFixed(2)}`} />
    </filter>
  </svg>
);

// Enter displacement curve (px): ease-out into slot from +120 below
const inYAt = (bf: number) => mix(120, 0, ramp(bf, 0, SWAP, EASE.snappy));
// Exit displacement curve: accelerating ease-in upward to -130
const outYAt = (bf: number) => mix(0, -130, ramp(bf, 0, SWAP - 1, EASE.exit));

export const PillSlotCycle: React.FC = () => {
  const frame = useCurrentFrame();

  // Measure full sentence width (STEM + gap + "do it all.") for finale centering
  const finalRef = useRef<HTMLDivElement>(null);
  const [finalW, setFinalW] = useState(1240);
  useLayoutEffect(() => {
    if (finalRef.current) setFinalW(finalRef.current.offsetWidth || 1240);
  }, []);

  // Stem intro: ease-out float up, fade in + subtle deblur
  const stemT = ramp(frame, 0, INTRO, EASE.out);

  const cycleStart = INTRO;
  const cycleEnd = cycleStart + CYCLES * BEAT;

  // Current pill cycle index
  const rel = frame - cycleStart;
  const idx = Math.max(0, Math.min(Math.floor(rel / BEAT), CYCLES - 1));
  const beatFrame = rel - idx * BEAT;

  // Finale: pill flies out upward, "do it all." slides in from below (sole overshoot in sequence)
  const isFinale = frame >= cycleEnd;
  const finT = interpolate(frame, [cycleEnd, cycleEnd + FIN], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.back(1.4)),
  });
  // Smoothly center the entire line after landing
  const centerT = ramp(frame, cycleEnd + FIN - 2, CENTER, EASE.smooth);
  const shiftX = centerT * ((1920 - finalW) / 2 - STEM_LEFT);

  const stemStyle: React.CSSProperties = {
    fontFamily: FONT,
    fontWeight: 800,
    fontSize: 96,
    color: G.ink1,
    letterSpacing: '-0.035em',
    whiteSpace: 'nowrap',
  };

  // Slot content rendering
  let slot: React.ReactNode = null;
  if (!isFinale && rel >= 0) {
    const incoming = PILLS[idx];
    const outgoing = idx > 0 ? PILLS[idx - 1] : null;

    // Incoming pill: flips in around cylinder from +120px below, blur proportional to velocity
    const inT = ramp(beatFrame, 0, SWAP, EASE.snappy);
    const inY = inYAt(beatFrame);
    const inV = Math.abs(inYAt(beatFrame + 0.5) - inYAt(beatFrame - 0.5));
    const inBlur = Math.min(14, inV * 0.55);

    // Outgoing pill: accelerates upward to -130px and fades out
    const outT = ramp(beatFrame, 0, SWAP - 1, EASE.exit);
    const outY = outYAt(beatFrame);
    const outV = Math.abs(outYAt(beatFrame + 0.5) - outYAt(beatFrame - 0.5));
    const outBlur = Math.min(12, outV * 0.45);

    slot = (
      <div style={{ position: 'relative', display: 'inline-block', perspective: 1400 }}>
        <VBlur id="psc-in" std={inBlur} />
        <VBlur id="psc-out" std={outBlur} />
        {/* Invisible spacer matching current pill width */}
        <Pill label={incoming.label} icon={incoming.icon} style={{ visibility: 'hidden' }} />
        {outgoing && outT < 1 && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              transformOrigin: '50% 100%',
              transform: `translateY(${outY.toFixed(2)}px) rotateX(${(34 * outT).toFixed(2)}deg) scale(${mix(1, 0.94, outT).toFixed(4)})`,
              opacity: 1 - outT,
              filter: outBlur > 0.3 ? 'url(#psc-out)' : undefined,
            }}
          >
            <Pill label={outgoing.label} icon={outgoing.icon} lift={outT} />
          </div>
        )}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            transformOrigin: '50% 0%',
            transform: `translateY(${inY.toFixed(2)}px) rotateX(${(-38 * (1 - inT)).toFixed(2)}deg) scale(${mix(0.94, 1, inT).toFixed(4)})`,
            opacity: idx === 0 ? inT : Math.min(1, inT * 1.6),
            filter: inBlur > 0.3 ? 'url(#psc-in)' : undefined,
          }}
        >
          <Pill label={incoming.label} icon={incoming.icon} lift={1 - inT} />
        </div>
      </div>
    );
  } else if (isFinale) {
    // Final pill flies out upward (first 7f), then "do it all." lands
    const lastOutT = ramp(frame, cycleEnd, 7, EASE.exit);
    const fv = Math.abs(
      interpolate(frame + 0.5, [cycleEnd, cycleEnd + FIN], [90, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.4)) }) -
        interpolate(frame - 0.5, [cycleEnd, cycleEnd + FIN], [90, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.back(1.4)) }),
    );
    const finBlur = Math.min(10, fv * 0.5);
    slot = (
      <div style={{ position: 'relative', display: 'inline-block', perspective: 1400 }}>
        <VBlur id="psc-fin" std={finBlur} />
        <VBlur id="psc-last" std={Math.min(12, lastOutT * 12)} />
        <span
          style={{
            ...stemStyle,
            display: 'inline-block',
            marginLeft: WORD_GAP - STEM_GAP,
            opacity: Math.min(1, finT * 1.4),
            transform: `translateY(${((1 - finT) * 90).toFixed(2)}px)`,
            filter: finBlur > 0.3 ? 'url(#psc-fin)' : undefined,
          }}
        >
          do it all.
        </span>
        {lastOutT < 1 && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: -8,
              transformOrigin: '50% 100%',
              transform: `translateY(${(-130 * lastOutT).toFixed(2)}px) rotateX(${(34 * lastOutT).toFixed(2)}deg) scale(${mix(1, 0.94, lastOutT).toFixed(4)})`,
              opacity: 1 - lastOutT,
              filter: lastOutT > 0.03 ? 'url(#psc-last)' : undefined,
            }}
          >
            <Pill label={PILLS[CYCLES - 1].label} icon={PILLS[CYCLES - 1].icon} lift={lastOutT} />
          </div>
        )}
      </div>
    );
  }

  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Backdrop tone="light" light={{ x: 0.4, y: 0.3 }} accent="#5b63d3" grain={0.045} vignette={0.14} />
      {/* Hidden width measurement: complete finale sentence */}
      <div ref={finalRef} style={{ position: 'absolute', visibility: 'hidden', display: 'flex', gap: WORD_GAP }}>
        <span style={stemStyle}>{STEM}</span>
        <span style={stemStyle}>do it all.</span>
      </div>
      {/* Stem remains fixed: line is anchored to the left, unaffected by pill width changes (centers only after finale lands) */}
      <div
        style={{
          position: 'absolute',
          left: STEM_LEFT,
          top: 540,
          transform: `translate(${shiftX.toFixed(2)}px, calc(-50% + ${((1 - stemT) * 50).toFixed(2)}px))`,
          display: 'flex',
          alignItems: 'center',
          gap: STEM_GAP,
          opacity: stemT,
          filter: stemT < 0.98 ? `blur(${((1 - stemT) * 6).toFixed(2)}px)` : undefined,
        }}
      >
        <span style={stemStyle}>{STEM}</span>
        {slot}
      </div>
    </AbsoluteFill>
  );
};
