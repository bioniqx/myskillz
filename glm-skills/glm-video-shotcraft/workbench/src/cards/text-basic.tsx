import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { CardDef } from "./types";
import { FONT_STACK, lerp, power2Out, power3Out, power4Out, tw } from "./shared";

// text-basic · Basic text card — fully parameterized content, size, color, animation
const FPS = 30;

interface Props {
  content?: string;
  fontSize?: number;
  color?: string;
  bg?: string;
  transparentBg?: boolean;
  fontWeight?: string;
  letterSpacing?: number;
  align?: string;
  anim?: string;
  delay?: number;
  animDur?: number;
}

const TextBasic: React.FC<Props> = ({
  content = "Type your text here",
  fontSize = 64,
  color = "#1d1d1f",
  bg = "#ffffff",
  transparentBg = false,
  fontWeight = "700",
  letterSpacing = 0,
  align = "center",
  anim = "fade-up",
  delay = 0.3,
  animDur = 0.4,
}) => {
  const t = useCurrentFrame() / FPS;
  const lines = String(content).split("\n");

  let opacity = 1;
  let transform = "";
  let clipPath: string | undefined;
  if (anim === "fade-up") {
    const p = tw(t, delay, animDur, power3Out);
    opacity = p;
    transform = `translateY(${lerp(24, 0, p)}px)`;
  } else if (anim === "slam") {
    const p = tw(t, delay, animDur, power4Out);
    opacity = p;
    transform = `scale(${lerp(1.12, 1, p)})`;
  } else if (anim === "mask") {
    const p = tw(t, delay, animDur, power3Out);
    clipPath = `inset(0 ${lerp(100, 0, p)}% 0 0)`;
  } else if (anim === "typewriter") {
    const total = String(content).length || 1;
    const shown = Math.floor(tw(t, delay, animDur, (x) => x) * total);
    const remain = String(content).slice(0, shown);
    const tLines = remain.split("\n");
    return (
      <AbsoluteFill
        style={{
          background: transparentBg ? "transparent" : bg,
          display: "flex",
          alignItems: "center",
          justifyContent:
            align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center",
          padding: "0 72px",
          fontFamily: FONT_STACK,
        }}
      >
        <div
          style={{
            fontSize,
            fontWeight: Number(fontWeight),
            color,
            letterSpacing,
            lineHeight: 1.3,
            textAlign: align as React.CSSProperties["textAlign"],
            whiteSpace: "pre-wrap",
          }}
        >
          {tLines.join("\n")}
        </div>
      </AbsoluteFill>
    );
  } else if (anim === "fade") {
    opacity = tw(t, delay, animDur, power2Out);
  }

  return (
    <AbsoluteFill
      style={{
        background: transparentBg ? "transparent" : bg,
        display: "flex",
        alignItems: "center",
        justifyContent:
          align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center",
        padding: "0 72px",
        fontFamily: FONT_STACK,
      }}
    >
      <div
        style={{
          fontSize,
          fontWeight: Number(fontWeight),
          color,
          letterSpacing,
          lineHeight: 1.3,
          opacity,
          transform,
          clipPath,
          textAlign: align as React.CSSProperties["textAlign"],
          whiteSpace: "pre-wrap",
        }}
      >
        {lines.join("\n")}
      </div>
    </AbsoluteFill>
  );
};

export const textBasicCard: CardDef = {
  id: "text-basic",
  name: "Basic Text",
  category: "Workbench",
  durationInFrames: 120,
  accent: "#0a84ff",
  component: TextBasic as React.ComponentType<Record<string, unknown>>,
  schema: [
    { type: "textarea", key: "content", label: "Text Content", default: "Type your text here" },
    { type: "slider", key: "fontSize", label: "Font Size", default: 64, min: 16, max: 180, step: 1, unit: "px" },
    { type: "color", key: "color", label: "Text Color", default: "#1d1d1f" },
    {
      type: "select", key: "fontWeight", label: "Font Weight", default: "700",
      options: [
        { value: "400", label: "Regular 400" },
        { value: "600", label: "Semi-Bold 600" },
        { value: "700", label: "Bold 700" },
        { value: "900", label: "Black 900" },
      ],
    },
    { type: "slider", key: "letterSpacing", label: "Letter Spacing", default: 0, min: -4, max: 24, step: 0.5, unit: "px" },
    {
      type: "select", key: "align", label: "Alignment", default: "center",
      options: [
        { value: "left", label: "Left" },
        { value: "center", label: "Center" },
        { value: "right", label: "Right" },
      ],
    },
    {
      type: "select", key: "anim", label: "Entrance Animation", default: "fade-up",
      options: [
        { value: "fade-up", label: "Fade Up" },
        { value: "slam", label: "Slam" },
        { value: "mask", label: "Mask Reveal" },
        { value: "typewriter", label: "Typewriter" },
        { value: "fade", label: "Fade" },
        { value: "none", label: "None" },
      ],
    },
    { type: "slider", key: "delay", label: "Entrance Delay", default: 0.3, min: 0, max: 3, step: 0.05, unit: "s" },
    { type: "slider", key: "animDur", label: "Animation Duration", default: 0.4, min: 0.1, max: 2, step: 0.05, unit: "s" },
    { type: "color", key: "bg", label: "Background Color", default: "#ffffff" },
    { type: "boolean", key: "transparentBg", label: "Transparent Background", default: false },
  ],
};
