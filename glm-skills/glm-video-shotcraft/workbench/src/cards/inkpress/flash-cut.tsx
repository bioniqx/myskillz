import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import type { CardDef } from "../types";

// Warm white flash cut — parameterized version (from template/src/aifl/FlashCut.tsx)
// Warm white bloom bridging 5f on each side of hard cut: peak at 40% (FIXED); configurable opacity and warm color.

interface Props {
  peak?: number;
  color?: string;
  duration?: number;
}

const FlashCut: React.FC<Props> = ({ peak = 0.85, color = "#fff8eb", duration = 10 }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [0, duration * 0.4, duration], [0, peak, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity: o,
        background: `radial-gradient(ellipse at 50% 45%, ${color}, ${color}8c 55%, transparent 80%)`,
      }}
    />
  );
};

export const flashCutCard: CardDef = {
  id: "inkpress-flash-cut",
  name: "Warm White Flash Cut",
  category: "Workbench",
  durationInFrames: 10,
  accent: "#f7c948",
  durationProp: "duration",
  component: FlashCut as React.ComponentType<Record<string, unknown>>,
  summary: "Placed 5 frames before hard cut, bridging 5 frames each side; covers seams without excess glow",
  schema: [
    { type: "slider", key: "peak", label: "Peak Opacity", default: 0.85, min: 0.2, max: 1, step: 0.05 },
    { type: "color", key: "color", label: "Warm White", default: "#fff8eb" },
  ],
};
