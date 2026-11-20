// chip-grid-single-select-blackout — Single Select 1-frame gray flash & blackout toggle
// Five option chips in a 3+2 centered layout enter staggered. On cursor click: 1-frame active gray flash, followed by 5-frame linear transition to black (white text) + 1->1.04->1 subtle rebound;
// Remaining chips dim to 18% with locked positions. ~1.5s later, non-selected chips fade to 0, selected black chip centers and scales down, revealing billing calculation below.
//
// Iteration 2 redesign (porcelain · checkout decision):
// - look = porcelain (cool white · ink blue-black · cobalt blue). Native 1080p layout:
//   eyebrow + 84px question "How would you like to pay?", 96px physical chips (36px text, hairline border + top specular + dual soft shadows), spanning ~62% width.
// - Two-stage selection state: 56f single-frame gray flash (:active) -> 57–62f linear transition to dark ink (:selected, linear)
//   + sin rebound 0.04; other chips reduce opacity only with static transform. Cursor glides from bottom-right along an arc to trigger selection.
// - Selected black chip illuminates with a subtle cobalt blue floor ring; on consolidation, it shifts up, scales to 0.88, and centers horizontally, shadow expanding with elevation.
// - Checkout outcome: new price "$34.44" 180px tabular + "/mo", original price "$42.00" struck through with line,
//   and cobalt "Save 18%" badge pops with overshoot — settling as a pricing poster.
//
// Timeline (30fps, 165f total):
//   0–14    Eyebrow tracking collapses, question rises word-by-word
//   8–28    5 chips rise staggered (3f intervals, snappy)
//   26–54   Deliberation: cursor enters from bottom-right, gliding toward "Annual billing" (subtle 1.5% camera push)
//   56      Single-frame gray active flash (click down)
//   57–62   Linear black transition 5f; 57–66 rebound; 57–66 non-selected chips drop to 18% (positions locked)
//   66–101  Selected hold ~1.2s (floor glow breathes); cursor fades from 70f
//   101–119 Consolidation: unselected chips fade to 0 (101–110); selected chip shifts up / scales 0.88 / centers (18f smooth)
//   108–134 Outcome: original price rises -> strikethrough at 118f -> active price rises -> "Save 18%" pops at 128f
//   134–165 Settled hold 31f
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { EASE, FONT, mix, ramp, softShadow } from '../../_fixtures/Polish';
import { LOOKS, Stage, TextReveal, alpha, type } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const CHIP_GRID_SINGLE_SELECT_BLACKOUT_DURATION = 165;

const L = LOOKS.porcelain;
const INK = '#0b1020'; // Target dark tone: deep ink blue-black (avoids harsh #000)

const NAMES = ['Annual billing', 'Monthly billing', 'Two-year commitment', 'Student', 'Nonprofit rate'];
const WIDTHS = [346, 364, 476, 236, 330]; // Fixed chip widths (calibrated for 36px type + 44px padding)
const TI = 0; // Selected target item
const CHIP_H = 96;
const GAP = 22;
const ROW_Y = [452, 570]; // Top positions of chip rows
const FS = 56; // Gray flash frame
const COLLAPSE = 101; // Consolidation start (~1.5s post-selection)
const COLLAPSE_DUR = 18;
const TARGET_Y = 330; // Consolidated target center y
const TARGET_S = 0.88; // Scales down to 0.88 (text stays ≈32px for legibility)

// 3+2 centered chip grid coordinates (locked in place)
const chipPos = (i: number) => {
  const row = i < 3 ? 0 : 1;
  const ids = row === 0 ? [0, 1, 2] : [3, 4];
  const total = ids.reduce((a, k) => a + WIDTHS[k], 0) + GAP * (ids.length - 1);
  let x = (1920 - total) / 2;
  for (const k of ids) {
    if (k === i) break;
    x += WIDTHS[k] + GAP;
  }
  return { x, y: ROW_Y[row] };
};

const lin = (f: number, a: number, b: number) => Math.max(0, Math.min(1, (f - a) / (b - a)));
const outQuad = (t: number) => 1 - (1 - t) * (1 - t);
const h2r = (h: string) => [1, 3, 5].map((k) => parseInt(h.slice(k, k + 2), 16));
const mixC = (p: number, a: string, b: string) => {
  const A = h2r(a), B = h2r(b), q = Math.max(0, Math.min(1, p));
  return `rgb(${A.map((v, k) => Math.round(v + (B[k] - v) * q)).join(',')})`;
};

const Cursor: React.FC<{ frame: number }> = ({ frame }) => {
  const p0 = chipPos(TI);
  const tx = p0.x + WIDTHS[TI] * 0.62, ty = p0.y + CHIP_H * 0.58;
  const p = ramp(frame, 26, FS - 2 - 26, EASE.swift);
  const x = mix(1500, tx, p);
  const y = mix(960, ty, p) - Math.sin(Math.PI * p) * 60;
  const press = frame >= FS - 1 && frame < FS + 6 ? 1 - 0.16 * Math.sin((Math.PI * (frame - FS + 1)) / 7) : 1;
  const show = ramp(frame, 24, 8, EASE.out) * (1 - ramp(frame, 70, 12, EASE.out));
  return (
    <svg width={46} height={50} viewBox="0 0 20 22" style={{
      position: 'absolute', left: x, top: y, transform: `scale(${press.toFixed(3)})`, transformOrigin: '4px 2px', opacity: show,
      filter: `drop-shadow(0 3px 5px ${alpha(L.shadow, 0.28)})`,
    }}>
      <path d="M2 1 L2 17 L6.5 13.2 L9.4 20 L12.4 18.7 L9.5 12 L15 11.6 Z" fill={L.ink} stroke="#ffffff" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
};

export const ChipGridSingleSelectBlackout: React.FC = () => {
  const frame = useCurrentFrame();

  // ── Dual-stage selection mechanics ──
  const flash = frame === FS ? 1 : 0; // Exactly 1 frame active flash
  const bk = lin(frame, FS + 1, FS + 6); // Linear transition to black over 5f (deliberately un-eased)
  const pr = lin(frame, FS + 1, FS + 10);
  const pulse = 1 + Math.sin(pr * Math.PI) * 0.04 * (pr > 0 ? 1 : 0);
  const fade = outQuad(lin(frame, FS + 1, FS + 10));
  const gone = outQuad(lin(frame, COLLAPSE, COLLAPSE + 9));
  const lift = ramp(frame, COLLAPSE, COLLAPSE_DUR, EASE.smooth);

  const p0 = chipPos(TI);
  const c0x = p0.x + WIDTHS[TI] / 2, c0y = p0.y + CHIP_H / 2;
  const dx = (960 - c0x) * lift, dy = (TARGET_Y - c0y) * lift;

  // Camera: gentle push during deliberation, settles on consolidation
  const cam = 1 + 0.015 * ramp(frame, 20, 60, EASE.smooth) - 0.015 * ramp(frame, COLLAPSE, 30, EASE.smooth);

  // Question yields during consolidation (rises and fades out), clearing stage for outcome
  const titleOut = ramp(frame, COLLAPSE - 4, 16, EASE.exit);

  // ── Pricing outcome ──
  const oldIn = ramp(frame, 108, 14, EASE.snappy);
  const strike = ramp(frame, 118, 8, EASE.swift);
  const saveIn = ramp(frame, 128, 14, EASE.overshoot);

  return (
    <AbsoluteFill style={{ background: L.bg[1], overflow: 'hidden', fontFamily: FONT.sans }}>
      <Stage look={L} keyLight={{ x: 0.5, y: 0.12 }} fill={null} />

      <AbsoluteFill style={{ transform: `scale(${cam.toFixed(4)})`, transformOrigin: '50% 50%' }}>
        {/* Eyebrow + Question */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 168, textAlign: 'center', opacity: 1 - titleOut, transform: `translateY(${(-30 * titleOut).toFixed(2)}px)` }}>
          {/* Eyebrow: mark + lowercase brand logotype + caps tag (tracking collapse) */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 14, opacity: ramp(frame, 0, 10, EASE.out) }}>
            <ShotcraftMark size={32} tone="light" />
            <span style={{ ...type(26, 680), letterSpacing: '0.01em', color: L.ink }}>{BRAND.name}</span>
            <span style={{
              ...type(22, 650, { caps: true }), color: L.accent,
              letterSpacing: `${(0.24 + 0.3 * (1 - ramp(frame, 0, 18, EASE.snappy))).toFixed(3)}em`,
            }}>· Billing cycle</span>
          </div>
          <div style={{ marginTop: 22 }}>
            <TextReveal text="How would you like to pay?" by="word" variant="rise" start={3} each={16} gap={2.5}
              style={{ ...type(84, 700), color: L.ink }} />
          </div>
        </div>

        {/* chip */}
        {NAMES.map((n, i) => {
          const { x, y } = chipPos(i);
          const inP = ramp(frame, 8 + i * 3, 16, EASE.snappy);
          const sel = i === TI;
          if (!sel) {
            const op = inP * mix(1, 0.18, fade) * (1 - gone);
            return (
              <div key={i} style={{
                position: 'absolute', left: x, top: y + (1 - inP) * 30, width: WIDTHS[i], height: CHIP_H, boxSizing: 'border-box',
                borderRadius: CHIP_H / 2, background: `linear-gradient(180deg, #ffffff, ${L.surface2})`,
                border: `1px solid ${L.line}`, boxShadow: `inset 0 1px 0 #ffffff, ${softShadow(6, { color: L.shadow, strength: 1.1 })}`,
                display: 'grid', placeItems: 'center', opacity: op, transform: 'none',
                ...type(36, 560), color: L.ink,
              }}>{n}</div>
            );
          }
          const elev = 6 + 10 * bk + 26 * lift;
          return (
            <div key={i} style={{
              position: 'absolute', left: x, top: y + (1 - inP) * 30, width: WIDTHS[i], height: CHIP_H, opacity: inP,
              transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) scale(${(pulse * mix(1, TARGET_S, lift)).toFixed(4)})`,
            }}>
              {/* Floor ring glow: illuminates beneath selected chip */}
              <div style={{
                position: 'absolute', left: -120, right: -120, top: CHIP_H * 0.35, height: CHIP_H * 1.3,
                background: `radial-gradient(ellipse 50% 50% at 50% 50%, ${alpha(L.accent, 0.2 * bk * (1 - 0.5 * lift))} 0%, transparent 70%)`,
                filter: 'blur(6px)',
              }} />
              <div style={{
                position: 'absolute', inset: 0, boxSizing: 'border-box', borderRadius: CHIP_H / 2, overflow: 'hidden',
                background: bk > 0 ? `linear-gradient(180deg, ${mixC(bk, '#ffffff', '#1d2438')}, ${mixC(bk, '#f3f6fb', INK)})` : `linear-gradient(180deg, #ffffff, ${L.surface2})`,
                border: `1px solid ${bk > 0 ? alpha(INK, 0.1 + 0.9 * bk) : L.line}`,
                boxShadow: `inset 0 1px 0 ${alpha('#ffffff', 1 - 0.85 * bk)}, ${softShadow(elev, { color: L.shadow, strength: 1.1 + 0.9 * bk })}`,
                display: 'grid', placeItems: 'center', ...type(36, 600), color: mixC(bk, L.ink, '#ffffff'),
              }}>
                {/* Active press gray layer: 1 frame */}
                <div style={{ position: 'absolute', inset: 0, background: 'rgba(120,128,146,0.5)', opacity: flash }} />
                <span style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 14 }}>
                  <svg width={30} height={30} viewBox="0 0 18 18" style={{ marginLeft: -12 * bk, width: 30 * bk, opacity: bk }}>
                    <path d="M3.5 9.5 L7.3 13 L14.5 5" stroke="#ffffff" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {n}
                </span>
              </div>
            </div>
          );
        })}

        {/* ── Outcome: strikethrough -> active price -> Save 18% ── */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 452, display: 'flex', justifyContent: 'center', alignItems: 'flex-end', gap: 44 }}>
          {/* Hidden before reveal: prevents masked text remnants from showing before trigger */}
          <div style={{ height: 82, overflow: 'hidden', marginBottom: 0, opacity: frame >= 108 ? 1 : 0 }}>
            <div style={{ position: 'relative', transform: `translateY(${((1 - oldIn) * 110).toFixed(1)}%)`, ...type(60, 500), color: mixC(strike, L.ink2, L.ink3) }}>
              $42.00
              <div style={{
                position: 'absolute', left: -4, top: '54%', height: 4, borderRadius: 2, background: L.ink3,
                width: `calc(${(strike * 100).toFixed(1)}% + ${(8 * strike).toFixed(1)}px)`,
              }} />
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <TextReveal text="$34.44" by="char" variant="rise" start={116} each={14} gap={1.2}
              style={{ ...type(180, 750), letterSpacing: '-0.05em', color: L.ink }} />
            <span style={{ ...type(48, 500), color: L.ink2, opacity: ramp(frame, 124, 10, EASE.out) }}>/mo</span>
          </div>
        </div>
        <div style={{
          position: 'absolute', left: 0, right: 0, top: 690, display: 'flex', justifyContent: 'center',
        }}>
          <div style={{
            padding: '12px 26px', borderRadius: 99, background: L.accent, color: L.onAccent, ...type(32, 650),
            boxShadow: `inset 0 1px 0 rgba(255,255,255,0.3), 0 10px 26px -10px ${alpha(L.accent, 0.8)}`,
            opacity: Math.min(1, saveIn * 1.5), transform: `translateY(${((1 - saveIn) * 16).toFixed(2)}px) scale(${(0.8 + 0.2 * saveIn).toFixed(3)})`,
          }}>Save 18% · billed $413.28 yearly</div>
        </div>

        <Cursor frame={frame} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
