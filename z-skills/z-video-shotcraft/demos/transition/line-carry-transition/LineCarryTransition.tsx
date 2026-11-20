// line-carry-transition: graphic relay pan transition (Catch Me If You Can title style)
// Scene A progress bar fills -> end extends into line bursting out of card edge -> camera pans 1920px following line -> turns 90 degrees
// to enclose Scene B frame; frame closes, poster grows inside. Single continuous line, zero cuts.
//
// Redesign (sand architectural drafting: Saul Bass graphic poster):
// - look = sand (beige paper + ink + terracotta). 8px crisp ink line, square cap right angles; pen tip is solitary terracotta dot —
//   viewer eyes track this single moving focal point.
// - Narrative: A = video-shotcraft "Render Release Film" card (160px percentage counter tracks line; full = rationale for launch);
//   B = enclosed 720x480 frame blooms into film poster (terracotta sun + navy hills + bold tagline); gallery-label style text on left,
//   horizontal line segment serves as underline baseline for label.
// - World width 3840 (A left half / B right half), single polyline growing via dashoffset:
//   M 336,760 -> H 2880 -> V 280 -> H 3600 -> V 760 -> H 2880 close, total length 4944.
// - Core mechanism: during pan drawn = 1144 + cam; line growth syncs with camera speed; pen tip pins at x ~ 1480 until turn;
//   continuous velocity across transitions (progress ease-out -> burst endpoints zero speed -> camera in-out -> frame close in-out).
// - World content applies directional motion blur based on camera speed; line and pen tip remain crisp outside blur layer.
//
// Timeline (30fps, total 190f):
//   0-4     A progress card static (frame 0 present), empty track
//   4-40    Progress bar 0->100% (36f ease-out), percentage and MB counters sync
//   40-46   Full hold beat: status updates to "Ready to ship", checkmark pops (spring)
//   46-56   Burst phase: line shoots from bar end to x=1480
//   56-112  Camera pans left 1920px (56f smooth in-out), line extends in sync; ~92f line reaches corner and turns up
//   100-126 Scene B label rises line-by-line
//   112-136 Close frame: line traverses top, right, bottom edges to close (24f in-out); 136-142 pen tip dissipates
//   136-166 In-frame poster: background fills -> sun rises -> hills stagger -> poster text emerges
//   166–190 hold 24f
// Drafting ticks (1200-2760, 120px step) reveal after line passes, providing velocity reference.
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, mix, ramp, softShadow, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, TYPE, alpha, springAt, stagger, type } from '../../_fixtures/Look';
import { BRAND } from '../../_fixtures/Brand';

export const LINE_CARRY_TRANSITION_DURATION = 190;

const L = LOOKS.sand;
const LINE_Y = 760;
const X0 = 336; // Progress bar start (in-card left margin)
const BAR = 648; // Progress bar length
const TIP_X = 1480; // Pinned screen X for pen tip during pan
const FX0 = 2880, FX1 = 3600, FY0 = 280; // Frame B coordinates (bottom = LINE_Y)
const SEGS: Array<[number, number, number, number]> = [
  [X0, LINE_Y, FX0, LINE_Y],
  [FX0, LINE_Y, FX0, FY0],
  [FX0, FY0, FX1, FY0],
  [FX1, FY0, FX1, LINE_Y],
  [FX1, LINE_Y, FX0, LINE_Y],
];
const lens = SEGS.map(([a, b, c, d]) => Math.hypot(c - a, d - b));
const TOTAL = lens.reduce((s, x) => s + x, 0); // 4944
const PATH = `M ${X0} ${LINE_Y} H ${FX0} V ${FY0} H ${FX1} V ${LINE_Y} H ${FX0}`;

const PAN0 = 56, PAN1 = 112;
const camAt = (f: number) => 1920 * ramp(f, PAN0, PAN1 - PAN0, EASE.smooth);
const LEAD = TIP_X - X0; // Pan offset: drawn = LEAD + cam
const drawnAt = (f: number) => {
  if (f < 46) return BAR * ramp(f, 4, 36, EASE.out);
  if (f < PAN0) return mix(BAR, LEAD, ramp(f, 46, 10, EASE.swift));
  if (f < PAN1) return LEAD + camAt(f);
  return mix(LEAD + 1920, TOTAL, ramp(f, PAN1, 24, EASE.smooth));
};
const tipAt = (d: number): [number, number] => {
  let r = Math.max(0, Math.min(d, TOTAL));
  for (let i = 0; i < SEGS.length; i++) {
    const [a, b, c, e] = SEGS[i];
    if (r <= lens[i]) {
      const t = r / lens[i];
      return [a + (c - a) * t, b + (e - b) * t];
    }
    r -= lens[i];
  }
  return [FX0, LINE_Y];
};

const NAVY = L.accent2;
const CREAM = '#f7eedf';

// Graphic poster (Saul Bass paper cutout): terracotta sun + navy hills + bold typography; p = entry progress
const Poster: React.FC<{ w: number; h: number; f: number; mini?: boolean }> = ({ w, h, f, mini }) => {
  const sun = mini ? 1 : ramp(f, 140, 22, EASE.snappy);
  const hill = (i: number) => (mini ? 1 : ramp(f, 146 + stagger(i, 2, 6, EASE.out), 20, EASE.snappy));
  const txt = mini ? 1 : ramp(f, 152, 18, EASE.snappy);
  const k = w / 720;
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', background: CREAM }}>
      <svg width={w} height={h} viewBox="0 0 720 480" style={{ position: 'absolute', inset: 0 }}>
        <circle cx={468} cy={mix(480, 226, sun)} r={142} fill={L.accent} />
        {/* Navy hill and sun overprint (multiply blend simulating risograph overprint) */}
        <path d={`M 250 480 Q 540 ${mix(620, 250, hill(0))} 830 480 Z`} fill={NAVY} style={{ mixBlendMode: 'multiply' }} />
        <path d={`M -60 480 Q 150 ${mix(600, 300, hill(1))} 420 480 Z`} fill={L.ink} />
        <rect x={0} y={420} width={720} height={60} fill={L.ink} opacity={hill(1)} />
      </svg>
      {!mini && (
        <div style={{ position: 'absolute', left: 44 * k, top: 38 * k, overflow: 'hidden' }}>
          <div style={{ transform: `translateY(${((1 - txt) * 110).toFixed(2)}%)`, ...type(72, 900), color: L.ink, lineHeight: 0.9, letterSpacing: '-0.035em' }}>
            FRAME<br />MOTION
          </div>
        </div>
      )}
      {!mini && (
        <div style={{ position: 'absolute', left: 44, bottom: 14, ...type(22, 600, { mono: true }), color: CREAM, opacity: txt, letterSpacing: '0.08em' }}>
          CRAFT THE SHOT.
        </div>
      )}
    </div>
  );
};

// Scene A: render progress card (760x500 @ 280,300; track at y=760)
const ExportCard: React.FC<{ pct: number; f: number }> = ({ pct, f }) => {
  const done = pct >= 99.95;
  const check = springAt(f, 40, { damping: 14, stiffness: 220 });
  return (
    <div style={{
      position: 'absolute', left: 280, top: 300, width: 760, height: 500, boxSizing: 'border-box', padding: '48px 56px',
      background: `linear-gradient(180deg, ${L.surface}, #f8f1e6)`, borderRadius: 28,
      boxShadow: `inset 0 1px 0 #fff, inset 0 0 0 1px ${L.line}, ${softShadow(22, { color: L.shadow, strength: 0.9 })}`,
      fontFamily: FONT.sans,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
        <div style={{ position: 'relative', width: 120, height: 80, borderRadius: 8, overflow: 'hidden', boxShadow: `0 0 0 1px ${L.line}`, flex: 'none' }}>
          <Poster w={120} h={80} f={f} mini />
        </div>
        <div>
          <div style={{ ...type(38, 680), color: L.ink }}>launch-film.mp4</div>
          <div style={{ ...type(28, 500), color: L.ink3, marginTop: 8 }}>1920×1080 · 30 fps · h264</div>
        </div>
      </div>
      <div style={{ position: 'absolute', left: 56, right: 56, top: 236, display: 'flex', alignItems: 'flex-end' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, ...type(30, 600), color: done ? L.accent : L.ink3 }}>
            {done && (
              <svg width={30} height={30} viewBox="0 0 30 30" style={{ transform: `scale(${check.toFixed(3)})` }}>
                <circle cx={15} cy={15} r={15} fill={L.accent} />
                <path d="M8.5 15.5 13 20l8.5-9" stroke="#fff" strokeWidth={3.2} fill="none" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
            {done ? 'Ready to ship' : 'Rendering…'}
          </div>
          <div style={{ ...type(170, 780), color: L.ink, marginTop: 4 }}>
            {Math.round(pct)}<span style={{ ...type(TYPE.h3, 650), color: L.ink3, marginLeft: 6 }}>%</span>
          </div>
        </div>
        <div style={{ marginLeft: 'auto', ...type(28, 500, { mono: true }), color: L.ink3, paddingBottom: 34 }}>
          {(pct * 0.48).toFixed(1)} / 48 MB
        </div>
      </div>
      {/* Progress bar track (ink fill = path itself) */}
      <div style={{ position: 'absolute', left: X0 - 280, top: LINE_Y - 300 - 4, width: BAR, height: 8, background: alpha(L.ink, 0.1) }} />
    </div>
  );
};

export const LineCarryTransition: React.FC = () => {
  const f = useCurrentFrame();
  const cam = camAt(f);
  const drawn = drawnAt(f);
  const vx = -velocity(camAt, f);
  const pct = Math.min(100, (Math.min(drawn, BAR) / BAR) * 100);
  const [tx, ty] = tipAt(drawn);
  const tipO = 1 - ramp(f, 136, 6, EASE.linear);
  const closed = f >= 136;
  const fillIn = ramp(f, 134, 10, EASE.out); // Frame interior background
  const world: React.CSSProperties = { position: 'absolute', left: 0, top: 0, width: 3840, height: 1080, transform: `translateX(${(-cam).toFixed(2)}px)` };
  const capIn = (k: number) => ramp(f, 100 + k * 6, 20, EASE.snappy);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden' }}>
      {/* Shared stage lighting (screen space) */}
      <Stage look={L} keyLight={{ x: 0.28, y: 0.02 }} fill={{ x: 0.9, y: 0.95 }} />

      {/* World content: translates with camera pan, directional blur during fast phase */}
      <SpeedBlur vx={vx} amount={0.28} max={16}>
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
          <div style={world}>
            {/* Drafting dot grid providing motion reference, fading at edges */}
            <div style={{
              position: 'absolute', inset: 0,
              backgroundImage: `radial-gradient(circle, ${alpha(L.ink, 0.13)} 1.7px, ${alpha(L.ink, 0)} 2.3px)`,
              backgroundSize: '60px 60px', backgroundPosition: '6px 10px',
              WebkitMaskImage: 'linear-gradient(180deg, transparent 6%, #000 28%, #000 80%, transparent 97%)',
              maskImage: 'linear-gradient(180deg, transparent 6%, #000 28%, #000 80%, transparent 97%)',
            }} />
            {/* Scene A kicker */}
            <div style={{ position: 'absolute', left: 280, top: 214, display: 'flex', gap: 18, alignItems: 'baseline', ...type(TYPE.label + 4, 700, { caps: true }), letterSpacing: '0.24em' }}>
              <span style={{ color: L.accent }}>01</span><span style={{ color: L.ink2 }}>Render</span>
            </div>
            <ExportCard pct={pct} f={f} />
            {/* Scene B label: outside frame, rises line-by-line as camera arrives */}
            <div style={{ position: 'absolute', left: 2080, top: 300, width: 720 }}>
              <div style={{ display: 'flex', gap: 18, alignItems: 'baseline', ...type(TYPE.label + 4, 700, { caps: true }), letterSpacing: '0.24em', opacity: capIn(0) }}>
                <span style={{ color: L.accent }}>02</span><span style={{ color: L.ink2 }}>Premiere</span>
              </div>
              <div style={{ ...type(TYPE.h1, 820), color: L.ink, marginTop: 26 }}>
                {['Launch', 'film.'].map((t, k) => (
                  <div key={t} style={{ overflow: 'hidden', padding: '0.04em 0 0.14em', margin: '-0.04em 0 -0.14em' }}>
                    <div style={{ transform: `translateY(${((1 - capIn(k + 0.5)) * 115).toFixed(2)}%)` }}>{t}</div>
                  </div>
                ))}
              </div>
              <div style={{ ...type(TYPE.small, 500), color: L.ink2, marginTop: 30, opacity: capIn(2.2) }}>
                Crafted with {BRAND.name} · 30 fps
              </div>
            </div>
            {/* Inside Frame B: poster grows after frame closure */}
            {closed && (
              <div style={{
                position: 'absolute', left: FX0, top: FY0, width: FX1 - FX0, height: LINE_Y - FY0, opacity: fillIn,
                boxShadow: softShadow(26 * fillIn, { color: L.shadow, strength: 0.8 }),
              }}>
                <Poster w={FX1 - FX0} h={LINE_Y - FY0} f={f} />
              </div>
            )}
          </div>
        </div>
      </SpeedBlur>

      {/* Single continuous evolving line (crisp outside blur layer) */}
      <div style={world}>
        <svg width={3840} height={1080} style={{ position: 'absolute', inset: 0, overflow: 'visible' }}>
          {/* Drafting tick scale revealing under line as motion reference */}
          {Array.from({ length: 14 }, (_, i) => {
            const x = 1200 + i * 120;
            const on = ramp(X0 + drawn, x, 40, EASE.out);
            if (on <= 0) return null;
            const major = i % 4 === 0;
            return (
              <g key={i} opacity={on}>
                <line x1={x} x2={x} y1={LINE_Y + 10} y2={LINE_Y + (major ? 34 : 20)} stroke={alpha(L.ink, major ? 0.55 : 0.3)} strokeWidth={2} />
                {major && (
                  <text x={x + 8} y={LINE_Y + 62} fill={alpha(L.ink, 0.42)} style={{ ...type(22, 600, { mono: true }) }}>{`${(i / 4 + 1) * 12} cm`}</text>
                )}
              </g>
            );
          })}
          <path d={PATH} fill="none" stroke={L.ink} strokeWidth={8} strokeLinecap="square" strokeLinejoin="miter"
            strokeDasharray={`${drawn.toFixed(2)} ${TOTAL + 20}`} />
          {tipO > 0.001 && (
            <g opacity={tipO}>
              <circle cx={tx} cy={ty} r={30} fill={L.accent} opacity={0.16} />
              <circle cx={tx} cy={ty} r={14} fill={L.accent} />
            </g>
          )}
        </svg>
      </div>
    </AbsoluteFill>
  );
};
