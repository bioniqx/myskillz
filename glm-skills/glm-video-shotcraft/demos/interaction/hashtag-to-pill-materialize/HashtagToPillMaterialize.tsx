// hashtag-to-pill-materialize (bear-app 18-21.5s remake, frame-by-frame calibrated)
// Calibrated rhythm (25fps reference):
//  1) White bg centered typing "#music": geometric sans-serif (Futura aesthetic), mid-gray ink, solid red non-blinking cursor, human typing cadence
//  2) Materialization = 1-frame cut: text + cursor -> broad light gray borderless capsule + gray icon + "music" (same font size, # replaced by icon)
//  3) Hold ~0.6s -> smoothly scales down (~0.55x) and moves left into page tag slot (~0.55s, easeInOut)
//  4) Another 1-frame cut reveals final note page: cream base, forest green headline "My favorite shots", capsule switches to sage green, 3 lines of body —
//     (pure direct cut to finished page without extra card fly-ins)
// Polish pass: subtle paper texture gradient + grain on both backgrounds; capsule is tactile solid — top highlight
// inner glow + subtle volumetric gradient + elevation shadow (floats 10px in hero state, drops to 0 on landing, embedding into page);
// directional motion blur along movement vector; final page includes header metadata (breadcrumbs + edit timestamp).
// Hard cuts, ease curves, and all timing checkpoints preserved.
// Brand adaptation: topic tag "#music" -> "#shots" (same character count), musical note replaced with clapperboard,
// final page showcases video-shotcraft shots (headline "My favorite shots").
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from 'remotion';
import { Grain, SpeedBlur, velocity } from '../../_fixtures/Polish';

// Reveal at 83f followed by 37f hold (~1.2s breathing, R1), total 4s
export const HASHTAG_TO_PILL_MATERIALIZE_DURATION = 120;
const FONT = "Futura, 'Century Gothic', 'Avenir Next', 'Trebuchet MS', sans-serif";

const C = {
  bgWhite: 'linear-gradient(180deg, #fdfdfc 0%, #fbfbfa 60%, #f6f6f3 100%)',
  bgCream: 'linear-gradient(180deg, #f6f3e8 0%, #f3f0e4 55%, #eeeadc 100%)',
  meta: '#a7a392',
  ink: '#454543',
  cursor: '#e0453f',
  pillGray: '#e9e9e7',
  pillTextGray: '#4b4b49',
  iconGray: '#7e7e7c',
  pillSage: '#d5e0cf',
  iconSage: '#5c7a63',
  titleGreen: '#2d5c47',
  pillSageText: '#3f5e4c',
  body: '#4c4b43',
};

// ---- mulberry32 (deterministic pseudo-random generator for typing jitter) ----
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const TEXT = '#shots';
// Typing start & per-character cadence (frames), 4-8 frames with human cadence jitter
const TYPE_START = 8;
const rand = mulberry32(20260717);
const TYPE_AT: number[] = (() => {
  const at: number[] = [];
  let f = TYPE_START;
  for (let i = 0; i < TEXT.length; i++) {
    at.push(f);
    f += 4 + Math.floor(rand() * 3); // 4-6 frames (~6 chars/sec)
  }
  return at;
})();

// ---- Timeline (30fps, total 132 frames, aligned to reference 18-21.5s) ----
const MORPH = 48;       // 1-frame cut materialization (hold ~0.5s after typing)
const MOVE_START = 66;  // Capsule starts scale-down and move left (0.6s post morph)
const MOVE_END = 80;    // Settles into slot (0.47s)
const REVEAL = 83;      // 1-frame cut reveals final page, static hold to tail

// ---- Geometry (1920x1080 scaled from 1280x720 reference) ----
const FS = 132;                       // Font size for typing and capsule text
const HERO = { x: 960, y: 540 };      // Large capsule center
const PILL_W = 740, PILL_H = 236;     // 493x157 @720p x 1.5
const END_SCALE = 0.554;              // Target scale (273/493)
const SLOT = { x: 361, y: 473 };      // Tag slot center position

// Clapperboard icon: clapper board body + angled clapper top with masked chevron stripes
const ClapperIcon: React.FC<{ size: number; color: string }> = ({ size, color }) => {
  const id = React.useId().replace(/[^a-zA-Z0-9]/g, '');
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" style={{ display: 'block' }}>
      <defs>
        <mask id={`k${id}`}>
          <rect x="0" y="0" width="48" height="48" fill="#fff" />
          {[0, 1, 2].map((i) => (
            <polygon key={i} points={`${11 + i * 10},8 ${15.5 + i * 10},8 ${19.5 + i * 10},18 ${15 + i * 10},18`} fill="#000" />
          ))}
        </mask>
      </defs>
      <rect x="4" y="21" width="40" height="23" rx="3.5" fill={color} />
      <g transform="rotate(-17 5 19.5)">
        <rect x="4" y="9" width="40" height="9" rx="2" fill={color} mask={`url(#k${id})`} />
      </g>
    </svg>
  );
};

// Capsule (rendered at large font size, scaled via transform ensuring size match during materialization)
// lift = elevation height (px): elevated in hero state, drops to 0 flush with page
const Pill: React.FC<{ bg: string; iconColor: string; textColor: string; lift: number }> = ({ bg, iconColor, textColor, lift }) => (
  <div style={{
    width: PILL_W, height: PILL_H, borderRadius: PILL_H / 2,
    // Borderless: volume conveyed via top highlight + micro-gradient + elevation shadow
    background: `linear-gradient(180deg, rgba(255,255,255,0.32) 0%, rgba(255,255,255,0) 46%, rgba(0,0,0,0.025) 100%), ${bg}`,
    boxShadow: `inset 0 3px 0 rgba(255,255,255,0.7), inset 0 -2px 0 rgba(40,40,30,0.03), ` +
      `0 ${(1 + lift * 0.12).toFixed(1)}px ${(2 + lift * 0.3).toFixed(1)}px rgba(40,40,30,${(0.04 + lift * 0.003).toFixed(3)}), ` +
      `0 ${(lift * 1.6).toFixed(1)}px ${(lift * 4).toFixed(1)}px ${(-lift * 0.6).toFixed(1)}px rgba(40,40,30,${(lift * 0.009).toFixed(3)})`,
    display: 'flex', alignItems: 'center', paddingLeft: 96, boxSizing: 'border-box', gap: 66,
  }}>
    <ClapperIcon size={104} color={iconColor} />
    <span style={{ fontSize: FS, fontWeight: 500, color: textColor, letterSpacing: 2 }}>shots</span>
  </div>
);

export const HashtagToPillMaterialize: React.FC = () => {
  const frame = useCurrentFrame();

  // ---- Typing ----
  const typedCount = TYPE_AT.filter((t) => frame >= t).length;
  const typed = TEXT.slice(0, typedCount);

  // ---- Scale down and move left ----
  const moveAt = (f: number) => interpolate(f, [MOVE_START, MOVE_END], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.5, 0, 0.25, 1),
  });
  const pxAt = (f: number) => interpolate(moveAt(f), [0, 1], [HERO.x, SLOT.x]);
  const pyAt = (f: number) => interpolate(moveAt(f), [0, 1], [HERO.y, SLOT.y]);
  const moveT = moveAt(frame);
  const px = pxAt(frame);
  const py = pyAt(frame);
  const ps = interpolate(moveT, [0, 1], [1, END_SCALE]);
  // Peak speed ~70px/frame: motion blur along velocity vector, tapering naturally at endpoints
  const vx = velocity(pxAt, frame);
  const vy = velocity(pyAt, frame);
  // Elevation: 10px during hero hold, descends in second half of travel, flush on arrival
  const lift = 10 * (1 - interpolate(moveT, [0.35, 1], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }));
  // Subtle settle on materialization (3 frames 1.03->1)
  const settle = interpolate(frame, [MORPH, MORPH + 3], [1.03, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad),
  });

  const revealed = frame >= REVEAL;

  return (
    <AbsoluteFill style={{ background: revealed ? C.bgCream : C.bgWhite, fontFamily: FONT }}>
      {/* Final page (cut reveal, followed by static hold) */}
      {revealed && (
        <>
          {/* Header metadata: breadcrumb + edit timestamp (32px, low contrast) */}
          <div style={{
            position: 'absolute', left: 164, right: 160, top: 86, display: 'flex', alignItems: 'center',
            fontSize: 32, fontWeight: 500, color: C.meta, letterSpacing: 0.6,
          }}>
            <span>Notes</span>
            <span style={{ margin: '0 18px', opacity: 0.7 }}>/</span>
            <span>Shots</span>
            <span style={{ marginLeft: 'auto' }}>Edited just now</span>
          </div>
          <div style={{
            position: 'absolute', left: 164, right: 160, top: 144, height: 1,
            background: 'linear-gradient(90deg, rgba(120,112,80,0.16), rgba(120,112,80,0.06))',
          }} />
          <div style={{
            position: 'absolute', left: 160, top: 168,
            fontSize: 122, fontWeight: 700, color: C.titleGreen, letterSpacing: 0.5,
          }}>
            My favorite shots
          </div>
          <div style={{
            position: 'absolute', left: 152, top: 618,
            fontSize: 70, fontWeight: 500, color: C.body, lineHeight: 1.33, letterSpacing: 0.3,
          }}>
            A few camera moves I keep stealing from<br />
            video-shotcraft: the crash zoom, the orbit,<br />
            the whip pan. Welcome. Bring popcorn.
          </div>
        </>
      )}

      {/* Typing layer: text + solid red cursor (non-blinking), disappears at morph */}
      {frame < MORPH && (
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span style={{ fontSize: FS, fontWeight: 500, color: C.ink, letterSpacing: 2, whiteSpace: 'pre' }}>
              {typed}
            </span>
            <span style={{
              display: 'inline-block', width: 7, height: 150,
              background: C.cursor, marginLeft: 8, borderRadius: 2,
            }} />
          </div>
        </AbsoluteFill>
      )}

      {/* Capsule layer: 1-frame cut appearance -> hold -> travel to slot -> switches to sage green on reveal */}
      {frame >= MORPH && (
        <SpeedBlur vx={vx} vy={vy} amount={0.1} max={7}>
        <div style={{
          position: 'absolute', left: 0, top: 0,
          // origin must be 0 0: translate places origin at target center, scale pivots around it,
          // avoiding default 50% 50% offset drift of (1-s) * halfWidth
          transformOrigin: '0 0',
          transform: `translate(${px}px, ${py}px) scale(${ps * settle})`,
        }}>
          <div style={{ transform: 'translate(-50%, -50%)' }}>
            {revealed
              ? <Pill bg={C.pillSage} iconColor={C.iconSage} textColor={C.pillSageText} lift={0} />
              : <Pill bg={C.pillGray} iconColor={C.iconGray} textColor={C.pillTextGray} lift={lift} />}
          </div>
        </div>
        </SpeedBlur>
      )}
      {/* Subtle paper grain: prevents banding on flat tints, cuts cleanly with background */}
      <Grain opacity={0.05} step={2} />
    </AbsoluteFill>
  );
};
