// blinds-slice: staggered vertical blinds flip transition
// 12 vertical 160px slats flip left-to-right staggered, transitioning scene from A to B as the wave passes.
//
// Redesign (paper: Swiss grid magazine page flip):
// - look = paper. Two pages of video-shotcraft publication: Page A warm white paper + ink headline "Frame.",
//   Page B solid vermilion + cream headline "Craft." ("Frame motion. Craft the shot."). High contrast clarifies slat rotation wave.
//   12-column grid layout (160px per column with visible hairlines) — each column equals one slat, aligning structure with motion.
// - True 3D slats: preserve-3d double-sided panels (front A slice, back B slice, backface hidden), rotating around vertical axis
//   rotateY 0->180 deg with 1900px perspective — edge-on at 90 deg reveals dark recess behind slats.
//   Illumination: surfaces facing away dim via sin(theta), surfaces facing key light sweep specular highlight at ~35 deg; bright slat edge line.
// - Rhythm: physical spring flip per slat (damping 13 / stiffness 75: ~13f travel, ~5 deg overshoot settle);
//   staggered start along t^0.78 curve (interval 3.4f -> 2.1f accelerating); subtle camera push 1->1.02->1 during wave.
// - Unmask on wave completion (3D structure unmounts, Page B renders natively sharp); cream hairline draws across top header, page number ticks to 02.
//
// Timeline (30fps, total 132f):
//   0-24    Page A hold (camera slow push 1->1.006)
//   24-52   Launch: slat i starts flipping at 24 + stagger(i, 12, 28, t^0.78)
//   24-~76  Flip: each slat ~13f travel with ~5 deg overshoot; dark shadow wave traverses
//   ~80     Unmask: after final slat converges (|theta-180| < 0.3 deg for 4 frames), Page B renders native
//   82-102  Aftermath: header line draws across, camera settles back to 1
//   102–132 hold
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, Grain, Vignette, ramp } from '../../_fixtures/Polish';
import { LOOKS, alpha, springAt, stagger, type } from '../../_fixtures/Look';
import { ShotcraftWordmark } from '../../_fixtures/Brand';

export const BLINDS_SLICE_DURATION = 132;

const L = LOOKS.paper;
const STRIPS = 12;
const W = 160; // 12 x 160 = 1920 (12 layout columns)
const WAVE0 = 24;
const SPAN = 28; // Total stagger launch duration
// t^0.78: interval tightens 3.4f -> 2.1f for accelerating wave without sluggish initial gap
const startOf = (i: number) => WAVE0 + stagger(i, STRIPS, SPAN, (t) => Math.pow(t, 0.78));
const angleOf = (f: number, i: number) => {
  const s = startOf(i);
  return f < s ? 0 : 180 * springAt(f, s, { damping: 13, stiffness: 75 });
};
// Unmask frame: after final slat converges (|theta-180| < 0.3 deg)
const UNMASK = (() => {
  for (let f = startOf(STRIPS - 1); f < 200; f++) {
    let ok = true;
    for (let k = 0; k < 4; k++) if (Math.abs(angleOf(f + k, STRIPS - 1) - 180) > 0.3) ok = false;
    if (ok) return f;
  }
  return 80;
})();

const RED = '#e5432d';
const CREAM = '#fffaf3';

// ------------- Page Layouts (A & B) -------------
type PageProps = { mark: 'dark' | 'light'; bg: string; ink: string; sub: string; accent: string; line: string; chapter: string; word: string; dot: string; body: string; page: string; rule?: number };

const Page: React.FC<PageProps> = ({ mark, bg, ink, sub, accent, line, chapter, word, dot, body, page, rule = 1 }) => (
  <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, background: bg, overflow: 'hidden' }}>
    {/* 12-column grid hairlines */}
    {Array.from({ length: STRIPS - 1 }, (_, i) => (
      <div key={i} style={{ position: 'absolute', left: (i + 1) * W, top: 0, bottom: 0, width: 1, background: line }} />
    ))}
    {/* Header */}
    <div style={{ position: 'absolute', left: 96, right: 96, top: 92, display: 'flex', alignItems: 'baseline', color: ink }}>
      {/* Header wordmark: video-shotcraft (all lowercase) */}
      <div style={{ width: 480, alignSelf: 'center' }}>
        <ShotcraftWordmark size={30} markScale={1.6} gap={14} tone={mark} color={ink} />
      </div>
      <div style={{ ...type(28, 500), color: sub, flex: 1 }}>Shot Recipe Journal</div>
      <div style={{ ...type(26, 500, { mono: true }), color: sub }}>Nº 07 — 2026</div>
    </div>
    <div style={{ position: 'absolute', left: 96, right: 96, top: 152, height: 2, background: ink, transform: `scaleX(${rule})`, transformOrigin: '0 50%' }} />
    {/* Top right: chapter + body (columns 8-12) */}
    <div style={{ position: 'absolute', left: 7 * W, top: 250, width: 4 * W + 40, color: ink }}>
      <div style={{ ...type(28, 800, { caps: true }), letterSpacing: '0.2em', color: accent }}>{chapter}</div>
      <div style={{ ...type(52, 560), lineHeight: 1.14, letterSpacing: '-0.025em', marginTop: 26, whiteSpace: 'pre-line' }}>{body}</div>
    </div>
    {/* Headline: starts column 1 with descender clearance */}
    <div style={{
      position: 'absolute', left: 84, bottom: 156, color: ink, fontFamily: FONT.sans, fontSize: 400, fontWeight: 850,
      letterSpacing: '-0.065em', lineHeight: 0.8, whiteSpace: 'nowrap',
    }}>
      {word}<span style={{ color: dot }}>.</span>
    </div>
    <div style={{ position: 'absolute', right: 96, bottom: 168, color: sub, ...type(28, 500, { mono: true }) }}>{page}</div>
  </div>
);

const PageA: React.FC = () => (
  <Page mark="light" bg="#f3eee4" ink={L.ink} sub={L.ink2} accent={RED} line={alpha(L.ink, 0.07)} chapter="Chapter 01"
    word="Frame" dot={RED} body={"Shot recipes for\ncinematic product films."} page="01 / 02" />
);
const PageB: React.FC<{ rule?: number }> = ({ rule }) => (
  <Page mark="dark" bg={RED} ink={CREAM} sub={alpha(CREAM, 0.72)} accent={L.ink} line={alpha(CREAM, 0.13)} chapter="Chapter 02"
    word="Craft" dot={L.ink} body={"Direct the film.\nLet the agent shoot it."} page="02 / 02" rule={rule} />
);

// Slat slice: outer 160px clip with inner negative offset
const Slice: React.FC<{ x: number; children: React.ReactNode }> = ({ x, children }) => (
  <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
    <div style={{ position: 'absolute', left: -x, top: 0, width: 1920, height: 1080 }}>{children}</div>
  </div>
);

// Slat surface lighting: shadow when facing away + specular sheen when facing key light (theta 0-90 deg)
const FaceLight: React.FC<{ th: number; lead: 'left' | 'right' }> = ({ th, lead }) => {
  const r = (th * Math.PI) / 180;
  const shade = 0.5 * Math.sin(r);
  const spec = 0.22 * Math.max(0, Math.cos((th - 35) * (Math.PI / 70))) * Math.sin(r * 2 > Math.PI ? Math.PI : r * 2);
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: `linear-gradient(${lead === 'left' ? 90 : 270}deg, rgba(20,12,6,${(shade * 0.7).toFixed(3)}) 0%, rgba(20,12,6,${shade.toFixed(3)}) 100%)`,
      }} />
      {spec > 0.005 && <div style={{ position: 'absolute', inset: 0, background: `rgba(255,248,236,${spec.toFixed(3)})`, mixBlendMode: 'screen' }} />}
      {/* Bright slat edge line */}
      <div style={{ position: 'absolute', top: 0, bottom: 0, [lead]: 0, width: 2, background: `rgba(255,250,240,${(0.7 * Math.sin(r)).toFixed(3)})` } as React.CSSProperties} />
    </>
  );
};

export const BlindsSlice: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = 1 + 0.006 * ramp(frame, 0, WAVE0, EASE.smooth)
    + 0.014 * ramp(frame, WAVE0, 26, EASE.smooth) * (1 - ramp(frame, 60, 34, EASE.smooth));
  const rule = frame < UNMASK ? 1 : ramp(frame, UNMASK + 2, 20, EASE.snappy);

  let body: React.ReactNode;
  if (frame < startOf(0)) {
    body = <PageA />;
  } else if (frame >= UNMASK) {
    // Unmask: Page B native render, header line draws across as post-flip settle beat
    body = <PageB rule={rule} />;
  } else {
    body = (
      <>
        {/* Recessed dark groove revealed behind vertical slats */}
        <AbsoluteFill style={{ background: 'linear-gradient(180deg, #1d1712 0%, #120d0a 100%)' }} />
        <div style={{ position: 'absolute', inset: 0, perspective: 1900, perspectiveOrigin: '50% 50%' }}>
          {Array.from({ length: STRIPS }, (_, i) => {
            const x = i * W;
            const th = angleOf(frame, i);
            const front = th < 90;
            return (
              <div key={i} style={{
                position: 'absolute', left: x, top: 0, width: W, height: 1080, transformStyle: 'preserve-3d',
                transform: `rotateY(${(-th).toFixed(3)}deg)`, transformOrigin: '50% 50%',
              }}>
                {/* Front: Page A slice */}
                <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', overflow: 'hidden' }}>
                  <Slice x={x}><PageA /></Slice>
                  {front && th > 0.05 && <FaceLight th={th} lead="left" />}
                </div>
                {/* Back: Page B slice (pre-rotated 180 deg) */}
                <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden', WebkitBackfaceVisibility: 'hidden', overflow: 'hidden', transform: 'rotateY(180deg)' }}>
                  <Slice x={x}><PageB /></Slice>
                  {!front && Math.abs(180 - th) > 0.05 && <FaceLight th={Math.min(90, Math.abs(180 - th))} lead="right" />}
                </div>
              </div>
            );
          })}
        </div>
      </>
    );
  }

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam.toFixed(5)})`, transformOrigin: '50% 50%' }}>
        {body}
      </div>
      {/* Shared vignette and grain layer */}
      <Vignette strength={0.2} inner={0.5} color={L.shadow} />
      <Grain opacity={0.06} />
    </AbsoluteFill>
  );
};
