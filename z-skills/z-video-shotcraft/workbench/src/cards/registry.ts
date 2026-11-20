import type { CardDef } from "./types";
import { textBasicCard } from "./text-basic";
import { titleCardCard } from "./inkpress/title-card";
import { captionStripCard } from "./inkpress/caption-strip";
import { flashCutCard } from "./inkpress/flash-cut";
import { audioClipCard, imageClipCard, videoClipCard } from "./media-cards";
import { BG_CARDS } from "./background-cards";
import { DEMO_CARDS } from "./demoCards";
import { PROJECT_CARDS } from "./projectCards";
import { LEGACY_CARDS } from "./legacyCards";
import { buildCardRegistry } from "./buildRegistry";

/** Card registry (first-come first-served by id):
 *  - Native cards: basic text / Ink Press title / caption / flash cut;
 *  - Media cards: audio / video / image;
 *  - Background cards;
 *  - Film unit cards from linked project manifest;
 *  - Motion library: demo components from demos/;
 *  - Legacy compatibility cards. */
const ALL: CardDef[] = [
  textBasicCard,
  titleCardCard,
  captionStripCard,
  flashCutCard,
  audioClipCard,
  videoClipCard,
  imageClipCard,
  ...BG_CARDS,
  ...PROJECT_CARDS,
  ...DEMO_CARDS,
];

const registry = buildCardRegistry(ALL, LEGACY_CARDS);
export const CARD_LIST: CardDef[] = registry.cardList;
export const CARDS: Record<string, CardDef> = registry.cards;
