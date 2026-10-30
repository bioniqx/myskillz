import React from "react";
import { AbsoluteFill, Freeze, Sequence, useCurrentFrame } from "remotion";
import type { ProjectData } from "../types";
import { CARDS } from "../cards/registry";
import { MANIFEST } from '../cards/projectCards';
import { themedProps, themedBackground } from '../theme';

/** Time remapping: clip local frame -> card source frame (inOffset + f * speed).
 *  Cards are pure functions of frame; pass through without Freeze when unshifted. */
const TimeRemap: React.FC<{
  inOffset: number;
  speed: number;
  children: React.ReactNode;
}> = ({ inOffset, speed, children }) => {
  const frame = useCurrentFrame();
  if (speed === 1 && inOffset === 0) return <>{children}</>;
  return <Freeze frame={Math.max(0, inOffset + frame * speed)}>{children}</Freeze>;
};

export const MainComposition: React.FC<{ project: ProjectData }> = ({ project }) => {
  // tracks[0] in UI is topmost track -> rendered last (overlays on top)
  const ordered = [...project.tracks].reverse();
  return (
    <AbsoluteFill style={{ background: themedBackground(project, MANIFEST) ?? "#0e0e10" }}>
      {ordered.map(
        (track) =>
          !track.hidden &&
          track.clips.map((clip) => {
            const card = CARDS[clip.cardId];
            if (!card) return null;
            const Comp = card.component;
            const duration = Math.max(1, Math.round(clip.duration));
            const props: Record<string, unknown> = themedProps(MANIFEST, card, project.themeId, clip.props, project.themeColors);
      // Film component calculates fade-out from duration/dur: inject source duration
            if (card.durationProp)
              props[card.durationProp] = Math.max(1, Math.round(clip.inOffset + duration * clip.speed));
      // Audio card: trim/speed handled by internal <Audio trimBefore playbackRate>;
      // do not wrap in Freeze to allow native playback
            if (card.kind === "audio") {
              return (
                <Sequence key={clip.id} from={clip.start} durationInFrames={duration}>
                  <Comp {...props} inOffset={clip.inOffset} speed={clip.speed} />
                </Sequence>
              );
            }
            return (
              <Sequence key={clip.id} from={clip.start} durationInFrames={duration}>
                <AbsoluteFill
                  style={{
                    opacity: clip.opacity,
                    transform: `translate(${clip.x}px, ${clip.y}px) scale(${clip.scale})`,
                  }}
                >
                  {card.kind === "video" ? (
                    // Video cards: native playback channel with layer wrapping
                    <Comp {...props} inOffset={clip.inOffset} speed={clip.speed} />
                  ) : (
                    <TimeRemap inOffset={clip.inOffset} speed={clip.speed}>
                      <Comp {...props} />
                    </TimeRemap>
                  )}
                </AbsoluteFill>
              </Sequence>
            );
          }),
      )}
    </AbsoluteFill>
  );
};
