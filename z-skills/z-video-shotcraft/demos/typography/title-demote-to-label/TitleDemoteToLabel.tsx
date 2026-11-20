// title-demote-to-label — Hero title demotes to section label (two-part sequence)
// Source: perplexity-promo 16–18.5s; Variant B derived from framer text-selection-title.
//
// Redesign round 2 (paper · Swiss grid editorial layout · product = video-shotcraft storyboard workbench):
// - look = paper (warm white paper · ink · vermilion). Hero is 220px / 850-weight poster titles "Frame." and "Craft." (from brand tagline "Frame motion. Craft the shot."),
//   with vermilion period — serving as the visual anchor when demoted to section label. 12-column grid with 120 margin, hairline rules, and mono eyebrow create editorial structure.
// - Demotion: single continuous tween (26f, asymmetric in-out: decisive start, soft landing) scale 1→0.22, center→top-left label slot,
//   transform-origin left-center, center correction translate(-50%) zeros out over tween; directional motion blur scaled to velocity during flight.
//   Eyebrow "CHAPTER 01" fades out in 6f at takeoff, replaced by "01 /" wiping in from left as label lands.
// - Content stagger-reveals 12f into demotion (clip-reveal + shift-up + fade-in, front-loaded stagger), zero gap at handoff:
//   A = lead-in + 3 cards (recipe card / testimonial / beat grid); B = storyboard script with vermilion text selection -> connecting line -> matched shot card.
// - No white flash between variations: A content exits ease-in upward, A label shifts up one row, grays out and shrinks into "previous section" (no stacking across sections),
//   B hero title emerges on the same stage — seamless single Stage continuity.
// - Variant B: vermilion selection sweeps in (3px caret at right edge) -> holds 10f -> left edge clears -> demotes.
//
// Timeline (30fps, 246f total):
//   A  0–16    Eyebrow tracking tightens + title rises char-by-char from below baseline (rise, settles progressively)
//      16–36   Hold 20f (subtle 1.5% push-in to keep frame dynamic)
//      36–62   Demote 26f; content grows starting frame 48 (~44f total growth)
//      92–112  Hold
//   Tr 112–124 A content exits (exit 12f); A label 124–140 moves up into "previous section"
//   B  118–134 B title reveals; 136–146 selection sweeps in; 146–156 hold; 156–164 clear; 166–192 demote; 178 content grows
//      226–246 Hold and settle (tail frame = complete editorial poster)
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, SpeedBlur, bezier, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

const L = LOOKS.paper;
export const TITLE_DEMOTE_TO_LABEL_DURATION = 246;

const B0 = 112; // Variant B (transition) start
const MARGIN = 120; // Grid left margin
const HERO = 220; // Hero font size
const LABEL_SCALE = 0.22; // Demoted scale target (≈48px)
const SLOT = { x: MARGIN + 96, y: 196 }; // Label slot (left-center anchor); prefix reserved for "01 /"
const DEMOTE_EASE = bezier(0.6, 0, 0.18, 1); // Asymmetric in-out: decisive start, soft landing
const SEL = alpha(L.accent, 0.2);

// ───────────── Grow block: left-to-right clip reveal + shift up + fade in (no content distortion) ─────────────
const Grow: React.FC<{ frame: number; at: number; dur?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  frame, at, dur = 20, children, style,
}) => {
  const p = ramp(frame, at, dur, EASE.out);
  return (
    <div style={{
      opacity: Math.min(1, p * 1.6),
      transform: `translateY(${((1 - p) * 30).toFixed(2)}px)`,
      clipPath: p < 1 ? `inset(-60px ${((1 - (0.3 + 0.7 * p)) * 100).toFixed(2)}% -60px -20px)` : undefined,
      ...style,
    }}>
      {children}
    </div>
  );
};

const Tag: React.FC<{ label: string; color?: string }> = ({ label, color = L.accent }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, ...type(22, 700, { caps: true, mono: true }), letterSpacing: '0.14em', color: L.ink2 }}>
    <span style={{ width: 10, height: 10, borderRadius: 5, background: color }} />
    {label}
  </span>
);

const card: React.CSSProperties = {
  position: 'relative', width: 536, height: 430, borderRadius: 22, background: L.surface,
  border: `1px solid ${L.line}`, boxShadow: `inset 0 1px 0 rgba(255,255,255,0.9), ${softShadow(10, { color: L.shadow, strength: 0.9 })}`,
  padding: '34px 36px', boxSizing: 'border-box', overflow: 'hidden',
};

// ───────────── A: Framing (lead-in + 3 cards: recipe / testimonial / beat grid) ─────────────
const ContentA: React.FC<{ frame: number; at: number }> = ({ frame, at }) => {
  const t = (k: number) => at + k; // Front-loaded stagger
  return (
    <div style={{ position: 'absolute', left: MARGIN, top: 262, width: 1680 }}>
      <Grow frame={frame} at={t(8)} dur={18}>
        <div style={{ height: 1.5, background: alpha(L.ink, 0.85) }} />
      </Grow>
      <Grow frame={frame} at={t(6)} style={{ marginTop: 40 }}>
        <div style={{ ...type(60, 650), color: L.ink, whiteSpace: 'nowrap' }}>
          Pick a shot. <span style={{ color: L.ink3 }}>Each one comes with a recipe.</span>
        </div>
      </Grow>
      <div style={{ display: 'flex', gap: 36, marginTop: 56 }}>
        <Grow frame={frame} at={t(10)} dur={22}>
          <div style={card}>
            <Tag label="Recipe card" />
            <div style={{ ...type(42, 700), color: L.ink, marginTop: 26, lineHeight: 1.12 }}>Crash zoom punch</div>
            <div style={{ ...type(32, 400), color: L.ink2, marginTop: 18, lineHeight: 1.35 }}>Slam into the one number that matters.</div>
            <div style={{ position: 'absolute', left: 36, right: 36, bottom: 30, display: 'flex', justifyContent: 'space-between', ...type(22, 500, { mono: true }), color: L.ink3 }}>
              <span>camera / punch-in</span><span>18f</span>
            </div>
          </div>
        </Grow>
        <Grow frame={frame} at={t(16)} dur={22}>
          <div style={{ ...card, background: L.ink, border: 'none' }}>
            <Tag label="Review" color={L.accent} />
            <div style={{ fontFamily: '"Iowan Old Style", Palatino, Georgia, serif', fontSize: 52, lineHeight: 1.12, fontStyle: 'italic', color: L.surface, marginTop: 26, letterSpacing: '-0.015em' }}>
              “Camera moves I’d have keyframed for a <span style={{ color: L.accent }}>week</span>.”
            </div>
            <div style={{ position: 'absolute', left: 36, right: 36, bottom: 30, ...type(22, 500, { mono: true }), color: alpha(L.surface, 0.5) }}>
              Saved from launch day · 03:12
            </div>
          </div>
        </Grow>
        <Grow frame={frame} at={t(24)} dur={22}>
          <div style={card}>
            <Tag label="Beat grid" color={L.accent2} />
            <div style={{ ...type(42, 700), color: L.ink, marginTop: 26, lineHeight: 1.12 }}>Launch BGM, 128 BPM</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, height: 120, marginTop: 30 }}>
              {Array.from({ length: 34 }, (_, i) => {
                const hgt = 18 + 90 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.43));
                return <span key={i} style={{ width: 7, height: hgt, borderRadius: 4, background: i < 13 ? L.accent2 : alpha(L.ink, 0.18) }} />;
              })}
            </div>
            <div style={{ position: 'absolute', left: 36, right: 36, bottom: 30, display: 'flex', justifyContent: 'space-between', ...type(22, 500, { mono: true }), color: L.ink3 }}>
              <span>Cuts on the beat</span><span>00:32</span>
            </div>
          </div>
        </Grow>
      </div>
    </div>
  );
};

// ───────────── B: Storyboard script + in-sentence selection -> connector -> matched shot card ─────────────
const ContentB: React.FC<{ frame: number; at: number }> = ({ frame, at }) => {
  const sel = ramp(frame, at + 20, 12, EASE.swift); // Sweep in selection on sentence
  const wire = ramp(frame, at + 30, 12, EASE.swift); // Connector line from selection to card
  const body: React.CSSProperties = { ...type(58, 450), lineHeight: 1.5, color: L.ink2, whiteSpace: 'nowrap' };
  return (
    <div style={{ position: 'absolute', left: MARGIN, top: 262, width: 1680 }}>
      <Grow frame={frame} at={at + 6} dur={18}>
        <div style={{ height: 1.5, background: alpha(L.ink, 0.85) }} />
      </Grow>
      <Grow frame={frame} at={at + 8} style={{ marginTop: 40 }}>
        <div style={{ ...type(22, 700, { caps: true, mono: true }), letterSpacing: '0.14em', color: L.ink3 }}>
          Launch film <span style={{ color: L.accent }}>·</span> Storyboard v4
        </div>
      </Grow>
      <div style={{ position: 'relative', marginTop: 22 }}>
        <Grow frame={frame} at={at + 10}><div style={body}>The launch film opens on the dashboard,</div></Grow>
        <Grow frame={frame} at={at + 12}><div style={body}>glides past the chart and, best of all,</div></Grow>
        <Grow frame={frame} at={at + 14}>
          <div style={body}>
            <span style={{ position: 'relative', color: L.ink }}>
              <span style={{ position: 'absolute', left: -6, top: 8, bottom: 4, width: `calc(${(sel * 100).toFixed(2)}% + 12px)`, background: SEL, borderRadius: 5 }} />
              <span style={{ position: 'relative' }}>every cut lands right on the beat.</span>
            </span>
          </div>
        </Grow>
        <Grow frame={frame} at={at + 16}><div style={{ ...body, color: L.ink3 }}>Sound design and the logo sting come last.</div></Grow>
        {/* Connector: from right edge of selection to side card */}
        <svg width={1680} height={400} style={{ position: 'absolute', left: 0, top: 0, overflow: 'visible', pointerEvents: 'none' }}>
          <path d="M 800 217 L 1112 217" stroke={L.accent} strokeWidth={2.5} fill="none" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - wire} />
          {wire > 0.02 && <circle cx={800} cy={217} r={6} fill={L.accent} />}
        </svg>
        {/* Marginalia: matched shot recipe card */}
        <div style={{ position: 'absolute', left: 1120, top: -40, width: 560 }}>
          <Grow frame={frame} at={at + 38} dur={22}>
            <div style={{ ...card, width: 560, height: 'auto', padding: '32px 36px 30px' }}>
              <Tag label="Shot match · 2 cards" />
              <div style={{ ...type(40, 650), color: L.ink, marginTop: 22, lineHeight: 1.18 }}>
                Every line of the script becomes a tuned shot.
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 28 }}>
                {[['beat-cut-moves', '4 cuts'], ['crash-zoom-punch', '18f']].map(([a, b]) => (
                  <div key={a} style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 18px', borderRadius: 12, background: L.surface2, ...type(26, 500, { mono: true }), color: L.ink2 }}>
                    <span>{a}</span><span style={{ color: L.accent }}>{b}</span>
                  </div>
                ))}
              </div>
            </div>
          </Grow>
        </div>
      </div>
    </div>
  );
};

// Footer: hairline rule + mono fine-print (shared across sections, anchors bottom edge of poster)
const Footer: React.FC<{ frame: number }> = ({ frame }) => {
  const p = ramp(frame, 54, 26, EASE.out);
  return (
    <div style={{ position: 'absolute', left: MARGIN, right: MARGIN, top: 948, opacity: p }}>
      <div style={{ height: 1, background: L.line, transformOrigin: 'left', transform: `scaleX(${p.toFixed(4)})` }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, ...type(22, 500, { mono: true }), letterSpacing: '0.06em', color: L.ink3 }}>
        <span>{BRAND.name} / storyboard</span><span>Autosaved · just now</span>
      </div>
    </div>
  );
};

// ───────────── Title: Reveal -> (Selection) -> Demote ─────────────
const Title: React.FC<{
  frame: number; word: string; num: string; reveal: number; demote: number; select?: { on: number; off: number };
  retire?: number; // Frame when bumped upward by next section (becomes "previous section")
}> = ({ frame, word, num, reveal, demote, select, retire }) => {
  const demAt = (f: number) => ramp(f, demote, 26, DEMOTE_EASE);
  const dem = demAt(frame);
  const v = demAt(frame + 0.5) - demAt(frame - 0.5);
  const hold = ramp(frame, reveal + 14, demote - reveal - 14, EASE.linear);
  const scale = mix(1 + 0.015 * hold, LABEL_SCALE, dem);
  const x = mix(960, SLOT.x, dem);
  const y = mix(540, SLOT.y, dem);
  // Retire: shift up one row, shrink, and fade to secondary gray
  const ret = retire !== undefined ? ramp(frame, retire, 16, EASE.swift) : 0;
  const ry = -68 * ret;
  const rs = 1 - 0.3 * ret;
  if (frame < reveal) return null;

  // Eyebrow: tracking tightens from wide (reveal), fades out in 6f at takeoff
  const eyebrowIn = ramp(frame, reveal, 16, EASE.out);
  const eyebrowOut = ramp(frame, demote, 6, EASE.exit);
  // Selection (Variant B)
  let selL = 0, selW = 0, caret = 0;
  if (select) {
    const on = ramp(frame, select.on, 10, EASE.swift);
    const off = ramp(frame, select.off, 8, EASE.exit);
    selL = off * 100;
    selW = Math.max(0, on * 100 - selL);
    caret = frame >= select.on && frame < select.off + 6 ? 1 - off : 0;
  }
  // "01 /" wipes in from left 4f before landing
  const numIn = ramp(frame, demote + 20, 12, EASE.out);
  const ink = ret > 0 ? `rgb(${[23, 19, 15].map((c, k) => Math.round(mix(c, [155, 145, 132][k], ret))).join(',')})` : L.ink;

  return (
    <>
      {/* Settled "01 /" */}
      <div style={{
        position: 'absolute', left: MARGIN, top: SLOT.y + ry, transform: `translateY(-50%) scale(${rs})`, transformOrigin: 'left center',
        ...type(30, 700, { mono: true }), color: ret > 0.5 ? L.ink3 : L.accent, whiteSpace: 'nowrap',
        clipPath: `inset(-10px ${((1 - numIn) * 100).toFixed(1)}% -10px 0)`, opacity: numIn,
      }}>
        {num} <span style={{ color: L.ink3 }}>/</span>
      </div>
      <SpeedBlur vx={v * (SLOT.x - 960)} vy={v * (SLOT.y - 540)} amount={0.2} max={12}>
        <div style={{
          position: 'absolute', left: x - (SLOT.x - MARGIN) * (1 - rs), top: y + ry,
          transform: `translate(${(-(1 - dem) * 50).toFixed(3)}%, -50%) scale(${(scale * rs).toFixed(4)})`,
          transformOrigin: 'left center', whiteSpace: 'nowrap',
        }}>
          {/* Eyebrow */}
          <div style={{
            position: 'absolute', left: 14, top: -46, ...type(30, 700, { caps: true, mono: true }),
            letterSpacing: `${(0.3 - 0.12 * eyebrowIn).toFixed(3)}em`, color: L.accent,
            opacity: eyebrowIn * (1 - eyebrowOut), whiteSpace: 'nowrap',
          }}>
            Chapter {num}
          </div>
          <div style={{ position: 'relative', ...type(HERO, 850), letterSpacing: '-0.055em', color: ink, padding: '0 14px' }}>
            {selW > 0 && (
              <div style={{ position: 'absolute', left: `${selL}%`, width: `${selW}%`, top: '8%', bottom: '2%', background: SEL, borderRadius: 6 }} />
            )}
            {caret > 0 && (
              <div style={{ position: 'absolute', left: `calc(${(selL + selW).toFixed(2)}% - 2px)`, top: '4%', bottom: '-2%', width: 5, borderRadius: 3, background: L.accent, opacity: caret }} />
            )}
            <span style={{ position: 'relative' }}>
              <TextReveal text={word} start={reveal} by="char" variant="rise" each={16} gap={1.6} />
              <span style={{ color: ret > 0.5 ? L.ink3 : L.accent, display: 'inline-block', transform: `scale(${ramp(frame, reveal + 10, 14, EASE.overshoot).toFixed(3)})`, transformOrigin: '50% 85%' }}>.</span>
            </span>
          </div>
        </div>
      </SpeedBlur>
    </>
  );
};

export const TitleDemoteToLabel: React.FC = () => {
  const frame = useCurrentFrame();
  // Content A exit
  const outA = ramp(frame, B0, 12, EASE.exit);
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.3, y: 0.05 }} fill={{ x: 0.9, y: 0.95 }} />
      {/* Grid header: top-right brand (mark + lowercase wordmark) / page number (mono fine-print) */}
      <div style={{ position: 'absolute', right: MARGIN, top: 182, display: 'flex', alignItems: 'center', gap: 40, ...type(22, 600, { caps: true, mono: true }), letterSpacing: '0.16em', color: L.ink3, opacity: ramp(frame, 40, 20, EASE.out) }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12, textTransform: 'none', letterSpacing: '0.04em' }}><ShotcraftMark size={28} tone="light" />{BRAND.name}</span><span style={{ color: L.ink }}>{frame < 190 ? '01' : '02'} / 04</span>
      </div>
      {frame < B0 + 14 && (
        <div style={{ position: 'absolute', inset: 0, opacity: 1 - outA, transform: `translateY(${(-50 * outA).toFixed(2)}px)` }}>
          <ContentA frame={frame} at={48} />
        </div>
      )}
      {frame >= B0 + 40 && <ContentB frame={frame} at={178} />}
      <Footer frame={frame} />
      <Title frame={frame} word="Frame" num="01" reveal={0} demote={36} retire={B0 + 54} />
      <Title frame={frame} word="Craft" num="02" reveal={B0 + 6} demote={166} select={{ on: 136, off: 156 }} />
    </AbsoluteFill>
  );
};
