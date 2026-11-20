// Crane rise reveal (crane-rise-reveal) — crane shot: focal point -> wide view.
//
// Iteration 2 redesign (porcelain SaaS · video-shotcraft render queue):
// - look = porcelain (cool white + cobalt blue, accented with teal). World = a product window designed for shots: top bar + "Render queue" page header
//   (right-side 104px KPI for today's rendered frames) + 12-row shot render task table. Opening camera is 3.0x tightly cropped on row 10—shot ID / cut / recipe card
//   display as large 63px text, with a cobalt blue "tracking" dot at the row head so viewers first recognize "this is a specific shot".
// - Rise: translate = screen center - target * scale, target and scale share a bezier(0.2,0,0.25,1) curve (zero-speed launch,
//   ~19% peak speed, long-tail gentle deceleration = crane boom feel). As the top of the viewport crosses each row, a cobalt blue sheen sweeps across the row from the head (triggered on crossing,
//   synced frame-by-frame with camera motion) — "surging in row by row"; header KPI (today's rendered frames) synchronously counts from 0 to 48,210 (sense of volume), and the window detaches from the frame,
//   landing as a physical artifact on the porcelain stage (background dot grid shifts with 0.35 parallax, conveying depth).
// - Aftermath: After settling, the tracked row status capsule flips from "Rendering" to teal "Rendered" with a checkmark — the single micro-event in the hold phase,
//   concluding with: "the row you were focusing on is just one cell in this entire wall."
//
// Timeline (30fps, 165f total):
//   0–24    Close-up hold: camera +1.5% preparatory push-in (taking a breath), row-head tracking point pulses
//   24–126  Crane rise 102f: early ~40f fast section wrapped in CameraMotionBlur; row sheens triggered on crossing; KPI count (expo-out, finishes with camera move)
//   126–138 Settle: window shadow retracts to resting elevation, KPI last digit settles
//   134–148 Aftermath: tracked row status flips to Rendered (spring damping 16)
//   148–165 Clean hold settle
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { CameraMotionBlur } from '@remotion/motion-blur';
import { bezier, ramp, mix, EASE, FONT, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha, springAt } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CRANE_RISE_REVEAL_DURATION = 165; // Close-up hold 24f + crane rise 102f + settle/aftermath/hold 39f

const L = LOOKS.porcelain;
const HOLD = 24;
const MOVE_END = 126;
const BLUR_END = 64; // Remove motion blur once speed drops below ~35% peak (blurring slow movement softens text)
const FLIP = 134; // Tracked row status flips to Rendered (data layer still named delivered)
const crane = bezier(0.2, 0, 0.25, 1);

// ───────────── World Geometry (Final frame = 1:1 world) ─────────────
const WX = 120, WY = 90, WW = 1680, WH = 900; // Product window
const PAD = 48;
const CX = WX + PAD; // Content left edge
const BAR_H = 72;
const HEAD_Y = WY + BAR_H; // Header top
const THEAD_Y = WY + 262; // Table header
const ROW0 = WY + 302;
const ROW_H = 48;
const ROWS = 12;
const TRACK = 9; // Tracked row
const rowTop = (i: number) => ROW0 + i * ROW_H;

// Columns (relative to content left edge): id = shot ID, route = cut (prev shot -> next shot), carrier = recipe card, kg = frames
const COL = { id: 0, route: 172, carrier: 560, eta: 790, status: 930, prog: 1150, kg: 1480 };

// ───────────── Camera ─────────────
const S0 = 3.0;
const BREATH = 0.015;
const F0X = 441; // Close-up focus point x: tracking point sits ~60px from left screen edge, window left border just out of frame
const F1 = { x: 960, y: 540 };
const camAt = (frame: number) => {
  const breath = ramp(frame, 0, HOLD, EASE.smooth);
  const e = crane(Math.min(1, Math.max(0, (frame - HOLD) / (MOVE_END - HOLD))));
  const s0 = S0 * (1 + BREATH * breath);
  const s = mix(s0, 1, e);
  // Close-up bottom edge stops 30px above window bottom (above rounded corner, no outside bleed); target shifts down with push-in to stay anchored
  const fy0 = WY + WH - 30 - 540 / s0;
  const fx = mix(F0X, F1.x, e);
  const fy = mix(fy0, F1.y, e);
  return { s, e, tx: 960 - fx * s, ty: 540 - fy * s, visTop: fy - 540 / s };
};

// Row sheen trigger frame: viewport top edge crosses row top (rows already in frame at start do not trigger)
const ROW_TRIG = Array.from({ length: ROWS }, (_, i) => {
  if (camAt(HOLD).visTop <= rowTop(i)) return -1;
  for (let f = HOLD; f <= MOVE_END; f++) if (camAt(f).visTop <= rowTop(i) + 2) return f;
  return MOVE_END;
});
const HEAD_TRIG = (() => {
  for (let f = HOLD; f <= MOVE_END; f++) if (camAt(f).visTop <= HEAD_Y + 60) return f;
  return MOVE_END;
})();

// ───────────── Data (Mock video-shotcraft render queue; recipe card names from this library) ─────────────
type Row = { id: string; from: string; to: string; carrier: string; eta: string; status: 'transit' | 'customs' | 'delivered' | 'loading'; prog: number; kg: string };
const DATA: Row[] = [
  { id: 'SH-0401', from: 'Cold open', to: 'Logo', carrier: 'brand-ink-open', eta: '09:40', status: 'delivered', prog: 1, kg: '104' },
  { id: 'SH-0402', from: 'Logo', to: 'Hero', carrier: 'text-as-mask', eta: '10:15', status: 'transit', prog: 0.72, kg: '96' },
  { id: 'SH-0403', from: 'Hero', to: 'Dashboard', carrier: 'crash-zoom-punch', eta: '11:05', status: 'customs', prog: 0.48, kg: '120' },
  { id: 'SH-0404', from: 'Dashboard', to: 'Search', carrier: 'cursor-flyover', eta: '11:30', status: 'transit', prog: 0.61, kg: '150' },
  { id: 'SH-0405', from: 'Search', to: 'Results', carrier: 'type-and-filter', eta: '12:10', status: 'loading', prog: 0.12, kg: '73' },
  { id: 'SH-0406', from: 'Results', to: 'Detail', carrier: 'steep-tilt-glide', eta: '12:45', status: 'transit', prog: 0.83, kg: '180' },
  { id: 'SH-0407', from: 'Detail', to: 'Chart', carrier: 'timeline-travel', eta: '13:20', status: 'delivered', prog: 1, kg: '210' },
  { id: 'SH-0408', from: 'Chart', to: 'Voice', carrier: 'voice-waveform-live', eta: '13:55', status: 'transit', prog: 0.54, kg: '172' },
  { id: 'SH-0409', from: 'Voice', to: 'Team', carrier: 'spotlight-hero-card', eta: '14:05', status: 'customs', prog: 0.4, kg: '140' },
  { id: 'SH-0410', from: 'Team', to: 'Launch', carrier: 'crane-rise-reveal', eta: '14:20', status: 'transit', prog: 0.91, kg: '165' },
  { id: 'SH-0411', from: 'Launch', to: 'Outro', carrier: 'grain-dissolve', eta: '14:50', status: 'loading', prog: 0.2, kg: '90' },
  { id: 'SH-0412', from: 'Outro', to: 'Lockup', carrier: 'neon-triple-marquee', eta: '15:30', status: 'transit', prog: 0.66, kg: '120' },
];

const STATUS = {
  transit: { label: 'Rendering', fg: L.accent, bg: alpha(L.accent, 0.1) },
  customs: { label: 'In review', fg: '#b7791f', bg: 'rgba(214,158,46,0.13)' },
  delivered: { label: 'Rendered', fg: '#00866f', bg: alpha(L.accent2, 0.13) },
  loading: { label: 'Queued', fg: L.ink2, bg: 'rgba(76,86,110,0.09)' },
} as const;

const text = (size: number, weight: number, color: string, extra: React.CSSProperties = {}): React.CSSProperties => ({
  position: 'absolute', fontFamily: FONT.sans, fontSize: size, fontWeight: weight, color, whiteSpace: 'nowrap',
  letterSpacing: size >= 40 ? '-0.03em' : '-0.01em', lineHeight: 1, fontVariantNumeric: 'tabular-nums', ...extra,
});

const Pill: React.FC<{ kind: keyof typeof STATUS; x: number; y: number; scale?: number; check?: number }> = ({ kind, x, y, scale = 1, check = 0 }) => {
  const s = STATUS[kind];
  return (
    <div style={{
      position: 'absolute', left: x, top: y, height: 28, padding: '0 13px 0 10px', borderRadius: 14, background: s.bg,
      display: 'flex', alignItems: 'center', gap: 7, transform: `scale(${scale})`, transformOrigin: '0% 50%',
    }}>
      {kind === 'delivered' && check > 0 ? (
        <svg width={14} height={14} viewBox="0 0 14 14">
          <path d="M2.5 7.4 L5.6 10.2 L11.5 3.8" fill="none" stroke={s.fg} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"
            pathLength={1} strokeDasharray={1} strokeDashoffset={1 - check} />
        </svg>
      ) : (
        <div style={{ width: 7, height: 7, borderRadius: 4, background: s.fg }} />
      )}
      <span style={{ fontFamily: FONT.sans, fontSize: 17, fontWeight: 600, color: s.fg, letterSpacing: '-0.005em' }}>{s.label}</span>
    </div>
  );
};

// Single task row
const RowView: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const r = DATA[i];
  const top = rowTop(i);
  const tracked = i === TRACK;
  const flip = tracked ? springAt(frame, FLIP, { damping: 16, stiffness: 190 }) : 0;
  const kind = tracked && frame >= FLIP + 2 ? 'delivered' : r.status;
  const prog = tracked ? mix(r.prog, 1, ramp(frame, FLIP - 4, 16, EASE.out)) : r.prog;
  const pillPop = tracked && frame >= FLIP ? 0.86 + 0.14 * flip : 1;
  const check = tracked ? ramp(frame, FLIP + 4, 10, EASE.out) : 0;
  // Tracking point pulse (most pronounced during close-up hold, maintains subtle pulse afterward)
  const beat = 0.5 + 0.5 * Math.sin(frame / 5.5);
  const ty = top + ROW_H / 2;
  const fg = L.ink;
  // Focus: during close-up hold, only the tracked row is solid, others dimmed to 38%; recovers within ~26f after lift-off ("inspect this item first, then the whole")
  const focus = tracked ? 1 : mix(0.38, 1, ramp(frame, HOLD - 2, 28, EASE.out));
  return (
    <div style={{ opacity: focus }}>
      {tracked && (
        <div style={{
          position: 'absolute', left: WX + 10, top: top + 3, width: WW - 20, height: ROW_H - 6, borderRadius: 12,
          background: `linear-gradient(90deg, ${alpha(L.accent, 0.11)} 0%, ${alpha(L.accent, 0.05)} 60%, ${alpha(L.accent, 0.03)} 100%)`,
          boxShadow: `inset 0 0 0 1px ${alpha(L.accent, 0.22)}`,
        }} />
      )}
      {!tracked && i < ROWS - 1 && i !== TRACK - 1 && (
        <div style={{ position: 'absolute', left: CX, top: top + ROW_H - 0.5, width: WW - PAD * 2, height: 1, background: L.line }} />
      )}
      {tracked && (
        <>
          <div style={{ position: 'absolute', left: CX - 26, top: ty - 5, width: 10, height: 10, borderRadius: 5, background: L.accent }} />
          <div style={{
            position: 'absolute', left: CX - 26 - 6 * beat, top: ty - 5 - 6 * beat, width: 10 + 12 * beat, height: 10 + 12 * beat,
            borderRadius: 20, border: `1.5px solid ${alpha(L.accent, 0.5 * (1 - beat))}`,
          }} />
        </>
      )}
      <span style={text(20, 600, tracked ? L.accent : L.ink2, { left: CX + COL.id, top: ty - 10, fontFamily: FONT.mono, letterSpacing: '0em' })}>{r.id}</span>
      <span style={text(21, 600, fg, { left: CX + COL.route, top: ty - 11 })}>
        {r.from}<span style={{ color: L.ink3, fontWeight: 400 }}>{'  →  '}</span>{r.to}
      </span>
      <span style={text(20, 500, L.ink2, { left: CX + COL.carrier, top: ty - 10 })}>{r.carrier}</span>
      <span style={text(20, 500, L.ink2, { left: CX + COL.eta, top: ty - 10 })}>{r.eta}</span>
      <Pill kind={kind} x={CX + COL.status} y={ty - 14} scale={pillPop} check={check} />
      {/* Progress bar */}
      <div style={{ position: 'absolute', left: CX + COL.prog, top: ty - 3, width: 260, height: 6, borderRadius: 3, background: 'rgba(15,30,60,0.07)' }}>
        <div style={{
          width: `${prog * 100}%`, height: '100%', borderRadius: 3,
          background: kind === 'delivered' ? L.accent2 : tracked ? L.accent : alpha(L.ink, 0.32),
        }} />
      </div>
      <span style={text(20, 500, L.ink2, { left: CX + COL.kg, top: ty - 10, width: 84, textAlign: 'right' })}>
        {r.kg}<span style={{ color: L.ink3 }}> f</span>
      </span>
    </div>
  );
};

const fmt = (n: number) => Math.round(n).toLocaleString('en-US');

// Product window (world coordinates)
const World: React.FC<{ frame: number }> = ({ frame }) => {
  // Window shadow: tight during close-up (almost invisible), rises to floating height after pull-back — "a physical object resting on the stage"
  const elev = mix(6, 34, ramp(frame, HOLD + 30, MOVE_END - HOLD - 20, EASE.swift));
  const kpi = 48210 * ramp(frame, HOLD + 6, MOVE_END - HOLD + 4, EASE.snappy);
  const headOn = ramp(frame, HEAD_TRIG - 8, 20, EASE.out);
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <div style={{
        position: 'absolute', left: WX, top: WY, width: WW, height: WH, borderRadius: 28, background: L.surface,
        boxShadow: `inset 0 0 0 1px ${L.line}, ${softShadow(elev, { color: L.shadow, strength: 1.15 })}, 0 ${elev * 2}px ${elev * 4}px -${elev}px ${alpha(L.shadow, 0.14)}`,
      }} />
      {/* Top bar */}
      <div style={{ position: 'absolute', left: WX, top: WY, width: WW, height: BAR_H, borderBottom: `1px solid ${L.line}` }} />
      {/* Brand: mark + video-shotcraft logotype (all-lowercase, brand typography) */}
      <ShotcraftMark size={32} tone="light" style={{ position: 'absolute', left: CX - 3, top: WY + 20 }} />
      <span style={text(22, 700, BRAND.ink, { left: CX + 38, top: WY + 25, fontFamily: BRAND.font, letterSpacing: '0.02em' })}>{BRAND.name}</span>
      <div style={{ position: 'absolute', left: CX + 250, top: WY, height: BAR_H, display: 'flex', gap: 40 }}>
        {['Shots', 'Render queue', 'Timeline', 'Workbench', 'Gallery'].map((t, k) => (
          <div key={t} style={{ position: 'relative', height: BAR_H, display: 'flex', alignItems: 'center' }}>
            <span style={{ ...text(18, k === 1 ? 600 : 500, k === 1 ? L.ink : L.ink3), position: 'relative' }}>{t}</span>
            {k === 1 && <div style={{ position: 'absolute', left: -2, right: -2, bottom: -1, height: 2, background: L.ink }} />}
          </div>
        ))}
      </div>
      <div style={{ position: 'absolute', left: WX + WW - PAD - 330, top: WY + 18, width: 270, height: 36, borderRadius: 10, background: L.surface2, boxShadow: `inset 0 0 0 1px ${L.line}` }}>
        <span style={text(17, 500, L.ink3, { left: 16, top: 10 })}>Search shots…</span>
        <span style={text(14, 600, L.ink3, { left: 228, top: 11, fontFamily: FONT.mono })}>⌘K</span>
      </div>
      <div style={{ position: 'absolute', left: WX + WW - PAD - 40, top: WY + 18, width: 36, height: 36, borderRadius: 18, background: 'linear-gradient(135deg, #9fb4ff, #2f5bff)' }} />

      {/* Page header: Title + KPI */}
      <div style={{ opacity: 0.35 + 0.65 * headOn }}>
        <span style={text(16, 700, L.accent, { left: CX, top: HEAD_Y + 44, letterSpacing: '0.16em' })}>LIVE · RENDER FARM</span>
        <span style={text(64, 700, L.ink, { left: CX - 3, top: HEAD_Y + 76, letterSpacing: '-0.035em' })}>Render queue</span>
        <span style={text(20, 500, L.ink3, { left: CX, top: HEAD_Y + 152 })}>Updated live · 1080p · 30 fps · 4 render workers</span>
        <span style={text(104, 750, L.ink, { left: WX + WW - PAD - 520, top: HEAD_Y + 46, width: 520, textAlign: 'right', letterSpacing: '-0.045em' })}>{fmt(kpi)}</span>
        <span style={text(20, 500, L.ink3, { left: WX + WW - PAD - 520, top: HEAD_Y + 158, width: 520, textAlign: 'right' })}>
          frames rendered today<span style={{ color: '#00866f', fontWeight: 600 }}>{'   ▲ 12.4%'}</span>
        </span>
      </div>

      {/* Table header */}
      {[['SHOT', COL.id], ['CUT', COL.route], ['RECIPE CARD', COL.carrier], ['ETA', COL.eta], ['STATUS', COL.status], ['PROGRESS', COL.prog]].map(([t, x]) => (
        <span key={t as string} style={text(14, 700, L.ink3, { left: CX + (x as number), top: THEAD_Y + 14, letterSpacing: '0.14em' })}>{t}</span>
      ))}
      <span style={text(14, 700, L.ink3, { left: CX + COL.kg, top: THEAD_Y + 14, width: 84, textAlign: 'right', letterSpacing: '0.14em' })}>FRAMES</span>
      <div style={{ position: 'absolute', left: CX, top: ROW0 - 1, width: WW - PAD * 2, height: 1, background: L.line }} />

      {DATA.map((_, i) => <RowView key={i} i={i} frame={frame} />)}
    </div>
  );
};

// Camera layer: World -> Screen
const Cam: React.FC<{ frame: number; children: React.ReactNode }> = ({ frame, children }) => {
  const { s, tx, ty } = camAt(frame);
  return (
    <div style={{ position: 'absolute', width: 1920, height: 1080, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
      {children}
    </div>
  );
};

// Stage background dot grid: 0.35 parallax with camera ("further" than window)
const DOTS = (() => {
  const out: { x: number; y: number }[] = [];
  for (let y = -600; y <= 1700; y += 48) for (let x = -900; x <= 2800; x += 48) out.push({ x, y });
  return out;
})();
const BackDots: React.FC<{ frame: number }> = ({ frame }) => {
  const { s, tx, ty } = camAt(frame);
  const k = 0.35;
  const sp = 1 + (s - 1) * k;
  const px = 960 + (tx + 960 * s - 960) * k - 960 * sp; // Keep parallax layer concentric with main camera
  const py = 540 + (ty + 540 * s - 540) * k - 540 * sp;
  return (
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
      <g transform={`translate(${px.toFixed(2)} ${py.toFixed(2)}) scale(${sp.toFixed(4)})`}>
        {DOTS.map((d, i) => <circle key={i} cx={d.x} cy={d.y} r={1.6} fill={alpha(L.ink, 0.13)} />)}
      </g>
    </svg>
  );
};

// Page reads frame internally: CameraMotionBlur relies on useCurrentFrame within subtree for multisampling; passing frame from outside freezes sampling
const Page: React.FC = () => {
  const frame = useCurrentFrame();
  return (
  <AbsoluteFill style={{ overflow: 'hidden' }}>
    <Stage look={L} keyLight={{ x: 0.5, y: 0.02 }} fill={{ x: 0.85, y: 1 }} grain={0} vignette={0.14}>
      <BackDots frame={frame} />
    </Stage>
    <Cam frame={frame}>
      <World frame={frame} />
    </Cam>
  </AbsoluteFill>
  );
};

// Row sheen (excluded from CameraMotionBlur: multisampling translucent color blocks causes banding)
const Sweeps: React.FC<{ frame: number }> = ({ frame }) => (
  <AbsoluteFill style={{ overflow: 'hidden', pointerEvents: 'none' }}>
    <Cam frame={frame}>
      {ROW_TRIG.map((t, i) => {
        if (t < 0 || i === TRACK) return null;
        const p = ramp(frame, t, 20, EASE.out);
        const op = Math.min(1, ramp(frame, t, 3, EASE.linear)) * (1 - ramp(frame, t + 6, 18, EASE.out));
        if (op <= 0.002) return null;
        const head = mix(-0.2, 1.1, p);
        return (
          <div key={i} style={{
            position: 'absolute', left: WX + 10, top: rowTop(i) + 3, width: WW - 20, height: ROW_H - 6, borderRadius: 12, opacity: op,
            background: `linear-gradient(90deg, ${alpha(L.accent, 0.03)} 0%, ${alpha(L.accent, 0.14)} ${(head * 100).toFixed(1)}%, ${alpha(L.accent, 0)} ${((head + 0.22) * 100).toFixed(1)}%)`,
            boxShadow: `inset 0 0 0 1px ${alpha(L.accent, 0.18)}`,
          }} />
        );
      })}
    </Cam>
  </AbsoluteFill>
);

export const CraneRiseReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const fast = frame > HOLD + 1 && frame < BLUR_END;
  // Close-up vignette: darkens edges to focus on tracked row, recedes after pull-back (stage's subtle ambient vignette takes over)
  const vig = 1 - ramp(frame, HOLD, 60, EASE.swift);
  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      {fast ? (
        <CameraMotionBlur shutterAngle={150} samples={10}>
          <Page />
        </CameraMotionBlur>
      ) : (
        <Page />
      )}
      <Sweeps frame={frame} />
      <AbsoluteFill style={{
        pointerEvents: 'none', opacity: vig,
        background: `radial-gradient(ellipse 75% 70% at 45% 58%, ${alpha(L.shadow, 0)} 55%, ${alpha(L.shadow, 0.16)} 100%)`,
      }} />
    </AbsoluteFill>
  );
};
