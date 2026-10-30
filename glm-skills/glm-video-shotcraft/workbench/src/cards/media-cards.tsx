import React from "react";
import { AbsoluteFill, Audio, Img, OffthreadVideo, staticFile } from "remotion";
import type { CardDef } from "./types";

// —— Media cards: video / image / audio files directly on tracks ——
// kind:"video"/"audio": trim=trimBefore, speed=playbackRate

const VideoClip: React.FC<{
  file?: string;
  fit?: string;
  muted?: boolean;
  volume?: number;
  inOffset?: number;
  speed?: number;
}> = ({ file = "", fit = "contain", muted = false, volume = 1, inOffset = 0, speed = 1 }) => {
  if (!file) return null;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <OffthreadVideo
        src={staticFile(file)}
        trimBefore={Math.round(inOffset)}
        playbackRate={speed}
        muted={muted}
        volume={volume}
        style={{ width: "100%", height: "100%", objectFit: fit as React.CSSProperties["objectFit"] }}
      />
    </AbsoluteFill>
  );
};

export const videoClipCard: CardDef = {
  id: "video-clip",
  name: "Video Footage",
  category: "Media",
  kind: "video",
  timing: "realtime",
  durationInFrames: 150,
  accent: "#30d158",
  component: VideoClip as React.ComponentType<Record<string, unknown>>,
  schema: [
    { type: "text", key: "file", label: "File (under public/)", default: "" },
    {
      type: "select", key: "fit", label: "Fit", default: "contain",
      options: [
        { value: "contain", label: "Contain" },
        { value: "cover", label: "Cover" },
      ],
    },
    { type: "boolean", key: "muted", label: "Muted", default: false },
    { type: "slider", key: "volume", label: "Volume", default: 1, min: 0, max: 1, step: 0.01 },
  ],
};

const ImageClip: React.FC<{ file?: string; fit?: string }> = ({ file = "", fit = "contain" }) => {
  if (!file) return null;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Img
        src={staticFile(file)}
        style={{ width: "100%", height: "100%", objectFit: fit as React.CSSProperties["objectFit"] }}
      />
    </AbsoluteFill>
  );
};

export const imageClipCard: CardDef = {
  id: "image-clip",
  name: "Image Footage",
  category: "Media",
  timing: "realtime",
  durationInFrames: 90,
  accent: "#64d2ff",
  component: ImageClip as React.ComponentType<Record<string, unknown>>,
  schema: [
    { type: "text", key: "file", label: "File (under public/)", default: "" },
    {
      type: "select", key: "fit", label: "Fit", default: "contain",
      options: [
        { value: "contain", label: "Contain" },
        { value: "cover", label: "Cover" },
      ],
    },
  ],
};

/** Audio card (BGM / SFX): trim=trimBefore, speed=playbackRate */
const AudioClip: React.FC<{ file?: string; volume?: number; inOffset?: number; speed?: number }> =
  ({ file = "", volume = 1, inOffset = 0, speed = 1 }) => {
    if (!file) return null;
    return (
      <Audio
        src={staticFile(file)}
        volume={volume}
        trimBefore={Math.round(inOffset)}
        playbackRate={speed}
      />
    );
  };

export const audioClipCard: CardDef = {
  id: "audio-clip",
  name: "Audio",
  category: "Audio",
  kind: "audio",
  timing: "realtime",
  durationInFrames: 90,
  accent: "#ff9f0a",
  component: AudioClip as React.ComponentType<Record<string, unknown>>,
  schema: [
    { type: "text", key: "file", label: "File (under public/)", default: "" },
    { type: "slider", key: "volume", label: "Volume", default: 1, min: 0, max: 1, step: 0.01 },
  ],
};
