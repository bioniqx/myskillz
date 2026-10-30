// outline-word-fill — Outline to Solid Fill instantaneous illumination
// Outlined word rapidly scales down ~3.2x into center; dashed circle continuously contracts from off-screen rotating slowly;
// horizontal dashed crosshair lines extend inward; outline preheats then hard cuts to solid fill in 1 frame with a single flash.
//
// Redesign (technical drafting HUD: white-hot illumination):
// - look = ember (warm dark base, amber-orange). Native 1920 layout: 220px Helvetica Neue
//   outlined text (2px warm gray stroke), r=410 dashed circle + inner 72-tick reticle ring (counter-rotating) + register marks, mono readouts
//   "BEFORE 1 week" / "AFTER 4 hrs" — communicating speedup via before/after comparison data.
// - Illumination: frame 54 cuts directly to white-hot solid fill (#fff5ee); circle and crosshairs lock to orange, "4 hrs" turns orange;
//   dual-layer bloom decays over 8f; shockwave ring expands from circle edge over 14f; key light pulses once.
// - Outer circle rotation brakes to a stop on illumination (locked), while inner reticle continues counter-rotation.
// - Curves: snappy 11f text scale contraction (with velocity defocus), slow 44f circle contraction,
//   contrasting tempos; crosshairs extend over 18f, stopping 28px outside circle.
// - Static font used (Helvetica Neue) to avoid variable font internal stroke intersection artifacts.
//
// Timeline (30fps, total 90f):
//   0-2    Stage lighting and dust established on frame 0
//   2-13   Outlined text scales 3.2->1 (fades in 2-8)
//   8-52   Dashed circle contracts 2.8->1 with rotation (fades in 8-18)
//   28-46  Crosshairs extend, readouts fade in
//   44-53  Stroke preheat: warm gray -> glowing amber-white
//   54     Direct cut illumination + lock (rotation brakes); 54-62 bloom decay; 54-68 shockwave
//   56-70  Kicker / subtitle rise inside circle
//   70-90  Hold 20f (slow 1.5% push)
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, mix, ramp } from '../../_fixtures/Polish';
import { Dust, LOOKS, Stage, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const OUTLINE_WORD_FILL_DURATION = 90; // 3.0s @30fps

const L = LOOKS.ember;
const CX = 960;
const CY = 540;
const R = 410; // Dashed circle radius
const WORD = 'Faster';
const SIZE = 220;
const POP = 54; // Illumination cut frame
const STATIC_SANS = '"Helvetica Neue", Helvetica, Arial, sans-serif';

const lerpColor = (a: [number, number, number], b: [number, number, number], t: number) =>
  `rgb(${Math.round(mix(a[0], b[0], t))},${Math.round(mix(a[1], b[1], t))},${Math.round(mix(a[2], b[2], t))})`;
const GREY: [number, number, number] = [138, 118, 104]; // Warm gray stroke / drafting lines
const HOT: [number, number, number] = [255, 196, 150]; // Preheated amber-white
const ORANGE: [number, number, number] = [255, 107, 44];

const wordScaleAt = (f: number) => mix(3.2, 1, ramp(f, 2, 11, EASE.snappy));

export const OutlineWordFill: React.FC = () => {
  const frame = useCurrentFrame();

  const born = ramp(frame, 2, 6, EASE.out);
  const ws = wordScaleAt(frame);
  const zoomBlur = Math.min(6, Math.abs(wordScaleAt(frame + 0.5) - wordScaleAt(frame - 0.5)) * 9);
  const cin = ramp(frame, 8, 10, EASE.out);
  const shrink = ramp(frame, 8, 44, EASE.out);
  const ext = ramp(frame, 28, 18, EASE.out);
  const warm = ramp(frame, 44, 9, EASE.swift);
  const lit = frame >= POP ? 1 : 0; // Direct cut: discrete binary state
  const flash = lit * (1 - ramp(frame, POP, 8, EASE.out));
  const lock = lit * (0.55 + 0.45 * flash); // Retains amber tone after lock
  const shock = ramp(frame, POP, 14, EASE.out);
  // Outer circle brakes to stop on lock; inner reticle continues counter-rotation during hold
  const rot = 0.22 * Math.min(frame, POP) + (frame > POP ? 6 * ramp(frame, POP, 14, EASE.out) : 0);
  const rotIn = -0.14 * frame;
  const sub = (d: number) => ramp(frame, 56 + d, 14, EASE.snappy);
  const push = 1 + 0.015 * ramp(frame, 0, OUTLINE_WORD_FILL_DURATION, EASE.swift);

  const strokeC = lerpColor(GREY, HOT, warm);
  const lineC = lit ? lerpColor([150, 120, 100], ORANGE, lock) : lerpColor(GREY, [150, 120, 100], warm);
  const lineEnd = CX - R - 28; // Crosshairs terminate 28px outside circle

  return (
    <AbsoluteFill style={{ background: L.bg[1] }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.5 }} fill={{ x: 0.5, y: 1.1 }} intensity={0.45 + 0.5 * flash + 0.15 * lit} grain={0.09} vignette={0.6}>
        <Dust look={L} count={22} seed={3} drift={0.12} opacity={0.4} />
      </Stage>

      <AbsoluteFill style={{ transform: `scale(${push.toFixed(5)})` }}>
        <svg width={1920} height={1080} viewBox="0 0 1920 1080" style={{ position: 'absolute', inset: 0 }}>
          {/* Shockwave ring: expands outward from circle on cut */}
          {lit > 0 && shock < 1 && (
            <circle cx={CX} cy={CY} r={R + shock * 160} fill="none" stroke={alpha('#ff8a4c', 0.55 * (1 - shock))} strokeWidth={2 + 10 * (1 - shock)} />
          )}
          <g transform={`translate(${CX} ${CY}) scale(${mix(2.8, 1, shrink).toFixed(5)})`} opacity={cin}>
            {/* Main dashed circle (rotating) */}
            <g transform={`rotate(${rot.toFixed(3)})`}>
              <circle r={R} fill="none" stroke={lineC} strokeWidth={2} strokeDasharray="22 18" />
              {[0, 90, 180, 270].map((a) => (
                <line key={a} x1={0} y1={-R - 22} x2={0} y2={-R + 10} stroke={lineC} strokeWidth={2.5} strokeLinecap="round" transform={`rotate(${a})`} />
              ))}
            </g>
            {/* Inner reticle ring (counter-rotating, dimmed texture layer) */}
            <g transform={`rotate(${rotIn.toFixed(3)})`}>
              <circle r={R - 34} fill="none" stroke={lineC} strokeWidth={1} opacity={0.35} />
              {Array.from({ length: 72 }, (_, i) => {
                const major = i % 6 === 0;
                return (
                  <line key={i} x1={0} y1={-(R - 34)} x2={0} y2={-(R - (major ? 58 : 44))} stroke={lineC}
                    strokeWidth={major ? 2 : 1.2} opacity={major ? 0.7 : 0.32} transform={`rotate(${i * 5})`} />
                );
              })}
            </g>
          </g>
          {/* Horizontal dashed crosshairs extending inward */}
          <line x1={0} y1={CY} x2={lineEnd * ext} y2={CY} stroke={lineC} strokeWidth={2} strokeDasharray="14 12" opacity={ext} />
          <line x1={1920} y1={CY} x2={1920 - lineEnd * ext} y2={CY} stroke={lineC} strokeWidth={2} strokeDasharray="14 12" opacity={ext} />
          {/* Crosshair target dots */}
          <circle cx={lineEnd * ext} cy={CY} r={5} fill={lineC} opacity={ext} />
          <circle cx={1920 - lineEnd * ext} cy={CY} r={5} fill={lineC} opacity={ext} />
        </svg>

        {/* Readouts: left = before, right = after (turns orange on lock) */}
        <div style={{ position: 'absolute', left: 120, top: CY - 74, opacity: ext, transform: `translateX(${((1 - ext) * -30).toFixed(2)}px)`, ...type(30, 500, { mono: true }), letterSpacing: '0.12em', color: L.ink3 }}>
          BEFORE <span style={{ color: L.ink2 }}>1 week</span>
        </div>
        <div style={{ position: 'absolute', right: 120, top: CY - 74, opacity: ext, transform: `translateX(${((1 - ext) * 30).toFixed(2)}px)`, ...type(30, 500, { mono: true }), letterSpacing: '0.12em', color: L.ink3, textAlign: 'right' }}>
          AFTER <span style={{ color: lit ? L.accent : L.ink2, textShadow: lit && flash > 0.02 ? `0 0 ${(18 * flash).toFixed(1)}px ${alpha(L.accent, 0.8)}` : undefined }}>4 hrs</span>
        </div>

        {/* Kicker / subtitle within circle boundaries */}
        {/* Kicker = brand mark + lowercase wordmark */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: CY - 200, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16, opacity: sub(0), transform: `translateY(${((1 - sub(0)) * 16).toFixed(2)}px)`, ...type(28, 600, { mono: true }), letterSpacing: '0.16em', color: L.ink2 }}>
          <ShotcraftMark size={40} tone="dark" />
          <span>{BRAND.name}</span>
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, top: CY + 128, textAlign: 'center', opacity: sub(3), transform: `translateY(${((1 - sub(3)) * 16).toFixed(2)}px)`, ...type(40, 450), letterSpacing: '-0.01em', color: L.ink2 }}>
          One prompt to a finished promo.
        </div>

        {/* Dual-layer typography: bottom outline stroke, top solid white-hot fill (cut) */}
        <div style={{
          position: 'absolute', left: CX, top: CY, fontFamily: STATIC_SANS, fontSize: SIZE, fontWeight: 500, letterSpacing: '0.005em', lineHeight: 1,
          opacity: born, transform: `translate(-50%, -54%) scale(${ws.toFixed(5)})`, whiteSpace: 'nowrap',
        }}>
          <div style={{
            color: 'transparent', WebkitTextStroke: `2px ${strokeC}`, opacity: 1 - lit,
            filter: zoomBlur > 0.05 ? `blur(${(zoomBlur / ws).toFixed(2)}px)` : warm > 0.01 ? `drop-shadow(0 0 ${(10 * warm).toFixed(1)}px ${alpha('#ff9a5c', 0.5 * warm)})` : undefined,
          }}>
            {WORD}
          </div>
          <div style={{
            position: 'absolute', inset: 0, color: '#fff5ee', opacity: lit,
            textShadow: flash > 0.01 ? `0 0 ${(14 * flash).toFixed(1)}px rgba(255,255,255,${(0.7 * flash).toFixed(3)}), 0 0 ${(60 * flash).toFixed(1)}px ${alpha(L.accent, 0.65 * flash)}` : `0 0 40px ${alpha(L.accent, 0.18)}`,
          }}>
            {WORD}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
