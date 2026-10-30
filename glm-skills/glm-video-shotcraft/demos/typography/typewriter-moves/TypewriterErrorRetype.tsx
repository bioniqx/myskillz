// typewriter-error-retype | Typewriter error deletion and retype
// Light background, centered large text (eyebrow header Introducing video-shotcraft): from f2 types "just a slideshow" (16 chars) at 2f/char -> f32-48 pauses
// 16f (cursor blinks twice = hesitation) -> from f48 deletes "a slideshow" (11 chars) via backspace at 1.5f/char (characters vanish instantly)
// -> from f68 decisively types "your cinematic crew" (19 chars) at 1.5f/char (completes at f95) -> cursor blinks two cycles (10f/cycle) then extinguishes permanently at f110.
// Three tempo gears: type 2f / delete 1.5f / retype 1.5f with no pause. Concurrently with completion (f96-110, parallel with the two final cursor blinks), an accent marker highlight
// sweeps left-to-right across the lower half of "cinematic crew" to punctuate the manifesto; fully static after f110, total 160f -> true hold of 50f at conclusion.
// Monospace aesthetic: fixed-width span per character (100px mono font, 60px slot), no letter-spacing animation. Completely frame-deterministic.
// Look: soft light background + grain, near-black primary ink, cursor is a 6px rounded accent bar.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { G } from '../../_fixtures/Fixtures';
import { Backdrop, EASE, FONT, ramp } from '../../_fixtures/Polish';
import { BRAND, ShotcraftMark } from '../../_fixtures/Brand';

export const TYPEWRITER_ERROR_RETYPE_DURATION = 160;

const TEXT1 = 'just a slideshow'; // 16 chars
const KEEP = 5; // Retain "just "
const DEL = TEXT1.length - KEEP; // 11 chars to delete
const TEXT2 = 'your cinematic crew'; // 19 chars

const T1 = 2; // Start of first typing pass, 2f/char
const PAUSE_START = T1 + (TEXT1.length - 1) * 2; // Completed at f32
const DS = PAUSE_START + 16; // Start deletion at f48, 1.5f/char
const RS = 68; // Retype start, 1.5f/char (3.5f brief pause after deletion completes at f64.5)
const TYPE2_END = RS + (TEXT2.length - 1) * 1.5; // Completed at f95
const CURSOR_OFF = 115; // Extinguishes after two 10f blink cycles (last visual change at f110)

const SIZE = 100; // Font size
const CHAR_W = 60; // Character width for 100px monospace font (0.6em)
const LEFT = (1920 - 24 * CHAR_W) / 2; // Centers the final 24-char sentence overall; left edge anchored during typing to prevent lateral shift
const HL_START = 96; // Marker highlight start: sweeps immediately upon completion, concurrent with final two blinks, finishes before f110
const HL_DUR = 14;
const HL_FROM = 10; // Start character index of "cinematic crew" (index 10 in final phrase "just your cinematic crew")
const HL_LEN = 14;

// Cursor visibility: solid while typing/deleting; two blinks with 8f period during pause; two blinks with 10f period after completion; extinguished thereafter
const cursorOn = (f: number): boolean => {
  if (f >= CURSOR_OFF) return false;
  if (f >= TYPE2_END) {
    // From f95: on[95,100) off[100,105) on[105,110) off[110,115)
    return Math.floor((f - TYPE2_END) / 5) % 2 === 0;
  }
  if (f >= DS) return true; // Deletion + retype: solid (decisive)
  if (f >= PAUSE_START) {
    // Hesitation segment f32-48: on[32,36) off[36,40) on[40,44) off[44,48)
    return Math.floor((f - PAUSE_START) / 4) % 2 === 0;
  }
  return true; // First pass typing: solid
};

export const TypewriterErrorRetype: React.FC = () => {
  const f = useCurrentFrame();

  // Number of characters typed in first pass
  const n1 = f < T1 ? 0 : Math.min(TEXT1.length, Math.floor((f - T1) / 2) + 1);
  // Number of characters deleted (from tail)
  const removed = f < DS ? 0 : Math.min(DEL, Math.floor((f - DS) / 1.5) + 1);
  // Number of characters typed in second pass
  const n2 = f < RS ? 0 : Math.min(TEXT2.length, Math.floor((f - RS) / 1.5) + 1);

  const shown =
    TEXT1.slice(0, Math.max(KEEP, n1 - removed)).slice(0, n1) +
    TEXT2.slice(0, n2);

  const chars = shown.split('');

  const hl = ramp(f, HL_START, HL_DUR, EASE.snappy);

  return (
    <div style={{ width: 1920, height: 1080, position: 'relative', overflow: 'hidden' }}>
      <Backdrop tone="light" light={{ x: 0.42, y: 0.3 }} accent="#5b63d3" />
      {/* Marker highlight: spans lower half of manifesto words only, left to right */}
      {hl > 0 && (
        <div style={{
          position: 'absolute', left: LEFT + HL_FROM * CHAR_W - 10, top: 540 + SIZE * 0.06,
          width: (HL_LEN * CHAR_W + 20) * hl, height: SIZE * 0.36, borderRadius: 6,
          background: 'linear-gradient(90deg, rgba(91,99,211,0.26) 0%, rgba(91,99,211,0.20) 100%)',
        }} />
      )}
      {/* Eyebrow: left-aligned with typing baseline, fades in over opening 10f, contextualizes product intro — video-shotcraft mark + lowercase brand name */}
      <div style={{
        position: 'absolute', left: LEFT + 6, top: 540 - SIZE * 0.55 - 70,
        display: 'flex', alignItems: 'center', gap: 12,
        fontFamily: FONT.sans, fontSize: 34, fontWeight: 500, letterSpacing: '0.01em', color: G.ink3,
        opacity: ramp(f, 0, 10, EASE.out),
      }}>
        <ShotcraftMark size={40} tone="light" style={{ marginTop: -2 }} />
        <span>Introducing <span style={{ fontFamily: BRAND.font, fontWeight: 700, letterSpacing: '0.03em', color: G.ink1 }}>{BRAND.name}</span></span>
      </div>
      {/* Left-edge anchor: no horizontal jumping during typing (authentic typewriter feel); row centered vertically at 540 */}
      <div
        style={{
          position: 'absolute',
          left: LEFT,
          top: 540 - (SIZE * 1.1) / 2,
          display: 'flex',
          alignItems: 'center',
          height: SIZE * 1.1,
        }}
      >
        {chars.map((c, i) => (
          <span
            key={i}
            style={{
              display: 'inline-block',
              width: CHAR_W,
              textAlign: 'center',
              fontFamily: FONT.mono,
              fontSize: SIZE,
              fontWeight: 600,
              color: G.ink1,
              lineHeight: 1.1,
            }}
          >
            {c === ' ' ? '\u00a0' : c}
          </span>
        ))}
        {/* Cursor: accent color vertical bar, conditionally mounted rather than opacity 0 */}
        {cursorOn(f) && (
          <span
            style={{
              display: 'inline-block',
              width: 6,
              height: SIZE * 0.98,
              marginLeft: 4,
              borderRadius: 3,
              background: G.accent,
              boxShadow: '0 0 12px rgba(91,99,211,0.35)',
            }}
          />
        )}
      </div>
    </div>
  );
};
