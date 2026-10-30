// white-flash-logo-simplify-cut — White Flash Simplify transition
// Liquid metal chromatic wordmark flows with light, charges energy, then detonates a white-flash overexposure from center; as exposure recovers, flat wordmark occupies exact position —
// single flash executes dimension reduction from "spectacle -> brand identity".
//
// Redesign (aurora: liquid metal -> paper final look):
// - look = aurora (dark spectacle); flash lands onto editing paper (brand palette: paper / ink / amber).
//   Wordmark is "video-shotcraft" (all-lowercase, 700 weight, 15 chars scaled to FS),
//   both versions share identical size and placement — perceived as "same wordmark purified" rather than an image swap.
// - Tactile liquid texture: 1) flowing iridescent base (violet -> pink -> peach -> ice blue, background-size 300%),
//   2) vertical volume lighting, 3) chrome horizon reflection streak across center waist, 4) diagonal sheen sweep (single hero pass,
//   clipped to glyphs), 5) bloom glow + floor reflection (inverted fade). Aurora backlight + dust motes.
// - Flash detonates from within typography: brightness surges, horizontal anamorphic flare expands from center,
//   radial white glare expands to fill entire frame within 6f (quadratic ease-in).
// - Recovery uses exposure decay rather than fade-in: white layer clears over 22f (quint-out) as eyes adjust — flat mark already in place,
//   settling 1.03->1 into focus; ShotcraftMark draws above (frame opens first, amber slash enters),
//   amber rule draws, tagline rises word-by-word to lock final composition.
//
// Timeline (30fps, total 120f):
//   0-34    Spectacle: liquid mark present from frame 0, iridescent flow, sheen sweeps 6-34f, frame slow push 1->1.035
//   34-46   Charge: brightness 1->1.7, bloom surges, anamorphic flare expands (ease-in)
//   44-50   White-out: radial white glare expands from center (quadratic ease-in), 50-54 solid white hold
//   54-76   Exposure recovery: white layer 1->0 (quint-out); flat wordmark settles 1.03->1
//   72-96   Lock: amber rule 72-86, mark draws 74-96, tagline rises 78f+
//   96-120  Hold: slow drift 1->1.01 to resting lock
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, Grain, Vignette, mix, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const WHITE_FLASH_LOGO_SIMPLIFY_CUT_DURATION = 120;

const L = LOOKS.aurora;
const WORD = BRAND.name; // Wordmark all-lowercase
const FS = 190; // Scaled for 15-character wordmark width
const CY = 500; // Wordmark center y
const FLASH0 = 44;
const WHITE = 50; // Full whiteout cut frame
const RECOVER = 54;

// Three brand colors: paper / ink / accent (video-shotcraft: edit paper / studio ink / mirror amber)
const PAPER: [string, string] = ['#f7f5f0', '#ebe7de'];
const FLAT_INK: string = BRAND.ink;
const FLAT_ACCENT: string = BRAND.amber;
const MARK = 124; // ShotcraftMark dimensions in lock phase

const wordStyle: React.CSSProperties = {
  fontFamily: BRAND.font, fontSize: FS, fontWeight: 700, letterSpacing: '0.03em', lineHeight: 1, whiteSpace: 'nowrap',
};

// Wordmark text: omit tracking after f in ft so crossbars merge cleanly without seam artifacts

const wordText = (
  <>{WORD.slice(0, WORD.lastIndexOf('f'))}<span style={{ letterSpacing: 0 }}>f</span>{WORD.slice(WORD.lastIndexOf('f') + 1)}</>
);

const IRIS = 'linear-gradient(100deg, #7c6bff 0%, #b18cff 16%, #f472b6 32%, #ffc6a8 46%, #8fdcff 62%, #7c6bff 78%, #c58cff 90%, #7c6bff 100%)';

const centered = (y: number): React.CSSProperties => ({
  position: 'absolute', left: 0, right: 0, top: y - FS * 0.5, height: FS, display: 'flex', justifyContent: 'center', alignItems: 'center',
});

// Liquid wordmark (layered backgrounds clipped to text)
const LiquidWord: React.FC<{ frame: number; bright: number }> = ({ frame, bright }) => {
  const flow = (frame * 1.1) % 300;
  const sheen = ramp(frame, 6, 28, EASE.swift); // Diagonal sheen single pass
  const sx = mix(-30, 130, sheen);
  const layers = [
    // Diagonal sheen (visible 6-34f)
    sheen > 0 && sheen < 1
      ? `linear-gradient(105deg, rgba(255,255,255,0) ${sx - 10}%, rgba(255,255,255,0.85) ${sx}%, rgba(255,255,255,0) ${sx + 10}%)`
      : 'linear-gradient(0deg, transparent, transparent)',
    // Chrome horizon: bright band + dark band across character waist
    'linear-gradient(180deg, rgba(255,255,255,0) 40%, rgba(255,255,255,0.34) 49%, rgba(255,255,255,0.1) 52%, rgba(40,10,70,0.28) 56%, rgba(40,10,70,0) 68%)',
    // Vertical volume: lit top, shadowed bottom
    'linear-gradient(180deg, rgba(255,255,255,0.45) 0%, rgba(255,255,255,0) 38%, rgba(20,5,40,0) 60%, rgba(20,5,40,0.45) 100%)',
    IRIS,
  ];
  return (
    <span style={{
      ...wordStyle,
      backgroundImage: layers.join(', '),
      backgroundSize: '100% 100%, 100% 100%, 100% 100%, 300% 100%',
      backgroundPosition: `0 0, 0 0, 0 0, ${flow}% 0`,
      WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
      filter: bright > 1.001 ? `brightness(${bright.toFixed(3)}) saturate(${(1 / Math.sqrt(bright)).toFixed(3)})` : undefined,
      paddingBottom: 20,
    }}>{wordText}</span>
  );
};

export const WhiteFlashLogoSimplifyCut: React.FC = () => {
  const frame = useCurrentFrame();

  // --- Spectacle phase ---
  const push = 1 + 0.035 * ramp(frame, 0, FLASH0, EASE.smooth);
  const charge = ramp(frame, 34, 12, EASE.exit); // Charge surge 0->1
  const bright = 1 + 0.7 * charge;
  const flare = ramp(frame, 34, 14, EASE.exit);

  // --- Whiteout phase ---
  const burst = ramp(frame, FLASH0, WHITE - FLASH0, (t) => t * t); // Radial white expansion (quadratic ease-in)
  const whiteHold = frame >= WHITE && frame < RECOVER ? 1 : 0;
  const recover = 1 - ramp(frame, RECOVER, 22, EASE.out); // Exposure recovery 1->0
  const whiteA = frame < WHITE ? burst : frame < RECOVER ? 1 : recover;

  // --- Lock phase ---
  const focus = ramp(frame, RECOVER - 2, 26, EASE.snappy);
  const flatScale = mix(1.03, 1, focus) * (1 + 0.01 * ramp(frame, 96, 24, EASE.smooth));
  const rule = ramp(frame, 72, 14, EASE.snappy);
  const mark = ramp(frame, 74, 14, EASE.snappy); // Mark viewfinder reveal
  const cut = ramp(frame, 84, 12, EASE.snappy); // Amber slash enters

  const dark = frame < WHITE;

  return (
    <AbsoluteFill style={{ overflow: 'hidden', background: dark ? L.bg[1] : PAPER[0] }}>
      {dark ? (
        <>
          <Stage look={L} keyLight={{ x: 0.5, y: 0.2 }} fill={{ x: 0.82, y: 0.85 }} breathe={0.6}>
            <Dust look={L} count={36} seed={4} drift={0.2} opacity={0.5} />
            {/* Aurora backlight behind text */}
            <div style={{
              position: 'absolute', left: 360, right: 360, top: CY - 260, height: 520,
              background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha('#a78bfa', 0.28 + 0.25 * charge)} 0%, ${alpha('#f472b6', 0.08)} 45%, rgba(0,0,0,0) 72%)`,
            }} />
          </Stage>

          <div style={{ position: 'absolute', inset: 0, transform: `scale(${push.toFixed(5)})`, transformOrigin: `50% ${CY}px` }}>
            {/* Bloom: colored blurred duplicate */}
            <div style={{ ...centered(CY), opacity: 0.42 + 0.4 * charge, filter: 'blur(38px)' }}>
              <span style={{ ...wordStyle, backgroundImage: IRIS, backgroundSize: '300% 100%', backgroundPosition: `${(frame * 1.1) % 300}% 0`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>{wordText}</span>
            </div>
            {/* Floor reflection: flipped + faded */}
            <div style={{
              ...centered(CY + FS * 0.86), transform: 'scaleY(-1)', opacity: 0.22,
              WebkitMaskImage: 'linear-gradient(0deg, #000 0%, rgba(0,0,0,0.4) 30%, transparent 62%)',
              maskImage: 'linear-gradient(0deg, #000 0%, rgba(0,0,0,0.4) 30%, transparent 62%)',
            }}>
              <LiquidWord frame={frame} bright={bright} />
            </div>
            {/* Main wordmark */}
            <div style={centered(CY)}>
              <LiquidWord frame={frame} bright={bright} />
            </div>
            {/* Anamorphic flare expanding from wordmark center */}
            {flare > 0 && (
              <>
                {/* Flare: soft outer halo + sharp bright core without drop shadow */}
                <div style={{
                  position: 'absolute', left: 960 - 1100 * flare, width: 2200 * flare, top: CY - 24, height: 48,
                  background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha('#e9e2ff', 0.55 * flare)} 0%, rgba(233,226,255,0) 100%)`,
                }} />
                <div style={{
                  position: 'absolute', left: 960 - 1000 * flare, width: 2000 * flare, top: CY - 2, height: 4,
                  background: `linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,${(0.95 * flare).toFixed(3)}) 50%, rgba(255,255,255,0) 100%)`,
                }} />
                <div style={{
                  position: 'absolute', left: 960 - 900 * flare, width: 1800 * flare, top: CY - 90, height: 180,
                  background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha('#d8ccff', 0.45 * flare)} 0%, rgba(216,204,255,0) 70%)`,
                }} />
              </>
            )}
          </div>
        </>
      ) : (
        <>
          {/* Paper background: cool white with soft top light + vignette + grain */}
          <AbsoluteFill style={{ background: `linear-gradient(180deg, ${PAPER[0]} 0%, ${PAPER[1]} 100%)` }} />
          <AbsoluteFill style={{ background: 'radial-gradient(ellipse 60% 55% at 50% 40%, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0) 70%)' }} />
          <Vignette strength={0.1} inner={0.5} color="#2a2620" />
          <div style={{ position: 'absolute', inset: 0, transform: `scale(${flatScale.toFixed(5)})`, transformOrigin: `50% ${CY}px` }}>
            <div style={centered(CY)}>
              <span style={{ ...wordStyle, color: FLAT_INK, paddingBottom: 20 }}>{wordText}</span>
            </div>
            {/* Lock phase: ShotcraftMark + amber rule + brand tagline */}
            <div style={{ position: 'absolute', left: 960 - MARK / 2, top: CY - FS * 0.5 - 44 - MARK }}>
              <ShotcraftMark size={MARK} tone="light" frameProgress={mark} cutProgress={cut} />
            </div>
            <div style={{
              position: 'absolute', left: 960 - 48, top: CY + FS * 0.5 + 62, width: 96, height: 5, borderRadius: 3,
              background: FLAT_ACCENT, transform: `scaleX(${rule.toFixed(4)})`,
            }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: CY + FS * 0.5 + 106, textAlign: 'center', color: '#716d64', ...type(46, 480) }}>
              <TextReveal text={PITCH.en.motto} by="word" variant="rise" start={78} each={18} gap={4} />
            </div>
          </div>
          <Grain opacity={0.04} />
        </>
      )}

      {/* White flash: radial expansion from center, full-screen whiteout, decaying with recovery */}
      {whiteA > 0.001 && (
        frame < WHITE ? (
          <AbsoluteFill style={{
            background: `radial-gradient(circle ${(80 + burst * 1500).toFixed(1)}px at 50% ${CY}px, rgba(255,255,255,1) 0%, rgba(255,255,255,${(0.6 + 0.4 * burst).toFixed(3)}) 55%, rgba(255,255,255,0) 100%)`,
            opacity: Math.min(1, burst * 1.4),
          }} />
        ) : (
          <AbsoluteFill style={{ background: '#ffffff', opacity: whiteHold ? 1 : whiteA }} />
        )
      )}
    </AbsoluteFill>
  );
};
