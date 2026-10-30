import { create } from "zustand";
import { DEMO_CATEGORY_EN, DEMO_TEXT_RU } from "./cards/demoMeta";
import type { CardDef } from "./cards/types";

/** Workbench interface language: English is the default and standard.
 *  localStorage remembers the choice; top-bar dropdown toggles. Language only affects presentation.
 */
export type Locale = "en" | "zh" | "ru";
export const LOCALES: { id: Locale; label: string }[] = [
  { id: "en", label: "English" },
  { id: "zh", label: "English" },
  { id: "ru", label: "English" },
];
const STORAGE_KEY = "shotcraft-workbench-locale";

const readSaved = (): Locale => {
  try {
    const v = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    return v === "zh" || v === "ru" ? v : "en";
  } catch {
    return "en";
  }
};

/** Called by Workbench App (useEffect): applies locale and title to document */
export const applyLocaleToDocument = (l: Locale) => {
  document.documentElement.lang = "en";
  document.title = STRINGS[l]["app.title"];
};

export const useLocale = create<{ locale: Locale; setLocale: (l: Locale) => void }>((set) => ({
  locale: readSaved(),
  setLocale: (l) => {
    try { localStorage.setItem(STORAGE_KEY, l); } catch { /* private mode */ }
    set({ locale: l });
  },
}));

// —— UI chrome ——
const EN = {
  "app.title": "ShotCraft Workbench · Motion Workbench",
  "lang.title": "Interface language",

  "undo": "↩ Undo",
  "undo.title": "Undo (⌘Z)",
  "redo": "↪ Redo",
  "redo.title": "Redo (⇧⌘Z)",
  "export.film": "Export video",
  "export.title": "Render the current project to MP4 with Remotion (saved to workbench/exports/)",
  "export.running": "Exporting {pct}%",
  "export.done": "✓ Exported · Show file",
  "export.revealTitle": "Show the exported MP4 in Finder",
  "export.again": "Export again",
  "export.failedRetry": "Export failed · Retry",
  "export.startFailed": "Export failed to start",
  "exportJson": "Export JSON",
  "import": "Import",
  "import.invalid": "Import failed: not a valid project JSON",
  "reset": "Reset demo",
  "reset.confirm": "Reset to the demo project? Current content will be replaced (undoable).",
  "split.library": "Drag to resize the library",
  "split.inspector": "Drag to resize the properties panel",
  "split.timeline": "Drag to resize the timeline",

  "tl.split": "✂ Split",
  "tl.split.title": "Split the selected clip at the playhead (S)",
  "tl.dup": "⧉ Duplicate",
  "tl.dup.title": "Duplicate the selected clip (⌘D)",
  "tl.del": "🗑 Delete",
  "tl.del.title": "Delete the selected clip (Delete)",
  "tl.addTrack": "+ Track",
  "tl.addTrack.title": "Add a track (on top)",
  "tl.fit": "⤢ Fit",
  "tl.fit.title": "Zoom to fit all content",
  "tl.zoom": "Zoom",
  "tl.reorder.title": "Drag up or down to reorder tracks (upper tracks cover lower ones)",
  "tl.showTrack": "Show track",
  "tl.hideTrack": "Hide track",
  "tl.deleteTrack": "Delete track",
  "tl.deleteTrack.confirm": "Delete track “{name}” and its {n} clips?",

  "insp.title": "Properties",
  "insp.empty1": "Select a clip on the timeline",
  "insp.empty2": "to edit its text, colors,",
  "insp.empty3": "animation timing, speed and layer.",
  "insp.shortcuts1": "Shortcuts: Space play · S split",
  "insp.shortcuts2": "Delete remove · ⌘Z undo · ⌘D duplicate",
  "insp.contentStyle": "Content & style",
  "insp.timing": "Timing & speed",
  "insp.start": "Start",
  "insp.duration": "Duration",
  "insp.speed": "Speed",
  "insp.inPoint": "In point",
  "insp.restore": "↺ Original duration",
  "insp.restore.title": "Restore the card’s original duration (scaled by the current speed)",
  "insp.fpsMismatch":
    "This card is timed at {src}fps and the project runs at {fps}fps: its duration was converted and speed set to {ratio}× to keep the rhythm. If the card times itself with useVideoConfig().fps (spring etc.), timing still drifts by {inv}×.",
  "insp.layer": "Layer",
  "insp.opacity": "Opacity",
  "insp.scale": "Scale",
  "insp.x": "Offset X",
  "insp.y": "Offset Y",
  "insp.deleteClip": "Delete clip",

  "lib.tab.media": "Media",
  "lib.tab.cards": "Motion",
  "lib.tab.sfx": "Sound",
  "lib.tab.themes": "Themes",
  "lib.cellHint": "Click to preview, drag onto the timeline",
  "lib.tunable": " · tunable",
  "lib.importFilm": "⇣ Import film: {name}",
  "lib.importFilm.title":
    "Split the film by its src/workbench.ts manifest into shot / transition / caption / overlay / SFX / music tracks (undoable)\n{dir}",
  "lib.linkedNoManifest":
    "Linked {dir}, but the project has no src/workbench.ts manifest, so it can’t be split for import (see references/workbench.md)",
  "lib.notLinked": "No film project linked. In workbench/ run: node scripts/open.mjs <project dir>",
  "lib.filmUnits": "Film units (add another copy)",
  "lib.mediaFiles": "Media files (project public/)",
  "lib.video": "Video",
  "lib.image": "Image",
  "lib.projectAudio": "Project audio (public/)",
  "lib.usedIn": "Used ×{n}",
  "lib.unused": "Unused",
  "lib.bgm": "BGM options (assets/audio/bgm)",
  "lib.sfxLib": "SFX library · {cat}",
  "lib.foot.themes": "Theme switches are undoable · saved with the project",
  "lib.foot.cards": "{n} motion cards ({m} tunable)",
  "lib.foot.sfx": " · SFX library {n}",
  "lib.foot.units": " · film units {n}",
  "lib.foot.hint": "Click to preview · drag onto the timeline",

  "prev.audioCard": "🔊 Audio card",
  "prev.tag": "Preview",
  "prev.dragHint": "Drag media onto the timeline to add it",
  "prev.back": "✕ Back to project",
  "prev.toStart": "Go to start",
  "prev.playPause": "Play / Pause (Space)",
  "prev.loop": "Loop",

  "theme.aria": "Film theme",
  "theme.presets": "Presets",
  "theme.hint": "Pick a style, then adjust the colors.",
  "theme.none": "This project provides no themes yet.",
  "theme.mine": "My themes",
  "theme.delete.aria": "Delete {name}",
  "theme.deleted": "Deleted “{name}”",
  "theme.applied": "Applied “{name}”",
  "theme.editor": "Replace colors",
  "theme.reset": "Reset preset",
  "theme.name.aria": "Palette name",
  "theme.name.placeholder": "Palette name (optional)",
  "theme.save": "Save palette",
  "theme.import": "Import palette",
  "theme.export": "Export palette",
  "theme.file.aria": "Import palette file",
  "theme.limit": "50 palettes saved. Delete unused ones first.",
  "theme.saved": "Saved “{name}” (this browser only).",
  "theme.saveFailed": "Save failed: browser storage is unavailable. Export the palette as a backup.",
  "theme.exported": "Palette exported as JSON.",
  "theme.tooBig": "Palette file must be under 64 KB.",
  "theme.imported": "Imported and applied. Click “Save palette” to add it to My themes.",
  "theme.importFailed": "Import failed.",
  "theme.customized": "Customized · ",
  "theme.clickHint": "Click a swatch or type a HEX · ",
  "theme.switchResets": "switching presets resets the palette",
  "theme.note": "Applies to preview and export, undoable. Per-clip color edits take precedence.",
  "theme.paperNote": "The paper theme keeps its original screenshots. Pick another preset to edit the full palette.",
  "theme.noPalette": "Shown here once the project provides an editable palette.",
  "theme.pick.aria": "{label} color picker",
  "theme.hex.aria": "{label} hex value",
  "theme.field.page": "Background",
  "theme.field.surface": "Card",
  "theme.field.text": "Text",
  "theme.field.muted": "Secondary text",
  "theme.field.accent": "Accent",
  "theme.field.field": "Light fill",
  "theme.field.border": "Border",

  "palette.custom": "Custom",
  "palette.needTheme": "Select a theme that supports palettes first.",
  "palette.tooBig": "Palette file is too large; choose a JSON under 64 KB.",
  "palette.badJson": "The file is not valid JSON.",
  "palette.badFormat": "Palette file format is invalid.",
  "palette.badVersion": "Choose a palette JSON exported by ShotCraft (version 1).",
  "palette.badTheme": "This project doesn’t support the palette’s base theme.",
  "palette.noColors": "The palette has no colors field.",
  "palette.badColors": "All color fields are required and must use #RRGGBB.",

  "track.transitions": "Transitions",
  "track.captions": "Captions",
  "track.overlays": "Overlays",
  "track.shots": "Shots",
  "track.music": "Music",
  "track.sfx": "SFX",
  "track.background": "Background",
  "track.new": "Track {n}",

  "demo.name": "Untitled project",
} as const;

export type StringKey = keyof typeof EN;

const ZH: Record<StringKey, string> = EN;
const RU: Record<StringKey, string> = EN;

export const STRINGS: Record<Locale, Record<StringKey, string>> = { en: EN, zh: ZH, ru: RU };

const fill = (s: string, params?: Record<string, string | number>) =>
  params ? s.replace(/\{(\w+)\}/g, (_, k) => (params[k] !== undefined ? String(params[k]) : `{${k}}`)) : s;

export const t = (key: StringKey, params?: Record<string, string | number>): string => {
  const l = useLocale.getState().locale;
  const tmpl = STRINGS[l]?.[key] ?? EN[key] ?? key;
  return fill(tmpl, params);
};

export const useT = () => {
  const l = useLocale((s) => s.locale);
  return (key: StringKey, params?: Record<string, string | number>) => {
    const tmpl = STRINGS[l]?.[key] ?? EN[key] ?? key;
    return fill(tmpl, params);
  };
};

/** Translates label segment */
const translateSegment = (s: string, _to: Locale): string => {
  return s;
};

/** Content label display: returns English text */
export const tx = (s: string | undefined | null): string => {
  if (!s) return "";
  const to = useLocale.getState().locale;
  const whole = translateSegment(s, to);
  if (whole !== s || !s.includes(" · ")) return whole;
  return s.split(" · ").map((seg) => translateSegment(seg, to)).join(" · ");
};

export const useTx = () => {
  useLocale((s) => s.locale);
  return tx;
};

/** Card name: prefers nameEn */
export const cardName = (card: Pick<CardDef, "name" | "nameEn">): string => {
  return card.nameEn || card.name;
};

/** Card summary: prefers summaryEn */
export const cardSummary = (card: Pick<CardDef, "summary" | "summaryEn">): string | undefined => {
  return card.summaryEn ?? card.summary;
};

/** Theme preset name written as "Name · English": returns the second part if split, else label */
export const themeLabel = (label: string): string => {
  const parts = label.split(" · ");
  if (parts.length === 2) {
    return parts[1];
  }
  return tx(label);
};
