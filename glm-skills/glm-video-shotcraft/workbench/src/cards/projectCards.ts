import type React from "react";
import type { CardDef } from "./types";
import type { ManifestUnit, WorkbenchManifest } from "./manifest";
import { UNIT_KINDS, groupUnits, unitsOf } from "./manifest";
import { WORKBENCH as RAW } from "@proj/workbench";
export { unitsOf } from "./manifest";
export type { UnitKind } from "./manifest";

/** Linked film project manifest (null if unlinked or manifest missing) */
export const MANIFEST: WorkbenchManifest | null = (RAW ?? null) as WorkbenchManifest | null;

const KIND_LABEL = { shot: "Shot", transition: "Transition", caption: "Caption", overlay: "Overlay" } as const;
const KIND_ACCENT: Record<keyof typeof KIND_LABEL, string> = {
  shot: "#4c9aff",
  transition: "#f7c948",
  caption: "#34c759",
  overlay: "#8e8e93",
};

/** Film unit cards + cardId mapping for importer from manifest.groupUnits */
/** Preserves consistent topology with manifest content hash */
const build = (m: WorkbenchManifest | null) => {
  const cards: CardDef[] = [];
  const cardIdOfUnit = m ? groupUnits(m) : new Map<ManifestUnit, string>();
  if (!m) return { cards, cardIdOfUnit };
  for (const kind of UNIT_KINDS) {
    const byCard = new Map<string, ManifestUnit[]>();
    for (const u of unitsOf(m, kind)) {
      const id = cardIdOfUnit.get(u)!;
      const g = byCard.get(id);
      if (g) g.push(u);
      else byCard.set(id, [u]);
    }
    for (const [id, units] of byCard) {
      const first = units[0];
      const name =
        units.find((u) => u.cardName)?.cardName ??
        (units.length > 1 ? `${KIND_LABEL[kind]} · ${componentName(first.component)}` : (first.label ?? first.id));
      cards.push({
        id,
        name,
      category: "Film Units",
        durationInFrames: Math.max(2, first.duration),
      // Film units author at manifest frame rate
        sourceFps: m.fps,
        width: m.width,
        height: m.height,
        component: first.component,
        themeKey: first.themeKey,
        schema: first.schema ?? [],
        durationProp: first.durationProp,
        accent: first.accent ?? KIND_ACCENT[kind],
      });
    }
  }
  return { cards, cardIdOfUnit };
};

const componentName = (c: React.ComponentType<Record<string, unknown>>) =>
  (c as { displayName?: string }).displayName ?? c.name ?? "Component";

const built = build(MANIFEST);
export const PROJECT_CARDS: CardDef[] = built.cards;
export const cardIdOfUnit = (u: ManifestUnit) => built.cardIdOfUnit.get(u)!;

/** Original film composition registered as ProjOriginal for parity comparison */
export const ORIGINAL = MANIFEST?.original ?? null;
