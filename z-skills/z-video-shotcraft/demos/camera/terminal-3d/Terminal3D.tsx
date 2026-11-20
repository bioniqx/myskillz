// terminal-3d —— Three terminal windows distributed across 3D space; camera flies between windows (pulling back en route); at each window a typewriter types commands and results stream line-by-line.
// Core technique preserved: window pose table → camera inverse transform; both flights feature a sinusoidal pull-back hump; out-of-focus windows blur; no typing during flight.
//
// Round 2 redesign (design decisions)
// - look = lime (graphite dark field · fluorescent yellow-green): terminal aesthetic with tech feel, single accent reserved for prompts, ✓, and final READY artifact title.
// - Content structured into a complete "3-step video production" pipeline (Brand round: video-shotcraft universe): hypothetical CLI "shotcraft" — 01 init sets up storyboard
//   → 02 render renders shots (shot count + progress cells) → 03 export audio mix and export; final line ● READY launch-film.mp4 has the only bloom glow in the sequence (Q4).
// - Windows redesigned specifically for camera moves: laid out at authentic 1240×700 resolution (rasterized 1:1 at camera settle, text never blurry, Q2), commands 46px,
//   output 34px monospace (≥ auxiliary text 32px, Q11); title bar displays step number and path, no longer generic "~/workspace — zsh".
// - Space: windows staggered along an arc in depth, each oriented with its own yaw; camera keeps an 8–10° side perspective at each station (clear legibility with volume);
//   floor features a line-by-line SVG perspective grid projected via camera matrix (constant stroke width without flicker), with yellow-green floor reflection pool beneath focus window;
//   each window is backed by a 560px stroked step number, creating parallax against the window during flight.
// - Typing features human cadence: 1–2f deterministic jitter per keystroke, 2f pause after command before "Enter"; output prints rapidly in terminal fashion (3f fade-in +
//   10px leftward settle, 4f line pitch), status column spins through braille spinners before resolving to ✓.
//
// Timeline (30fps, 246f total)
//   0–24    Opening: camera pushes in from 260px pull-back to settle on first window (out curve), window in frame from frame 0
//   8–26    Type `shotcraft init` (14 chars) → ~28 Enter → 30–50 four lines of output (spinner → ✓)
//   48–62   Hold reading pause
//   62–92   Flight 1→2 (30f, swift asymmetric in-out + sin pull-back 820px; directional motion blur based on lateral screen speed)
//   94–111  Type `shotcraft render` → ~113 Enter → progress bar + counter 0→24 (20f, out curve) → three lines DONE → ✓ summary
//   140–152 Hold
//   152–182 Flight 2→3
//   184–201 Type `shotcraft export` → ~203 Enter → three lines export → ~220 ● READY artifact title pops in with bloom
//   222–246 Hold: camera ultra-slow push-in 2%, final frame is "delivery complete" poster
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, mix, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, alpha, glow } from '../../_fixtures/Look';

export const TERMINAL_3D_DURATION = 246;

const L = LOOKS.lime;
// Stage key light desaturated to olive gray-green: fluorescent accent reserved for prompt / ✓ / READY, preventing background from washing out green
const STAGE = { ...L, light: '#56613f', accent2: '#3a4a1c' };
const MONO = FONT.mono;
const W = 1180; // Window layout size (= screen size at settle)
const H = 620;
const PERSP = 1800; // Scene perspective distance
const FLOOR_Y = 500; // Ground height (world coordinates, y downward)

// ───────────── Window Pose Table (world coordinates, px / degrees) + Station Camera Side Angle ─────────────
type Pose = { x: number; y: number; z: number; ry: number };
const POSES: Pose[] = [
  { x: -1500, y: -30, z: -220, ry: 24 },
  { x: 0, y: 30, z: 260, ry: -14 },
  { x: 1520, y: -40, z: -160, ry: 28 },
];
const VIEW = [9, -8, 10]; // Camera side-angle relative to window at each station (degrees)
const TILT = -4; // Camera slight tilt-down (rotateX, degrees)

// Station schedule: each station [arrival frame, typing start]; flight intervals
const FLY = [[62, 92], [152, 182]] as const;
const TYPE_AT = [8, 94, 184];
const PULL_PEAK = 1250; // Pull-back distance during flight (scales down to ~0.6 at peak, framing all 3 windows)

// Deterministic pseudo-random
const rand = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

// ───────────── Camera ─────────────
// s = continuous station parameter (0..2), pull = pull-back distance
const camAt = (f: number) => {
  let s = 0;
  let pull = 260 * (1 - ramp(f, 0, 24, EASE.out)); // Opening push-in
  FLY.forEach(([a, b], i) => {
    const u = ramp(f, a, b - a, EASE.swift);
    s += u;
    const raw = Math.min(1, Math.max(0, (f - a) / (b - a)));
    pull += Math.sin(Math.PI * Math.pow(raw, 0.85)) * PULL_PEAK * (i === 0 ? 1 : 1.05);
  });
  pull -= 36 * ramp(f, 222, 24, EASE.smooth); // Tail ultra-slow push-in ~2%
  const i0 = Math.min(1, Math.floor(s));
  const k = s - i0;
  const a = POSES[i0], b = POSES[i0 + 1];
  const pose: Pose = { x: mix(a.x, b.x, k), y: mix(a.y, b.y, k), z: mix(a.z, b.z, k), ry: mix(a.ry, b.ry, k) };
  const view = mix(VIEW[i0], VIEW[i0 + 1], k);
  return { s, pull, pose, yaw: view - pose.ry };
};

// Projection strictly isomorphic to world CSS transform: translateZ(-pull) rotateX(TILT) rotateY(yaw) translate(-pose)
const project = (cam: ReturnType<typeof camAt>, p: [number, number, number]) => {
  const x0 = p[0] - cam.pose.x, y0 = p[1] - cam.pose.y, z0 = p[2] - cam.pose.z;
  const ty = (cam.yaw * Math.PI) / 180, tx = (TILT * Math.PI) / 180;
  const x1 = x0 * Math.cos(ty) + z0 * Math.sin(ty);
  const z1 = -x0 * Math.sin(ty) + z0 * Math.cos(ty);
  const y2 = y0 * Math.cos(tx) - z1 * Math.sin(tx);
  const z2 = y0 * Math.sin(tx) + z1 * Math.cos(tx) - cam.pull;
  return { x: x1, y: y2, z: z2 };
};
const toScreen = (q: { x: number; y: number; z: number }) => {
  const k = PERSP / (PERSP - q.z);
  return { x: 960 + q.x * k, y: 540 + q.y * k, k };
};

// ───────────── Perspective Floor (SVG, line-by-line projection; bright foreground, fading into dark field) ─────────────
const Floor: React.FC<{ cam: ReturnType<typeof camAt>; frame: number }> = ({ cam }) => {
  const segs: React.ReactNode[] = [];
  const CELL = 240;
  const near = PERSP - 120;
  const line = (a: [number, number, number], b: [number, number, number], key: string) => {
    const N = 8;
    for (let j = 0; j < N; j++) {
      const pa = project(cam, [mix(a[0], b[0], j / N), a[1], mix(a[2], b[2], j / N)]);
      const pb = project(cam, [mix(a[0], b[0], (j + 1) / N), a[1], mix(a[2], b[2], (j + 1) / N)]);
      if (pa.z > near || pb.z > near) continue;
      const depth = PERSP - (pa.z + pb.z) / 2; // Distance to camera
      const op = Math.max(0, Math.min(1, 1.25 - depth / 4200));
      if (op < 0.02) continue;
      const sa = toScreen(pa), sb = toScreen(pb);
      segs.push(<line key={`${key}${j}`} x1={sa.x} y1={sa.y} x2={sb.x} y2={sb.y} strokeOpacity={op * op} />);
    }
  };
  for (let i = -14; i <= 14; i++) line([i * CELL, FLOOR_Y, -3600], [i * CELL, FLOOR_Y, 2400], `c${i}`);
  for (let j = -15; j <= 10; j++) line([-3400, FLOOR_Y, j * CELL], [3400, FLOOR_Y, j * CELL], `r${j}`);
  return (
    <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
      <g stroke={alpha(L.accent, 0.34)} strokeWidth={1.4}>{segs}</g>
    </svg>
  );
};

// Floor reflection beneath focus window (projected below window base)
const FloorPool: React.FC<{ cam: ReturnType<typeof camAt>; i: number; on: number }> = ({ cam, i, on }) => {
  if (on < 0.02) return null;
  const p = POSES[i];
  const q = project(cam, [p.x, FLOOR_Y, p.z]);
  if (q.z > PERSP - 200) return null;
  const s = toScreen(q);
  const w = 1500 * s.k, h = 260 * s.k;
  return (
    <div style={{
      position: 'absolute', left: s.x - w / 2, top: s.y - h / 2, width: w, height: h, borderRadius: '50%',
      background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.26 * on)} 0%, ${alpha(L.accent, 0.08 * on)} 45%, ${alpha(L.accent, 0)} 72%)`,
    }} />
  );
};

// Backlight behind focus window (projected to window center in screen space): lifts dark window body out of dark field
const BackLight: React.FC<{ cam: ReturnType<typeof camAt>; i: number; on: number }> = ({ cam, i, on }) => {
  if (on < 0.02) return null;
  const p = POSES[i];
  const q = project(cam, [p.x, p.y - 60, p.z - 300]);
  if (q.z > PERSP - 200) return null;
  const s = toScreen(q);
  const w = 2500 * s.k, h = 1250 * s.k;
  return (
    <div style={{
      position: 'absolute', left: s.x - w / 2, top: s.y - h / 2, width: w, height: h, borderRadius: '50%',
      background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha('#d8e4b8', 0.3 * on)} 0%, ${alpha('#a8b878', 0.11 * on)} 46%, ${alpha('#9fb06a', 0)} 72%)`,
    }} />
  );
};

// ───────────── Terminal Content ─────────────
type Seg = [string, string]; // [text, color]
type Line = { mark?: 'spin' | 'pass'; segs: Seg[]; at: number; big?: boolean };
const C = { key: L.ink3, val: L.ink, dim: L.ink2, ok: L.accent };

type Win = { step: string; name: string; path: string; cmd: string; lines: Line[] };
const WINS: Win[] = [
  {
    step: '01', name: 'storyboard', path: '~/promo', cmd: 'shotcraft init',
    lines: [
      { mark: 'spin', at: 0, segs: [['template   ', C.key], ['ink-press', C.val]] },
      { mark: 'spin', at: 4, segs: [['shots      ', C.key], ['12 recipe cards', C.val], [' · 2.5D', C.dim]] },
      { mark: 'spin', at: 8, segs: [['audio      ', C.key], ['beat grid at ', C.dim], ['120 bpm', C.val]] },
      { mark: 'pass', at: 14, segs: [['ready      ', C.ok], ['next: shotcraft render', C.val]] },
    ],
  },
  {
    step: '02', name: 'render', path: '~/promo', cmd: 'shotcraft render',
    lines: [
      { at: 0, segs: [] }, // Progress bar + counter (custom rendering)
      { at: 10, segs: [['DONE ', C.ok], [' act-1/opening     ', C.val], [' 8', C.dim]] },
      { at: 14, segs: [['DONE ', C.ok], [' act-2/features    ', C.val], ['10', C.dim]] },
      { at: 18, segs: [['DONE ', C.ok], [' act-3/outro       ', C.val], [' 6', C.dim]] },
      { mark: 'pass', at: 24, segs: [['24 shots', C.ok], ['  ·  ', C.dim], ['1080p · 30fps', C.val]] },
    ],
  },
  {
    step: '03', name: 'export', path: '~/promo', cmd: 'shotcraft export',
    lines: [
      { mark: 'spin', at: 0, segs: [['mix        ', C.key], ['voice + sfx', C.val], [' · -14 LUFS', C.dim]] },
      { mark: 'spin', at: 4, segs: [['encode     ', C.key], ['h264 · 1080p30', C.val]] },
      { mark: 'spin', at: 8, segs: [['jianying   ', C.key], ['draft exported', C.val]] },
      { at: 15, big: true, segs: [] }, // ● READY artifact title (custom rendering)
    ],
  },
];

// Keystroke cadence: baseline 1.15f/char + deterministic jitter; returns frame offset of char k
const charTimes = (cmd: string, seed: number) => {
  const out: number[] = [];
  let t = 0;
  for (let k = 0; k < cmd.length; k++) {
    out.push(t);
    const c = cmd[k];
    t += 0.75 + rand(seed * 31 + k) * 0.9 + (c === ' ' ? 0.6 : 0);
  }
  return { out, end: t };
};
const TYPING = WINS.map((w, i) => charTimes(w.cmd, i + 3));
const enterAt = (i: number) => TYPE_AT[i] + TYPING[i].end + 2; // Pause 2f after typing before Enter
const SPIN = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

const Mark: React.FC<{ kind: 'spin' | 'pass'; t: number }> = ({ kind, t }) => {
  const done = kind === 'pass' || t > 6;
  return (
    <span style={{ display: 'inline-block', width: '1.6em', color: done ? C.ok : C.dim }}>
      {done ? '✓' : SPIN[Math.floor(t * 1.5) % SPIN.length]}
    </span>
  );
};

const Terminal: React.FC<{ i: number; frame: number; focus: number }> = ({ i, frame, focus }) => {
  const w = WINS[i];
  const t0 = TYPE_AT[i];
  const tf = frame - t0;
  const n = TYPING[i].out.filter((x) => x <= tf).length;
  const typing = tf >= 0 && n < w.cmd.length;
  const ent = enterAt(i);
  const caretOn = typing || Math.floor((frame - (tf < 0 ? 0 : t0 + TYPING[i].end)) / 8) % 2 === 0;
  const out0 = ent + 2;
  const lineIn = (at: number) => ramp(frame, out0 + at, 6, EASE.snappy);

  return (
    <div style={{
      position: 'absolute', inset: 0, borderRadius: 22, overflow: 'hidden',
      background: `linear-gradient(180deg, #20241b 0%, #181b14 30%, #111309 100%)`,
      boxShadow: `inset 0 0 0 1.5px ${alpha('#e8ffc0', 0.1 + 0.08 * focus)}, inset 0 2px 0 ${alpha('#ffffff', 0.08 + 0.1 * focus)}`,
      fontFamily: MONO,
    }}>
      {/* Title bar: three dots (desaturated) + step number / name + path */}
      <div style={{
        position: 'absolute', left: 0, top: 0, right: 0, height: 72, display: 'flex', alignItems: 'center',
        padding: '0 30px', gap: 14, borderBottom: `1.5px solid ${alpha('#e8ffc0', 0.07)}`,
        background: `linear-gradient(180deg, ${alpha('#ffffff', 0.035)}, ${alpha('#ffffff', 0)})`,
      }}>
        {[0, 1, 2].map((k) => (
          <div key={k} style={{ width: 16, height: 16, borderRadius: 8, background: alpha(L.ink, 0.16), boxShadow: `inset 0 1px 0 ${alpha('#ffffff', 0.12)}` }} />
        ))}
        <div style={{ marginLeft: 22, fontSize: 24, fontWeight: 700, color: L.accent, letterSpacing: '0.04em' }}>{w.step}</div>
        <div style={{ fontSize: 24, fontWeight: 500, color: L.ink2, letterSpacing: '0.02em' }}>{w.name}</div>
        <div style={{ marginLeft: 'auto', fontSize: 22, color: L.ink3 }}>{w.path} — zsh</div>
      </div>

      {/* Command line: permanent prompt + typed characters + adjacent block cursor */}
      <div style={{ position: 'absolute', left: 56, top: 124, fontSize: 52, fontWeight: 600, color: L.ink, whiteSpace: 'pre', lineHeight: 1 }}>
        <span style={{ color: L.accent }}>❯ </span>
        {w.cmd.slice(0, Math.max(0, n))}
        {frame < ent + 1 && (
          <span style={{
            display: 'inline-block', width: '0.58em', height: '1.08em', marginLeft: 4, verticalAlign: '-0.16em',
            borderRadius: 3, background: L.accent, opacity: caretOn ? 0.95 : 0,
          }} />
        )}
      </div>

      {/* Output */}
      <div style={{ position: 'absolute', left: 56, right: 56, top: 220 }}>
        {w.lines.map((ln, k) => {
          const p = lineIn(ln.at);
          if (p <= 0) return null;
          const lt = frame - (out0 + ln.at);
          const style: React.CSSProperties = {
            position: 'absolute', left: 0, top: k * 70, fontSize: 38, fontWeight: 500, whiteSpace: 'pre', lineHeight: 1,
            opacity: Math.min(1, p * 1.8), transform: `translateX(${((1 - p) * -10).toFixed(2)}px)`,
          };
          if (i === 1 && k === 0) {
            // Progress cells + shot counter (20f out curve; one cell per shot)
            const c = ramp(frame, out0, 20, EASE.out);
            const N = 24;
            return (
              <div key={k} style={{ ...style, display: 'flex', alignItems: 'center', gap: 22 }}>
                <div style={{ display: 'flex', gap: 5 }}>
                  {Array.from({ length: N }, (_, j) => (
                    <div key={j} style={{
                      width: 17, height: 34, borderRadius: 3,
                      background: j < Math.round(c * N) ? L.accent : alpha(L.ink, 0.1),
                    }} />
                  ))}
                </div>
                <span style={{ color: L.ink, fontVariantNumeric: 'tabular-nums' }}>{String(Math.round(c * N)).padStart(2, ' ')}</span>
                <span style={{ color: L.ink3 }}>/ {N} shots</span>
              </div>
            );
          }
          if (ln.big) {
            // ● READY artifact title: sequence's only bloom glow (Q4)
            const pop = ramp(frame, out0 + ln.at, 14, EASE.overshoot);
            const g = ramp(frame, out0 + ln.at, 26, EASE.out);
            const pulse = 0.55 + 0.45 * Math.cos(Math.max(0, lt) / 6);
            return (
              <div key={k} style={{
                ...style, top: k * 70 + 16, display: 'flex', alignItems: 'center', gap: 26,
                transform: `translateX(${((1 - p) * -10).toFixed(2)}px) scale(${mix(0.94, 1, pop).toFixed(4)})`, transformOrigin: 'left center',
              }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 14, height: 56, padding: '0 22px', borderRadius: 12,
                  background: L.accent, color: L.onAccent, fontSize: 30, fontWeight: 800, letterSpacing: '0.08em',
                  boxShadow: `0 0 ${(40 * g).toFixed(1)}px ${alpha(L.accent, 0.45 * g)}`,
                }}>
                  <div style={{ width: 14, height: 14, borderRadius: 7, background: L.onAccent, opacity: 0.4 + 0.6 * pulse }} />
                  READY
                </div>
                <span style={{ fontSize: 52, fontWeight: 700, color: L.accent, letterSpacing: '-0.01em', textShadow: glow(L.accent, 0.55 * g) }}>
                  launch-film.mp4
                </span>
              </div>
            );
          }
          return (
            <div key={k} style={style}>
              {ln.mark && <Mark kind={ln.mark} t={lt} />}
              {!ln.mark && <span style={{ display: 'inline-block', width: '0em' }} />}
              {ln.segs.map(([s, c], j) => <span key={j} style={{ color: c }}>{s}</span>)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ───────────── Main Component ─────────────
export const Terminal3D: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(frame);
  const v = cam.pose;

  // Lateral screen speed (px/frame): camera target screen translation speed → directional blur, active only during flight
  const a = camAt(frame - 0.5), b = camAt(frame + 0.5);
  const kS = PERSP / (PERSP + cam.pull);
  const vx = -(b.pose.x - a.pose.x) * kS;
  const vy = -(b.pose.y - a.pose.y) * kS;

  const world = `translateZ(${(-cam.pull).toFixed(2)}px) rotateX(${TILT}deg) rotateY(${cam.yaw.toFixed(3)}deg) translate3d(${(-v.x).toFixed(2)}px,${(-v.y).toFixed(2)}px,${(-v.z).toFixed(2)}px)`;

  return (
    <AbsoluteFill style={{ background: L.bg[2] }}>
      <Stage look={STAGE} keyLight={{ x: 0.36, y: -0.06 }} fill={{ x: 0.82, y: 1.0 }} horizon={0.47} intensity={1} breathe={0.4}>
        <Floor cam={cam} frame={frame} />
        {[0, 1, 2].map((i) => (
          <BackLight key={`b${i}`} cam={cam} i={i} on={Math.max(0, 1 - Math.abs(cam.s - i))} />
        ))}
        {[0, 1, 2].map((i) => (
          <FloorPool key={i} cam={cam} i={i} on={Math.max(0, 1 - Math.abs(cam.s - i))} />
        ))}
        <Dust look={L} count={36} seed={5} drift={0.35} opacity={0.45} />
      </Stage>
      <SpeedBlur vx={vx} vy={vy} amount={0.14} max={10}>
        <div style={{ position: 'absolute', inset: 0, perspective: PERSP, overflow: 'hidden' }}>
          <div style={{ position: 'absolute', left: 960, top: 540, width: 0, height: 0, transformStyle: 'preserve-3d', transform: world }}>
            {POSES.map((p, i) => {
              // Depth of field: farther stations blur more; depth expands during pull-back (all 3 visible as terminals), defocus narrows with pull-back
              const wide = Math.min(1, Math.max(0, cam.pull / PULL_PEAK));
              const focus = Math.min(1, Math.max(0, 1 - Math.abs(cam.s - i) * 1.25) + wide * 0.45);
              const blur = (1 - focus) * 3;
              return (
                <React.Fragment key={i}>
                  {/* Stroked step number behind window (matches window yaw, located top-left behind window) */}
                  <div style={{
                    position: 'absolute', left: -W / 2 - 120, top: -H / 2 - 270, whiteSpace: 'nowrap',
                    transform: `translate3d(${p.x}px,${p.y}px,${p.z - 380}px) rotateY(${p.ry}deg)`,
                    fontFamily: FONT.sans, fontSize: 560, fontWeight: 800, lineHeight: 1, letterSpacing: '-0.05em',
                    color: 'transparent', WebkitTextStroke: `2px ${alpha(L.accent, 0.07 + 0.3 * focus)}`,
                  }}>{WINS[i].step}</div>
                  {/* Window */}
                  <div style={{
                    position: 'absolute', left: -W / 2, top: -H / 2, width: W, height: H,
                    transform: `translate3d(${p.x}px,${p.y}px,${p.z}px) rotateY(${p.ry}deg)`,
                    borderRadius: 22,
                    boxShadow: `0 50px 120px ${alpha('#000000', 0.7)}, 0 0 0 1px ${alpha('#000000', 0.4)}, 0 0 90px ${alpha(L.accent, 0.07 * focus)}`,
                    filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px) brightness(${(0.62 + 0.38 * focus).toFixed(3)})` : undefined,
                    opacity: 0.72 + 0.28 * focus,
                  }}>
                    <Terminal i={i} frame={frame} focus={focus} />
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </SpeedBlur>
    </AbsoluteFill>
  );
};
