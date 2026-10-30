// fracture — Fracture Reassemble (motion-lab final port to native Remotion)
// 5x5 tiles reassemble from 3D random fragment states (large displacement + 3-axis rotation) into a unified poster,
// rippling into position based on Manhattan distance from center. Following a hold, all fragments accelerate and rotate outward away from center off-screen.
// Forward = opening, reverse = transition. Design coordinates 480x270 (scaled proportionally via DesignStage).
//
// Polish details:
// - All 25 tiles slice from the same unified poster (each tile offsets background-position by its grid cell), revealing the full picture only on reassembly
//   rather than 25 disconnected color blocks; Poster = cool dark field + top-left soft key + bottom glowing horizon arc + title
// - Title is printed onto the poster (each tile carries its slice of typography) and illuminates during hold; on exit, typography fragments and tears away with the tiles
// - Tiles shaded by surface normal relative to camera, with 1px top edge specular highlight; damped wobble on landing (~10f) gives a physical snap into slot
// - Poster subtly pushes in 3% during hold; flight phases (reassemble / scatter) wrapped in CameraMotionBlur, hold remains crisp
// - Backdrop upgraded from flat #0b0b10 to subtle ambient gradient + backlight expanding with assembly progress
// - DesignStage uses raster="zoom": typography within 3D tiles rasterizes at target resolution without bitmap scaling artifacts
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';
import { DesignStage, E, rand, seg, useT } from '../../_fixtures/Motion';
import { bezier, Backdrop, FONT, Grain } from '../../_fixtures/Polish';
import { ShotcraftWordmark } from '../../_fixtures/Brand';

export const FRACTURE_DURATION = 156; // 5200ms @30fps

const N = 5;
const ACCENT_HUE = 218; // Template accent hue, customizable per project (poster palette derives from it)
const PW = 380; // Poster design dimensions (reassembled)
const PH = 230;
const TW = PW / N; // 76 — tile width
const TH = PH / N; // 46
const SEAM = 0.5; // Seam (design px, scales to 2px) — preserves tile structure without clipping glyphs

// Reassembly curve: soft start, rapid midpoint, extended deceleration into slot (snaps in tighter than symmetric inOutCubic)
const landEase = bezier(0.42, 0, 0.3, 1);

// Full poster artwork (drawn at PWxPH; each tile crops its own cell)
const h = ACCENT_HUE;
const POSTER_BG = [
  // Bottom horizon glow arc: thin bright ring + soft outer halo
  `radial-gradient(circle at 64% 168%, rgba(0,0,0,0) 0 61%, hsla(${h},80%,78%,0.85) 61.6%, hsla(${h},70%,62%,0.28) 63.2%, hsla(${h},60%,50%,0) 70%)`,
  // Ground glow inside arc
  `radial-gradient(ellipse 70% 55% at 64% 100%, hsla(${h},70%,55%,0.32) 0%, hsla(${h},70%,45%,0) 70%)`,
  // Top-left key light
  `radial-gradient(ellipse 55% 75% at 18% 0%, hsla(${h},45%,78%,0.30) 0%, hsla(${h},45%,70%,0) 65%)`,
  // Base: vertical gradient in cool dark field
  `linear-gradient(165deg, hsl(${h},30%,21%) 0%, hsl(${h},34%,12%) 55%, hsl(${h},38%,8%) 100%)`,
].join(', ');

// Tile parameter table: cell pos + entry fragment state + exit direction (seeds match effect.js)
const TILES = Array.from({ length: N * N }, (_, seed) => {
  const r = Math.floor(seed / N);
  const c = seed % N;
  // Exit vector: radiates away from frame center (random angle for center tile) ensuring all fragments clear frame
  const ang =
    r === 2 && c === 2
      ? rand(seed + 300) * Math.PI * 2
      : Math.atan2(r - 2 + (rand(seed + 310) - 0.5) * 0.8, c - 2 + (rand(seed + 320) - 0.5) * 0.8);
  return {
    r,
    c,
    dx: (rand(seed) - 0.5) * 900,
    dy: (rand(seed + 50) - 0.5) * 600,
    dz: (rand(seed + 100) - 0.3) * 700,
    rx: (rand(seed + 150) - 0.5) * 360,
    ry: (rand(seed + 200) - 0.5) * 360,
    rz: (rand(seed + 250) - 0.5) * 360,
    exX: Math.cos(ang) * (620 + rand(seed + 330) * 260),
    exY: Math.sin(ang) * (470 + rand(seed + 340) * 220),
    exR: (rand(seed + 350) - 0.5) * 300,
    wob: rand(seed + 360) < 0.5 ? -1 : 1, // Damped settle wobble direction
    delay: (Math.abs(r - 2) + Math.abs(c - 2)) * 0.045,
  };
});

// Poster typography: eyebrow + video-shotcraft logotype (mark + lowercase text; stamped onto poster and sliced with tiles)
const PosterType: React.FC<{ on: number }> = ({ on }) => (
  <div
    style={{
      position: 'absolute',
      left: 0,
      top: 0,
      width: PW,
      height: PH,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 6,
      // Bottom padding 16 (= eyebrow height + gap): wordmark center lands exactly on row 3 tile center (y=115), mark avoids horizontal seam
      paddingBottom: 16,
      boxSizing: 'border-box',
      fontFamily: FONT.sans,
      color: '#f3f5fb',
      opacity: on,
    }}
  >
    <div style={{ fontSize: 8.5, fontWeight: 600, letterSpacing: '0.24em', color: `hsla(${h},70%,86%,0.85)` }}>
      INTRODUCING
    </div>
    {/* Centered at size 22, mark sits inside column 2 tile (x≈76–119), avoiding vertical seam */}
    <ShotcraftWordmark size={22} tone="dark" gap={9} />
  </div>
);

const Scene: React.FC = () => {
  const t = useT();
  const T = FRACTURE_DURATION - 1; // t -> frame conversion
  const typeOn = seg(t, 0.42, 0.52, E.outCubic);
  // Subtle camera push during hold (starts at 0.45, maintains velocity through scatter)
  const push = 1 + 0.03 * seg(t, 0.45, 1, E.inOutQuad);
  // Reassembly progress -> ambient backlight behind poster
  const whole = seg(t, 0.28, 0.55, E.outCubic) * (1 - seg(t, 0.7, 0.86, E.inQuad));
  return (
    <DesignStage raster="zoom">
      <Backdrop tone="dark" light={{ x: 0.5, y: 0.08 }} accent={`hsl(${h},70%,60%)`} grain={0} vignette={0.55} />
      {/* Ambient backlight: illuminates on reassembly as if poster glows */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: `radial-gradient(ellipse 52% 56% at 50% 52%, hsla(${h},70%,58%,0.26) 0%, hsla(${h},70%,50%,0) 70%)`,
          opacity: whole,
        }}
      />
      <div style={{ position: 'absolute', inset: 0, perspective: 900, overflow: 'hidden' }}>
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: PW,
            height: PH,
            margin: `${-PH / 2}px 0 0 ${-PW / 2}px`,
            transformStyle: 'preserve-3d',
            transform: `scale(${push})`,
          }}
        >
          {TILES.map((tl, i) => {
            const land = tl.delay + 0.34;
            const tin = seg(t, tl.delay, land, landEase);
            // Tightened exit window: latest corner tile launches at 0.79, clears by 0.97
            const tout = seg(t, 0.7 + tl.delay * 0.5, 0.7 + tl.delay * 0.5 + 0.18, E.inCubic);
            const inv = 1 - tin; // Entrance: fragment state -> seated
            // Slot settle wobble: damped rotateX wobble (<=2.5 deg) + subtle z dip within ~10f after landing
            const since = (t - land) * T; // Frames elapsed since landing
            const settle = since > 0 && since < 14 ? Math.exp(-since / 3.2) * Math.sin(since * 0.75) : 0;
            const rx = tl.rx * inv + tl.wob * 2.5 * settle;
            const ry = tl.ry * inv;
            const rz = tl.rz * inv + tl.exR * tout;
            const tz = tl.dz * inv - 4 * Math.abs(settle);
            // Directional shading: darker when normal tilts away from camera (cos theta = cos rx * cos ry)
            const facing = Math.abs(Math.cos((rx * Math.PI) / 180) * Math.cos((ry * Math.PI) / 180));
            const shade = (1 - facing) * 0.6;
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: tl.c * TW + SEAM / 2,
                  top: tl.r * TH + SEAM / 2,
                  width: TW - SEAM,
                  height: TH - SEAM,
                  borderRadius: 1.6,
                  overflow: 'hidden',
                  transform: `translate3d(${tl.dx * inv + tl.exX * tout}px,${tl.dy * inv + tl.exY * tout}px,${tz}px)
          rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${rz}deg)`,
                  opacity: Math.min(1, tin * 2.5), // Physical exit without fading out
                  boxShadow: `inset 0 0.35px 0 rgba(255,255,255,0.16), inset 0 0 0 0.3px rgba(255,255,255,0.07)`,
                }}
              >
                {/* Poster slice for this cell (background + text), offset inversely by grid position */}
                <div style={{ position: 'absolute', left: -tl.c * TW - SEAM / 2, top: -tl.r * TH - SEAM / 2, width: PW, height: PH, background: POSTER_BG }}>
                  <PosterType on={typeOn} />
                </div>
                {/* Directional shading */}
                {shade > 0.004 && <div style={{ position: 'absolute', inset: 0, background: `rgba(4,6,12,${shade.toFixed(3)})` }} />}
              </div>
            );
          })}
        </div>
      </div>
    </DesignStage>
  );
};

export const Fracture: React.FC = () => {
  const t = useT();
  // Apply motion blur only during flight: assemble (t<0.53) and scatter (t>0.7); hold remains sharp for legibility
  const flying = t < 0.53 || t > 0.7;
  return (
    <AbsoluteFill>
      {flying ? (
        <CameraMotionBlur shutterAngle={170} samples={8}>
          <Scene />
        </CameraMotionBlur>
      ) : (
        <Scene />
      )}
      {/* Grain placed outside blur (multisampling would smooth it away) */}
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
