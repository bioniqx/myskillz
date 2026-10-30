// Feature card 3D flip reveal (card-flip-reveal) - Apple bento flip sequence.
// Mechanics unchanged: a row of feature cards flip 180° along Y axis staggered (perspective + double-sided backface hidden).
// Front side shows the feature UI; back side shows the key outcome metric (semantically paired).
// Overshoots at the end of flip before settling back; a dynamic light glint travels along the edge at its thinnest angle.
//
// Round 2 Redesign (Design decisions)
// - look = graphite (near-monochrome dark stage, white emphasis, champagne gold accents). Front is dark feature card, back is bright porcelain white outcome card:
//   flip = dark-to-light inversion, illuminating the "so what?" answer. After all three flip, screen transforms from dark cards into white metric posters.
// - Content: three video-shotcraft capabilities: Prompt (one-line generation) / Recipes (camera moves) / Library (recipe search).
//   Front features large-type UI designed for camera framing (>= 28px); back features 158px metric 3.2x / -41% / 0.2s + 34px takeaway,
//   with "Before / With Shotcraft" comparison bars shrinking after settling.
// - Card vertical 480x620 (bento ratio); three cards total 1536px width, occupying 80% screen width; top-left 84px title + gold kicker;
//   Cards stand on a dark mirror floor - each card has a synchronously flipping reflection (masked fade), establishing 3D space.
// - Flip animation: 4f prep (reverse tilt -10°) -> 16f accelerated flip to 194° (bezier 0.55,0,0.3,1) -> physical spring settles back to 180°;
//   Card lifts off ground during flip (scale +6%), surfaces darken based on angle deviation from main light (|cos theta| shading);
//   A narrow light band sweeps left-to-right between 60–120° along the edge (physical lighting, not an artificial sweep effect).
//   Back metric shrinks from 1.08 to 1 on settle, label lags by 4f.
//
// Timeline (30fps, 150f)
//   0–16    Row of dark cards already on screen, kicker + title rise line-by-line, camera slowly pushes 1 -> 1.03 throughout
//   22–48   Card 0: 22 prep -> 26–42 flip -> 42–52 spring settle, metric contracts, label rises
//   34–60   Card 1 (staggered by 12f)
//   46–72   Card 2
//   72–150  All settled, hold ~78f (R1); final frame is poster of three white outcome cards
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, bezier, mix, ramp } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, springAt, type } from '../../_fixtures/Look';
import { BRAND } from '../../_fixtures/Brand';

export const CARD_FLIP_REVEAL_DURATION = 150;

const L = LOOKS.graphite;
const GOLD = L.accent2;
const CW = 480;
const CH = 620;
const GAP = 48;
const X0 = (1920 - (CW * 3 + GAP * 2)) / 2; // 192
const Y = 330;
const FLIP0 = 22;
const STAGGER = 12;
const PRE = 4; // Preparation frames
const FLIP = 16; // Flip frames
const PEAK_DEG = 194;

const flipEase = bezier(0.55, 0, 0.3, 1);

// Flip angle for card i at frame f: 0 -> -10 (prep) -> 194 (accelerated flip) -> 180 (spring settle)
const angleAt = (f: number, i: number) => {
  const s = FLIP0 + i * STAGGER;
  if (f < s + PRE) return -10 * ramp(f, s, PRE, EASE.out);
  if (f < s + PRE + FLIP) return mix(-10, PEAK_DEG, ramp(f, s + PRE, FLIP, flipEase));
  return PEAK_DEG - (PEAK_DEG - 180) * springAt(f, s + PRE + FLIP, { damping: 15, stiffness: 190 });
};

const FEATURES = [
  { name: 'Prompt', desc: 'One line in, a whole film out.', value: '3.2×', label: 'faster first cut', bars: [1, 0.31], unit: ['48 min', '15 min'] },
  { name: 'Recipes', desc: 'Camera moves, pre-tuned.', value: '−41%', label: 'time spent keyframing', bars: [1, 0.59], unit: ['6.1 h', '3.6 h'] },
  { name: 'Library', desc: 'Every shot, one search away.', value: '0.2s', label: 'to find the right move', bars: [1, 0.06], unit: ['3.4 s', '0.2 s'] },
];

// ───────────── Front UI (dark theme, large type) ─────────────
const FrontUI: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const ink = L.ink, ink2 = L.ink2, ink3 = L.ink3;
  if (i === 0) {
    const caret = Math.floor(frame / 9) % 2 === 0;
    return (
      <div style={{ fontSize: 30, lineHeight: 1.42, color: ink2, fontWeight: 450 }}>
        <div style={{ color: ink }}>Make a 30s launch film,</div>
        <div style={{ color: ink }}>
          open on a crash zoom<span style={{ display: 'inline-block', width: 3, height: 34, verticalAlign: -6, background: caret ? GOLD : 'transparent', marginLeft: 2 }} />
          <span style={{ color: alpha(ink, 0.32) }}> and</span>
        </div>
        <div style={{ color: alpha(ink, 0.32) }}>end on the logo sting.</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 26 }}>
          <div style={{ height: 40, padding: '0 14px', borderRadius: 10, boxShadow: `inset 0 0 0 2px ${alpha(ink, 0.22)}`, display: 'flex', alignItems: 'center', fontFamily: FONT.mono, fontSize: 22, fontWeight: 600, color: ink }}>Tab</div>
          <div style={{ fontSize: 24, color: ink3 }}>to accept</div>
        </div>
      </div>
    );
  }
  if (i === 1) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {['#8a8f99', '#c9b48a', '#6f7480', '#a8acb4'].map((c, k) => (
            <div key={k} style={{ width: 48, height: 48, borderRadius: 24, background: c, marginLeft: k ? -12 : 0, boxShadow: `0 0 0 3px ${L.surface}` }} />
          ))}
          <div style={{ marginLeft: 16, fontSize: 24, color: ink3 }}>Recipe · crash zoom</div>
        </div>
        {['Push 1 → 1.6 in 6f', 'Blur rides the snap', 'Land on the downbeat'].map((t, k) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 14, marginTop: k ? 18 : 30 }}>
            <div style={{ width: 8, height: 8, borderRadius: 4, background: k === 0 ? GOLD : alpha(ink, 0.4) }} />
            <div style={{ fontSize: 30, color: ink, fontWeight: 500 }}>{t}</div>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div>
      <div style={{ height: 70, borderRadius: 18, background: L.surface2, boxShadow: `inset 0 0 0 1.5px ${alpha(ink, 0.12)}`, display: 'flex', alignItems: 'center', gap: 14, padding: '0 22px' }}>
        <svg width={26} height={26} viewBox="0 0 26 26"><circle cx={11} cy={11} r={8} fill="none" stroke={ink2} strokeWidth={2.6} /><path d="M17 17l6 6" stroke={ink2} strokeWidth={2.6} strokeLinecap="round" /></svg>
        <div style={{ fontSize: 30, color: ink, fontWeight: 500 }}>crash zoom</div>
      </div>
      {[['Crash zoom punch', 'Card'], ['Zoom-through', 'Card'], ['Dolly zoom', 'Style']].map(([t, k2], k) => (
        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: k ? 14 : 26, padding: '0 6px' }}>
          <div style={{ width: 36, height: 44, borderRadius: 7, background: alpha(ink, k === 0 ? 0.9 : 0.16) }} />
          <div style={{ fontSize: 28, color: k === 0 ? ink : ink2, fontWeight: k === 0 ? 650 : 450 }}>{t}</div>
          <div style={{ marginLeft: 'auto', fontSize: 22, color: ink3 }}>{k2}</div>
        </div>
      ))}
    </div>
  );
};

// Surface shading: darkens as surface angles away from camera; narrow light band sweeps left-to-right between 60–120° (near thinnest edge angle)
const FaceLight: React.FC<{ angle: number; dark: boolean }> = ({ angle, dark }) => {
  const c = Math.abs(Math.cos((angle * Math.PI) / 180));
  const shade = (1 - c) * (dark ? 0.55 : 0.4);
  const band = Math.max(0, 1 - Math.abs(angle - 90) / 34);
  const pos = mix(-20, 120, Math.min(1, Math.max(0, (angle - 56) / 68)));
  return (
    <>
      <div style={{ position: 'absolute', inset: 0, background: '#000', opacity: shade }} />
      {band > 0.01 && (
        <div style={{
          position: 'absolute', inset: 0, opacity: band * (dark ? 0.5 : 0.35),
          background: `linear-gradient(100deg, rgba(255,255,255,0) ${pos - 12}%, rgba(255,255,255,0.9) ${pos}%, rgba(255,255,255,0) ${pos + 12}%)`,
        }} />
      )}
    </>
  );
};

const FlipCard: React.FC<{ i: number; frame: number }> = ({ i, frame }) => {
  const angle = angleAt(frame, i);
  const f = FEATURES[i];
  const s = FLIP0 + i * STAGGER;
  const lift = Math.max(0, Math.sin((Math.min(180, Math.max(0, angle)) * Math.PI) / 180));
  const land = s + PRE + FLIP;
  const num = springAt(frame, land - 2, { damping: 18, stiffness: 160 });
  const lab = ramp(frame, land + 2, 14, EASE.snappy);
  return (
    <div style={{ position: 'absolute', inset: 0, perspective: 1600 }}>
      <div style={{
        position: 'absolute', inset: 0, transformStyle: 'preserve-3d',
        transform: `translateZ(${(lift * 60).toFixed(2)}px) rotateY(${angle.toFixed(3)}deg)`,
      }}>
        {/* Front: dark feature card */}
        <div style={{
          position: 'absolute', inset: 0, backfaceVisibility: 'hidden', borderRadius: 34, overflow: 'hidden',
          background: `linear-gradient(180deg, #1d1e22 0%, ${L.surface} 48%, #111214 100%)`,
          boxShadow: `inset 0 0 0 1.5px ${alpha('#ffffff', 0.09)}, inset 0 2px 0 ${alpha('#ffffff', 0.08)}`,
          fontFamily: FONT.sans,
        }}>
          <div style={{ position: 'absolute', left: 40, top: 40, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontFamily: FONT.mono, fontSize: 22, fontWeight: 600, color: L.ink3 }}>0{i + 1}</div>
            <div style={{ ...type(22, 700, { caps: true }), color: L.ink2, letterSpacing: '0.16em' }}>Feature</div>
          </div>
          <div style={{ position: 'absolute', left: 40, right: 40, top: 112 }}>
            <FrontUI i={i} frame={frame} />
          </div>
          <div style={{ position: 'absolute', left: 40, right: 40, bottom: 40 }}>
            <div style={{ ...type(52, 750), color: L.ink }}>{f.name}</div>
            <div style={{ ...type(28, 450), color: L.ink2, marginTop: 10 }}>{f.desc}</div>
          </div>
          <FaceLight angle={angle} dark />
        </div>
        {/* Back: porcelain white outcome card */}
        <div style={{
          position: 'absolute', inset: 0, backfaceVisibility: 'hidden', transform: 'rotateY(180deg)', borderRadius: 34, overflow: 'hidden',
          background: 'linear-gradient(180deg, #fbfaf7 0%, #f1f0ec 100%)',
          boxShadow: `inset 0 0 0 1.5px rgba(0,0,0,0.06), inset 0 2px 0 rgba(255,255,255,0.9)`,
          fontFamily: FONT.sans, color: '#0d0d0f',
        }}>
          <div style={{ position: 'absolute', left: 40, top: 40, display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 12, height: 12, borderRadius: 6, background: '#b8925a' }} />
            <div style={{ ...type(22, 700, { caps: true }), color: '#6b6a66', letterSpacing: '0.16em' }}>{f.name}</div>
          </div>
          {/* Comparison bars: Before / With Shotcraft (grows after settling) */}
          <div style={{ position: 'absolute', left: 40, right: 40, top: 112 }}>
            {(['Before', `With ${BRAND.short}`] as const).map((t, k) => {
              const g = k === 0 ? 1 : ramp(frame, land + 4, 18, EASE.snappy);
              const w = k === 0 ? f.bars[0] : mix(f.bars[0], f.bars[1], g);
              return (
                <div key={t} style={{ marginTop: k ? 26 : 0 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline' }}>
                    <div style={{ ...type(22, 700, { caps: true }), color: k ? '#0d0d0f' : '#8a8984', letterSpacing: '0.14em' }}>{t}</div>
                    <div style={{ marginLeft: 'auto', fontFamily: FONT.mono, fontSize: 24, fontWeight: 600, color: k ? '#0d0d0f' : '#8a8984', opacity: k ? lab : 1 }}>{f.unit[k]}</div>
                  </div>
                  <div style={{ height: 16, borderRadius: 8, marginTop: 10, background: 'rgba(0,0,0,0.06)', overflow: 'hidden' }}>
                    <div style={{ width: `${(w * 100).toFixed(2)}%`, height: '100%', borderRadius: 8, background: k ? '#0d0d0f' : 'rgba(0,0,0,0.18)' }} />
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ position: 'absolute', left: 36, right: 30, bottom: 128 }}>
            <div style={{
              ...type(158, 800), letterSpacing: '-0.06em', lineHeight: 0.9, color: '#0d0d0f', whiteSpace: 'nowrap',
              transform: `scale(${mix(1.08, 1, num).toFixed(4)})`, transformOrigin: 'left bottom',
            }}>{f.value}</div>
          </div>
          <div style={{
            position: 'absolute', left: 40, right: 40, bottom: 48, ...type(34, 550), color: '#3d3c39',
            opacity: lab, transform: `translateY(${((1 - lab) * 14).toFixed(2)}px)`,
          }}>{f.label}</div>
          <FaceLight angle={180 - angle} dark={false} />
        </div>
      </div>
    </div>
  );
};

export const CardFlipReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const push = 1 + 0.03 * ramp(frame, 0, 150, EASE.smooth);
  return (
    <AbsoluteFill style={{ overflow: 'hidden' }}>
      <Stage look={L} keyLight={{ x: 0.5, y: -0.05 }} fill={{ x: 0.5, y: 1.1 }} horizon={0.88} intensity={0.9}>
        {/* Mirror floor: subtly bright reflective surface below horizon */}
        <div style={{
          position: 'absolute', left: 0, right: 0, top: Y + CH, bottom: 0,
          background: `linear-gradient(180deg, ${alpha('#ffffff', 0.035)} 0%, ${alpha('#ffffff', 0)} 60%)`,
          borderTop: `1px solid ${alpha('#ffffff', 0.06)}`,
        }} />
      </Stage>
      <AbsoluteFill style={{ transform: `scale(${push.toFixed(4)})`, transformOrigin: '50% 60%' }}>
        {/* Title */}
        <div style={{ position: 'absolute', left: X0, top: 118, fontFamily: FONT.sans }}>
          <div style={{ ...type(26, 700, { caps: true }), color: GOLD, letterSpacing: '0.18em' }}>
            <TextReveal text={`${BRAND.name} · Launch results`} by="word" variant="blur" start={0} each={14} gap={2} />
          </div>
          <div style={{ ...type(84, 760), color: L.ink, marginTop: 18 }}>
            <TextReveal text="Three features. Three outcomes." by="word" variant="rise" start={2} each={18} gap={2.5} />
          </div>
        </div>
        {[0, 1, 2].map((i) => (
          <React.Fragment key={i}>
            {/* Reflection: vertically mirrored clone of card with gradient mask */}
            <div style={{
              position: 'absolute', left: X0 + i * (CW + GAP), top: Y + CH + 6, width: CW, height: CH,
              transform: 'scaleY(-1)', transformOrigin: 'center', opacity: 0.22,
              WebkitMaskImage: 'linear-gradient(0deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 26%)',
              maskImage: 'linear-gradient(0deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 26%)',
            }}>
              <FlipCard i={i} frame={frame} />
            </div>
            {/* Contact shadow */}
            <div style={{
              position: 'absolute', left: X0 + i * (CW + GAP) + 30, width: CW - 60, top: Y + CH - 18, height: 36, borderRadius: '50%',
              background: 'radial-gradient(ellipse 50% 50% at 50% 50%, rgba(0,0,0,0.7), rgba(0,0,0,0) 70%)',
              transform: `scaleX(${Math.max(0.12, Math.abs(Math.cos((angleAt(frame, i) * Math.PI) / 180))).toFixed(3)})`,
            }} />
            <div style={{ position: 'absolute', left: X0 + i * (CW + GAP), top: Y, width: CW, height: CH }}>
              <FlipCard i={i} frame={frame} />
            </div>
          </React.Fragment>
        ))}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
