import type { CardDef } from "./types";
import { DEMO_MODULES } from "./demo-index";
import { DEMO_CATEGORIES, DEMO_META } from "./demoMeta";

/** Shot card motion library: indexed from demos/ by scripts/gen-index.mjs.
 *  Components export <Stem>: React.FC with duration constants.
 *  Tunable on timeline via clipping, speed, freeze, and layer transforms.
 *  Tunable via speed, trimming, and layer transforms.
 *  See references/workbench.md for custom prop schema conversion.
 *  DesignStage cards normalize timing to clip length; other cards freeze tail frame.
 */
export const DEMO_CARDS: CardDef[] = DEMO_MODULES.map((m) => {
  const meta = DEMO_META[m.stem];
  return {
    id: `demo:${m.stem}`,
    name: meta?.name ?? m.stem,
    nameEn: meta?.nameEn ?? m.stem,
    category: meta?.category ?? "Motion",
    durationInFrames: Math.max(2, Math.round(m.duration)),
    component: m.component,
    schema: [],
    accent: "#c58a2a",
    preview: meta?.preview ? `cardpreviews/${meta.preview}` : undefined,
    summary: meta?.summary,
    summaryEn: meta?.summaryEn,
  };
});

export { DEMO_CATEGORIES };
