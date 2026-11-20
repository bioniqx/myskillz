// gradient-transition — smooth transition between linear, radial, and conic CSS gradients:
// Intra-type per-parameter interpolation (angle/stops/center/radius/start angle); narrow crossfade between types.
//
// Redesign (aurora violet: keynote opener):
// - look = aurora (violet-pink dark field). Gradients form the hero visual — foreground contains typography synced to gradient types:
//   "Bend light." (linear: angle sweep) -> "Focus it." (radial: diagonal roaming highlight) -> video-shotcraft wordmark (conic: rotating tricolor ring).
//   Verbs directly describe parameter motion in each section.
// - Color palette: shared violet / magenta / ice-blue gamut across all sections, darkened perimeter,
//   providing contrast for typography; conic uses A->B->C->A ring centered behind wordmark with pre-blur.
// - Performance: gradients rendered on 480x270 canvas scaled up 4x with grain overlay preventing banding.

// - Footer annotation: live readout of active gradient parameters (mono) and phase index.
//
// Timeline (30fps, total 200f):
//   0-68    linear: angle 18->198 deg, 3-stop HSL interpolation; 6-26f "Bend light." rises word-by-word
//   56-68   Crossfade linear -> radial (12f), both layers in motion
//   56-132  radial: center (24%,72%) -> (68%,38%) diagonal roam, radius 48%->80%; 52-62f prior text exits, 66-86f "Focus it."
//   118-132 Crossfade radial -> conic (14f)
//   118-200 conic: start angle 0->250 deg rotation (ease-out deceleration); 114-124f prior text exits,
//           128-150f wordmark tracking resolves, 140-160f brand tagline enters; 160-200f hold
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, Grain, bezier, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, TYPE, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, PITCH, ShotcraftMark } from '../../_fixtures/Brand';

export const GRADIENT_TRANSITION_DURATION = 200;

const L = LOOKS.aurora;

type H3 = [number, number, number];
const hsl = ([h, s, l]: H3, a = 1) => `hsla(${h.toFixed(1)},${s.toFixed(1)}%,${l.toFixed(1)}%,${a})`;
// HSL 3-channel interpolation (avoids graying compared to RGB)
const mixH = (a: H3, b: H3, k: number): H3 => [mix(a[0], b[0], k), mix(a[1], b[1], k), mix(a[2], b[2], k)];

// Small canvas: rendered at 480x270, scaled 4x
const SW = 480, SH = 270;
const SLOW = bezier(0.45, 0, 0.2, 1);

const layer = (background: string, opacity: number, extra?: React.CSSProperties): React.CSSProperties => ({
  position: 'absolute', inset: 0, background, opacity, ...extra,
});

export const GradientTransition: React.FC = () => {
  const f = useCurrentFrame();

  // --- linear: angle sweep + color stop drift ---
  const p1 = ramp(f, 0, 68, EASE.swift);
  const ang = mix(18, 198, p1);
  const l1a = mixH([300, 86, 64], [330, 88, 66], p1);
  const l1b = mixH([268, 76, 40], [250, 78, 44], p1);
  const l1c: H3 = [250, 62, 7];
  // Distinct stop lightness (64 -> 40 -> 7) visualizing angle sweep
  const bg1 =
    `radial-gradient(ellipse 60% 70% at ${mix(18, 70, p1).toFixed(1)}% ${mix(10, 22, p1).toFixed(1)}%, ${hsl(l1a, 0.3)}, ${hsl(l1a, 0)} 70%), ` +
    `linear-gradient(${ang.toFixed(2)}deg, ${hsl(l1a)} 0%, ${hsl(l1b)} 34%, ${hsl(l1c)} 78%, ${hsl(l1c)} 100%)`;

  // --- radial: diagonal center movement + radius expansion ---
  const p2 = ramp(f, 56, 76, EASE.swift);
  const rcx = mix(24, 68, p2), rcy = mix(72, 38, p2), rr = mix(48, 80, p2);
  const core = mixH([326, 92, 72], [282, 88, 70], p2);
  const mid = mixH([292, 72, 38], [256, 74, 36], p2);
  const rpx = (rr / 100) * SW;
  const bg2 =
    `radial-gradient(circle ${rpx.toFixed(1)}px at ${rcx.toFixed(2)}% ${rcy.toFixed(2)}%, ${hsl(core)} 0%, ${hsl(mid)} 36%, ${hsl([250, 62, 8])} 100%)`;

  // --- conic: tricolor ring A->B->C->A rotation, center offset behind wordmark ---
  const p3 = ramp(f, 118, 82, SLOW);
  const from = mix(0, 250, p3);
  const bg3 =
    `conic-gradient(from ${from.toFixed(2)}deg at 64% 54%, hsl(262,84%,60%), hsl(322,86%,64%), hsl(205,90%,68%), hsl(262,84%,60%))`;

  // Crossfade weights (narrow window)
  const x12 = ramp(f, 56, 12, EASE.smooth);
  const x23 = ramp(f, 118, 14, EASE.smooth);
  const w1 = 1 - x12;
  const w2 = x12 - x23;
  const w3 = x23;

  // Parameter readouts (footer annotation)
  const phase = f < 62 ? 0 : f < 125 ? 1 : 2;
  const readout = [
    `linear-gradient(${Math.round(ang)}deg, …)`,
    `radial-gradient(circle ${Math.round(rr)}% at ${Math.round(rcx)}% ${Math.round(rcy)}%)`,
    `conic-gradient(from ${Math.round(from)}deg at 64% 54%)`,
  ][phase];

  // video-shotcraft wordmark tracking tighten
  const markP = ramp(f, 128, 26, EASE.snappy);
  const subP = ramp(f, 142, 20, EASE.snappy);

  return (
    <AbsoluteFill style={{ background: L.bg[2], overflow: 'hidden' }}>
      {/* 3-layer background: rendered on small canvas, scaled 4x */}
      <div style={{ position: 'absolute', left: 0, top: 0, width: SW, height: SH, transform: `scale(${1920 / SW})`, transformOrigin: '0 0' }}>
        <div style={layer(bg1, w1)} />
        <div style={layer(bg2, w2)} />
        {w3 > 0.001 && (
          <div style={{ position: 'absolute', inset: 0, opacity: w3 }}>
            {/* Bleed and blur smoothing center artifact and banding */}
            <div style={layer(bg3, 1, { inset: -14, filter: 'blur(9px)' })} />
            {/* Edge and left-side vignette for text contrast */}
            <div style={layer(`radial-gradient(ellipse 62% 78% at 64% 54%, rgba(8,5,18,0) 18%, rgba(8,5,18,0.55) 64%, rgba(8,5,18,0.92) 100%)`, 1)} />
            <div style={layer(`linear-gradient(90deg, rgba(8,5,18,0.55) 0%, rgba(8,5,18,0) 46%)`, 1)} />
          </div>
        )}
      </div>
      {/* Text zone vignette for initial two phases */}
      <div style={layer(`linear-gradient(90deg, rgba(8,5,18,0.42) 0%, rgba(8,5,18,0) 55%)`, 1 - w3)} />
      <div style={layer(`radial-gradient(ellipse 80% 80% at 50% 50%, rgba(6,4,14,0) 55%, rgba(6,4,14,0.55) 100%)`, 1)} />
      <Grain opacity={0.1} blend="soft-light" />

      {/* Foreground typography synchronized with gradient motion */}
      <div style={{ position: 'absolute', left: 160, top: 404, ...type(TYPE.display, 760), color: L.ink, textShadow: `0 10px 50px ${alpha('#05020c', 0.35)}` }}>
        {f < 66 && <TextReveal text="Bend light." by="word" variant="blur" start={6} each={20} gap={5} out={{ start: 52, dur: 12 }} />}
      </div>
      <div style={{ position: 'absolute', left: 160, top: 404, ...type(TYPE.display, 760), color: L.ink, textShadow: `0 10px 50px ${alpha('#05020c', 0.35)}` }}>
        {f >= 62 && f < 128 && <TextReveal text="Focus it." by="word" variant="blur" start={66} each={20} gap={5} out={{ start: 114, dur: 12 }} />}
      </div>
      {f >= 124 && (
        <div style={{ position: 'absolute', left: 160, top: 300 }}>
          <div style={{ ...type(TYPE.label, 700, { caps: true }), letterSpacing: '0.3em', color: alpha(L.ink, 0.75), opacity: ramp(f, 124, 16, EASE.out) }}>
            Introducing
          </div>
          {/* Brand mark: outline stroke -> diagonal slash + wordmark tracking tighten */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 44, marginTop: 30,
            opacity: ramp(f, 128, 12, EASE.out),
            filter: markP < 0.98 ? `blur(${((1 - markP) * 14).toFixed(2)}px)` : undefined,
          }}>
            <ShotcraftMark size={168} tone="dark" frameProgress={ramp(f, 128, 18, EASE.snappy)} cutProgress={ramp(f, 138, 14, EASE.snappy)} />
            <div style={{
              fontFamily: BRAND.font, fontSize: 156, fontWeight: 700, lineHeight: 1, whiteSpace: 'nowrap', color: L.ink,
              letterSpacing: `${mix(0.1, 0.01, markP).toFixed(4)}em`,
              textShadow: `0 12px 60px ${alpha('#05020c', 0.4)}`,
            }}>
              {BRAND.name}
            </div>
          </div>
          <div style={{
            ...type(TYPE.h3, 500), color: alpha(L.ink, 0.82), marginTop: 40,
            opacity: subP, transform: `translateY(${((1 - subP) * 18).toFixed(2)}px)`,
          }}>
            {PITCH.en.motto}
          </div>
        </div>
      )}

      {/* Footer technical annotation: live parameters + phase index */}
      <div style={{ position: 'absolute', left: 160, right: 160, bottom: 96, opacity: ramp(f, 0, 16, EASE.out) }}>
        <div style={{ height: 1.5, background: alpha(L.ink, 0.18) }} />
        <div style={{ display: 'flex', marginTop: 22, alignItems: 'baseline' }}>
          <div style={{ ...type(30, 500, { mono: true }), color: alpha(L.ink, 0.7) }}>{readout}</div>
          <div style={{ marginLeft: 'auto', ...type(30, 600, { mono: true }), color: alpha(L.ink, 0.7) }}>
            <span style={{ color: L.ink }}>{String(phase + 1).padStart(2, '0')}</span> / 03
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
