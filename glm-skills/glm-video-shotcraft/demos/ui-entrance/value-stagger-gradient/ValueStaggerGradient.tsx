// value-stagger-gradient — Value Stagger Numerical Gradient (ported from motion-lab final to native Remotion)
// stagger doesn't just offset timing, but maps property values into gradients across N elements: during 16-bar entrance,
// delay=stagger(time), while height/hue/blur are all stagger([from,to]) numerical gradients;
// Beat 2 switches to from:'center', pulse amplitude fans out from center origin.
// Design canvas 480x270 (DesignStage zoom scaling, rasterized at target resolution), parameter table calibrated to this coordinate space.
// Polish revision:
// - Bars use height growth (bottom-anchored) rather than scaleY, preventing squished rounded corners; top specular highlight + floor reflection + baseline tick marks;
// - Code caption rendered as syntax-highlighted code strip (≥38px output height), vertical cross-fade transition between beats, no hard cut;
// - Bars and code strip centered as unified composition; tinted dark backdrop + soft glow beneath bars + vignette + grain (native resolution).
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { DesignStage, E, lerp, seg, useT } from '../../_fixtures/Motion';
import { EASE, FONT, Grain, Vignette } from '../../_fixtures/Polish';

export const VALUE_STAGGER_GRADIENT_DURATION = 150; // 5000ms @30fps

// Numerical gradient util (equivalent to stagger([a,b]) value mode)
const staggerVal = (i: number, n: number, a: number, b: number, ease?: (x: number) => number) => {
  let k = n <= 1 ? 0 : i / (n - 1);
  if (ease) k = ease(k);
  return lerp(k, a, b);
};

const N = 16;
const C = (N - 1) / 2;
const BARS = Array.from({ length: N }, (_, i) => ({
  i,
  hue: staggerVal(i, N, 200, 320), // Numerical gradient: hue spread
  hMax: staggerVal(i, N, 92, 32), // Numerical gradient: height 1→0.35
  distC: Math.abs(i - C) / C,
}));

const BASE_Y = 196; // Baseline (design px)
const SWITCH = 0.52; // Code line switch between beats

// Syntax-highlighted token: [text, color]
const KEY = '#9aa3bd';
const FN = '#c9b3ff';
const NUM = '#86d4ff';
const STR = '#f3b58c';
const PUN = '#5f6782';
type Tok = [string, string];
const LINE1: Tok[] = [
  ['scale', KEY], [': ', PUN], ['stagger', FN], ['([', PUN], ['1', NUM], [', ', PUN], ['0.35', NUM], ['])', PUN],
  ['   hue', KEY], [': ', PUN], ['stagger', FN], ['([', PUN], ['200', NUM], [', ', PUN], ['320', NUM], ['])', PUN],
];
const LINE2: Tok[] = [
  ['pulse', KEY], [': ', PUN], ['stagger', FN], ['([', PUN], ['.06', NUM], [', ', PUN], ['.42', NUM], ['], { ', PUN],
  ['from', KEY], [': ', PUN], ["'center'", STR], [' })', PUN],
];

const Code: React.FC<{ toks: Tok[]; style: React.CSSProperties }> = ({ toks, style }) => (
  <div style={{ position: 'absolute', left: 0, right: 0, textAlign: 'center', whiteSpace: 'pre', ...style }}>
    {toks.map(([s, c], k) => (
      <span key={k} style={{ color: c }}>{s}</span>
    ))}
  </div>
);

export const ValueStaggerGradient: React.FC = () => {
  const t = useT();
  // Code strip: fades in and floats up; between beats, old line shifts up/fades out, new line enters from below (≈5f cross-fade)
  const capIn = seg(t, 0.03, 0.12, EASE.out);
  const sw = seg(t, SWITCH - 0.018, SWITCH + 0.022, EASE.smooth);
  // Soft glow beneath bars spreads with beat 1, slightly surges on beat 2 pulse
  const pulseC = Math.sin(seg(t, 0.56, 0.74) * Math.PI);
  return (
    <AbsoluteFill style={{ background: 'linear-gradient(180deg, #0e0f15 0%, #0a0b0f 100%)' }}>
      <AbsoluteFill
        style={{
          background: 'radial-gradient(ellipse 46% 34% at 50% 66%, rgba(120,110,255,0.16), rgba(120,110,255,0) 70%)',
          opacity: 0.35 + 0.65 * seg(t, 0.06, 0.5) + pulseC * 0.3,
        }}
      />
      <DesignStage bg="transparent" raster="zoom">
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', fontFamily: FONT.mono }}>
          {/* Code strip */}
          <div
            style={{
              position: 'absolute', left: '50%', top: 40, height: 22, width: 316, marginLeft: -158, borderRadius: 7,
              background: 'rgba(255,255,255,0.035)', boxShadow: 'inset 0 0 0 0.25px rgba(255,255,255,0.12), inset 0 0.25px 0 rgba(255,255,255,0.08)',
              overflow: 'hidden', opacity: capIn, transform: `translateY(${lerp(capIn, 4, 0).toFixed(3)}px)`,
            }}
          >
            <Code toks={LINE1} style={{ top: 5.6, fontSize: 9.5, lineHeight: '11px', opacity: 1 - sw, transform: `translateY(${(-sw * 12).toFixed(3)}px)` }} />
            <Code toks={LINE2} style={{ top: 5.6, fontSize: 9.5, lineHeight: '11px', opacity: sw, transform: `translateY(${((1 - sw) * 12).toFixed(3)}px)` }} />
          </div>
          {/* Baseline + tick marks */}
          <div style={{ position: 'absolute', left: '7%', right: '7%', top: BASE_Y + 0.5, height: 0.3, background: 'rgba(255,255,255,0.12)', opacity: seg(t, 0.02, 0.1) }} />
          {BARS.map(({ i, hue, hMax, distC }) => {
            // Beat 1: timing stagger (linear from first) x numerical gradient (y/blur fanned out simultaneously)
            const d = i * 0.02;
            const e = seg(t, 0.06 + d, 0.28 + d, E.outCubic);
            const y0 = staggerVal(i, N, 46, 14); // Displacement amount is itself a gradient
            const b0 = staggerVal(i, N, 8, 2); // Blur amount gradient
            // Beat 2: from:'center' — wave and amplitude propagate from center
            const w = seg(t, 0.56 + distC * 0.13, 0.74 + distC * 0.13);
            const pulse = Math.sin(w * Math.PI);
            const amp = lerp(1 - distC, 0.06, 0.42); // Amplitude gradient: largest at center
            const h = hMax * e * (1 + pulse * amp);
            const x = `${8 + i * 5.4}%`;
            const blur = (1 - e) * b0;
            const bright = 1 + pulse * 0.55;
            const body = `linear-gradient(180deg, hsl(${hue},80%,70%) 0%, hsl(${hue},72%,56%) 45%, hsl(${hue},66%,40%) 100%)`;
            return (
              <React.Fragment key={i}>
                {/* Tick mark */}
                <div style={{ position: 'absolute', top: BASE_Y + 3, left: `${8 + i * 5.4 + 1.7}%`, width: 0.3, height: 2.5, background: 'rgba(255,255,255,0.18)', opacity: seg(t, 0.02, 0.1) }} />
                {/* Bar body (bottom-anchored, grows via height) */}
                <div
                  style={{
                    position: 'absolute',
                    top: BASE_Y - h,
                    left: x,
                    width: '3.4%',
                    height: h,
                    borderRadius: 4,
                    background: body,
                    boxShadow: `inset 0 0.5px 0 rgba(255,255,255,0.45), inset 0 0 0 0.25px rgba(255,255,255,0.10), 0 0 10px hsla(${hue},85%,58%,${(0.18 + pulse * 0.22).toFixed(3)})`,
                    opacity: e,
                    filter: `${blur > 0.02 ? `blur(${blur.toFixed(2)}px) ` : ''}brightness(${bright.toFixed(3)})`,
                    transform: `translateY(${((1 - e) * y0).toFixed(3)}px)`,
                    overflow: 'hidden',
                  }}
                >
                  {/* Left-edge highlight strip */}
                  <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '34%', background: 'linear-gradient(90deg, rgba(255,255,255,0.16), rgba(255,255,255,0))' }} />
                </div>
                {/* Ground reflection: inverted, fading, slightly blurred */}
                <div
                  style={{
                    position: 'absolute',
                    top: BASE_Y + 1.5,
                    left: x,
                    width: '3.4%',
                    height: h * 0.45,
                    borderRadius: 4,
                    background: `linear-gradient(180deg, hsla(${hue},70%,52%,0.32), hsla(${hue},70%,40%,0))`,
                    opacity: e * 0.8,
                    filter: `blur(${(0.8 + blur).toFixed(2)}px) brightness(${bright.toFixed(3)})`,
                    transform: `translateY(${((1 - e) * y0 * 0.4).toFixed(3)}px)`,
                  }}
                />
              </React.Fragment>
            );
          })}
        </div>
      </DesignStage>
      <Vignette strength={0.5} color="#000000" inner={0.45} />
      <Grain opacity={0.08} blend="soft-light" />
    </AbsoluteFill>
  );
};
