// research-card-stack-scroll — Research Stack paper card stacked flow (motion-lab finalized design ported to native Remotion)
// Dark paper cards continuously fly in and stack at the center along a slightly down-right axis:
// entrance is a 6-frame brisk spring with translateY(-40) + scale 0.94→1, landing with a 1-frame squash;
// only the top card fully renders title + author + abstract sharply;
// cards underneath increase blur/dimming by depth, revealing only the top title bar;
// a light gray horizontal grid in the background moves synchronously as a speed reference.
// Design coordinates: 480×270 (proportionally scaled by DesignStage); parameters calibrated to this system.
import React from 'react';
import { DesignStage, E, lerp, rand, seg, useT } from '../../_fixtures/Motion';

export const RESEARCH_CARD_STACK_SCROLL_DURATION = 144; // 4800ms @30fps

const ORANGE = '#FF6A1F';
const ORANGE_SOFT = '#FF8A44';
const INK = '#1A1A1A';
const FONT = '-apple-system,system-ui,"SF Pro Text","PingFang SC",sans-serif';

// Original setup's stage.clientWidth/clientHeight branch — original render stage is constantly 480×270
const W = 480;
const H = 270;
const F = 144; // Total recipe frames (f = t·F)
const PER = 12; // One card enters every 12 frames
const GAP = 30; // Downward spacing between cards after stacking
const XOFF = 9; // Rightward offset during flow

// Logical canvas 420×250 → proportional scaling to actual stage
const LW = 420;
const LH = 250;
const S = Math.min(W / LW, H / LH);

const TITLES = [
  'Sparse Attention Mechanisms for Long-Context Reasoning',
  'Retrieval Drift in Multi-Hop Agent Pipelines',
  'Latent Caching Reduces Tool-Call Latency by 41%',
  'On the Calibration of Preference Reward Models',
  'Grid-Aligned Motion Priors for UI Animation',
  'Cheap Verifiers Beat Expensive Samplers',
  'Structured Decoding Without Grammar Loss',
  'Depth-Ordered Compositing for Live Interfaces',
  'Token-Budget Routing in Agent Fleets',
  'Contrastive Layouts for Document Understanding',
  'Fast Approximate Re-Ranking at Query Time',
  'Signal Propagation in Deep Residual Agents',
  'A Note on Deterministic Replay of Motion',
];
const CW = 296;
const CH = 96;

export const ResearchCardStackScroll: React.FC = () => {
  const t = useT();
  const f = t * F;
  const focus = Math.floor(f / PER); // Only the top card renders body content
  return (
    <DesignStage bg="#FAFAFA">
      {/* Background horizontal grid: moves downward in sync with the flow as a speed reference */}
      <div
        style={{
          position: 'absolute',
          inset: -40,
          backgroundImage: 'linear-gradient(rgba(0,0,0,.055) 1px,transparent 1px)',
          backgroundSize: '100% 24px',
          transform: `translateY(${((f / PER) * GAP * S) % 24}px)`,
        }}
      />
      {/* Logical canvas track: center anchor + proportional scaling */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          width: 0,
          height: 0,
          transformOrigin: '0 0',
          transform: `scale(${S})`,
        }}
      >
        {TITLES.map((tt, i) => {
          const e = f - i * PER; // Local frame for this card
          const p = seg(Math.max(0, Math.min(1, (e + 6) / 6)), 0, 1, E.outCubic); // 6-frame entrance
          const drift = (Math.max(0, e) / PER) * GAP; // Downward drift with the flow after stacking
          const squash = e >= 0 && e < 1.6 ? 0.97 : 1; // 1-frame squash on landing
          const y = lerp(p, -40, 0) + drift;
          const x = (Math.max(0, e) / PER) * XOFF;
          const depth = Math.min(1, drift / (GAP * 3)); // Increasing blur + dimming with depth
          const opacity =
            e < -6 ? 0 : Math.min(1, (e + 6) / 2) * (1 - Math.max(0, (drift - GAP * 3.2) / (GAP * 1.6)));
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: -CW / 2,
                top: -CH / 2 - 14,
                width: CW,
                height: CH,
                background: INK,
                borderRadius: 11,
                overflow: 'hidden',
                fontFamily: FONT,
                zIndex: i,
                opacity,
                boxShadow: '0 14px 34px rgba(0,0,0,.22)',
                border: '1px solid #2A2A2A',
                boxSizing: 'border-box',
                transform: `translate(${x}px,${y}px) scale(${lerp(p, 0.94, 1)},${lerp(p, 0.94, 1) * squash})`,
                filter: `blur(${(depth * 4).toFixed(2)}px) brightness(${(1 - depth * 0.25).toFixed(3)})`,
              }}
            >
              {/* Left accent bar: orange every 4 cards */}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  width: 3,
                  height: '100%',
                  background: i % 4 === 1 ? ORANGE : '#2E2E2E',
                }}
              />
              {/* Title bar: rendered on all cards */}
              <div
                style={{
                  position: 'absolute',
                  left: 14,
                  top: 11,
                  width: 264,
                  font: `650 9.5px/1.35 ${FONT}`,
                  color: '#F0F0F0',
                }}
              >
                {tt}
              </div>
              {/* Body content (author + abstract skeleton lines): visible only on focused card */}
              <div style={{ position: 'absolute', left: 14, top: 40, width: 266, opacity: i === focus ? 1 : 0 }}>
                <div style={{ font: `500 8px/1 ${FONT}`, color: ORANGE_SOFT, letterSpacing: '.3px' }}>
                  {`A. Author, B. Writer, C. Reader · preprint:24${10 + i}.0${i % 9}${i % 7}`}
                </div>
                {[0, 1, 2, 3].map((k) => (
                  <div
                    key={k}
                    style={{
                      marginTop: k ? 5 : 9,
                      width: `${100 - k * 11 - rand(i * 5 + k) * 12}%`,
                      height: 4,
                      borderRadius: 2,
                      background: '#3A3A3A',
                    }}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </DesignStage>
  );
};
