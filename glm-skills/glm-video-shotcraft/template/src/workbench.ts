// Workbench manifest — how the film decomposes into editable clips.
//
// The shotcraft workbench (../../workbench, `node scripts/open.mjs <this project>`)
// reads `WORKBENCH` and rebuilds the film as tracks: shots / transitions / captions
// / SFX, each unit exactly where its <Sequence> sits in aifl/Main.tsx. Every table here is
// imported from Main.tsx, so editing the timeline there moves the workbench too —
// there is no second copy of the timing to drift.
//
// Editable properties per unit come from `schema` (text / colour / number / select /
// boolean fields; see workbench/src/cards/types.ts PropField). Each scene exports its
// `*_DEFAULTS` (copy, sizes, palette) and reads them as props with defaults, so the
// schema defaults below are the same object the scene renders with — the inspector
// shows exactly what is on screen, and an untouched import renders the original film.
// Motion timing (cues, eases, camera keys) is deliberately NOT exposed.
import { createElement, type FC } from 'react';
import { withThemes } from './themes/manifest';
import {
  AIFL_SHOTS, AIFL_TOTAL, AiflMain, CAPTIONS, FLASH_CUTS, SFX, TITLE_CARDS, parseWords, sfxDuration,
} from './aifl/Main';
import { SceneOpen, SCENE_OPEN_DEFAULTS } from './aifl/live/SceneOpen';
import { SceneFlyIn, SCENE_FLYIN_DEFAULTS } from './aifl/live/SceneFlyIn';
import { SceneDetail, SCENE_DETAIL_DEFAULTS } from './aifl/live/SceneDetail';
import { ScenePapers, SCENE_PAPERS_DEFAULTS } from './aifl/live/ScenePapers';
import { SceneWbr, SCENE_WBR_DEFAULTS } from './aifl/live/SceneWbr';
import { SceneOutroLive, SCENE_OUTRO_DEFAULTS } from './aifl/live/SceneOutroLive';
import { PaperTitleCard, TITLE_CARD_DEFAULTS } from './aifl/PaperTitleCard';
import { Caption, CAPTION_DEFAULTS } from './aifl/Caption';
import { FlashCut } from './aifl/FlashCut';

// —— schema field helpers (plain data; shape = workbench PropField) ——
type Field = Record<string, unknown> & { type: string; key: string; label: string; default: unknown };
const text = (key: string, label: string, def: string): Field => ({ type: 'text', key, label, default: def });
const textarea = (key: string, label: string, def: string): Field => ({ type: 'textarea', key, label, default: def });
const color = (key: string, label: string, def: string): Field => ({ type: 'color', key, label, default: def });
const size = (key: string, label: string, def: number, min: number, max: number): Field => ({
  type: 'slider', key, label, default: def, min, max, step: 1, unit: 'px',
});

// —— adapters: prop-driven wrappers so the workbench can edit copy without touching the scenes ——
type TitleProps = Partial<typeof TITLE_CARD_DEFAULTS> & { text?: string; sub?: string; subDigits?: string; duration?: number };
export const TitleCardUnit: FC<TitleProps> = ({ text = '', sub = '', subDigits = '', duration = 55, ...style }) =>
  createElement(PaperTitleCard, {
    duration,
    words: parseWords(text),
    sub: sub || undefined,
    subDigits: subDigits || undefined,
    ...style,
  });
TitleCardUnit.displayName = 'PaperTitleCard';

type CaptionProps = Partial<typeof CAPTION_DEFAULTS> & { text?: string; bottom?: number; duration?: number };
export const CaptionUnit: FC<CaptionProps> = ({ text = '', bottom = 72, duration = 40, ...style }) =>
  createElement(Caption, { text, bottom, duration, ...style });
CaptionUnit.displayName = 'Caption';

export const FlashUnit: FC<{ duration?: number }> = ({ duration = 10 }) => createElement(FlashCut, { duration });
FlashUnit.displayName = 'FlashCut';

// —— schemas: one per parametrized component; defaults come straight from the *_DEFAULTS objects ——
const D = {
  open: SCENE_OPEN_DEFAULTS,
  flyin: SCENE_FLYIN_DEFAULTS,
  detail: SCENE_DETAIL_DEFAULTS,
  papers: SCENE_PAPERS_DEFAULTS,
  wbr: SCENE_WBR_DEFAULTS,
  outro: SCENE_OUTRO_DEFAULTS,
  title: TITLE_CARD_DEFAULTS,
  caption: CAPTION_DEFAULTS,
};

const SCHEMAS = {
  open: [
    text('wordmark', 'Wordmark', D.open.wordmark),
    size('wordmarkSize', 'Wordmark Font Size', D.open.wordmarkSize, 60, 200),
    text('kicker', 'Kicker (Typewriter)', D.open.kicker),
    size('kickerSize', 'Kicker Font Size', D.open.kickerSize, 14, 48),
    text('noteLine1', 'Floating Note · Line 1', D.open.noteLine1),
    text('noteLine2', 'Floating Note · Line 2 (Italic + Highlight)', D.open.noteLine2),
    size('noteSize', 'Note Font Size', D.open.noteSize, 20, 64),
    color('ink', 'Ink Color', D.open.ink),
    color('amber', 'Amber Accent', D.open.amber),
    color('muted', 'Muted Ink (Kicker)', D.open.muted),
    color('paper', 'Paper Background', D.open.paper),
  ],
  flyin: [
    text('query', 'Search Query Text', D.flyin.query),
    color('accent', 'Amber Accent (Cursor / Ripple / Selection)', D.flyin.accent),
  ],
  detail: [color('accent', 'Embed Seam Color', D.detail.accent)],
  papers: [
    text('title', 'Top-Right Title', D.papers.title),
    text('subtitle', 'Top-Right Subtitle', D.papers.subtitle),
    size('counterSize', 'Counter Font Size', D.papers.counterSize, 48, 160),
    color('amber', 'Amber Accent', D.papers.amber),
    color('muted', 'Muted Ink', D.papers.muted),
  ],
  wbr: [
    text('kicker', 'Top-Right Kicker', D.wbr.kicker),
    size('kickerSize', 'Kicker Font Size', D.wbr.kickerSize, 14, 48),
    textarea('pastWeeks', 'Past Reports (per line: Week|Date|Title)', D.wbr.pastWeeks),
    color('amber', 'Amber Accent', D.wbr.amber),
    color('muted', 'Muted Ink', D.wbr.muted),
  ],
  outro: [
    text('wordmark', 'Wordmark', D.outro.wordmark),
    size('wordmarkSize', 'Wordmark Font Size', D.outro.wordmarkSize, 60, 220),
    text('tagline', 'Tagline', D.outro.tagline),
    size('taglineSize', 'Tagline Font Size', D.outro.taglineSize, 14, 48),
    color('ink', 'Ink Color', D.outro.ink),
    color('amber', 'Amber Accent', D.outro.amber),
    color('muted', 'Muted Ink', D.outro.muted),
  ],
  title: [
    textarea('text', 'Copy (*word* = Amber emphasis)', ''),
    text('sub', 'Subtitle (Monospace)', ''),
    text('subDigits', 'Subtitle Counter', ''),
    size('fontSize', 'Font Size', D.title.fontSize, 60, 160),
    color('ink', 'Ink Color', D.title.ink),
    color('accent', 'Accent Color', D.title.accent),
    color('muted', 'Subtitle Muted Color', D.title.muted),
    color('paper', 'Paper Background', D.title.paper),
  ],
  caption: [
    text('text', 'Caption Text', ''),
    { type: 'slider', key: 'bottom', label: 'Bottom Margin', default: 72, min: 20, max: 400, step: 2, unit: 'px' } as Field,
    size('fontSize', 'Font Size', D.caption.fontSize, 14, 48),
    color('color', 'Text Color', D.caption.color),
    color('accent', 'Bullet Color', D.caption.accent),
  ],
};

type ShotKey = keyof typeof AIFL_SHOTS;
const scene = <T extends Record<string, unknown>>(
  key: ShotKey, label: string, component: FC<Partial<T>>, defaults: T, schema: Field[],
) => ({
  id: key,
  label,
  from: AIFL_SHOTS[key].from,
  duration: AIFL_SHOTS[key].duration,
  component: component as FC<Record<string, unknown>>,
  props: { ...defaults },
  schema,
});
const title = (key: keyof typeof TITLE_CARDS, label: string) => {
  const t = TITLE_CARDS[key] as { text: string; sub?: string; subDigits?: string };
  return {
    id: key,
    label,
    from: AIFL_SHOTS[key].from,
    duration: AIFL_SHOTS[key].duration,
    component: TitleCardUnit as FC<Record<string, unknown>>,
    props: { text: t.text, sub: t.sub ?? '', subDigits: t.subDigits ?? '', ...D.title },
    schema: SCHEMAS.title,
    durationProp: 'duration',
    cardId: 'title-card',
    cardName: 'Title Card · Ink Press',
    accent: '#b5651d',
  };
};

const PAPER_WORKBENCH = {
  name: 'Ink Press · AIFL promo',
  fps: 30,
  width: 1920,
  height: 1080,
  total: AIFL_TOTAL,
  background: '#f2eee6',
  shots: [
    scene('morning', 'S1 Ink Trace Opening → Wide → Hero Card', SceneOpen, D.open, SCHEMAS.open),
    title('card1', 'Title Card 1 · One Place'),
    scene('table', 'S3 Deck Deal → Fly In → Search Filter', SceneFlyIn, D.flyin, SCHEMAS.flyin),
    scene('macro', 'S4 Detail Macro Close-Up', SceneDetail, D.detail, SCHEMAS.detail),
    title('card2', 'Title Card 2 · Paper Radar'),
    scene('chart', 'S6 Paper Radar List Stack', ScenePapers, D.papers, SCHEMAS.papers),
    title('cardWbr', 'Title Card 3 · Weekly Report'),
    scene('wbr', 'S8 Weekly Report Typewriter Reveal', SceneWbr, D.wbr, SCHEMAS.wbr),
    title('card3', 'Title Card 4 · Same Page'),
    scene('outro', 'S10 Outro Group Assembly → Stamped Mark', SceneOutroLive, D.outro, SCHEMAS.outro),
  ],
  transitions: FLASH_CUTS.map((cut, i) => ({
    id: `flash-${i + 1}`,
    label: `Flash @${cut}f`,
    from: cut - 5,
    duration: 10,
    component: FlashUnit as FC<Record<string, unknown>>,
    durationProp: 'duration',
    cardId: 'flash-cut',
    cardName: 'Warm White Flash Transition',
  })),
  captions: CAPTIONS.map((c, i) => ({
    id: `caption-${i + 1}`,
    label: c.text,
    from: c.from,
    duration: c.duration,
    component: CaptionUnit as FC<Record<string, unknown>>,
    props: { text: c.text, ...D.caption },
    schema: SCHEMAS.caption,
    durationProp: 'duration',
    cardId: 'caption',
    cardName: 'Caption Strip',
  })),
  sfx: SFX.map((s) => ({
    from: s.from,
    duration: sfxDuration(s),
    src: `audio/${s.src}`,
    volume: s.volume,
  })),
  // z-order of the overlay layers, top → bottom (flash cuts sit above the captions in Main.tsx)
  order: ['transitions', 'captions', 'overlays'] as const,
  // the untouched film, registered in the workbench Studio as `ProjOriginal` for frame-by-frame comparison
  original: AiflMain as FC<Record<string, unknown>>,
};
export const WORKBENCH = withThemes(PAPER_WORKBENCH);
