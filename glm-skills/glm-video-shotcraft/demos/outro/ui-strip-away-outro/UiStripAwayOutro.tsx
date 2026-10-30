// ui-strip-away-outro — framer-ai 33–36.5s
// Fullscreen "editor" UI where cursor clicks highlighted Publish button -> UI evaporates layer-by-layer in staggered sequence
// (each layer combines fade + directional displacement + evaporation blur, moving from perimeter to center) -> dark background leaves only button -> button fades yielding to wordmark.
// Polish: editorial-grade mockup UI (dark layers panel, authentic property inspector fields, dot grid canvas, browser preview frame containing
// fixture cards), hairline borders + dual soft shadows; Publish uses accent color, elevated to dark field with matching halo;
// dark field has subtle cool hue (central shimmer + vignette + grain); wordmark is video-shotcraft mark + wordmark lockup, focus-rack entrance.
// Brand cycle: editor represents video-shotcraft workspace (layers = shots of a launch film); toolbar logo and closing lockup use brand mark.
import React from 'react';
import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig, Easing } from 'remotion';
import { G, Card } from '../../_fixtures/Fixtures';
import { EASE, FONT, Grain, Vignette, mix, ramp, hairline, softShadow, innerHighlight } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const UI_STRIP_AWAY_OUTRO_DURATION = 144; // Holds >= 1s after wordmark locks (R1)

const CLICK = 34; // Click frame
// Evaporation hierarchy (delays after click, perimeter leaves first)
const STRIP = {
  sidebar: CLICK + 4,
  leftPanel: CLICK + 8,
  canvasCards: CLICK + 12,
  topbarEnds: CLICK + 16,
  canvasBg: CLICK + 20,
  toolbarShell: CLICK + 24,
};
const STRIP_DUR = 14;
const BTN_FADE = CLICK + 52;
const LOGO_IN = CLICK + 62;

const ACCENT = G.accent; // Publish brand highlight color
const INK = '#0b0c10'; // Dark field: cool-toned near black
// Publish button geometry: toolbar right edge -> screen center
const BTN_W = 150;
const BTN_H = 40;
const BTN_FROM = { x: 1920 - 24 - BTN_W / 2, y: 30 };
const BTN_TO = { x: 960, y: 540 };

// Layer evaporation progress -> {opacity, transform, filter}: ease-in exit acceleration + displacement + progressive blur (evaporation effect)
const strip = (frame: number, start: number, dx: number, dy: number): React.CSSProperties => {
  const p = interpolate(frame, [start, start + STRIP_DUR], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.in(Easing.quad), // Exit acceleration
  });
  return {
    opacity: 1 - p,
    transform: `translate(${dx * p}px, ${dy * p}px)`,
    filter: p > 0.001 ? `blur(${(p * 7).toFixed(2)}px)` : undefined,
  };
};

// Small icons (1.5px stroked icons, matching fixture design language)
const Icon: React.FC<{ d: string; size?: number; color?: string }> = ({ d, size = 18, color = G.ink2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const IC = {
  cursor: 'M5 3l13 8-6 1.5L9 19z',
  frame: 'M7 3v18M17 3v18M3 7h18M3 17h18',
  text: 'M5 6V4h14v2M12 4v16M9 20h6',
  pen: 'M12 19l7-7-3-3-7 7-1 4zM14 7l3 3',
  image: 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4',
  comp: 'M12 3l4 4-4 4-4-4zM12 13l4 4-4 4-4-4z',
  layer: 'M4 7h16v10H4z',
  textL: 'M6 7V5h12v2M12 5v14',
  group: 'M4 6h7v5H4zM13 6h7v5h-7zM4 13h16v5H4z',
};

const LAYERS: [string, string, number, boolean?][] = [
  ['frame', 'Launch film', 0],
  ['layer', 'Cold open', 1],
  ['group', 'Hero shot', 1],
  ['textL', 'Title card', 2],
  ['textL', 'Subtitle', 2],
  ['group', 'Feature shots', 1, true],
  ['layer', 'Shot — Crash zoom', 2],
  ['layer', 'Shot — Dolly push', 2],
  ['layer', 'Shot — Whip pan', 2],
  ['layer', 'Shot — Beat cut', 2],
  ['layer', 'Logo sting', 1],
];

const Field: React.FC<{ label: string; value: string; w?: number }> = ({ label, value, w }) => (
  <div style={{
    height: 34, flex: w ? 'none' : 1, width: w, borderRadius: 8, background: G.fill, border: hairline(0.07),
    display: 'flex', alignItems: 'center', gap: 8, padding: '0 10px', boxSizing: 'border-box',
    fontFamily: FONT.sans, fontSize: 13, fontVariantNumeric: 'tabular-nums',
  }}>
    <span style={{ color: G.ink3 }}>{label}</span>
    <span style={{ color: G.ink1, fontWeight: 500 }}>{value}</span>
  </div>
);

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 10, paddingBottom: 18, borderBottom: hairline(0.07) }}>
    <div style={{ fontFamily: FONT.sans, fontSize: 12, fontWeight: 600, color: G.ink1, letterSpacing: '0.01em' }}>{title}</div>
    {children}
  </div>
);

export const UiStripAwayOutro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Background: editor base -> dark field (darkens as canvasBg layer evaporates)
  const bgDark = interpolate(frame, [STRIP.canvasBg, STRIP.canvasBg + STRIP_DUR + 6], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.quad),
  });

  const sidebar = strip(frame, STRIP.sidebar, -140, 0);
  const leftPanel = strip(frame, STRIP.leftPanel, -90, 20);
  const topLeft = strip(frame, STRIP.topbarEnds, -80, -60);
  const topRight = strip(frame, STRIP.topbarEnds, 80, -60);
  const toolbarShell = strip(frame, STRIP.toolbarShell, 0, -50);
  const canvasFrame = strip(frame, STRIP.canvasBg, 0, 40);

  // Canvas cards staggered evaporation (staggered by 3f, alternating left and right)
  const cardStrip = (i: number) => strip(frame, STRIP.canvasCards + i * 3, i % 2 ? 70 : -70, 50 + i * 10);

  // Button: click pulse + final fade-out
  const press = spring({ frame: frame - CLICK, fps, config: { damping: 12, stiffness: 220 } });
  const pressScale = frame < CLICK ? 1 : 1 - 0.12 * Math.sin(Math.min(1, press) * Math.PI);
  const btnOp = 1 - ramp(frame, BTN_FADE, 12, EASE.exit);
  // Button glides from toolbar position to screen center during evaporation, dominating the dark field
  const btnCenter = interpolate(frame, [STRIP.toolbarShell, STRIP.toolbarShell + 18], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.inOut(Easing.cubic),
  });
  const btnX = mix(BTN_FROM.x, BTN_TO.x, btnCenter);
  const btnY = mix(BTN_FROM.y, BTN_TO.y, btnCenter);
  const btnScale = 1 + 0.5 * btnCenter;
  // Directional trail blur during peak migration (blur based on frame delta, 0 at rest)
  const dPrev = interpolate(frame - 1, [STRIP.toolbarShell, STRIP.toolbarShell + 18], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic),
  });
  const btnSpeed = Math.hypot(BTN_TO.x - BTN_FROM.x, BTN_TO.y - BTN_FROM.y) * Math.abs(btnCenter - dPrev);
  const btnBlur = Math.min(3, btnSpeed * 0.04);
  // Button scales up slightly and dissolves upon fade-out, handing the dark field over to the wordmark
  const btnRelease = ramp(frame, BTN_FADE, 12, EASE.out);

  // Wordmark handoff: spring settle + focus blur; text lags mark by 3f (follower)
  const logoP = spring({ frame: frame - LOGO_IN, fps, config: { damping: 14, stiffness: 90 } });
  const wordP = spring({ frame: frame - LOGO_IN - 3, fps, config: { damping: 14, stiffness: 90 } });

  // Cursor moves to button: distinct x and y easing creates a natural curved wrist motion; tip depresses on click
  const curX = interpolate(frame, [4, CLICK - 2], [820, BTN_FROM.x + 18], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad),
  });
  const curY = interpolate(frame, [4, CLICK - 2], [640, BTN_FROM.y + 4], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.15, 1),
  });
  const curOp = 1 - ramp(frame, CLICK + 6, 10, EASE.out);
  const curPress = frame >= CLICK - 1 && frame < CLICK + 3 ? 0.88 : 1;

  const toolbarBase: React.CSSProperties = {
    position: 'absolute', top: 0, height: 60, background: '#fbfbfa', borderBottom: hairline(0.08),
    boxSizing: 'border-box', display: 'flex', alignItems: 'center', fontFamily: FONT.sans,
  };

  return (
    <AbsoluteFill style={{ background: INK, overflow: 'hidden' }}>
      {/* Dark field: subtle cool central glow (illuminates as background darkens) */}
      <AbsoluteFill style={{
        opacity: bgDark,
        background: 'radial-gradient(ellipse 50% 45% at 50% 50%, rgba(120,128,220,0.10) 0%, rgba(120,128,220,0.03) 50%, rgba(0,0,0,0) 75%)',
      }} />

      {/* Editor base (dot matrix canvas, acting as an evaporable background layer) */}
      <AbsoluteFill style={{
        opacity: 1 - bgDark,
        backgroundColor: '#ececea',
        backgroundImage: 'radial-gradient(rgba(20,22,28,0.10) 1px, transparent 1.2px)',
        backgroundSize: '24px 24px',
      }} />

      {/* Left sidebar (layers panel) */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 240, boxSizing: 'border-box', paddingTop: 76,
        background: 'linear-gradient(180deg, #1c1d22 0%, #16171b 100%)', boxShadow: 'inset -1px 0 0 rgba(255,255,255,0.06)',
        fontFamily: FONT.sans, ...sidebar,
      }}>
        <div style={{ padding: '0 18px 12px', fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', color: 'rgba(255,255,255,0.36)' }}>LAYERS</div>
        {LAYERS.map(([ic, name, depth, sel]) => (
          <div key={name} style={{
            height: 32, margin: '0 10px', borderRadius: 7, display: 'flex', alignItems: 'center', gap: 9,
            paddingLeft: 10 + depth * 16, fontSize: 13, color: sel ? '#fff' : 'rgba(255,255,255,0.62)',
            background: sel ? 'rgba(128,136,240,0.22)' : 'transparent',
            boxShadow: sel ? 'inset 0 0 0 1px rgba(128,136,240,0.35)' : 'none',
          }}>
            <Icon d={IC[ic as keyof typeof IC]} size={14} color={sel ? '#c9cdff' : 'rgba(255,255,255,0.42)'} />
            {name}
          </div>
        ))}
      </div>

      {/* Right inspector panel */}
      <div style={{
        position: 'absolute', right: 0, top: 60, bottom: 0, width: 300, background: '#fbfbfa', borderLeft: hairline(0.08),
        padding: 22, boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 18, ...leftPanel,
      }}>
        <Section title="Frame">
          <div style={{ display: 'flex', gap: 8 }}><Field label="X" value="320" /><Field label="Y" value="130" /></div>
          <div style={{ display: 'flex', gap: 8 }}><Field label="W" value="1180" /><Field label="H" value="850" /></div>
        </Section>
        <Section title="Layout">
          <div style={{ display: 'flex', gap: 8 }}><Field label="Gap" value="40" /><Field label="Pad" value="70" /></div>
        </Section>
        <Section title="Fill">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#ffffff', border: hairline(0.12), boxSizing: 'border-box' }} />
            <Field label="Hex" value="FFFFFF" />
            <Field label="" value="100%" w={64} />
          </div>
        </Section>
        <Section title="Effects">
          <div style={{ display: 'flex', gap: 8 }}><Field label="Shadow" value="Soft · 16" /></div>
        </Section>
      </div>

      {/* Top toolbar left half (logo + tools) */}
      <div style={{ ...toolbarBase, left: 0, width: 760, gap: 6, padding: '0 16px', ...topLeft }}>
        <div style={{ marginRight: 14 }}><ShotcraftMark size={34} tone="light" /></div>
        {[IC.cursor, IC.frame, IC.text, IC.pen, IC.image, IC.comp].map((d, i) => (
          <div key={i} style={{
            width: 36, height: 36, borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: i === 0 ? G.accentSoft : 'transparent',
          }}>
            <Icon d={d} size={18} color={i === 0 ? ACCENT : G.ink2} />
          </div>
        ))}
      </div>
      {/* Top toolbar center (title) */}
      <div style={{ ...toolbarBase, left: 760, right: 400, justifyContent: 'center', gap: 10, ...toolbarShell }}>
        <span style={{ fontSize: 14, color: G.ink3 }}>{BRAND.name}</span>
        <span style={{ fontSize: 14, color: G.ink3 }}>/</span>
        <span style={{ fontSize: 14, color: G.ink1, fontWeight: 600, letterSpacing: '-0.01em' }}>Launch film</span>
        <span style={{ fontSize: 11.5, fontWeight: 500, color: G.ink2, padding: '3px 8px', borderRadius: 6, background: G.fill2 }}>Draft</span>
      </div>
      {/* Top toolbar right base (avatars + Invite; Publish rendered separately on top layer) */}
      <div style={{ ...toolbarBase, right: 0, width: 400, justifyContent: 'flex-end', gap: 12, padding: `0 ${24 + BTN_W + 12}px 0 24px`, ...topRight }}>
        <div style={{ display: 'flex' }}>
          {['JL', 'MR'].map((n, i) => (
            <div key={n} style={{
              width: 30, height: 30, borderRadius: 15, marginLeft: i ? -8 : 0, background: i ? '#dfe1e8' : '#e9e6df',
              border: '2px solid #fbfbfa', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 600, color: '#4a4c53',
            }}>{n}</div>
          ))}
        </div>
        <div style={{
          height: 34, padding: '0 14px', borderRadius: 9, border: hairline(0.13), boxSizing: 'border-box',
          display: 'flex', alignItems: 'center', fontSize: 13.5, fontWeight: 500, color: G.ink1, background: '#fff',
          boxShadow: softShadow(1),
        }}>Invite</div>
      </div>

      {/* Canvas area: large browser-style card + four content cards */}
      <div style={{ position: 'absolute', left: 320, top: 130, width: 1180, height: 850, ...canvasFrame }}>
        <div style={{
          position: 'absolute', inset: 0, background: G.card, border: hairline(0.09), borderRadius: 18, overflow: 'hidden',
          boxShadow: `${innerHighlight(0.9)}, ${softShadow(22)}`,
        }}>
          <div style={{
            height: 46, borderBottom: hairline(0.07), display: 'flex', alignItems: 'center', gap: 8, padding: '0 18px',
            background: 'linear-gradient(180deg, #fbfbfa 0%, #f5f5f3 100%)',
          }}>
            {['#ec6a5e', '#f4bf4f', '#61c554'].map((c) => (
              <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c, opacity: 0.85 }} />
            ))}
            <div style={{
              marginLeft: 16, height: 26, width: 380, background: G.fill, borderRadius: 8, display: 'flex', alignItems: 'center',
              padding: '0 12px', fontFamily: FONT.sans, fontSize: 12.5, color: G.ink2, gap: 6,
            }}>
              <svg width={11} height={11} viewBox="0 0 24 24" fill="none" stroke={G.ink3} strokeWidth={2.4}><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
              {BRAND.repo}
            </div>
          </div>
        </div>
        {[0, 1, 2, 3].map((i) => {
          const s = cardStrip(i);
          return (
            <div key={i} style={{ position: 'absolute', left: 70 + (i % 2) * 560, top: 120 + Math.floor(i / 2) * 340, ...s }}>
              <Card w={480} h={280} seed={i + 2} />
            </div>
          );
        })}
      </div>

      {/* Publish button (highlight layer, exits last): centered, scaled by layout to keep typography crisp */}
      <div
        style={{
          position: 'absolute', left: btnX, top: btnY, width: 0, height: 0, zIndex: 30,
          opacity: btnOp, transform: `scale(${pressScale * (1 + 0.06 * btnRelease)})`,
          filter: btnBlur > 0.2 ? `blur(${btnBlur.toFixed(2)}px)` : undefined,
        }}
      >
        {/* Hero halo on dark field: matching soft glow disc, intensifies as field darkens */}
        <div style={{
          position: 'absolute', left: -260, top: -160, width: 520, height: 320, borderRadius: '50%',
          background: 'radial-gradient(ellipse at center, rgba(91,99,211,0.38) 0%, rgba(91,99,211,0.10) 40%, rgba(91,99,211,0) 70%)',
          opacity: btnCenter * bgDark,
        }} />
        <div
          style={{
            position: 'absolute',
            width: BTN_W * btnScale, height: BTN_H * btnScale,
            left: -(BTN_W * btnScale) / 2, top: -(BTN_H * btnScale) / 2,
            borderRadius: 10 * btnScale,
            background: 'linear-gradient(180deg, #6a72e0 0%, #545cd0 100%)',
            boxShadow: `inset 0 1px 0 rgba(255,255,255,0.28), inset 0 0 0 1px rgba(255,255,255,0.06), 0 1px 2px rgba(30,34,120,0.35), 0 0 ${30 + 40 * btnCenter}px rgba(110,118,240,${(0.18 + 0.4 * btnCenter * bgDark).toFixed(3)})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 * btnScale,
            fontFamily: FONT.sans, fontWeight: 600, fontSize: 15 * btnScale, letterSpacing: '-0.01em', color: '#ffffff',
          }}
        >
          <svg width={14 * btnScale} height={14 * btnScale} viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 19V5M5 12l7-7 7 7" />
          </svg>
          Publish
        </div>
      </div>

      {/* Wordmark handoff */}
      {frame >= LOGO_IN && (
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 30, transform: `scale(${0.86 + 0.14 * logoP})` }}>
            <div style={{ opacity: Math.min(1, logoP * 1.4), filter: logoP < 0.995 ? `blur(${((1 - logoP) * 9).toFixed(2)}px)` : undefined }}>
              <ShotcraftMark size={132} tone="dark" />
            </div>
            <div style={{
              opacity: Math.min(1, wordP * 1.4), transform: `translateX(${((1 - wordP) * -16).toFixed(2)}px)`,
              filter: wordP < 0.995 ? `blur(${((1 - wordP) * 9).toFixed(2)}px)` : undefined,
              fontFamily: BRAND.font, fontWeight: 700, fontSize: 68, lineHeight: 1, letterSpacing: '0.03em', color: BRAND.paper, paddingBottom: 4, whiteSpace: 'nowrap',
            }}>
              {BRAND.name}
            </div>
          </div>
        </AbsoluteFill>
      )}

      {/* Cursor */}
      <svg width={30} height={38} viewBox="0 0 14 18" style={{
        position: 'absolute', left: curX, top: curY, opacity: curOp, zIndex: 40,
        transform: `scale(${curPress})`, transformOrigin: '2px 2px', filter: 'drop-shadow(0 3px 5px rgba(16,18,24,0.3))',
      }}>
        <path d="M1 1 L1 15 L4.6 11.6 L7.2 17 L9.4 16 L6.9 10.7 L12 10.7 Z" fill="#111216" stroke="#ffffff" strokeWidth={1.1} strokeLinejoin="round" />
      </svg>

      {/* Vignette + grain: intensifies with dark field (minimal on bright field) */}
      <Vignette strength={0.12 + 0.45 * bgDark} inner={0.42} color="#000000" />
      <Grain opacity={0.05 + 0.03 * bgDark} blend="soft-light" />
    </AbsoluteFill>
  );
};
