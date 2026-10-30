// paparazzi-flash (B continuous flash freeze) — Triple white flashes at highlight moments, each flash hard-cutting to different crops of the same scene
// (wide view -> award card -> number close-up), shutter afterglow settles, third flash resolves on the number.
//
// Redesign (Awards night · you are the camera):
// - look = graphite (near-monochrome dark field; white for flashes, champagne gold reserved for award info). Scene is an annual award plaque in front of a step-and-repeat backdrop
//   (tiled video-shotcraft mark / wordmark brickwork): "Shot of the Year", "Take 1 · first prompt,
//   final cut.", "video-shotcraft". Three crops step closer: wide view -> card -> 280px "Take 1".
// - Viewfinder HUD (screen layer, unscaled by crops): four-corner bracket, exposure readouts, frame counter, flash recharge indicator.
//   8f before each flash, focus box shrinks from large to target crop area, turning champagne gold 3f before lock = anticipation beat;
//   white flash = primary action; cut-in settles 1.03->1 + downward drop = shutter recoil; shot counter increments, flash recharge resets = follow-through.
// - 30f before flash is "live": ambient background flashes from other cameras, slow camera push; each post-flash frame is a static photo,
//   subtly desaturated with boosted contrast; live vs frozen contrast makes each flash feel captured.
//
// Timeline (30fps, 140f total):
//   0–30    Live footage: slow push + 6 distant background flashes; focus locks card starting 22f
//   30      First flash -> wide freeze (22f interval); 44–52 focus bracket shrinks to card crop
//   52      Second flash -> card freeze (18f interval); 62–70 focus bracket shrinks to "Take 1"
//   70      Third flash -> digit close-up freeze
//   70–140  Hold 70f: subtle 1->1.015 push-in; 84f bottom-right "Saved" fades in, final frame is a complete award photograph
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, Grain, Vignette, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, alpha, type } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const PAPARAZZI_FLASH_DURATION = 140; // Live footage 30f + triple flash 40f + hold 70f

const L = LOOKS.graphite;
const GOLD = L.accent2;
const F1 = 30;
const F2 = 52;
const F3 = 70;
const FLASHES = [F1, F2, F3];
const SETTLE = 6; // Cut-in settle
const DECAY = 4; // White flash decay
const BLOOM = 7; // Post-flash bloom decay
const AF = 8; // Focus bracket lead-in

const hash = (i: number) => {
  const s = Math.sin(i * 127.3 + 11.7) * 43758.5453;
  return s - Math.floor(s);
};

// ───────────── Scene (1920x1080 wide coordinates) ─────────────
const CARD = { x: 610, y: 176, w: 700, h: 780 };
const DIGIT = { cx: CARD.x + 350, cy: CARD.y + 412 }; // Center of "Take 1" + right description

// Distant flashes from other cameras (live section only)
const POPS = [
  { f: 3, x: 300, y: 300 }, { f: 9, x: 1620, y: 220 }, { f: 13, x: 420, y: 780 },
  { f: 18, x: 1500, y: 700 }, { f: 23, x: 220, y: 520 }, { f: 27, x: 1760, y: 480 },
];

const Wall: React.FC = () => {
  const rows = 9;
  const cols = 6;
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden',
      background: `radial-gradient(ellipse 60% 70% at 50% 28%, #2a2b2f 0%, #18191c 55%, #0d0d0f 100%)` }}>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} style={{ position: 'absolute', left: (r % 2) * -170 - 60, top: 20 + r * 124, display: 'flex', gap: 0, whiteSpace: 'nowrap' }}>
          {Array.from({ length: cols + 1 }, (_, c) => {
            // Backdrop tile: alternating video-shotcraft mark / wordmark (dimmed to 9% overall; mark preserves brand color with reduced opacity)
            const mark = (r + c) % 2 === 0;
            return (
              <div key={c} style={{ width: 340, height: 52, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {mark ? <ShotcraftMark size={52} tone="dark" style={{ opacity: 0.1 }} /> : (
                  <span style={{ fontFamily: BRAND.font, fontSize: 30, fontWeight: 700, letterSpacing: '0.03em', color: alpha('#ffffff', 0.09) }}>{BRAND.name}</span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

const Laurel: React.FC<{ s?: number }> = ({ s = 70 }) => (
  <svg width={s * 1.6} height={s} viewBox="0 0 112 70" fill="none" stroke={GOLD} strokeWidth={3} strokeLinecap="round">
    {[-1, 1].map((side) => (
      <g key={side} transform={side === 1 ? 'translate(112 0) scale(-1 1)' : undefined}>
        <path d="M44 64 C24 58 12 42 12 18" />
        {[0, 1, 2, 3].map((k) => {
          const y = 56 - k * 12;
          const x = 30 - k * 4.5;
          return <path key={k} d={`M${x} ${y} q -12 -2 -14 -12 q 12 0 14 12`} fill={alpha(GOLD, 0.25)} />;
        })}
      </g>
    ))}
    <path d="M56 22 l4 8 9 1 -7 6 2 9 -8 -5 -8 5 2 -9 -7 -6 9 -1 z" fill={GOLD} stroke="none" />
  </svg>
);

const Scene: React.FC<{ f: number; live: boolean }> = ({ f, live }) => (
  <div style={{ position: 'absolute', inset: 0, fontFamily: FONT.sans, color: L.ink }}>
    <Wall />
    {/* Stage overhead light */}
    <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(ellipse 34% 60% at 50% 40%, rgba(255,250,240,0.12) 0%, rgba(255,250,240,0) 70%)` }} />
    {/* Distant flashes from other cameras: 4-point starburst + soft glow, 3f each */}
    {live && POPS.map((p, i) => {
      const t = f - p.f;
      if (t < 0 || t > 3) return null;
      const a = 1 - t / 3;
      return (
        <div key={i} style={{ position: 'absolute', left: p.x - 120, top: p.y - 120, width: 240, height: 240, opacity: a }}>
          <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(230,240,255,0.35) 18%, rgba(255,255,255,0) 60%)' }} />
          <div style={{ position: 'absolute', left: 0, right: 0, top: 118, height: 4, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.9), transparent)' }} />
          <div style={{ position: 'absolute', top: 30, bottom: 30, left: 118, width: 4, background: 'linear-gradient(180deg, transparent, rgba(255,255,255,0.8), transparent)' }} />
        </div>
      );
    })}
    {/* Award plaque card */}
    <div style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, borderRadius: 40, overflow: 'hidden',
      background: 'linear-gradient(165deg, #2a2b30 0%, #18191c 45%, #121315 100%)',
      boxShadow: `inset 0 0 0 1.5px ${alpha('#ffffff', 0.12)}, inset 0 1.5px 0 ${alpha('#ffffff', 0.22)}, 0 60px 120px -40px rgba(0,0,0,0.95), 0 0 0 1px rgba(0,0,0,0.6)` }}>
      {/* Card surface light: soft highlight across top edge */}
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 80% 40% at 30% 0%, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 70%)' }} />
      <div style={{ position: 'absolute', left: 60, top: 56, display: 'flex', alignItems: 'center', gap: 20 }}>
        <Laurel s={52} />
        <div style={{ ...type(22, 700, { caps: true }), letterSpacing: '0.24em', color: GOLD }}>Best in Motion · 2026</div>
      </div>
      <div style={{ position: 'absolute', left: 58, top: 136, ...type(72, 720), letterSpacing: '-0.035em' }}>Shot of the Year</div>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 236, height: 1.5, background: alpha('#ffffff', 0.12) }} />
      <div style={{ position: 'absolute', left: 52, top: 262, display: 'flex', alignItems: 'flex-start', lineHeight: 0.86 }}>
        <span style={{ ...type(110, 700), letterSpacing: '-0.04em', color: L.ink2, marginTop: 22, marginRight: 14 }}>Take</span>
        <span style={{ ...type(280, 820), letterSpacing: '-0.06em', lineHeight: 0.86 }}>1</span>
      </div>
      <div style={{ position: 'absolute', left: 430, top: 336, ...type(44, 580), color: L.ink2, lineHeight: 1.12, whiteSpace: 'nowrap' }}>
        first<br />prompt,<br /><span style={{ color: GOLD }}>final cut.</span>
      </div>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 624, height: 1.5, background: alpha('#ffffff', 0.12) }} />
      <div style={{ position: 'absolute', left: 60, top: 660, display: 'flex', alignItems: 'center', gap: 22 }}>
        <div style={{ width: 80, height: 80, borderRadius: 22, background: `linear-gradient(150deg, ${BRAND.paper} 0%, #d6d2c8 100%)`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'inset 0 1.5px 0 #fff, 0 10px 24px -10px rgba(0,0,0,0.8)' }}>
          <ShotcraftMark size={54} tone="light" />
        </div>
        <div>
          <div style={{ fontFamily: BRAND.font, fontSize: 44, fontWeight: 700, letterSpacing: '0.01em', lineHeight: 1.3 }}>{BRAND.name}</div>
          <div style={{ ...type(30, 450), color: L.ink3, marginTop: 4 }}>{PITCH.en.motto}</div>
        </div>
      </div>
    </div>
  </div>
);

// ───────────── Crop & HUD ─────────────
type View = { scale: number; cx: number; cy: number };
const VIEW_WIDE: View = { scale: 1.0, cx: 960, cy: 540 };
const VIEW_CARD: View = { scale: 1.6, cx: CARD.x + CARD.w / 2, cy: CARD.y + 290 };
const VIEW_DIGIT: View = { scale: 2.8, cx: DIGIT.cx, cy: DIGIT.cy };
const STILLS = [VIEW_WIDE, VIEW_CARD, VIEW_DIGIT];

// Wide-coordinate rect -> screen rect under specified view
const project = (r: { x: number; y: number; w: number; h: number }, v: View) => ({
  x: (r.x - v.cx) * v.scale + 960, y: (r.y - v.cy) * v.scale + 540, w: r.w * v.scale, h: r.h * v.scale,
});
const viewRect = (v: View) => ({ x: v.cx - 960 / v.scale, y: v.cy - 540 / v.scale, w: 1920 / v.scale, h: 1080 / v.scale });

const Brackets: React.FC<{ x: number; y: number; w: number; h: number; color: string; arm?: number; width?: number; opacity?: number }> = ({ x, y, w, h, color, arm = 46, width = 3, opacity = 1 }) => {
  const a = Math.min(arm, w / 3, h / 3);
  const d = `M${x} ${y + a}V${y}H${x + a} M${x + w - a} ${y}H${x + w}V${y + a} M${x + w} ${y + h - a}V${y + h}H${x + w - a} M${x + a} ${y + h}H${x}V${y + h - a}`;
  return <path d={d} stroke={color} strokeWidth={width} fill="none" opacity={opacity} strokeLinecap="square" />;
};

const Still: React.FC<{ view: View; f: number; live: boolean }> = ({ view, f, live }) => (
  <div style={{ position: 'absolute', left: 960 / view.scale - view.cx, top: 540 / view.scale - view.cy, width: 1920, height: 1080, zoom: view.scale }}>
    <Scene f={f} live={live} />
  </div>
);

export const PaparazziFlash: React.FC = () => {
  const frame = useCurrentFrame();
  let seg = -1;
  for (let i = 0; i < FLASHES.length; i++) if (frame >= FLASHES[i]) seg = i;

  // Shutter recoil: 1.03->1 settle + downward drop; bloom decay
  let settleScale = 1;
  let settleY = 0;
  let bloom = 0;
  if (seg >= 0) {
    const t = 1 - ramp(frame, FLASHES[seg], SETTLE, EASE.out);
    settleScale = 1 + 0.03 * t;
    settleY = -16 * t;
    bloom = 1 - ramp(frame, FLASHES[seg], BLOOM, EASE.out);
  }
  let flash = 0;
  for (const f of FLASHES) if (frame >= f && frame <= f + DECAY) flash = Math.max(flash, 0.95 * (1 - ramp(frame, f, DECAY, EASE.out)));
  const inFlash = FLASHES.some((f) => frame >= f && frame < f + DECAY);
  const jx = inFlash ? 2 * (hash(frame * 7 + 1) * 2 - 1) : 0;
  const jy = inFlash ? 2 * (hash(frame * 13 + 5) * 2 - 1) : 0;

  // Live footage: wide slow push (in-out); subtle push-in during hold phase
  const liveP = ramp(frame, 0, F1, EASE.smooth);
  const liveScale = mix(1.04, 1.1, liveP);
  const holdPush = seg === 2 ? mix(1, 1.015, ramp(frame, F3 + SETTLE, 64, EASE.smooth)) : 1;
  // Ambient brightness fluctuations from background camera flashes
  const popLift = seg === -1 ? POPS.reduce((m, p) => Math.max(m, frame >= p.f && frame <= p.f + 2 ? 0.06 * (1 - (frame - p.f) / 3) : 0), 0) : 0;

  // Focus bracket: shrinks from outer frame to target (screen coords) AF frames before next flash, turning gold on lock
  const curView: View = seg === -1 ? { scale: liveScale, cx: 960, cy: 540 } : STILLS[seg];
  const nextIdx = seg + 1;
  let af: React.ReactNode = null;
  if (nextIdx < FLASHES.length) {
    const fNext = FLASHES[nextIdx];
    const start = nextIdx === 0 ? F1 - 9 : fNext - AF;
    if (frame >= start && frame < fNext) {
      const target = nextIdx === 0 ? { x: CARD.x - 30, y: CARD.y - 30, w: CARD.w + 60, h: CARD.h + 60 } : viewRect(STILLS[nextIdx]);
      const r = project(target, curView);
      const p = ramp(frame, start, 6, EASE.snappy);
      const k = mix(1.3, 1, p);
      const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
      const locked = frame >= fNext - 3;
      af = <Brackets x={cx - (r.w * k) / 2} y={cy - (r.h * k) / 2} w={r.w * k} h={r.h * k} color={locked ? GOLD : '#ffffff'} width={locked ? 4 : 3} opacity={locked ? 1 : 0.85} arm={60} />;
    }
  }

  // HUD telemetry
  const shots = 23 + Math.max(0, seg + 1);
  const lastFlash = seg >= 0 ? FLASHES[seg] : -40;
  const charge = Math.min(1, (frame - lastFlash) / 16);
  const saved = ramp(frame, 84, 12, EASE.out);

  return (
    <AbsoluteFill style={{ background: '#0b0b0c', overflow: 'hidden' }}>
      <div style={{
        position: 'absolute', inset: 0, transformOrigin: '960px 540px',
        transform: `translate(${jx.toFixed(2)}px, ${(jy + settleY).toFixed(2)}px) scale(${(settleScale * holdPush * 1.012).toFixed(5)})`,
        // Freeze = photograph: subtle desaturation + boosted contrast; 7f bloom decay post-flash
        filter: seg >= 0
          ? `brightness(${(1 + 0.22 * bloom).toFixed(3)}) contrast(${(1.06 - 0.14 * bloom).toFixed(3)}) saturate(${(0.82 - 0.2 * bloom).toFixed(3)})`
          : popLift > 0 ? `brightness(${(1 + popLift).toFixed(3)})` : undefined,
      }}>
        {seg === -1 ? (
          <div style={{ position: 'absolute', inset: 0, transformOrigin: '960px 540px', transform: `scale(${liveScale.toFixed(5)})` }}>
            <Scene f={frame} live />
          </div>
        ) : (
          <Still view={STILLS[seg]} f={FLASHES[seg]} live={false} />
        )}
      </div>
      <Vignette strength={[0.5, 0.5, 0.56, 0.62][seg + 1]} inner={0.42} color="#000000" />
      <Grain opacity={0.1} blend="soft-light" />

      {/* Viewfinder HUD (screen layer) */}
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        <Brackets x={96} y={84} w={1728} h={912} color="#ffffff" opacity={0.5} arm={70} width={3} />
        {af}
      </svg>
      <div style={{ position: 'absolute', left: 130, top: 112, display: 'flex', alignItems: 'center', gap: 12, fontFamily: FONT.mono, fontSize: 24, fontWeight: 700, color: alpha('#ffffff', 0.7), letterSpacing: '0.08em' }}>
        <div style={{ width: 12, height: 12, borderRadius: 6, background: '#ff453a' }} />RAW · 45MP
      </div>
      <div style={{ position: 'absolute', right: 130, top: 106, display: 'flex', alignItems: 'center', gap: 14, fontFamily: FONT.mono, fontSize: 24, fontWeight: 700, color: charge >= 1 ? GOLD : alpha('#ffffff', 0.55), letterSpacing: '0.08em' }}>
        <svg width={30} height={30} viewBox="0 0 30 30">
          <circle cx={15} cy={15} r={12} stroke={alpha('#ffffff', 0.2)} strokeWidth={3} fill="none" />
          <circle cx={15} cy={15} r={12} stroke={charge >= 1 ? GOLD : '#ffffff'} strokeWidth={3} fill="none" strokeDasharray={`${(charge * 75.4).toFixed(1)} 76`} transform="rotate(-90 15 15)" strokeLinecap="round" />
        </svg>
        {charge >= 1 ? 'FLASH READY' : 'CHARGING'}
      </div>
      <div style={{ position: 'absolute', left: 130, bottom: 108, display: 'flex', gap: 40, fontFamily: FONT.mono, fontSize: 28, fontWeight: 600, color: alpha('#ffffff', 0.75), letterSpacing: '0.04em' }}>
        <span>1/250</span><span>F2.8</span><span>ISO 1600</span><span style={{ color: alpha('#ffffff', 0.45) }}>±0.0</span>
      </div>
      <div style={{ position: 'absolute', right: 130, bottom: 102, display: 'flex', alignItems: 'baseline', gap: 22, fontFamily: FONT.mono, color: alpha('#ffffff', 0.8) }}>
        <span style={{ fontSize: 24, fontWeight: 700, letterSpacing: '0.1em', color: GOLD, opacity: saved }}>✓ SAVED</span>
        <span style={{ fontSize: 40, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{String(shots).padStart(3, '0')}</span>
      </div>

      {/* White flash: solid center white with edge falloff (radial flash decay) */}
      {flash > 0.004 && (
        <AbsoluteFill style={{ opacity: flash, background: 'radial-gradient(ellipse 80% 90% at 50% 45%, #ffffff 0%, #ffffff 45%, rgba(250,250,255,0.86) 100%)' }} />
      )}
    </AbsoluteFill>
  );
};
