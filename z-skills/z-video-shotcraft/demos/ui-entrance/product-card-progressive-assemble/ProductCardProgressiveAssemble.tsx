// product-card-progressive-assemble — Detail card self-assembles as if fetched field by field
// Image → Title → Category pills → Price (original price struck-through & discounted, new price spring-pops) → Body lines + marker highlight → Swatches → Button,
// Entire card pushes forward ultra-slowly. Price markdown is the sole "mutation" event in the shot, positioned prominently in the middle.
//
// Round 2 redesign (Porcelain · Autofilling product detail page):
// - look = porcelain (cool white + cobalt blue). Redrawn in native 1920 coordinates: a 1520x840 detail card occupying 79% frame width,
//   left 640px studio shot (video-shotcraft mark as studio subject + seamless cyclorama backdrop + contact shadow), right fields set in real font sizes:
//   Title 108px, Price 112px, Body 34px, Pill 28px — no longer small text scaled up from a 480x270 canvas.
// - Technique refinement: A cobalt blue "autofill cursor" (stroked bounding box + AUTOFILL badge) jumps 2–3f ahead of each field into its slot,
//   its bounding box morphing with asymmetric in-out easing between fields; slots show light gray skeleton bars before fields land, fading as content rises
//   — visually conveying "a form being automatically filled field by field". Cursor is the sole hero visual effect (Q4), finally collapsing into the button.
// - Price event: $449 lands completely and holds for 18f, then within 6f simultaneously "shrinks + grays out + strikethrough sweeps from left", cobalt new price
//   Free (Apache-2.0 open source) spring-settles (damping 14) from 1.18 to 1, OPEN SOURCE chip slides in 6f later.
// - Marker highlight: Cobalt blue 16% backdrop scaleX 0→1 sweeps left-to-right in 6f, faster than field landing.
// - Finale: Button fill sweeps left-to-right (ink black), cursor collapses into button and fades out.
//
// Timeline (30fps, 172f total):
//   0–14    Card rises and settles (scale .96→1 + 30px upward, expo-out), skeleton slots in place
//   8–24    Cursor → Image: Studio shot reveals (defocus→sharp + product 1.08→1 slow settle)
//   20–34   Cursor → Title: Characters rise sequentially
//   30–44   Cursor → Pills: 3 staggered pops (3f interval, overshoot)
//   42–56   Cursor → Price: $449 lands
//   62–80   Price markdown (6f snap) + new price Free spring + chip
//   76–96   Cursor → Body: 3 lines staggered rise (3f), two highlights sweep at 86/90
//   96–112  Cursor → Swatches: 4 pops (3f) + swatch name
//   114–128 Cursor → Button: Background fills left-to-right, cursor collapses into button and vanishes
//   0–132   Entire card pushes forward 1→1.035 (asymmetric in-out)
//   132–172 Hold 40f, clean freeze
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const PRODUCT_CARD_PROGRESSIVE_ASSEMBLE_DURATION = 172;

const L = LOOKS.porcelain;
const BLUE = L.accent;

// Card geometry (frame coordinates)
const CW = 1520;
const CH = 840;
const CL = (1920 - CW) / 2;
const CT = (1080 - CH) / 2 + 6;
const PAD = 60;
const IMG = { x: PAD, y: PAD, w: 640, h: CH - PAD * 2 };
const COL = PAD + 640 + 64; // Right column x (card local)
const COLW = CW - COL - PAD;

// Field slots (card local coordinates) + cursor arrival frames
type Box = { x: number; y: number; w: number; h: number };
const F = {
  img: { box: { ...IMG }, at: 8 },
  title: { box: { x: COL, y: 66, w: 560, h: 150 }, at: 20 },
  pills: { box: { x: COL, y: 244, w: 560, h: 52 }, at: 30 },
  price: { box: { x: COL, y: 322, w: 670, h: 112 }, at: 42 }, // w 670: encloses OPEN SOURCE chip
  body: { box: { x: COL, y: 462, w: COLW, h: 150 }, at: 76 },
  swatch: { box: { x: COL, y: 636, w: 520, h: 56 }, at: 96 },
  cta: { box: { x: COL, y: 716, w: COLW, h: 64 }, at: 114 },
};
const ORDER: (keyof typeof F)[] = ['img', 'title', 'pills', 'price', 'body', 'swatch', 'cta'];
const HOP = 6; // Cursor jump duration (frames)
const LAND = 2; // Field lands this many frames after cursor arrives
const PRICE_DROP = 62;

const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

// Current cursor bounding box: swift interpolation between adjacent field boxes
const cursorBox = (f: number): Box & { k: number } => {
  let prev = F[ORDER[0]].box as Box;
  for (let i = 0; i < ORDER.length; i++) {
    const cur = F[ORDER[i]];
    const t0 = cur.at - HOP;
    if (f < cur.at) {
      const k = i === 0 ? 1 : ramp(f, t0, HOP, EASE.swift);
      const b = cur.box as Box;
      return { x: mix(prev.x, b.x, k), y: mix(prev.y, b.y, k), w: mix(prev.w, b.w, k), h: mix(prev.h, b.h, k), k };
    }
    prev = cur.box as Box;
  }
  return { ...prev, k: 1 };
};

// Field landing: skeleton fades + content rises 18px with blur fade-in (snappy 14f)
const landP = (f: number, key: keyof typeof F, extra = 0) => ramp(f, F[key].at + LAND + extra, 14, EASE.snappy);
const rise = (p: number, dist = 18): React.CSSProperties => ({
  opacity: clamp01(p * 1.8),
  transform: `translateY(${((1 - p) * dist).toFixed(2)}px)`,
  filter: p < 0.98 ? `blur(${((1 - p) * 6).toFixed(2)}px)` : undefined,
});
const pop = (f: number, start: number): React.CSSProperties => {
  const s = springAt(f, start, { damping: 13, stiffness: 260 });
  return { opacity: clamp01((f - start) / 4), transform: `scale(${mix(0.4, 1, s).toFixed(4)})` };
};

// Skeleton bars (light gray placeholders before fields land)
const Skeleton: React.FC<{ box: Box; fade: number; rows?: number[]; radius?: number }> = ({ box, fade, rows = [1], radius = 10 }) =>
  fade >= 1 ? null : (
    <div style={{ position: 'absolute', left: box.x, top: box.y, width: box.w, height: box.h, opacity: 1 - fade, display: 'flex', flexDirection: 'column', gap: 14, justifyContent: 'center' }}>
      {rows.map((w, i) => (
        <div key={i} style={{ height: Math.min(28, (box.h - 14 * (rows.length - 1)) / rows.length), width: `${w * 100}%`, borderRadius: radius, background: '#e8edf5' }} />
      ))}
    </div>
  );

// Product: video-shotcraft mark as studio subject (light theme), with independent ground contact shadow below (not a mark drop-shadow)
const ProductMark: React.FC = () => (
  <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    <div style={{
      position: 'absolute', left: 40, right: 40, top: 326, height: 52, borderRadius: '50%',
      background: `radial-gradient(closest-side, ${alpha(L.shadow, 0.26)}, ${alpha(L.shadow, 0)})`,
    }} />
    <ShotcraftMark size={368} tone="light" style={{ position: 'absolute', left: 46, top: 26 }} />
  </div>
);

const LINES: [string, boolean?][][] = [
  [['Shot recipes that '], ['direct every move', true], ['.']],
  [['Built on '], ['real page captures', true], [' and 2.5D,']],
  [['cut to the beat, rendered in Remotion.']],
];
// Swatches = 4 brand colors (selectable film looks)
const SWATCHES: [string, string][] = [[BRAND.ink, 'Ink'], [BRAND.paper, 'Paper'], [BRAND.amber, 'Amber'], [BRAND.slate, 'Slate']];

export const ProductCardProgressiveAssemble: React.FC = () => {
  const frame = useCurrentFrame();

  const enter = ramp(frame, 0, 14, EASE.snappy);
  const push = 1 + 0.035 * ramp(frame, 0, 132, EASE.swift);

  // Field progress
  const img = landP(frame, 'img');
  const title = landP(frame, 'title');
  const price = landP(frame, 'price');
  const sw = landP(frame, 'swatch');
  const cta = ramp(frame, F.cta.at + LAND, 12, EASE.out);

  // Price markdown (6f synchronized: shrink + gray out + strikethrough)
  const cut = ramp(frame, PRICE_DROP, 6, EASE.snappy);
  const strike = ramp(frame, PRICE_DROP, 5, EASE.out);
  const newP = springAt(frame, PRICE_DROP + 1, { damping: 14, stiffness: 240 });
  const chip = ramp(frame, PRICE_DROP + 7, 10, EASE.snappy);

  // Cursor
  const cb = cursorBox(frame);
  const cursorIn = ramp(frame, 2, 6, EASE.out);
  const cursorOut = ramp(frame, F.cta.at + 8, 8, EASE.exit);
  const cursorOp = cursorIn * (1 - cursorOut);
  const pad = 14 * (1 - cursorOut);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.05 }} fill={{ x: 0.85, y: 0.95 }} vignette={0.2} />
      {/* Background: faint cobalt blue glow behind right side of card (spatial depth) */}
      <div style={{ position: 'absolute', left: 1100, top: 520, width: 900, height: 700, background: `radial-gradient(closest-side, ${alpha(BLUE, 0.08)}, ${alpha(BLUE, 0)})` }} />

      <div style={{
        position: 'absolute', left: CL, top: CT, width: CW, height: CH,
        transform: `translateY(${((1 - enter) * 30).toFixed(2)}px) scale(${(mix(0.96, 1, enter) * push).toFixed(5)})`,
        transformOrigin: '50% 55%', opacity: clamp01(enter * 1.6),
      }}>
        {/* Card face: white + hairline border + inner highlight + two-tier tinted soft shadows */}
        <div style={{
          position: 'absolute', inset: 0, borderRadius: 36, background: 'linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%)',
          boxShadow: `inset 0 1px 0 #ffffff, 0 0 0 1px ${L.line}, 0 2px 4px ${alpha(L.shadow, 0.06)}, 0 40px 90px -20px ${alpha(L.shadow, 0.28)}`,
        }} />

        {/* Skeleton slots */}
        <Skeleton box={{ x: COL, y: 66, w: 200, h: 26 }} fade={title} />
        <Skeleton box={{ x: COL, y: 112, w: 520, h: 96 }} fade={title} rows={[0.85]} radius={16} />
        <Skeleton box={F.pills.box} fade={landP(frame, 'pills')} rows={[0.62]} radius={26} />
        <Skeleton box={F.price.box} fade={price} rows={[0.38]} radius={16} />
        <Skeleton box={F.body.box} fade={landP(frame, 'body')} rows={[0.92, 0.86, 0.6]} />
        <Skeleton box={F.swatch.box} fade={sw} rows={[0.5]} radius={28} />
        <Skeleton box={F.cta.box} fade={cta} rows={[1]} radius={32} />

        {/* Image: studio cyclorama backdrop + mark */}
        <div style={{ position: 'absolute', left: IMG.x, top: IMG.y, width: IMG.w, height: IMG.h, borderRadius: 24, overflow: 'hidden', background: '#eef2f8' }}>
          <div style={{ position: 'absolute', inset: 0, opacity: img, background: 'radial-gradient(110% 80% at 38% 26%, #ffffff 0%, #eef2f8 46%, #dde4ee 100%)' }} />
          <div style={{ position: 'absolute', left: 0, right: 0, top: '72%', bottom: 0, opacity: img, background: `linear-gradient(180deg, ${alpha(L.shadow, 0.04)}, ${alpha(L.shadow, 0)})` }} />
          <div style={{
            position: 'absolute', left: 90, top: 150, width: 460, height: 483,
            opacity: clamp01(img * 1.5),
            transform: `translateY(${((1 - img) * 26).toFixed(2)}px) scale(${mix(1.08, 1, ramp(frame, 10, 40, EASE.out)).toFixed(4)})`,
            filter: img < 0.98 ? `blur(${((1 - img) * 10).toFixed(2)}px)` : undefined,
          }}>
            <ProductMark />
          </div>
          <div style={{ position: 'absolute', left: 32, top: 30, fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.14em', color: L.ink3, opacity: img }}>01 / 06</div>
        </div>

        {/* Eyebrow + Title */}
        <div style={{ position: 'absolute', left: COL, top: 66, fontFamily: FONT.mono, fontSize: 22, letterSpacing: '0.18em', color: L.ink3, ...rise(title, 10) }}>
          VIDEO-SHOTCRAFT · AGENT SKILL
        </div>
        <div style={{ position: 'absolute', left: COL - 4, top: 104, ...type(112, 720), color: L.ink, letterSpacing: '-0.045em', whiteSpace: 'nowrap', ...rise(landP(frame, 'title', 2), 26) }}>
          Shotcraft
        </div>

        {/* Category pills: staggered pop */}
        <div style={{ position: 'absolute', left: COL, top: F.pills.box.y, display: 'flex', gap: 12 }}>
          {['Agent skill', 'Remotion', 'Shot recipes'].map((t, i) => (
            <div key={t} style={{
              ...type(28, 560), color: i === 2 ? L.ink : L.ink2, padding: '10px 22px', borderRadius: 99,
              background: i === 2 ? '#ffffff' : L.surface2, boxShadow: i === 2 ? `inset 0 0 0 1.5px ${alpha(L.ink, 0.16)}` : `inset 0 0 0 1px ${L.line}`,
              transformOrigin: 'left center', ...pop(frame, F.pills.at + LAND + i * 3),
            }}>{t}</div>
          ))}
        </div>

        {/* Price row: $449 lands → markdown; Free spring-pops; chip slides in */}
        <div style={{ position: 'absolute', left: COL, top: F.price.box.y, height: 112, width: 680, ...rise(price, 16) }}>
          <div style={{
            position: 'absolute', left: 0, bottom: 4, ...type(112, 760), letterSpacing: '-0.04em',
            color: cut > 0.5 ? L.ink3 : L.ink, transform: `scale(${mix(1, 0.46, cut).toFixed(4)})`, transformOrigin: '0% 88%', whiteSpace: 'nowrap',
          }}>
            $449
            <span style={{
              position: 'absolute', left: -6, right: -6, top: '50%', height: 9, borderRadius: 4, background: L.ink3,
              transform: `scaleX(${strike.toFixed(4)})`, transformOrigin: 'left center',
            }} />
          </div>
          <div style={{
            position: 'absolute', left: 150, bottom: 4, ...type(112, 780), letterSpacing: '-0.04em', color: BLUE, whiteSpace: 'nowrap',
            opacity: clamp01((frame - PRICE_DROP - 1) / 3), transform: `scale(${mix(1.18, 1, newP).toFixed(4)})`, transformOrigin: '0% 80%',
          }}>
            Free
          </div>
          <div style={{
            position: 'absolute', left: 412, top: 40, ...type(26, 700), color: BLUE, background: alpha(BLUE, 0.1),
            boxShadow: `inset 0 0 0 1.5px ${alpha(BLUE, 0.25)}`, padding: '8px 16px', borderRadius: 99, letterSpacing: '0.04em', whiteSpace: 'nowrap',
            opacity: chip, transform: `translateX(${((1 - chip) * -16).toFixed(2)}px)`,
          }}>
            OPEN SOURCE
          </div>
        </div>

        {/* Body: 3 staggered lines + marker highlight */}
        <div style={{ position: 'absolute', left: COL, top: F.body.box.y, width: COLW, ...type(34, 450), lineHeight: '50px', color: L.ink2, letterSpacing: '-0.012em' }}>
          {LINES.map((segs, li) => (
            <div key={li} style={{ whiteSpace: 'nowrap', ...rise(landP(frame, 'body', li * 3), 14) }}>
              {segs.map(([txt, mark], si) => !mark ? <span key={si}>{txt}</span> : (
                <span key={si} style={{ position: 'relative', display: 'inline-block' }}>
                  <span style={{
                    position: 'absolute', left: -4, right: -4, top: 6, bottom: 4, borderRadius: '4px 8px 6px 3px',
                    background: alpha(BLUE, 0.16), transform: `scaleX(${ramp(frame, 86 + li * 4, 6, EASE.out).toFixed(4)})`, transformOrigin: 'left center',
                  }} />
                  <span style={{ position: 'relative', color: L.ink, fontWeight: 620 }}>{txt}</span>
                </span>
              ))}
            </div>
          ))}
        </div>

        {/* Swatches: 4 pops + swatch name */}
        <div style={{ position: 'absolute', left: COL, top: F.swatch.box.y, height: 56, display: 'flex', alignItems: 'center', gap: 16 }}>
          {SWATCHES.map(([c], i) => (
            <div key={c} style={{
              width: 52, height: 52, borderRadius: 26, marginRight: i === 0 ? 4 : 0,
              background: `radial-gradient(circle at 35% 30%, rgba(255,255,255,0.35), rgba(255,255,255,0) 55%), ${c}`,
              boxShadow: i === 0 ? `0 0 0 4px #ffffff, 0 0 0 6px ${L.ink}` : `inset 0 0 0 1px ${alpha(L.ink, 0.12)}`,
              ...pop(frame, F.swatch.at + LAND + i * 3),
            }} />
          ))}
          <div style={{ marginLeft: 14, ...type(30, 450), color: L.ink3, ...rise(ramp(frame, F.swatch.at + 12, 12, EASE.snappy), 10) }}>
            Look · <span style={{ color: L.ink, fontWeight: 650 }}>Ink</span>
          </div>
        </div>

        {/* Button: background fills left to right */}
        <div style={{ position: 'absolute', left: F.cta.box.x, top: F.cta.box.y, width: F.cta.box.w, height: F.cta.box.h, borderRadius: 32, overflow: 'hidden', opacity: clamp01(cta * 4) }}>
          <div style={{ position: 'absolute', inset: 0, background: L.ink, transform: `scaleX(${cta.toFixed(4)})`, transformOrigin: 'left center' }} />
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, ...type(30, 650), color: '#ffffff', opacity: ramp(frame, F.cta.at + 8, 8, EASE.out) }}>
            Get the skill <span style={{ opacity: 0.5 }}>—</span> Free
          </div>
        </div>

        {/* Autofill cursor: stroked box + AUTOFILL badge, hops ahead of fields */}
        {cursorOp > 0.01 && (
          <div style={{
            position: 'absolute', left: cb.x - pad, top: cb.y - pad, width: cb.w + pad * 2, height: cb.h + pad * 2,
            borderRadius: 22, border: `2.5px solid ${BLUE}`, background: alpha(BLUE, 0.04), opacity: cursorOp,
            boxShadow: `0 0 0 6px ${alpha(BLUE, 0.08)}, 0 10px 30px ${alpha(BLUE, 0.16)}`,
          }}>
            <div style={{
              position: 'absolute', right: 18, top: -17, height: 32, padding: '0 12px', borderRadius: 8, background: BLUE, color: '#ffffff',
              display: 'flex', alignItems: 'center', gap: 8, fontFamily: FONT.mono, fontSize: 18, letterSpacing: '0.14em', whiteSpace: 'nowrap',
            }}>
              <span style={{ width: 8, height: 8, borderRadius: 4, background: '#ffffff', opacity: 0.6 + 0.4 * Math.sin(frame / 3) }} />
              AUTOFILL
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
