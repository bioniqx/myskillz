// Riso beat pump (riso-beat-pump) — combination rhythm of beat-punch-in (accent punch) x riso-misregistration-hit
// (misregistration). Beat frames [30,54,78,102] (every 24f per beat); on each hit:
// (1) Full screen scale snaps instantly to 1.08 in 1 frame (no fade-in), decays exponentially exp(-t/3) to 1 within 14f;
// (2) Title splits into G.mid/G.ink dual-color plates with multiply misregistration, initial offset increments each beat 4/7/11/16px
//     (plates move oppositely -> total separation 8/14/22/32px), converges over 12f damped cosine oscillation into registration;
// (3) Corresponding bottom beat indicator dots flash dark and remain active. Structure: 0–29f hold; 30–115f four beats; 116–139f true hold.
import React from 'react';
import { useCurrentFrame } from 'remotion';
import { G, Card, TitleBlock } from '../../_fixtures/Fixtures';

const HITS = [30, 54, 78, 102]; // Beat hit frames
const AMP = [4, 7, 11, 16]; // Per-plate initial offset per beat (px), escalates each hit
const PUMP_WIN = 14; // Scale pump window: strictly settles to 1 after 14f (ensures true hold at end)
const SPLIT_WIN = 12; // Split window: strictly settles to 0 after 12f (residual <0.4px, snaps to registration)

// Monochromatic print plate matching TitleBlock glyphs (misregistration requires tintable copies)
const Plate: React.FC<{ color: string; dx: number; dy: number }> = ({ color, dx, dy }) => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transform: `translate(${dx}px, ${dy}px)`,
      mixBlendMode: 'multiply',
    }}
  >
    <div
      style={{
        fontFamily: 'Helvetica, Arial, sans-serif',
        fontWeight: 800,
        fontSize: 160,
        color,
        letterSpacing: -1,
        whiteSpace: 'nowrap',
      }}
    >
      ON THE BEAT
    </div>
  </div>
);

export const RisoBeatPump: React.FC = () => {
  const frame = useCurrentFrame();

  // Find most recent hit beat (24f spacing > 14f window, exactly one beat active at any time)
  let beatIdx = -1;
  for (let i = 0; i < HITS.length; i++) {
    if (frame >= HITS[i]) beatIdx = i;
  }
  const t = beatIdx >= 0 ? frame - HITS[beatIdx] : Infinity;

  // (1) Full screen pump: snaps to 1.08 on hit frame (full value at t=0, no fade-in), exponential decay back to 1
  const pump = t < PUMP_WIN ? 1 + 0.08 * Math.exp(-t / 3) : 1;

  // (2) Title misregistration: damped cosine oscillation (6f period, two wobbles), strictly 0 outside window = in registration
  const split = t < SPLIT_WIN;
  const m = split ? Math.cos((2 * Math.PI * t) / 6) * Math.exp(-t / 3) : 0;
  const dx = beatIdx >= 0 ? AMP[beatIdx] * m : 0;
  const dy = dx * 0.45; // Minor y offset to mimic printing plate misalignment

  return (
    <div
      style={{
        width: 1920,
        height: 1080,
        background: G.bg,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Full-screen container: scale pump applies to all content */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: `scale(${pump})`,
          transformOrigin: 'center center',
        }}
      >
        {/* Title zone: mutual exclusion between normal / dual-plate misregistration */}
        <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 660 }}>
          {!split && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <TitleBlock text="ON THE BEAT" size={160} />
            </div>
          )}
          {split && (
            <>
              <Plate color={G.mid} dx={-dx} dy={dy} />
              <Plate color={G.ink} dx={dx} dy={-dy} />
            </>
          )}
        </div>

        {/* Bottom row of 3 small cards */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 660,
            display: 'flex',
            justifyContent: 'center',
            gap: 44,
          }}
        >
          <Card w={330} h={200} seed={2} />
          <Card w={330} h={200} seed={5} />
          <Card w={330} h={200} seed={8} />
        </div>

        {/* Beat markers: flashes dark on hit (8f scale pulse 1.8 -> 1) and stays dark */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: 950,
            display: 'flex',
            justifyContent: 'center',
            gap: 60,
          }}
        >
          {HITS.map((hit, i) => {
            const dt = frame - hit;
            const on = dt >= 0;
            const s = on && dt < 8 ? 1 + 0.8 * (1 - dt / 8) : 1;
            return (
              <div
                key={i}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 11,
                  background: on ? G.ink : G.bar,
                  transform: `scale(${s})`,
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
