import type React from "react";
import type { PropField } from "./types";

/** Film project manifest — exported in `src/workbench.ts` as `export const WORKBENCH: WorkbenchManifest`.
 *  Decomposes film into multitrack clips (shots / transitions / captions / overlays / SFX / music).
 *  All timing in absolute frames matching Main.tsx <Sequence from durationInFrames>. */

export type ManifestUnit = {
  /** Key into a theme's unitDefaults; omitted for components without theme support. */
  themeKey?: string;
  /** Unique id, becomes part of clip label on import */
  id: string;
  /** Display name on timeline (default id) */
  label?: string;
  /** Absolute start frame */
  from: number;
  /** Duration in frames */
  duration: number;
  component: React.ComponentType<Record<string, unknown>>;
  /** Actual props passed in film (= initial clip properties) */
  props?: Record<string, unknown>;
  /** Tunable properties; empty defaults to timing/speed/layer edits only */
  schema?: PropField[];
  /** Prop name to inject source duration into (e.g. "duration" / "dur") */
  durationProp?: string;
  /** Shared cardId for units using same card definition; defaults to component reference */
  cardId?: string;
  /** Card name in asset library */
  cardName?: string;
  accent?: string;
};

export type ManifestAudio = {
  from: number;
  /** Duration in frames (default 90) */
  duration?: number;
  /** Relative path under public/, e.g. "audio/whoosh-big.mp3" */
  src: string;
  volume: number;
  label?: string;
};

export type WorkbenchManifest = {
  /** Optional visual presets. Existing manifests require no changes. */
  themes?: ManifestTheme[];
  defaultTheme?: string;
  /** Prop injected into themed components in both preview and export. */
  themeProp?: string;
  paletteProp?: string;
  name: string;
  fps: number;
  width: number;
  height: number;
  /** Total film duration in frames */
  total: number;
  /** Stage background color */
  background?: string;
  /** Optional version string; defaults to manifest content hash
   *  (schedule / label / props / grouping / audio cues) */
  revision?: string;
  shots: ManifestUnit[];
  /** Transition layers (flashes, light leaks...) */
  transitions?: ManifestUnit[];
  /** Captions / dialogue strips */
  captions?: ManifestUnit[];
  /** Constant film overlays (grid, vignette, watermark...) */
  overlays?: ManifestUnit[];
  sfx?: ManifestAudio[];
  bgm?: ManifestAudio[];
  /** Layer z-order (top to bottom); default: transitions > captions > overlays */
  order?: ("transitions" | "captions" | "overlays")[];
  /** Original film composition (full Main) — registered as ProjOriginal in Studio */
  original?: React.ComponentType<Record<string, unknown>>;
};

export type ManifestTheme = {
  palette?: Record<string, string>;
  id: string;
  /** Recommended format: "Title · English" */
  label: string;
  background?: string;
  unitDefaults?: Record<string, Record<string, unknown>>;
};

export const UNIT_KINDS = ["shot", "transition", "caption", "overlay"] as const;
export type UnitKind = (typeof UNIT_KINDS)[number];

export const unitsOf = (m: WorkbenchManifest, kind: UnitKind): ManifestUnit[] =>
  kind === "shot" ? m.shots : (m[`${kind}s`] ?? []);

/** Unit -> cardId grouping: explicit cardId takes precedence; otherwise groups by component reference */
export const groupUnits = (m: WorkbenchManifest): Map<ManifestUnit, string> => {
  const out = new Map<ManifestUnit, string>();
  for (const kind of UNIT_KINDS) {
    const groups = new Map<unknown, ManifestUnit[]>();
    for (const u of unitsOf(m, kind)) {
      const k = u.cardId ?? u.component;
      const g = groups.get(k);
      if (g) g.push(u);
      else groups.set(k, [u]);
    }
    // Suffix with ~2/~3 if cardId collisions occur
    // and warn in console to update id
    const used = new Set<string>();
    for (const units of groups.values()) {
      const base = `proj:${kind}:${units[0].cardId ?? units[0].id}`;
      let id = base;
      for (let n = 2; used.has(id); n++) id = `${base}~${n}`;
      if (id !== base)
        console.warn(`[workbench] Manifest card id collision: ${base} already used; using ${id} instead — consider giving units distinct ids or setting explicit cardId`);
      used.add(id);
      for (const u of units) out.set(u, id);
    }
  }
  return out;
};

/** FNV-1a 32-bit hash outputting 8-char hex string */
const fnv1a = (s: string) => {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
};

/** Normalized string of manifest serializable fields for version hashing */
const canonical = (m: WorkbenchManifest): string => {
  const cardOf = groupUnits(m);
  const unit = (u: ManifestUnit) =>
    [
      cardOf.get(u) ?? "", u.id, u.label ?? "", u.from, u.duration, u.durationProp ?? "",
      (u.component as { displayName?: string }).displayName ?? "", JSON.stringify(u.props ?? {}),
      ...(u.themeKey ? [u.themeKey] : []),
    ].join("|");
  const audio = (kind: string, a: ManifestAudio) => [kind, a.from, a.duration ?? "", a.src, a.volume, a.label ?? ""].join("|");
  return [
    m.name, m.fps, m.width, m.height, m.total, m.background ?? "", (m.order ?? []).join(","),
    ...(m.themes ? [JSON.stringify(m.themes), m.defaultTheme ?? '', m.themeProp ?? ''] : []),
    ...UNIT_KINDS.flatMap((kind) => unitsOf(m, kind).map(unit)),
    ...(m.sfx ?? []).map((a) => audio("sfx", a)),
    ...(m.bgm ?? []).map((a) => audio("bgm", a)),
  ].join("\n");
};

/** Stable manifest version identifier saved to ProjectData.source */
export const manifestKey = (m: WorkbenchManifest) =>
  `${m.name}@${m.total}f#${m.revision ?? fnv1a(canonical(m))}`;
