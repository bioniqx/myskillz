// sakuga-timing-shift — Switching from shooting on 3s to shooting on 1s (sakuga timing shift)
//
// Redesign (Animator layout paper & cel card):
// - look = paper (warm white paper, ink, vermilion). The entire canvas is an animator layout sheet: top peg holes, light blue pencil
//   field guide / crosshairs as texture; bottom features a real exposure sheet (timesheet) — on 3s, only every 3 frames has a drawing number
//   (1, 4, 7...), with vertical lines in intermediate frames (reusing previous drawing), while on 1s every frame has a number. The viewer directly sees frames per second.
// - Subject is a cel-styled video-shotcraft product card: 5px ink outline, flat paper tone, unblurred hard-edged cel shadow,
//   containing 150px "30fps" + "every frame, crafted" — the motion itself is a frame-by-frame sprint, echoing 30 frames/sec on 1s.
// - Technique: 0–48f driven by q = floor(f/3)*3, 16 drawings flipbook-style stepping horizontally (65px/step), each pose unique (swing angle ±5°,
//   alternating squash/stretch, alternating hop); 48f switches to on 1s + two impact frames (screen inverted to ink background, burst focus lines = Japanese sakuga climax mark),
//   50–68f frame-by-frame smooth sprint returning to center (out-poly(4)), trailing speed-proportional horizontal speed lines, overshooting 40px then snapping into place.
//
// Timeline (30fps, 150f total):
//   0–48    On 3s: 16 drawings, corner tag "ON 3s / On 3s", exposure sheet numbered every 3 frames
//   48–49   Impact frame (only full-screen impact in clip); corner tag switches to "ON 1s / On 1s" and pops 1.25x
//   50–68   Sprint: out-poly(4) high initial velocity, scaleX stretched to ~1.3 with speed, speed lines scale with velocity
//   68–74   Overshoot settle; 74–80 landing squash 0.9/1.08 -> 1
//   80–150  Hold: subtle 2% camera push-in (ease-out), corner line boiling freezes at 108f
import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, SERIF, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const SAKUGA_TIMING_SHIFT_DURATION = 150; // On 3s 48f + sprint settle 32f + hold 70f

const L = LOOKS.paper;
const PENCIL = '#4f78b8'; // Light blue pencil (layout guide line color on animation paper)

const W = 1920;
const CARD_W = 600;
const CARD_H = 360;
const CARD_Y = 330;
const X_LEFT = 140;
const X_RIGHT = 1180;
const X_CENTER = (W - CARD_W) / 2; // 660
const OVERSHOOT = 40;

const SWITCH = 48;
const ARRIVE = 68;
const SETTLE = 74;
const BOIL_FREEZE = 108;

const C = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

// Phase 1: On 3s — linear position (stepped mechanical increments evoke flipbook motion), sampled at q
const pos1 = (t: number) => interpolate(t, [0, SWITCH - 3], [X_LEFT, X_RIGHT], C);
// Phase 2: On 1s — out-poly(4) sprint to overshoot point -> snap back
const pos2 = (t: number) =>
  t < ARRIVE
    ? interpolate(t, [SWITCH, ARRIVE], [X_RIGHT, X_CENTER - OVERSHOOT], { ...C, easing: Easing.out(Easing.poly(4)) })
    : interpolate(t, [ARRIVE, SETTLE], [X_CENTER - OVERSHOOT, X_CENTER], { ...C, easing: Easing.inOut(Easing.cubic) });

const h = (n: number) => {
  const s = Math.sin(n * 127.3) * 43758.5453;
  return s - Math.floor(s);
};

// Exposure sheet
const STRIP_N = 30;
const CELL = 44;
const CELL_GAP = 6;
const STRIP_W = STRIP_N * CELL + (STRIP_N - 1) * CELL_GAP; // 1494
const STRIP_X = (W - STRIP_W) / 2;
const STRIP_Y = 826;

// Cel card
const CelCard: React.FC = () => (
  <div style={{
    width: CARD_W, height: CARD_H, borderRadius: 30, background: L.surface, border: `5px solid ${L.ink}`,
    boxSizing: 'border-box', padding: '30px 40px', position: 'relative', overflow: 'hidden',
  }}>
    {/* Cel shadow color: hard-edged shaded patch on bottom right */}
    <div style={{ position: 'absolute', right: -60, bottom: -80, width: 360, height: 220, borderRadius: '50%', background: alpha(L.ink, 0.045) }} />
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <ShotcraftMark size={38} tone="light" frameColor={L.ink} />
      <div style={{ ...type(32, 800), fontFamily: BRAND.font, color: L.ink, letterSpacing: '0.01em' }}>{BRAND.name}</div>
      <div style={{ marginLeft: 'auto', ...type(22, 600, { mono: true }), color: L.ink2 }}>render 2048</div>
    </div>
    <div style={{ ...type(160, 900), color: L.ink, marginTop: 22, letterSpacing: '-0.05em', lineHeight: 0.9 }}>
      30<span style={{ color: L.accent, fontSize: 120, marginLeft: 6 }}>fps</span>
    </div>
    <div style={{ ...type(38, 600), color: L.ink2, marginTop: 18 }}>every frame, crafted</div>
  </div>
);

export const SakugaTimingShift: React.FC = () => {
  const f = useCurrentFrame();
  const onThrees = f < SWITCH;
  const impact = f >= SWITCH && f <= SWITCH + 1;

  // ---- Card ----
  const q = Math.floor(f / 3) * 3;
  const drawing = q / 3; // Drawing index
  const x = onThrees ? pos1(q) : pos2(f);
  // On-3s pose (frozen with q): swing angle + alternating squash/stretch + alternating hop
  const rot = onThrees
    ? Math.sin(q * 0.7) * 5
    : interpolate(f, [SWITCH, SWITCH + 8], [-4, 0], { ...C, easing: Easing.out(Easing.cubic) });
  const hop = onThrees ? (drawing % 2 === 0 ? -18 : -2) : 0;
  const poseSX = onThrees ? (drawing % 2 === 0 ? 0.97 : 1.035) : 1;
  const poseSY = onThrees ? (drawing % 2 === 0 ? 1.035 : 0.97) : 1;

  // Sprint velocity -> motion stretch + speed lines
  const v = onThrees ? 0 : Math.abs(pos2(f) - pos2(f - 1));
  const sFac = Math.min(v / 60, 1);
  const stretchX = 1 + 0.3 * sFac;
  const stretchY = 1 - 0.1 * sFac;
  // Landing squash
  const sqX = interpolate(f, [SETTLE - 2, SETTLE + 1, SETTLE + 6], [1, 0.92, 1], { ...C, easing: Easing.out(Easing.cubic) });
  const sqY = interpolate(f, [SETTLE - 2, SETTLE + 1, SETTLE + 6], [1, 1.07, 1], { ...C, easing: Easing.out(Easing.cubic) });
  // Hard-edge drop shadow: shifts with hop height on 3s, moves farther out during sprint
  const shOff = onThrees ? (hop < -5 ? 18 : 10) : 10 + 10 * sFac;

  // ---- Corner badge line boil (cycles every 4 frames, freezes at 108f) ----
  const qb = Math.min(Math.floor(f / 4) * 4, BOIL_FREEZE);
  const bx = (h(qb + 1) - 0.5) * 5;
  const by = (h(qb + 2) - 0.5) * 5;
  const brot = (h(qb + 3) - 0.5) * 2;
  const ul = [0, 1, 2, 3].map((i) => (h(qb * 3 + i * 7 + 11) - 0.5) * 8);
  const pop = interpolate(f, [SWITCH, SWITCH + 3, SWITCH + 10], [1, 1.25, 1], { ...C, easing: Easing.out(Easing.cubic) });

  // Intro: corner tag / exposure sheet float in (paper and card already visible at frame 0)
  const labelIn = ramp(f, 0, 14, EASE.out);
  const stripIn = ramp(f, 4, 16, EASE.out);
  // Subtle slow push-in during hold phase
  const cam = mix(1, 1.02, ramp(f, SETTLE, 150 - SETTLE, EASE.out));

  // Exposure sheet playhead: 1s cycle; freezes on current frame at 110f in hold phase
  const head = Math.min(f, 110) % STRIP_N;

  // Speed lines (sprint): 9 tapered horizontal ink lines trailing card (right side), length proportional to velocity, pseudo-random y position per frame
  const speedLines = !onThrees && !impact && sFac > 0.08
    ? Array.from({ length: 9 }, (_, i) => {
        const yy = CARD_Y + 20 + h(i * 7.3 + f * 0.37) * (CARD_H - 40);
        const len = (160 + h(i * 3.1 + f) * 260) * sFac;
        const x0 = x + CARD_W * stretchX * 0.8 + h(i * 5.7 + f * 1.3) * 80;
        const th = 3 + h(i * 2.9) * 6;
        return { yy, len, x0, th };
      })
    : [];

  // Impact frame: focus lines (radial wedges focused on card center)
  const cx = x + CARD_W / 2;
  const cy = CARD_Y + CARD_H / 2;
  const focusLines = impact
    ? Array.from({ length: 64 }, (_, i) => {
        const a = (i / 64) * Math.PI * 2 + h(i + f) * 0.05;
        const r0 = 300 + h(i * 1.7 + f) * 220;
        const r1 = 1500;
        const wd = 0.012 + h(i * 4.1) * 0.02;
        const p = (r: number, aa: number) => `${(cx + Math.cos(aa) * r).toFixed(1)},${(cy + Math.sin(aa) * r).toFixed(1)}`;
        return `M${p(r0, a)} L${p(r1, a - wd)} L${p(r1, a + wd)} Z`;
      }).join(' ')
    : '';

  const inkBg = impact; // Impact frame: screen inverted to ink background
  const lineColor = inkBg ? L.bg[0] : L.ink;

  return (
    <AbsoluteFill style={{ overflow: 'hidden', fontFamily: FONT.sans, background: L.bg[1] }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${cam.toFixed(5)})`, transformOrigin: '50% 46%' }}>
        <Stage look={L} keyLight={{ x: 0.45, y: 0.2 }} fill={null} grain={0.06}>
          {/* Animation paper: peg holes */}
          {[-1, 0, 1].map((k) => (
            <div key={k} style={{
              position: 'absolute', top: 34, left: 960 + k * 330 - (k === 0 ? 50 : 17), width: k === 0 ? 100 : 34, height: 34, borderRadius: 17,
              background: alpha(L.shadow, 0.13), boxShadow: `inset 0 3px 5px ${alpha(L.shadow, 0.22)}`,
            }} />
          ))}
          {/* Light blue pencil field guide: safe area + crosshairs + tick marks */}
          <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
            <g stroke={alpha(PENCIL, 0.22)} strokeWidth={1.5} fill="none">
              <rect x={110} y={110} width={1700} height={860} rx={4} />
              <rect x={260} y={190} width={1400} height={700} strokeDasharray="10 8" />
              <line x1={940} x2={980} y1={540} y2={540} />
              <line x1={960} x2={960} y1={520} y2={560} />
              {Array.from({ length: 17 }, (_, i) => <line key={i} x1={110 + i * 106.25} x2={110 + i * 106.25} y1={110} y2={124} />)}
            </g>
            <text x={1800} y={100} textAnchor="end" fill={alpha(PENCIL, 0.45)} fontSize={22} fontFamily={FONT.mono}>12 FLD</text>
          </svg>
        </Stage>

        {/* Impact frame: ink background + focus lines */}
        {inkBg && (
          <AbsoluteFill style={{ background: L.ink }}>
            <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
              <path d={focusLines} fill={L.bg[0]} opacity={0.9} />
            </svg>
          </AbsoluteFill>
        )}

        {/* Center landing slot: dashed pencil frame (animator target landing guide) */}
        {!inkBg && (
          <div style={{
            position: 'absolute', left: X_CENTER - 10, top: CARD_Y - 10, width: CARD_W + 20, height: CARD_H + 20, borderRadius: 36,
            border: `2px dashed ${alpha(PENCIL, 0.4)}`, boxSizing: 'border-box',
          }} />
        )}

        {/* Speed lines */}
        {speedLines.length > 0 && (
          <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
            {speedLines.map((s, i) => (
              <path key={i} d={`M${s.x0} ${s.yy - s.th / 2} L${s.x0 + s.len} ${s.yy} L${s.x0} ${s.yy + s.th / 2} Z`} fill={L.ink} opacity={0.85} />
            ))}
          </svg>
        )}

        {/* Main card: hard-edged cel shadow + body */}
        <div style={{
          position: 'absolute', left: 0, top: CARD_Y,
          transform: `translate(${x}px, ${hop}px) rotate(${rot}deg) scaleX(${stretchX * sqX * poseSX}) scaleY(${stretchY * sqY * poseSY})`,
          transformOrigin: '50% 100%',
        }}>
          <div style={{
            position: 'absolute', left: shOff, top: shOff + (onThrees ? -hop * 0.6 : 0), width: CARD_W, height: CARD_H, borderRadius: 30,
            background: inkBg ? L.accent : L.ink, opacity: inkBg ? 1 : 0.92,
          }} />
          <div style={{ position: 'relative' }}><CelCard /></div>
        </div>

        {/* Corner badge: ON 3s / ON 1s (hand-drawn line boil) */}
        <div style={{ position: 'absolute', left: 150, top: 120, opacity: labelIn, transform: `translateY(${mix(16, 0, labelIn)}px)` }}>
          <div style={{ transform: `translate(${bx}px, ${by}px) rotate(${brot}deg) scale(${pop})`, transformOrigin: '0% 60%', display: 'inline-block' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 26 }}>
              <div style={{ ...type(112, 900), fontStyle: 'italic', color: lineColor, letterSpacing: '-0.04em' }}>
                ON <span style={{ color: onThrees ? lineColor : L.accent }}>{onThrees ? '3s' : '1s'}</span>
              </div>
              <div style={{ ...type(40, 700, { serif: true }), fontFamily: `${SERIF}`, color: L.accent }}>
                {onThrees ? 'On 3s' : 'On 1s'}
              </div>
            </div>
            <svg width={300} height={24} style={{ display: 'block', marginTop: 2, overflow: 'visible' }}>
              <path d={`M 4 ${12 + ul[0]} Q 90 ${8 + ul[1]} 170 ${13 + ul[2]} T 296 ${10 + ul[3]}`} fill="none"
                stroke={onThrees ? lineColor : L.accent} strokeWidth={8} strokeLinecap="round" />
            </svg>
          </div>
          <div style={{ ...type(36, 500), color: inkBg ? L.bg[2] : L.ink2, marginTop: 10 }}>
            {onThrees ? '10 drawings per second' : '30 drawings per second'}
          </div>
        </div>

        {/* Top-right: exposure sheet header (textured text) */}
        <div style={{ position: 'absolute', right: 150, top: 146, textAlign: 'right', opacity: labelIn }}>
          <div style={{ ...type(26, 600, { mono: true }), color: inkBg ? L.bg[2] : L.ink3, letterSpacing: '0.12em' }}>SC 012 · CUT 04</div>
          <div style={{ ...type(26, 600, { mono: true }), color: inkBg ? L.bg[2] : L.ink3, letterSpacing: '0.12em', marginTop: 8 }}>
            {onThrees ? `A${String(drawing + 1).padStart(2, '0')} · 16 dwg` : `B${String(Math.min(f - SWITCH, SETTLE - SWITCH) + 1).padStart(2, '0')} · ${SETTLE - SWITCH + 1} dwg`}
          </div>
        </div>

        {/* Exposure sheet: 30 cells = 1 second. On 3s: drawing number every 3 cells with vertical lines in between (= hold); On 1s: every cell is numbered */}
        {!inkBg && (
          <div style={{ position: 'absolute', left: STRIP_X, top: STRIP_Y, opacity: stripIn, transform: `translateY(${mix(14, 0, stripIn)}px)` }}>
            <div style={{ position: 'absolute', left: -6, top: -6, width: STRIP_W + 12, height: 76, borderRadius: 8, border: `1.5px solid ${alpha(L.ink, 0.25)}` }} />
            {Array.from({ length: STRIP_N }).map((_, i) => {
              const key = onThrees ? i % 3 === 0 : true;
              const isHead = i === head;
              const num = onThrees ? i / 3 + 1 : i + 1;
              return (
                <div key={i} style={{
                  position: 'absolute', left: i * (CELL + CELL_GAP), top: 0, width: CELL, height: 64, borderRadius: 4,
                  background: isHead ? alpha(L.accent, 0.14) : 'transparent',
                  boxShadow: isHead ? `inset 0 0 0 2.5px ${L.accent}` : `inset 0 0 0 1px ${alpha(L.ink, 0.1)}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {key ? (
                    <div style={{
                      width: 34, height: 34, borderRadius: 17, border: `2.5px solid ${onThrees ? L.ink : L.accent}`, boxSizing: 'border-box',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      ...type(17, 700, { mono: true }), color: onThrees ? L.ink : L.accent,
                    }}>{num}</div>
                  ) : (
                    <div style={{ width: 3, height: 44, borderRadius: 2, background: alpha(L.ink, 0.45) }} />
                  )}
                </div>
              );
            })}
            <div style={{ position: 'absolute', left: 0, top: 92, width: STRIP_W, display: 'flex', justifyContent: 'space-between', ...type(32, 500), color: L.ink3 }}>
              <span>Exposure sheet</span>
              <span style={{ fontFamily: FONT.mono, fontSize: 28 }}>1 sec · 30 frames</span>
            </div>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
