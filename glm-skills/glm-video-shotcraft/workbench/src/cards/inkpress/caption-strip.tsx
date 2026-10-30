import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import type { CardDef } from "../types";

// Caption Strip · Ink Press — parameterized version (from template/src/aifl/Caption.tsx)
// Monospace text + amber square pip, 8f float-in, tail 8f fade-out (FIXED). Configurable text / bottom / size / color.

const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

interface Props {
  text?: string;
  bottom?: number;
  fontSize?: number;
  color?: string;
  accent?: string;
  uppercase?: boolean;
  duration?: number;
}

const CaptionStrip: React.FC<Props> = ({
  text = "SEARCH · FILTER · OPEN",
  bottom = 72,
  fontSize = 22,
  color = "#615c54",
  accent = "#b5651d",
  uppercase = true,
  duration = 60,
}) => {
  const frame = useCurrentFrame();
  const inT = interpolate(frame, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const outT = interpolate(frame, [duration - 8, duration], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom,
          display: "flex",
          justifyContent: "center",
          alignItems: "baseline",
          gap: 14,
          fontFamily: MONO,
          fontSize,
          letterSpacing: "0.14em",
          textTransform: uppercase ? "uppercase" : "none",
          color,
          opacity: inT * outT,
          transform: `translateY(${(1 - inT) * 8}px)`,
        }}
      >
        <span style={{ width: 6, height: 6, background: accent, display: "inline-block" }} />
        <span>{text}</span>
      </div>
    </AbsoluteFill>
  );
};

export const captionStripCard: CardDef = {
  id: "inkpress-caption",
  name: "Caption Strip",
  category: "Workbench",
  durationInFrames: 60,
  accent: "#34c759",
  durationProp: "duration",
  component: CaptionStrip as React.ComponentType<Record<string, unknown>>,
  summary: "Bottom full-width monospace caption strip guided by amber square; transparent background",
  schema: [
    { type: "text", key: "text", label: "Text", default: "SEARCH · FILTER · OPEN" },
    { type: "slider", key: "bottom", label: "Bottom Offset", default: 72, min: 20, max: 400, step: 2, unit: "px" },
    { type: "slider", key: "fontSize", label: "Font Size", default: 22, min: 14, max: 48, step: 1, unit: "px" },
    { type: "color", key: "color", label: "Text Color", default: "#615c54" },
    { type: "color", key: "accent", label: "Square Color", default: "#b5651d" },
    { type: "boolean", key: "uppercase", label: "All Caps", default: true },
  ],
};
