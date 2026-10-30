/** Project data model: Project -> Track -> Clip. All timing in timeline frames (default 30fps). */

export interface ClipData {
  id: string;
  cardId: string;
  /** Timeline start frame */
  start: number;
  /** Timeline duration (frames) — can be shorter or longer than card original duration */
  duration: number;
  /** In-point: frame offset in card source footage (source frames) */
  inOffset: number;
  /** Playback speed multiplier: source advances speed frames per timeline frame */
  speed: number;
  /** Layer opacity 0-1 */
  opacity: number;
  /** Layer overall scale */
  scale: number;
  /** Layer translation (px, composition space) */
  x: number;
  y: number;
  /** Card specific property overrides (default values from card schema) */
  props: Record<string, unknown>;
  /** Custom track label displayed on timeline (defaults to card name) */
  label?: string;
}

export interface TrackData {
  id: string;
  name: string;
  hidden?: boolean;
  clips: ClipData[];
}

export interface ProjectData {
  /** Visual preset; absent means the manifest's default, preserving older JSON. */
  themeId?: string;
  themeColors?: Record<string, string>;
  name: string;
  fps: number;
  width: number;
  height: number;
  /** Stage background color (AbsoluteFill background in film project; default near-black) */
  background?: string;
  /** Imported from which manifest (name + total) — used by ?import=project to detect changes */
  source?: string;
  tracks: TrackData[];
}

let seq = 0;
export const uid = (prefix: string) =>
  `${prefix}_${Date.now().toString(36)}${(seq++).toString(36)}`;

/** Exact content end frame (latest clip end; used for film export without padding) */
export const projectEndFrame = (project: ProjectData): number => {
  let end = 0;
  for (const t of project.tracks)
    for (const c of t.clips) end = Math.max(end, c.start + c.duration);
  return end;
};

/** Total project duration (frames): latest clip end + 1s padding, minimum 5s */
export const projectDuration = (project: ProjectData): number =>
  Math.max(5 * project.fps, projectEndFrame(project) + project.fps);
