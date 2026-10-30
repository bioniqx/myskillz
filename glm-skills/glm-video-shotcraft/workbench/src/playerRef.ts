import { createRef } from "react";
import type { PlayerRef } from "@remotion/player";

/** Globally shared Player handle for timeline seek and shortcut playback controls */
export const playerRef = createRef<PlayerRef>();

export const seekTo = (frame: number) => {
  playerRef.current?.seekTo(Math.max(0, Math.round(frame)));
};

export const togglePlay = () => {
  const p = playerRef.current;
  if (!p) return;
  if (p.isPlaying()) p.pause();
  else p.play();
};
