import type { ClipData, ProjectData, TrackData } from "./types";
import { uid } from "./types";
import type { ManifestAudio, WorkbenchManifest } from "./cards/manifest";
import { manifestKey } from "./cards/manifest";
import { MANIFEST, cardIdOfUnit, unitsOf } from "./cards/projectCards";
import { inheritedProps } from './theme';
import { t } from "./i18n";

const baseClip = (): Omit<ClipData, "id" | "cardId" | "start" | "duration"> => ({
  inOffset: 0, speed: 1, opacity: 1, scale: 1, x: 0, y: 0, props: {},
});

/** SFX usage count (the xN shown in the asset library project SFX list) */
export const sfxUsage = (m: WorkbenchManifest | null): Map<string, number> => {
  const out = new Map<string, number>();
  for (const s of m?.sfx ?? []) out.set(s.src, (out.get(s.src) ?? 0) + 1);
  return out;
};

const shortName = (src: string) => src.split("/").pop()!.replace(/\.[^.]+$/, "");

/** Audio cue -> clip: greedy bin-packing into non-overlapping tracks */
const packAudio = (cues: ManifestAudio[], trackName: string, defaultDuration: number, total: number): TrackData[] => {
  const lanes: { end: number; clips: ClipData[] }[] = [];
  for (const c of [...cues].sort((a, b) => a.from - b.from)) {
    const start = Math.max(0, Math.round(c.from));
    // Any Sequence extending past composition end is clipped in original film; clamped to total here as well
    const duration = Math.max(2, Math.min(Math.round(c.duration ?? defaultDuration), total - start));
    let lane = lanes.find((l) => l.end <= start);
    if (!lane) {
      lane = { end: 0, clips: [] };
      lanes.push(lane);
    }
    lane.clips.push({
      ...baseClip(),
      id: uid("clip"),
      cardId: "audio-clip",
      start,
      duration,
      props: { file: c.src, volume: c.volume },
      label: c.label ?? shortName(c.src),
    });
    lane.end = start + duration;
  }
  return lanes.map((lane, i) => ({
    id: uid("track"),
    name: lanes.length > 1 ? `${trackName} ${i + 1}` : trackName,
    clips: lane.clips,
  }));
};

/** Decomposes film by manifest into units: captions / transitions / overlays / shots / music / SFX.
 *  Each unit start/duration strictly matches <Sequence> in Main.tsx frame-for-frame. */
export const buildProjectFromManifest = (m: WorkbenchManifest = MANIFEST!): ProjectData => {
  const unitTrack = (kind: "shot" | "transition" | "caption" | "overlay", name: string): TrackData | null => {
    const units = unitsOf(m, kind);
    if (!units.length) return null;
    return {
      id: uid("track"),
      name,
      clips: units.map((u) => ({
        ...baseClip(),
        id: uid("clip"),
        cardId: cardIdOfUnit(u),
        start: Math.max(0, Math.round(u.from)),
        duration: Math.max(2, Math.min(Math.round(u.duration), m.total - Math.max(0, Math.round(u.from)))),
        props: inheritedProps(m, u.themeKey, u.props),
        label: u.label ?? u.id,
      })),
    };
  };

  const order = m.order ?? ["transitions", "captions", "overlays"];
  const NAMES = { transitions: t("track.transitions"), captions: t("track.captions"), overlays: t("track.overlays") } as const;
  const upper = order
    .map((k) => unitTrack(k.slice(0, -1) as "transition" | "caption" | "overlay", NAMES[k]))
    .filter((t): t is TrackData => !!t);

  const tracks: TrackData[] = [
    // tracks[0] is top layer matching original film z-index: transitions > captions > overlays > shots
    ...upper,
    unitTrack("shot", t("track.shots"))!,
    ...(m.bgm?.length ? packAudio(m.bgm, t("track.music"), m.total, m.total) : []),
    ...(m.sfx?.length ? packAudio(m.sfx, t("track.sfx"), 90, m.total) : []),
  ];

  return {
    ...(m.themes ? {themeId: m.defaultTheme ?? m.themes[0]?.id} : {}),
    name: m.name,
    fps: m.fps,
    width: m.width,
    height: m.height,
    background: m.background,
    source: manifestKey(m),
    tracks,
  };
};
