import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import type { CardDef } from "../types";
import { DigitRoll } from "./digit-roll";

// Title Card · Ink Press — parameterized version (from template/src/aifl/PaperTitleCard.tsx)
// Configurable: copy (*word* for emphasis), subtitle, digits, paper/ink/amber colors, font size, underline.
// Key rhythm FIXED: word-by-word 4f stagger / 9f entrance, underline 16-34f, tail 8f fade-out.

const SERIF = 'ui-serif, Georgia, "Times New Roman", serif';
const MONO = "ui-monospace, SFMono-Regular, Menlo, monospace";

/** Copy DSL: space-delimited words, `*word*` indicates amber italic emphasis */
export const parseWords = (text: string) =>
  text
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => {
      const m = w.match(/^\*(.+)\*$/);
      return m ? { text: m[1], accent: true } : { text: w, accent: false };
    });

interface Props {
  text?: string;
  sub?: string;
  subDigits?: string;
  bg?: string;
  ink?: string;
  accent?: string;
  fontSize?: number;
  underlineWidth?: number;
  duration?: number;
}

const TitleCard: React.FC<Props> = ({
  text = "All your team’s research, *one* place to go.",
  sub = "",
  subDigits = "",
  bg = "#f7f4ee",
  ink = "#1c1a17",
  accent = "#b5651d",
  fontSize = 116,
  underlineWidth = 220,
  duration = 55,
}) => {
  const frame = useCurrentFrame();
  const words = parseWords(text);
  const fadeOut = interpolate(frame, [duration - 8, duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const underline = interpolate(frame, [16, 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const subT = interpolate(frame, [10, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bg,
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeOut,
        backgroundImage: "radial-gradient(1100px 750px at 50% 42%, rgba(255,252,244,0.85), transparent 65%)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 1500 }}>
        <div
          style={{
            fontFamily: SERIF, fontSize, fontWeight: 600, lineHeight: 1.14,
            color: ink, letterSpacing: "-0.012em",
            display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: "0.26em",
          }}
        >
          {words.map((w, i) => {
            const delay = 4 + i * 4;
            const t = interpolate(frame, [delay, delay + 9], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.2, 0.75, 0.3, 1),
            });
            return (
              <span
                key={i}
                style={{
                  opacity: t,
                  transform: `scale(${1.28 - 0.28 * t})`,
                  filter: `blur(${(1 - t) * 7}px)`,
                  display: "inline-block",
                  fontStyle: w.accent ? "italic" : "normal",
                  color: w.accent ? accent : undefined,
                }}
              >
                {w.text}
              </span>
            );
          })}
        </div>
        <div
          style={{
            height: 6, width: underlineWidth, margin: "38px auto 0", borderRadius: 3,
            background: accent, transform: `scaleX(${underline})`,
          }}
        />
        {sub ? (
          <div style={{ fontFamily: MONO, fontSize: 26, letterSpacing: "0.12em", color: "rgba(28,26,23,0.62)", marginTop: 34, opacity: subT, textTransform: "uppercase", display: "flex", justifyContent: "center", alignItems: "baseline", gap: "0.5em" }}>
            {subDigits ? <DigitRoll value={subDigits} delay={12} fontSize={26} color={accent} /> : null}
            <span>{sub}</span>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const titleCardCard: CardDef = {
  id: "inkpress-title-card",
  name: "Title Card · Ink Press",
  category: "Workbench",
  durationInFrames: 55,
  accent: "#b5651d",
  durationProp: "duration",
  component: TitleCard as React.ComponentType<Record<string, unknown>>,
  summary: "Large serif type stamping in word-by-word with *word* amber italic emphasis and growing underline; fades out last 8 frames",
  schema: [
    { type: "textarea", key: "text", label: "Copy (*word* = emphasis)", default: "All your team’s research, *one* place to go." },
    { type: "text", key: "sub", label: "Subtitle (monospace)", default: "" },
    { type: "text", key: "subDigits", label: "Subtitle Rolling Digits", default: "" },
    { type: "color", key: "bg", label: "Paper Color", default: "#f7f4ee" },
    { type: "color", key: "ink", label: "Ink Color", default: "#1c1a17" },
    { type: "color", key: "accent", label: "Accent Color", default: "#b5651d" },
    { type: "slider", key: "fontSize", label: "Font Size", default: 116, min: 60, max: 160, step: 1, unit: "px" },
    { type: "slider", key: "underlineWidth", label: "Underline Width", default: 220, min: 0, max: 600, step: 10, unit: "px" },
  ],
};
