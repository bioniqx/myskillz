// word-relay-filmstrip — left filmstrip evidence steps while right title relays (constant noun + verb rotation)
//
// Redesign (graphite: cinematic editorial room):
// - look = graphite (near monochrome dark field + gold accent). Left column 940x530 page cards alternate black and white:
//   rhythm report / storyboard / render pipeline / final review / viewer / manifest, each verb paired with proof.
//   Subject is video-shotcraft (Shotcraft): frames -> builds -> ships.
// - Depth of field: focal card (center at y=540) full scale and brightness; neighbors dim + scale 0.94 + subtle blur,
//   stepping card focuses in as filmstrip advances.
// - Stepped mechanics: left column static except during 18f switch window, stepping one slot with vertical motion blur.
// - Right 140px typography: row 1 noun "Shotcraft" constant, row 2 italic white verb rotates in place —
//   old verb grays and exits top edge (8f ease-in), new verb rises letter-by-letter from bottom (1.2f stagger).
//   Vertical center = focal card midline y=540; gold leader line extends from focal card to word block,
//   retracting on switch and redrawing on settle; supporting footnote relays synchronously below word block.
//
// Timeline (30fps, total 180f):
//   0-16    Lead-in: filmstrip static, Shotcraft and leader line present, index 00
//   16-34   Slot 1: filmstrip scrolls to Storyboard, "frames" rises (23-45)
//   34-66   Hold (filmstrip static; camera slow push 1->1.02)
//   66-84   Slot 2: "frames" exits (66-74) -> "builds" rises (73-95), filmstrip scrolls to Render Pipeline
//   84–114  hold
//   114-132 Slot 3: "ships" (121-141), filmstrip stops on Final Review
//   141-180 Hold: final poster lock
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { EASE, FONT, SpeedBlur, mix, ramp, velocity } from '../../_fixtures/Polish';
import { LOOKS, Stage, alpha } from '../../_fixtures/Look';
import { BRAND, ShotcraftMark, ShotcraftWordmark } from '../../_fixtures/Brand';

export const WORD_RELAY_FILMSTRIP_DURATION = 180;

const L = LOOKS.graphite;

const CARD_W = 940;
const CARD_H = 530;
const GAP = 105;
const STEP = CARD_H + GAP;

const SANS = FONT.sans;
const SERIF_TXT = '"Iowan Old Style", "Charter", Georgia, serif';

// --- Page Card Collection: alternating black and white ---
// Storyboard (light) — proof for "frames": launch video storyboard document
const LightArticle: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#ffffff', padding: '30px 46px', fontFamily: SANS }}>
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 28, paddingBottom: 16, borderBottom: '1px solid #eceae5' }}>
      <ShotcraftWordmark size={19} tone="light" markScale={1.7} gap={9} />
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 26, fontSize: 14, color: '#8a8780' }}>
        {['Shots', 'Templates', 'Gallery', 'Docs'].map((t, i) => <span key={t} style={{ color: i === 0 ? '#1d1c1a' : undefined, fontWeight: i === 0 ? 600 : 400 }}>{t}</span>)}
      </div>
    </div>
    <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', color: '#c4523a', marginBottom: 12 }}>STORYBOARD · LAUNCH FILM · 42 S</div>
    <div style={{ fontFamily: SERIF_TXT, fontSize: 38, lineHeight: 1.14, color: '#1b1a18', width: 620, marginBottom: 22, letterSpacing: '-0.01em' }}>
      Twelve shots, one story,<br />every cut on the beat
    </div>
    <div style={{ display: 'flex', gap: 30 }}>
      <div style={{ flex: 1.3, fontFamily: SERIF_TXT, fontSize: 15.5, lineHeight: 1.6, color: '#5d5a54' }}>
        The film opens on the real dashboard, pushes into the empty state, then crash-zooms onto the first result. Every
        cut lands on a downbeat of the 112 BPM track, every camera move comes from a tuned shot recipe card, and the
        brand lockup holds for the last two bars before the call to action.
      </div>
      <div style={{ flex: 1, borderRadius: 10, background: '#f7f5f0', border: '1px solid #ebe7de', padding: '16px 18px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', color: '#9a7a3a', marginBottom: 12 }}>SHOT LIST</div>
        {[['S01', 'Dashboard push-in'], ['S02', 'Crash zoom punch'], ['S03', 'Word relay'], ['S04', 'Brand lockup']].map(([n, l]) => (
          <div key={l} style={{ display: 'flex', gap: 12, alignItems: 'baseline', marginBottom: 9 }}>
            <span style={{ width: 56, fontSize: 15, fontWeight: 700, color: '#1d1c1a', fontVariantNumeric: 'tabular-nums' }}>{n}</span>
            <span style={{ fontSize: 13.5, color: '#77736b' }}>{l}</span>
          </div>
        ))}
      </div>
    </div>
    {/* Figure 1: bar chart of shot durations + caption */} 
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 22, marginTop: 20, paddingTop: 14, borderTop: '1px solid #eceae5' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height: 48 }}>
        {[0.18, 0.24, 0.31, 0.46, 0.58, 0.72, 0.9, 1].map((v, i) => (
          <div key={i} style={{ width: 14, height: `${v * 100}%`, borderRadius: 2, background: i === 7 ? '#c4523a' : '#d9d4ca' }} />
        ))}
      </div>
      <div style={{ fontSize: 13, color: '#8a8780', lineHeight: 1.45 }}>
        <span style={{ fontWeight: 700, color: '#4a4741' }}>Fig. 1</span> — Shot lengths in frames, snapped to the beat grid
      </div>
      <div style={{ marginLeft: 'auto', fontSize: 13, color: '#8a8780' }}>Storyboard v3 · 30 fps</div>
    </div>
  </div>
);

const DarkMri: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#08090b', fontFamily: SANS }}>
    <div style={{ height: 46, borderBottom: '1px solid #1a1c21', display: 'flex', alignItems: 'center', gap: 14, padding: '0 24px' }}>
      <div style={{ fontSize: 15, fontWeight: 650, color: '#d4d7dc' }}>Scan Viewer</div>
      <div style={{ fontSize: 13, color: '#5f646e' }}>Study 0042 · Brain MRI · T2 FLAIR</div>
      <div style={{ marginLeft: 'auto', fontSize: 12.5, color: '#b8a24e', fontWeight: 600 }}>● 3 annotations</div>
    </div>
    <div style={{ display: 'flex', height: CARD_H - 46 }}>
      <div style={{ width: 190, borderRight: '1px solid #16181c', padding: '18px 18px' }}>
        <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: '0.12em', color: '#8d7c3e', marginBottom: 12 }}>SERIES</div>
        {['Axial T1', 'Axial T2', 'FLAIR', 'DWI b1000', 'ADC map'].map((t, i) => (
          <div key={t} style={{ fontSize: 13.5, color: i === 2 ? '#e2e4e8' : '#5c616b', padding: '6px 8px', borderRadius: 6, background: i === 2 ? 'rgba(255,255,255,0.05)' : 'transparent', marginBottom: 2 }}>{t}</div>
        ))}
      </div>
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: 290, height: 350, borderRadius: '46% 46% 42% 42%',
          background: 'radial-gradient(ellipse 46% 40% at 50% 42%, #b9bcc0 0%, #6c7076 34%, #33363c 62%, #101216 100%)',
          position: 'relative', boxShadow: '0 0 60px rgba(150,160,180,0.08)',
        }}>
          {[[118, 98], [196, 150], [92, 210]].map(([x, y], i) => (
            <div key={i} style={{ position: 'absolute', left: x, top: y, width: 14, height: 14, borderRadius: 7, border: '2px solid #d8b25a', boxShadow: '0 0 8px rgba(216,178,90,0.5)' }} />
          ))}
        </div>
      </div>
      <div style={{ width: 200, borderLeft: '1px solid #16181c', padding: '18px 18px' }}>
        <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: '0.12em', color: '#6a6f79', marginBottom: 12 }}>FINDINGS</div>
        {[['A1', 'Focal hyperintensity, 4 mm'], ['A2', 'No mass effect'], ['A3', 'Ventricles normal']].map(([k, v]) => (
          <div key={k} style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#d8b25a' }}>{k}</div>
            <div style={{ fontSize: 13, color: '#8a8f99', lineHeight: 1.4 }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

const LightTable: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#ffffff', padding: '28px 40px', fontFamily: SANS }}>
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 18 }}>
      <ShotcraftMark size={30} tone="light" style={{ marginRight: 12 }} />
      <div style={{ fontSize: 22, fontWeight: 700, color: '#1d1e21', letterSpacing: '-0.01em' }}>Q3 shipments by region</div>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 18, fontSize: 13.5, color: '#8b9099' }}>
        <span>Export CSV</span><span>Filters (2)</span>
      </div>
    </div>
    <div style={{ display: 'flex', fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', color: '#9aa0aa', padding: '0 0 8px', borderBottom: '1px solid #e6e8ec' }}>
      <span style={{ width: 40 }}>#</span><span style={{ flex: 1 }}>REGION</span>
      <span style={{ width: 110, textAlign: 'right' }}>UNITS</span><span style={{ width: 110, textAlign: 'right' }}>REVENUE</span><span style={{ width: 90, textAlign: 'right' }}>YOY</span>
    </div>
    {[
      ['Northern Europe', '48,210', '$12.4M', '+18%', '#3a8a52'], ['East Asia', '41,977', '$11.9M', '+9%', '#2c62b8'],
      ['North America', '39,402', '$10.2M', '+4%', '#caa53c'], ['Latin America', '22,816', '$5.1M', '+27%', '#b23a3a'],
      ['Middle East', '18,330', '$4.6M', '−2%', '#3a8a52'], ['Oceania', '9,114', '$2.3M', '+11%', '#2c62b8'],
      ['Southern Africa', '6,702', '$1.4M', '+6%', '#caa53c'],
    ].map(([name, u, r, y, c], i) => (
      <div key={name} style={{ display: 'flex', alignItems: 'center', padding: '10.5px 0', borderBottom: '1px solid #f0f1f4', fontSize: 15, color: '#2a2c30', fontVariantNumeric: 'tabular-nums' }}>
        <span style={{ width: 40, color: '#a0a5ae', fontSize: 13.5 }}>{i + 1}</span>
        <span style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: c }} />{name}
        </span>
        <span style={{ width: 110, textAlign: 'right' }}>{u}</span>
        <span style={{ width: 110, textAlign: 'right', fontWeight: 600 }}>{r}</span>
        <span style={{ width: 90, textAlign: 'right', color: y.startsWith('−') ? '#b8463d' : '#2e8a50', fontWeight: 600 }}>{y}</span>
      </div>
    ))}
  </div>
);

const DarkStats: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, #110f14 0%, #0c0b0f 100%)', padding: '34px 46px', fontFamily: SANS }}>
    <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', color: '#b0584c', marginBottom: 8 }}>PACING REPORT · LAUNCH FILM</div>
    <div style={{ fontSize: 28, fontWeight: 700, color: '#ece8e2', letterSpacing: '-0.015em', marginBottom: 22 }}>Motion energy, shot by shot</div>
    <div style={{ borderLeft: '2px solid #5e2530', paddingLeft: 26 }}>
      {[['S01', 0.24, '24.7'], ['S02', 0.33, '33.5'], ['S03', 0.46, '46.2'], ['S04', 0.58, '58.0'], ['S05', 0.69, '69.4'], ['S06', 0.86, '86.1']].map(([k, w, v], i) => (
        <div key={k as string} style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 14 }}>
          <span style={{ width: 40, fontSize: 14, color: '#7d7983', fontWeight: 600 }}>{k}</span>
          <div style={{ width: 520, height: i === 5 ? 22 : 16, borderRadius: 4, background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
            <div style={{ width: `${(w as number) * 100}%`, height: '100%', borderRadius: 4, background: i === 5 ? 'linear-gradient(90deg, #8c2f27, #d24a3a)' : '#5a5560' }} />
          </div>
          <span style={{ fontSize: 15, fontWeight: 700, color: i === 5 ? '#f08a76' : '#bdb8c2', fontVariantNumeric: 'tabular-nums' }}>{v}%</span>
        </div>
      ))}
    </div>
    <div style={{ marginTop: 22, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '16px 24px', display: 'flex', gap: 54 }}>
      {[['12', 'shots on the beat'], ['112', 'BPM soundtrack'], ['0', 'dropped frames']].map(([n, l]) => (
        <div key={l}>
          <div style={{ fontSize: 22, fontWeight: 750, color: '#e8735f', fontVariantNumeric: 'tabular-nums' }}>{n}</div>
          <div style={{ fontSize: 13, color: '#77727e' }}>{l}</div>
        </div>
      ))}
    </div>
  </div>
);

// Render Pipeline (dark) — proof for "builds": pipeline build progress
const DarkBuild: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, #111318 0%, #0c0d11 100%)', padding: '26px 40px', fontFamily: SANS }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
      <div style={{ fontSize: 19, fontWeight: 700, color: '#e6e8ee' }}>{BRAND.name} / launch-film</div>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: '#9aa1b4', padding: '3px 9px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.1)' }}>main</div>
      <div style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 700, color: '#e8b84a' }}>● Render #1284 running</div>
    </div>
    {/* Pipeline stages */} 
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
      {[['Storyboard', 1], ['Shots', 1], ['Sound', 1], ['Render', 1], ['Deliver', 0]].map(([t, ok], i) => (
        <React.Fragment key={t as string}>
          {i > 0 && <div style={{ flex: 1, height: 1, background: ok ? 'rgba(95,195,140,0.4)' : 'rgba(255,255,255,0.1)' }} />}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7, padding: '7px 12px', borderRadius: 9, fontSize: 13.5, fontWeight: 600,
            color: ok ? '#cfe9da' : '#f1d58f', background: ok ? 'rgba(95,195,140,0.09)' : 'rgba(232,184,74,0.1)',
            border: `1px solid ${ok ? 'rgba(95,195,140,0.22)' : 'rgba(232,184,74,0.3)'}`,
          }}>
            <span style={{ color: ok ? '#5fc38c' : '#e8b84a' }}>{ok ? '✓' : '◐'}</span>{t}
          </div>
        </React.Fragment>
      ))}
    </div>
    <div style={{ display: 'flex', gap: 18 }}>
      {/* Render logs */} 
      <div style={{ flex: 1.6, background: '#08090c', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '14px 18px', fontFamily: FONT.mono, fontSize: 13, lineHeight: 1.75, color: '#7c8293' }}>
        <div><span style={{ color: '#5f6577' }}>$</span> <span style={{ color: '#d4d8e2' }}>npx remotion render Main launch.mp4</span></div>
        <div><span style={{ color: '#5fc38c' }}>✓</span> Bundled 12 shots in 8.3s</div>
        <div><span style={{ color: '#5fc38c' }}>✓</span> 1,260 frames rendered · 0 dropped</div>
        <div><span style={{ color: '#5fc38c' }}>✓</span> 18 SFX cues locked to the beat</div>
        <div><span style={{ color: '#5fc38c' }}>✓</span> Encoded h264 · 1080p · 30 fps</div>
        <div><span style={{ color: '#e8b84a' }}>▲</span> <span style={{ color: '#c9cdd8' }}>Exporting JianYing draft…</span></div>
      </div>
      {/* Summary metrics */} 
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[['Duration', '42.0s'], ['Frames', '1,260'], ['Render time', '1m 42s']].map(([k, v]) => (
          <div key={k} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 10, padding: '11px 16px' }}>
            <div style={{ fontSize: 12, color: '#6c7283', fontWeight: 600, letterSpacing: '0.06em' }}>{k.toUpperCase()}</div>
            <div style={{ fontSize: 21, fontWeight: 700, color: '#e6e8ee', fontVariantNumeric: 'tabular-nums' }}>{v}</div>
          </div>
        ))}
      </div>
    </div>
  </div>
);

// Final Review (light) — proof for "ships": launch PR review
const CODE: { n: number; d?: '+' | '-'; t: [string, string][] }[] = [
  { n: 12, t: [['export function ', '#a626a4'], ['Hero', '#4078f2'], ['(props: ', '#383a42'], ['HeroProps', '#c18401'], [') {', '#383a42']] },
  { n: 13, t: [['  const ', '#a626a4'], ['film', '#383a42'], [' = ', '#0184bc'], ['staticFile', '#4078f2'], ['(', '#383a42'], ["'launch.mp4'", '#50a14f'], [');', '#383a42']] },
  { n: 14, d: '-', t: [['  return ', '#a626a4'], ['<img src={props.screenshot} alt=', '#383a42'], ['""', '#50a14f'], [' />;', '#383a42']] },
  { n: 14, d: '+', t: [['  return ', '#a626a4'], ['<video src={film} autoPlay muted loop', '#383a42']] },
  { n: 15, d: '+', t: [['    poster=', '#383a42'], ['"launch-poster.jpg"', '#50a14f'], [' />;', '#383a42']] },
  { n: 16, t: [['}', '#383a42']] },
  { n: 17, t: [['', '#383a42']] },
  { n: 18, t: [['export default ', '#a626a4'], ['Hero', '#4078f2'], [';', '#383a42']] },
];
const LightCode: React.FC = () => (
  <div style={{ position: 'absolute', inset: 0, background: '#ffffff', fontFamily: SANS, display: 'flex', flexDirection: 'column' }}>
    <div style={{ height: 52, display: 'flex', alignItems: 'center', gap: 12, padding: '0 28px', borderBottom: '1px solid #eceef1' }}>
      <div style={{ fontSize: 16, fontWeight: 700, color: '#1d1e21' }}>Add the launch film to the hero</div>
      <div style={{ fontSize: 13, color: '#8b9099' }}>#482 · 3 files · +24 −9</div>
      <div style={{ marginLeft: 'auto', fontSize: 12.5, fontWeight: 700, color: '#2e8a50', padding: '4px 10px', borderRadius: 10, background: 'rgba(46,138,80,0.1)' }}>✓ Checks passed</div>
    </div>
    <div style={{ display: 'flex', flex: 1 }}>
      <div style={{ width: 200, borderRight: '1px solid #eceef1', padding: '16px 18px', fontSize: 13.5, color: '#6b7079' }}>
        {[['src/', 0], ['landing/', 1], ['Hero.tsx', 2], ['Pricing.tsx', 2], ['public/', 0], ['launch.mp4', 1], ['launch-poster.jpg', 1]].map(([t, l]) => (
          <div key={t as string} style={{
            padding: '5px 8px', paddingLeft: 8 + (l as number) * 14, borderRadius: 6, marginBottom: 1,
            background: t === 'Hero.tsx' ? '#eef2fb' : 'transparent', color: t === 'Hero.tsx' ? '#2c62c6' : undefined,
            fontWeight: t === 'Hero.tsx' ? 600 : 400,
          }}>{t}</div>
        ))}
      </div>
      <div style={{ flex: 1, padding: '14px 0', fontFamily: FONT.mono, fontSize: 14.5, lineHeight: 1.85 }}>
        <div style={{ padding: '0 20px 8px', fontSize: 12.5, color: '#8b9099', fontFamily: SANS }}>src/landing/Hero.tsx</div>
        {CODE.map((r, i) => (
          <div key={i} style={{
            display: 'flex', whiteSpace: 'pre',
            background: r.d === '+' ? 'rgba(46,160,90,0.09)' : r.d === '-' ? 'rgba(200,60,50,0.07)' : 'transparent',
          }}>
            <span style={{ width: 44, textAlign: 'right', color: '#b3b7bf', paddingRight: 10, fontVariantNumeric: 'tabular-nums' }}>{r.n}</span>
            <span style={{ width: 18, color: r.d === '+' ? '#2e9a5e' : '#c4473c' }}>{r.d ?? ' '}</span>
            {r.t.map(([s, c], k) => <span key={k} style={{ color: c, opacity: r.d === '-' ? 0.6 : 1 }}>{s}</span>)}
          </div>
        ))}
        {/* Review comments */} 
        <div style={{ margin: '14px 20px 0 62px', display: 'flex', gap: 12, alignItems: 'flex-start', fontFamily: SANS }}>
          <div style={{ width: 30, height: 30, borderRadius: 15, background: '#e6e9f2', color: '#4a5577', fontSize: 12, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>MR</div>
          <div style={{ border: '1px solid #e6e8ec', borderRadius: 10, padding: '9px 14px', background: '#fafbfc' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#2a2c30', marginBottom: 2 }}>Mira R. <span style={{ fontWeight: 400, color: '#9aa0aa' }}>· approved</span></div>
            <div style={{ fontSize: 13.5, color: '#4a4e56' }}>Feels like a launch film from a real studio. Ship it.</div>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// Fixed alternating order
// Word k pairs with Card k+1: frames -> Storyboard, builds -> Pipeline, ships -> Review;
// Card 0 is rhythm report, Cards 4 & 5 are neighboring margins
const CARDS: React.FC[] = [DarkStats, LightArticle, DarkBuild, LightCode, DarkMri, LightTable];

const WORDS = ['frames', 'builds', 'ships'];
const NOTES = ['Storyboard · 12 shots on the beat', 'Render #1284 · 1080p30 · 1m 42s', 'PR #482 · approved · launch film'];
const SWITCHES = [16, 66, 114];
const SW_DUR = 18;
const SERIF = '"Didot", "Bodoni 72", "Playfair Display", Georgia, serif';
const FS = 140;
const LINE = Math.round(FS * 1.1); // 154: line height per row
const WX = 1196; // Left edge of word block
const BLOCK_TOP = 540 - LINE; // Center of two-line word block = 540
const CARD_L = 100;
const FOCUS_TOP = 540 - CARD_H / 2; // 275

// Filmstrip step: static except during switch window (asymmetric in-out)
const stepAt = (frame: number) => SWITCHES.reduce((acc, s) => acc + ramp(frame, s, SW_DUR, EASE.swift), 0);

// Verb: rises letter-by-letter from bottom mask; exits upward across top
const Verb: React.FC<{ word: string; frame: number; inAt: number; outAt: number | null }> = ({ word, frame, inAt, outAt }) => {
  const grey = outAt !== null ? ramp(frame, outAt - 10, 10, EASE.smooth) : 0;
  const pOut = outAt !== null ? ramp(frame, outAt, 8, EASE.exit) : 0;
  if (frame < inAt || pOut >= 1) return null;
  const c = Math.round(mix(0xf4, 0x6a, grey));
  return (
    <div style={{
      position: 'absolute', left: 0, top: 0, height: LINE, whiteSpace: 'pre', color: `rgb(${c},${c},${Math.round(c * 0.98)})`,
      transform: `translateY(${(-pOut * LINE * 0.9).toFixed(2)}px)`, opacity: 1 - pOut * 0.6,
    }}>
      {Array.from(word + '.').map((ch, i) => {
        const k = ramp(frame, inAt + i * 1.2, 16, EASE.snappy);
        const dot = i === word.length; // Gold period dot rises last
        return (
          <span key={i} style={{ display: 'inline-block', color: dot && grey < 0.5 ? L.accent2 : undefined, transform: `translateY(${((1 - k) * LINE * 0.95).toFixed(2)}px)` }}>{ch}</span>
        );
      })}
    </div>
  );
};

export const WordRelayFilmstrip: React.FC = () => {
  const frame = useCurrentFrame();
  const stepF = stepAt(frame);
  const scroll = stepF * STEP;
  const vy = -velocity((f) => stepAt(f) * STEP, frame);
  const cam = mix(1, 1.02, ramp(frame, 0, WORD_RELAY_FILMSTRIP_DURATION, EASE.swift));

  // Card positioning: focal card top y=275; distance controls dimming/scale/blur
  const total = CARDS.length * STEP;
  const cards: React.ReactNode[] = [];
  for (let rep = -1; rep < 2; rep++) {
    CARDS.forEach((C, i) => {
      const y = FOCUS_TOP + i * STEP + rep * total - scroll;
      if (y > 1200 || y < -CARD_H - 120) return;
      const dist = Math.min(1.4, Math.abs(y - FOCUS_TOP) / STEP);
      const dim = Math.min(0.68, dist * 0.68);
      const sc = 1 - 0.06 * Math.min(1, dist);
      const blur = Math.min(3, dist * 3);
      const dark = i % 2 === 0;
      cards.push(
        <div key={`${rep}-${i}`} style={{
          position: 'absolute', top: y, left: CARD_L, width: CARD_W, height: CARD_H, borderRadius: 18, overflow: 'hidden',
          background: dark ? '#0d0e10' : '#ffffff', transform: `scale(${sc.toFixed(4)})`,
          border: `1px solid ${dark ? alpha('#ffffff', 0.1) : alpha('#000000', 0.2)}`,
          boxShadow: `inset 0 1px 0 ${alpha('#ffffff', dark ? 0.08 : 0.6)}, 0 2px 6px ${alpha('#000000', 0.5)}, 0 40px 90px -30px ${alpha('#000000', 0.95)}`,
          filter: blur > 0.15 ? `blur(${blur.toFixed(2)}px)` : undefined,
        }}>
          <C />
          <div style={{ position: 'absolute', inset: 0, background: alpha(L.bg[1], dark ? dim : 0.04 + dim * 0.96) }} />
        </div>,
      );
    });
  }

  // Active word index
  const IN_AT = SWITCHES.map((s) => s + 7); // New word rises 7f after switch point
  const idx = IN_AT.filter((s) => frame >= s).length; // 0..3
  // Leader line: retracts 6f on switch, redraws 16f after card settles
  const lastS = [...SWITCHES].reverse().find((s) => frame >= s);
  const lineP = lastS === undefined
    ? ramp(frame, 0, 16, EASE.snappy)
    : frame < lastS + 10 ? 1 - ramp(frame, lastS, 6, EASE.exit) : ramp(frame, lastS + 10, 16, EASE.snappy);
  const LX0 = CARD_L + CARD_W + 14;
  const LX1 = WX - 40;

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden', background: L.bg[2] }}>
      <Stage look={L} keyLight={{ x: 0.72, y: 0.12 }} fill={{ x: 0.15, y: 1.0 }} intensity={0.85} breathe={0.4} />
      <div style={{ position: 'absolute', inset: 0, transformOrigin: '960px 540px', transform: `scale(${cam.toFixed(4)})` }}>
        <SpeedBlur vx={0} vy={vy} amount={0.22} max={10}>{cards}</SpeedBlur>

        {/* Leader line: focal card right edge -> word block midline (y=540) */} 
        <div style={{ position: 'absolute', left: LX0, top: 539, width: (LX1 - LX0) * lineP, height: 2, background: `linear-gradient(90deg, ${L.accent2}, ${alpha(L.accent2, 0.35)})` }} />
        <div style={{ position: 'absolute', left: LX0 - 7, top: 533, width: 14, height: 14, borderRadius: 7, background: L.accent2, opacity: Math.min(1, lineP * 2), boxShadow: `0 0 16px ${alpha(L.accent2, 0.6)}` }} />

        {/* Numeric index */} 
        <div style={{ position: 'absolute', left: WX + 6, top: BLOCK_TOP - 58, fontFamily: FONT.mono, fontSize: 28, color: L.ink3, letterSpacing: '0.04em' }}>
          <span style={{ color: L.accent2 }}>{String(idx).padStart(2, '0')}</span> / 03
        </div>
        {/* Word block: Shotcraft constant + verb relay */} 
        <div style={{ position: 'absolute', left: WX, top: BLOCK_TOP, fontFamily: SERIF, fontSize: FS, lineHeight: `${LINE}px`, letterSpacing: '-0.01em' }}>
          <div style={{ height: LINE, color: L.ink2, whiteSpace: 'pre' }}>{BRAND.short}</div>
          <div style={{ position: 'relative', height: LINE, width: 760, overflow: 'hidden', fontStyle: 'italic', padding: '0 0.2em 0 0', margin: '0 -0.2em 0 0' }}>
            {WORDS.map((w, i) => (
              <Verb key={w} word={w} frame={frame} inAt={IN_AT[i]} outAt={i + 1 < SWITCHES.length ? SWITCHES[i + 1] : null} />
            ))}
          </div>
        </div>
        {/* Supporting footnote relaying with verb */} 
        {NOTES.map((n, i) => {
          const pIn = ramp(frame, IN_AT[i] + 6, 14, EASE.snappy);
          const pOut = i + 1 < SWITCHES.length ? ramp(frame, SWITCHES[i + 1], 7, EASE.exit) : 0;
          const op = pIn * (1 - pOut);
          if (op <= 0.002) return null;
          return (
            <div key={n} style={{
              position: 'absolute', left: WX + 6, top: BLOCK_TOP + LINE * 2 + 40, fontFamily: FONT.sans, fontSize: 32, fontWeight: 450,
              color: L.ink2, letterSpacing: '-0.01em', opacity: op, transform: `translateY(${((1 - pIn) * 14 - pOut * 10).toFixed(2)}px)`, whiteSpace: 'nowrap',
            }}>
              {n}
            </div>
          );
        })}
      </div>
    </div>
  );
};
