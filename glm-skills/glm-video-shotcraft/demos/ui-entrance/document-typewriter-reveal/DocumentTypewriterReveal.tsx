// document-typewriter-reveal — Full typographic document "types" itself out behind a cursor, sidebars follow, historical items drop into track
// (Redesign v2 · Aurora dark stage · Floating app window)
// Core technique unchanged: content blocks "typed" out in pairs on beat (page-color mask shrinks right-anchored, accent caret rides leading reveal edge, strictly one caret at any time);
// name headings sprout an accent background after completion; left and right rails reveal top-down; 6 past weekly reports drop into the left rail in the final segment.
//
// Design decisions:
// - look = aurora (violet night + violet/pink light). Retains real weekly report screenshot (Q1), but no longer full-screen: it floats as an app window
//   on the violet night stage — rounded corners, hairline highlight border, violet backlight, long drop shadow; warm white paper glows like a lamp in the cold violet night.
// - Camera (monotonic Hermite spline, smooth velocity transitions): starts at 1.42x angled close-up (rotY -18°) on heading, window top-left and stage light enter together;
//   as caret types downward, camera dollies back and reduces tilt angle to reveal the full window (both rails fully visible, Q10); finally tilts slightly downward and pans up to make room for a bottom tagline.
// - Caret: deep violet 3px caret + matching soft glow; member name heading accent changed to aurora violet multiply (tints paper without washing out text).
// - Closing tagline "From screenshot / to showreel." (video-shotcraft slogan: transforming screenshots into cinematic reels) — second segment in accent, bottom-aligned with left window margin.
//   Screenshot texture and history items represent the captured document itself (aligned with baked-in texture entries), kept intact.
//
// Timeline (30fps, 150f total):
//   0–8     Title close-up framed (window + light), caret rests at title start
//   8–58    Type-in: 20 blocks in pairs, g-th pair cue = 8 + 4.4g, 9f each (in-out), final pair finishes ~57f
//   0–64    Camera dollies back: 1.42x angled -> 0.86x full window
//   54/62   Left / right rails reveal top-down (10f) + inner accent line grows then fades
//   66–100  6 past weekly reports drop into left rail (one every 5f, 9f gentle bounce + airborne shadow)
//   70–104  Camera tilts slightly downward and shifts up to poster framing (0.74x)
//   100–126 Tagline rises word by word
//   126–150 hold: 0.8% subtle push-in, breathing light
import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { EASE, FONT, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, Dust, TextReveal, alpha, type } from '../../_fixtures/Look';
import layout from '../../_textures/live-layout.json';

export const DOCUMENT_TYPEWRITER_REVEAL_DURATION = 150;

const L = LOOKS.aurora;
type Block = { x: number; y: number; w: number; h: number; tag: string };
const blocks = layout.wbr.blocks as Block[];
const leftRail = layout.wbr.leftRail;
const rightRail = layout.wbr.rightRail;
const PAGE_W = 1920;
const PAGE_H = layout.wbr.pageH;

const PAPER = '#fefcf9'; // Measured paper color from texture
const CARET = '#7a4dff'; // Deeper aurora violet for visibility on warm white paper
const WASH = 'rgba(196,170,255,0.4)';
const SANS = 'ui-sans-serif, system-ui, -apple-system, sans-serif';

// ───────────── Camera ─────────────
type Cam = { cx: number; cy: number; zoom: number; rotX: number; rotY: number; sx: number; sy: number };
type Key = Cam & { frame: number };
const ANCHORS: Key[] = [
  { frame: 0, cx: 690, cy: 320, zoom: 1.42, rotX: 8, rotY: -18, sx: 0, sy: 0 },
  { frame: 26, cx: 770, cy: 390, zoom: 1.24, rotX: 6, rotY: -13, sx: 0, sy: 0 },
  { frame: 64, cx: 960, cy: 540, zoom: 0.86, rotX: 4, rotY: -6, sx: 0, sy: -10 },
  { frame: 104, cx: 960, cy: 540, zoom: 0.74, rotX: 9, rotY: -3, sx: 0, sy: -78 },
  { frame: 150, cx: 960, cy: 540, zoom: 0.746, rotX: 9, rotY: -3, sx: 0, sy: -80 },
];
const PARAMS: (keyof Cam)[] = ['cx', 'cy', 'zoom', 'rotX', 'rotY', 'sx', 'sy'];
const hermite = (xs: number[], ys: number[]) => {
  const n = xs.length;
  const d = xs.slice(0, -1).map((x, i) => (ys[i + 1] - ys[i]) / (xs[i + 1] - x));
  const m = xs.map((_, i) => (i === 0 || i === n - 1 ? 0 : d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2));
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], h = a * a + b * b;
    if (h > 9) { const k = 3 / Math.sqrt(h); m[i] = k * a * d[i]; m[i + 1] = k * b * d[i]; }
  }
  return (x: number) => {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[n - 1]) return ys[n - 1];
    let i = 0;
    while (i < n - 2 && x > xs[i + 1]) i++;
    const h = xs[i + 1] - xs[i];
    const t = (x - xs[i]) / h;
    const t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m[i + 1];
  };
};
const CURVES = Object.fromEntries(PARAMS.map((p) => [p, hermite(ANCHORS.map((k) => k.frame), ANCHORS.map((k) => k[p]))])) as Record<keyof Cam, (x: number) => number>;
const camAt = (f: number): Cam => Object.fromEntries(PARAMS.map((p) => [p, CURVES[p](f)])) as Cam;
// Camera layer: layout-level zoom (Q2), mapping page coordinate (cx, cy) to screen (960+sx, 540+sy)
const PERSP = 2200;

// ───────────── Typing rhythm ─────────────
const REVEAL_EASE = Easing.bezier(0.4, 0, 0.6, 1);
const cueFor = (i: number) => 8 + Math.floor(i / 2) * 4.4;
const WIPE = 9;

const PAST_WEEKS = [
  { week: '2026 Week 27', date: 'Jul 3', title: '2026-W27 · Shotcraft Weekly' },
  { week: '2026 Week 26', date: 'Jun 26', title: '2026-W26 · Shotcraft Weekly' },
  { week: '2026 Week 25', date: 'Jun 19', title: '2026-W25 · Shotcraft Weekly' },
  { week: '2026 Week 24', date: 'Jun 12', title: '2026-W24 · Shotcraft Weekly' },
  { week: '2026 Week 23', date: 'Jun 5', title: '2026-W23 · Shotcraft Weekly' },
  { week: '2026 Week 22', date: 'May 29', title: '2026-W22 · Shotcraft Weekly' },
];
const WEEK_Y0 = 228;
const WEEK_H = 56;
const WEEK_CUE = (i: number) => 66 + i * 5;
const WEEK_DROP = Easing.bezier(0.2, 1.15, 0.3, 1);

// Member name headings (tag=h2, skipping first "Jackie's Download" summary header) sprout accent background after typing finishes
const memberH2 = new Set<number>();
{
  let seenH2 = 0;
  blocks.forEach((b, i) => {
    if (b.tag === 'h2' && seenH2++ > 0) memberH2.add(i);
  });
}

export const DocumentTypewriterReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const cam = camAt(frame);

  // Single caret: tracks the latest block actively being typed
  let caretIdx = -1;
  blocks.forEach((_, i) => {
    if (frame >= cueFor(i) && frame <= cueFor(i) + WIPE + 2) caretIdx = i;
  });
  // Opening 8f: caret blinks on standby at title start
  const idleBlink = frame < cueFor(0) ? (Math.floor(frame / 4) % 2 === 0 ? 1 : 0.25) : 0;

  const tagIn = ramp(frame, 100, 20, EASE.out);

  return (
    <AbsoluteFill style={{ fontFamily: FONT.sans, overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.02 }} fill={{ x: 0.88, y: 0.95 }} horizon={0.9} breathe={0.7} intensity={0.9}>
        <Dust look={L} count={24} seed={9} drift={0.16} opacity={0.4} />
      </Stage>

      {/* 3D camera */}
      <AbsoluteFill style={{ transform: `translate(${cam.sx.toFixed(2)}px, ${cam.sy.toFixed(2)}px)` }}>
        <div style={{ position: 'absolute', inset: 0, perspective: `${(PERSP * cam.zoom).toFixed(2)}px`, perspectiveOrigin: '960px 540px' }}>
          <div
            style={{
              position: 'absolute', width: PAGE_W, height: PAGE_H, zoom: cam.zoom,
              transform: `translate(${(960 / cam.zoom - cam.cx).toFixed(3)}px, ${(540 / cam.zoom - cam.cy).toFixed(3)}px) rotateY(${cam.rotY.toFixed(3)}deg) rotateX(${cam.rotX.toFixed(3)}deg)`,
              transformOrigin: `${cam.cx.toFixed(2)}px ${cam.cy.toFixed(2)}px`,
              transformStyle: 'preserve-3d',
            }}
          >
            {/* Backlight: violet glow halo behind window (page space, perspectives with window) */}
            <div
              style={{
                position: 'absolute', left: -220, top: -180, width: PAGE_W + 440, height: PAGE_H + 400, pointerEvents: 'none',
                background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.34)} 0%, ${alpha(L.accent2, 0.1)} 55%, transparent 72%)`,
                transform: 'translateZ(-40px)',
              }}
            />
            {/* App window: screenshot + type-in masks + rails + history items, all clipped to rounded corners */}
            <div
              style={{
                position: 'absolute', left: 0, top: 0, width: PAGE_W, height: PAGE_H, borderRadius: 26, overflow: 'hidden',
                background: PAPER,
                boxShadow: `0 0 0 1.5px ${alpha('#ffffff', 0.35)}, 0 70px 160px -20px ${alpha(L.shadow, 0.95)}, 0 20px 60px ${alpha('#000000', 0.55)}`,
              }}
            >
              <Img src={staticFile('textures/live/wbr-full.png')} style={{ position: 'absolute', width: PAGE_W, height: PAGE_H }} />

              {blocks.map((p, i) => {
                const cue = cueFor(i);
                const coverT = interpolate(frame, [cue, cue + WIPE], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: REVEAL_EASE });
                const bx = p.tag === 'li' ? p.x - 28 : p.x - 4;
                const by = p.y - 3;
                const bw = p.w + (p.tag === 'li' ? 34 : 10) + (p.tag === 'li' ? 24 : 120);
                const bh = p.h + 6;
                const caretX = bx + bw * (1 - coverT);
                const caretH = Math.min(22, p.h - 2);
                const nameCue = cue + WIPE + 4;
                const nameGrow = memberH2.has(i)
                  ? interpolate(frame, [nameCue, nameCue + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) })
                  : 0;
                // Active typing caret tracks within actual text width (ignores trailing mask whitespace)
                const textRight = p.x + p.w + 6;
                return (
                  <React.Fragment key={i}>
                    {nameGrow > 0 ? (
                      <div style={{ position: 'absolute', left: p.x - 4, top: p.y - 1, width: (p.w + 10) * nameGrow, height: p.h + 2, background: WASH, borderRadius: 4, mixBlendMode: 'multiply' }} />
                    ) : null}
                    {coverT > 0 ? (
                      <div style={{ position: 'absolute', left: bx, top: by, width: bw, height: bh, overflow: 'hidden' }}>
                        <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${coverT * 100}%`, background: PAPER }} />
                      </div>
                    ) : null}
                    {i === caretIdx ? (
                      <div
                        style={{
                          position: 'absolute', left: Math.min(caretX, textRight), top: p.y + (p.h - caretH) / 2, width: 3, height: caretH, background: CARET, borderRadius: 2,
                          boxShadow: `0 0 8px ${alpha(CARET, 0.6)}, 0 0 20px ${alpha(L.accent, 0.45)}`,
                          opacity: coverT > 0 ? 1 : interpolate(frame, [cue + WIPE, cue + WIPE + 2], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
                        }}
                      />
                    ) : null}
                  </React.Fragment>
                );
              })}
              {/* Opening standby caret */}
              {idleBlink > 0 ? (
                <div style={{ position: 'absolute', left: blocks[0].x - 4, top: blocks[0].y + 3, width: 3, height: 22, background: CARET, borderRadius: 2, opacity: idleBlink, boxShadow: `0 0 8px ${alpha(CARET, 0.6)}` }} />
              ) : null}

              {/* Dual-rail reveal: paper patches retract top-down, inner accent line grows with reveal then fades */}
              {[
                { rail: leftRail, cue: 54, inner: 'right' as const },
                { rail: rightRail, cue: 62, inner: 'left' as const },
              ].map(({ rail, cue, inner }, i) => {
                const t = interpolate(frame, [cue, cue + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
                const lineFade = interpolate(frame, [cue + 10, cue + 24], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                return (
                  <React.Fragment key={`rail${i}`}>
                    {t < 1 ? <div style={{ position: 'absolute', left: rail.x, top: rail.y + rail.h * t, width: rail.w, height: rail.h * (1 - t), background: PAPER }} /> : null}
                    {frame >= cue && lineFade > 0 ? (
                      <div style={{ position: 'absolute', left: inner === 'right' ? rail.x + rail.w - 2 : rail.x, top: rail.y, width: 2, height: rail.h * t, background: CARET, opacity: lineFade, boxShadow: `0 0 10px ${alpha(L.accent, 0.6)}` }} />
                    ) : null}
                  </React.Fragment>
                );
              })}

              {/* Past weekly reports: drop into left rail from above */}
              {PAST_WEEKS.map((w, i) => {
                const cue = WEEK_CUE(i);
                if (frame < cue) return null;
                const t = interpolate(frame, [cue, cue + 9], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: WEEK_DROP });
                const appear = interpolate(frame, [cue, cue + 3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                const air = Math.max(0, 1 - t);
                return (
                  <div
                    key={w.week}
                    style={{
                      position: 'absolute', left: 4, top: WEEK_Y0 + i * WEEK_H, width: leftRail.w - 8, height: WEEK_H,
                      transform: `translateY(${-48 * air}px)`, opacity: appear,
                      boxShadow: air > 0.02 ? `0 ${12 * air}px ${24 * air}px rgba(40,20,60,${0.2 * air})` : 'none',
                      background: PAPER, borderBottom: '1px solid rgba(31,41,55,0.07)', padding: '8px 10px 0', boxSizing: 'border-box', fontFamily: SANS,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <span style={{ fontSize: 13, fontWeight: 500, color: '#1f2937' }}>{w.week}</span>
                      <span style={{ fontSize: 10, color: '#9ca3af' }}>{w.date}</span>
                    </div>
                    <div style={{ marginTop: 2, fontSize: 11, color: '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{w.title}</div>
                  </div>
                );
              })}
              {/* Window top specular: subtle edge highlight (glass feel) */}
              <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 3, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.9), transparent)' }} />
            </div>
          </div>
        </div>
      </AbsoluteFill>

      {/* Closing tagline: bottom, left-aligned with window margin */}
      <div style={{ position: 'absolute', left: 250, top: 930, display: 'flex', alignItems: 'baseline', gap: 0, ...type(84, 760), color: L.ink, opacity: tagIn > 0 ? 1 : 0 }}>
        <TextReveal text="From screenshot" by="word" variant="rise" start={100} each={16} gap={3} />
        <TextReveal text="to showreel." by="word" variant="rise" start={108} each={16} gap={3} style={{ color: L.accent, marginLeft: '0.26em' }} />
      </div>
    </AbsoluteFill>
  );
};
