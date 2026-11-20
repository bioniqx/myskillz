#!/usr/bin/env node
// Generates static index and local manifests (untracked, run by npm install prepare hook and dev/build/studio pre-hooks):
//   src/cards/demo-index.ts   demos/ shot card demo component static index (webpack/Vite dual compatibility — Remotion CLI doesn't support import.meta.glob)
//   src/cards/legacy-index.ts Legacy project compatibility index for deprecated demos (excluded from asset library)
//   src/cards/demoMeta.ts     demo → English name / gallery category / preview video (generated from gallery/api/library.json + translations.js)
//   src/mediaManifest.ts      public/ asset manifest (linked via symlink from project public/) + repo SFX / BGM libraries
//   src/projMeta.ts           Metadata of linked video project
// Also ensures repo-level symlinks under public/ are in place: cardpreviews → gallery/media, sfxlib → assets/audio/sfx,
// bgmlib → assets/audio/bgm, textures/live (demo texture fallback → demos/_textures).
import {
  existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, statSync, symlinkSync, unlinkSync, writeFileSync,
} from "node:fs";
import { dirname, extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const wb = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(wb, "..");
const banner = "// Auto-generated, do not edit manually: node scripts/gen-index.mjs\n";
const norm = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

// —— Repo-level links (relative symlinks, idempotent) ——
const ensureLink = (linkPath, target) => {
  const abs = join(dirname(linkPath), target);
  if (!existsSync(abs)) return false;
  try {
    const st = lstatSync(linkPath);
    if (st.isSymbolicLink()) unlinkSync(linkPath);
    else return true; // Real file/dir (linked from project): do not touch
  } catch { /* does not exist */ }
  mkdirSync(dirname(linkPath), { recursive: true });
  symlinkSync(target, linkPath);
  return true;
};
const publicDir = join(wb, "public");
mkdirSync(publicDir, { recursive: true });
ensureLink(join(publicDir, "cardpreviews"), "../../gallery/media");
ensureLink(join(publicDir, "sfxlib"), "../../assets/audio/sfx");
ensureLink(join(publicDir, "bgmlib"), "../../assets/audio/bgm");
// Isolated namespace, never write old screenshots to user's linked public/textures
ensureLink(join(publicDir, "legacy-textures"), "../../demos/_legacy/_textures");
// Demo texture fallback: if project brings its own public/textures, use that as authoritative
{
  const tex = join(publicDir, "textures");
  let texIsLink = false;
  try { texIsLink = lstatSync(tex).isSymbolicLink(); } catch { /* none */ }
  if (!texIsLink && !existsSync(join(tex, "live"))) ensureLink(join(tex, "live"), "../../../demos/_textures");
}

// —— Demo index: files exporting `<Stem>: React.FC` (components without required props) are registered ——
// Duration resolution chain: exported `*_DURATION|*_DUR` constant (matches assets/scripts/smoke-render-demos.py, most reliable)
//   → Shot card md `duration:` `NNNf` → Gallery library.json duration `NNNf`
//   → Unexported file constant `const *DUR*|TOTAL|*END = N` → Default 150f (clips can be trimmed/held, motion-lab cards normalize to clip length)
const DUR_PAT = /export const (\w+_DURATION|\w+_DUR)\s*=/;
const MATERIAL_REQUIRED = new Set(["ClipCardLooping"]); // Requires real mp4 footage, cannot auto-generate
const demosDir = join(wb, "demosrc");
const framesIn = (text) => { const m = text && /(\d{2,4})\s*f\b/.exec(text); return m ? Number(m[1]) : 0; };
const cardMdFrames = (category, slug) => {
  try { const md = readFileSync(join(repo, "references/shots", category, `${slug}.md`), "utf8"); const m = /^duration:\s*(.*)$/m.exec(md); return framesIn(m?.[1]); } catch { return 0; }
};
let libForDur = { cards: [] };
try { libForDur = JSON.parse(readFileSync(join(repo, "gallery/api/library.json"), "utf8")); } catch { /* warn below */ }
const libDurFrames = (slug) => framesIn(libForDur.cards.find((c) => c.name === slug)?.duration);
const demos = [];
const walkDemos = (dir) => {
  for (const e of readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.name.startsWith("_") || e.name.startsWith(".")) continue;
    const p = join(dir, e.name);
    if (e.isDirectory()) { walkDemos(p); continue; }
    if (!e.name.endsWith(".tsx")) continue;
    const stem = e.name.replace(/\.tsx$/, "");
    if (MATERIAL_REQUIRED.has(stem)) continue;
    const src = readFileSync(p, "utf8");
    if (!new RegExp(`export const ${stem}\\s*:\\s*React\\.FC\\s*=`).test(src)) continue;
    const rel = relative(demosDir, p).replace(/\.tsx$/, "");
    const [category, slug] = rel.split("/");
    const m = DUR_PAT.exec(src);
    let durExport = m?.[1];
    let duration = 0;
    let durationSource = "export";
    if (!durExport) {
      duration = cardMdFrames(category, slug); durationSource = "card";
      if (!duration) { duration = libDurFrames(slug); durationSource = "gallery"; }
      if (!duration) {
        const im = /^const ([A-Z][A-Z0-9_]*(?:DUR|TOTAL|_END|FRAMES)[A-Z0-9_]*)\s*=\s*(\d+)\s*;/m.exec(src);
        if (im) { duration = Number(im[2]); durationSource = "inline"; }
      }
      if (!duration) { duration = 150; durationSource = "default"; }
    }
    demos.push({ stem, durExport, duration, durationSource, rel, category, slug });
  }
};
walkDemos(demosDir);
{
  const dupes = demos.map((d) => d.stem).filter((s, i, a) => a.indexOf(s) !== i);
  if (dupes.length) throw new Error(`Duplicate demo component name (card id uses component name, must be unique): ${[...new Set(dupes)].join(", ")}`);
}
writeFileSync(
  join(wb, "src/cards/demo-index.ts"),
  banner +
    'import type React from "react";\n' +
    demos
      .map((d, i) => `import { ${d.stem} as c${i}${d.durExport ? `, ${d.durExport} as d${i}` : ""} } from "@demos/${d.rel}";`)
      .join("\n") +
    `\n\nexport type DemoModule = {
  stem: string;
  slug: string;
  component: React.ComponentType<Record<string, unknown>>;
  duration: number;
  /** Duration source: export = exported by demo / card = shot card md / gallery = gallery / inline = in-file constant / default = fallback 150f */
  durationSource: "export" | "card" | "gallery" | "inline" | "default";
};

export const DEMO_MODULES: DemoModule[] = [
` +
    demos
      .map((d, i) => `  { stem: "${d.stem}", slug: "${d.slug}", component: c${i} as unknown as React.ComponentType<Record<string, unknown>>, duration: ${d.durExport ? `d${i}` : d.duration}, durationSource: "${d.durationSource}" },`)
      .join("\n") +
    "\n];\n",
);

// —— Frozen legacy project compatibility index: excluded from demos / meta / asset library counts ——
const legacyDir = join(demosDir, "_legacy");
const legacy = JSON.parse(readFileSync(join(legacyDir, "manifest.json"), "utf8")).cards;
const legacyStems = new Set();
for (const card of legacy) {
  if (!/^\w+$/.test(card.stem) || !/^[a-z0-9-]+\/[a-z0-9-]+\/\w+$/.test(card.path)
      || !Number.isInteger(card.duration) || card.duration < 2 || legacyStems.has(card.stem))
    throw new Error(`invalid legacy demo definition: ${card.stem}`);
  const src = readFileSync(join(legacyDir, `${card.path}.tsx`), "utf8");
  if (!new RegExp(`export const ${card.stem}\\s*:\\s*React\\.FC\\s*=`).test(src))
    throw new Error(`legacy demo export missing: ${card.stem}`);
  legacyStems.add(card.stem);
}
writeFileSync(
  join(wb, "src/cards/legacy-index.ts"),
  banner + 'import type React from "react";\n' +
    legacy.map((c, i) => `import { ${c.stem} as c${i} } from "@demos/_legacy/${c.path}";`).join("\n") +
    `\n\nexport const LEGACY_DEMO_MODULES: {
  stem: string; name: string; nameEn?: string; category: string; duration: number;
  component: React.ComponentType<Record<string, unknown>>;
}[] = [\n` +
    legacy.map((c, i) => `  { ...${JSON.stringify({ stem: c.stem, name: c.nameEn || c.name, nameEn: c.nameEn, category: c.category, duration: c.duration })}, component: c${i} as unknown as React.ComponentType<Record<string, unknown>> },`).join("\n") +
    "\n];\n",
);

// —— Demo metadata: gallery library.json (category / summary / styles) + translations.js (names) ——
let lib = { cards: [], categories: {} };
try { lib = JSON.parse(readFileSync(join(repo, "gallery/api/library.json"), "utf8")); } catch { console.warn("gen-index: cannot read gallery/api/library.json, using English names"); }
let i18n = { cardsZh: {}, stylesZh: {} };
try {
  const win = {};
  new Function("window", readFileSync(join(repo, "gallery/translations.js"), "utf8"))(win);
  i18n = win.GALLERY_I18N ?? i18n;
} catch { console.warn("gen-index: cannot read gallery/translations.js, using English names"); }
const cardBySlug = new Map(lib.cards.map((c) => [c.name, c]));
const mediaDir = join(repo, "gallery/media");
const filesPerSlug = new Map();
for (const d of demos) filesPerSlug.set(d.slug, (filesPerSlug.get(d.slug) ?? 0) + 1);
const meta = {};
for (const d of demos) {
  const card = cardBySlug.get(d.slug);
  const styles = card?.styles ?? [];
  let style = styles.find((s) => norm(s.key) === norm(d.stem));
  if (!style && styles.length === 1 && filesPerSlug.get(d.slug) === 1) style = styles[0];
  const nameEn = style ? style.key : `${d.slug} · ${d.stem}`;
  const summaryEn = (style && i18n.stylesEn?.[style.key]) || i18n.cardsEn?.[d.slug] || undefined;
  const catKey = card?.category ?? d.category;
  const preview = style && existsSync(join(mediaDir, `${style.key}.mp4`)) ? `${style.key}.mp4` : undefined;
  const catEn = lib.categories?.[catKey]?.en ?? catKey;
  meta[d.stem] = {
    name: nameEn,
    nameEn,
    card: d.slug,
    category: catEn,
    categoryKey: catKey,
    styleKey: style?.key,
    preview,
    summary: summaryEn ?? style?.description ?? card?.summary,
    summaryEn,
  };
}
const catOrder = Object.keys(lib.categories ?? {});
const categoryEn = Object.fromEntries(
  [...new Set(demos.map((d) => meta[d.stem].categoryKey))].map((k) => [k, lib.categories?.[k]?.en ?? k]),
);
const categories = [...new Set(demos.map((d) => meta[d.stem].categoryKey))]
  .sort((a, b) => (catOrder.indexOf(a) + 1 || 99) - (catOrder.indexOf(b) + 1 || 99))
  .map((k) => lib.categories?.[k]?.en ?? k);
const textRu = {};
writeFileSync(
  join(wb, "src/cards/demoMeta.ts"),
  banner +
    "// demo component name → English name / shot card / gallery category / preview video / summary\n" +
    `export type DemoMeta = { name: string; nameEn: string; card: string; category: string; categoryKey: string; styleKey?: string; preview?: string; summary?: string; summaryEn?: string };\n` +
    `export const DEMO_META: Record<string, DemoMeta> = ${JSON.stringify(meta, null, 2)};\n\n` +
    `/** Gallery categories (English, in gallery order), only containing categories with demos */\nexport const DEMO_CATEGORIES: string[] = ${JSON.stringify(categories)};\n` +
    `/** Category key → English name */\nexport const DEMO_CATEGORY_EN: Record<string, string> = ${JSON.stringify(categoryEn)};\n` +
    `/** Russian text dictionary (empty fallback) */\nexport const DEMO_TEXT_RU: Record<string, string> = ${JSON.stringify(textRu, null, 2)};\n`,
);

// —— Asset manifest: scan public/ (footage linked via symlinks; cardpreviews / sfxlib / bgmlib separate) ——
const KIND = {
  ".mp4": "video", ".webm": "video", ".mov": "video",
  ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".gif": "image", ".svg": "image",
  ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".aac": "audio", ".ogg": "audio", ".flac": "audio",
};
const SKIP_TOP = new Set(["cardpreviews", "sfxlib", "bgmlib", "legacy-textures"]);
const media = [];
const walk = (dir, rel) => {
  let ents;
  try { ents = readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of ents.sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.name.startsWith(".")) continue;
    const p = join(dir, e.name);
    const r = rel ? `${rel}/${e.name}` : e.name;
    let st;
    try { st = statSync(p); } catch { continue; } // Broken symlink: skip
    if (st.isDirectory()) { if (!rel && SKIP_TOP.has(e.name)) continue; walk(p, r); }
    else {
      const kind = KIND[extname(e.name).toLowerCase()];
      if (kind) media.push({ file: r, dir: rel, name: e.name, kind });
    }
  }
};
walk(publicDir, "");
const listAudio = (sub) => {
  const out = [];
  const base = join(publicDir, sub);
  if (!existsSync(base)) return out;
  const push = (rel, cat) => {
    const name = rel.split("/").pop();
    if (KIND[extname(name).toLowerCase()] === "audio") out.push({ file: `${sub}/${rel}`, cat, name: name.replace(/\.[^.]+$/, "") });
  };
  for (const e of readdirSync(base, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (e.name.startsWith(".")) continue;
    let isDir = false;
    try { isDir = statSync(join(base, e.name)).isDirectory(); } catch { continue; }
    if (isDir) {
      for (const f of readdirSync(join(base, e.name)).sort()) if (!f.startsWith(".")) push(`${e.name}/${f}`, e.name);
    } else push(e.name, "");
  }
  return out;
};
const sfxLib = listAudio("sfxlib");
const bgmLib = listAudio("bgmlib");
writeFileSync(
  join(wb, "src/mediaManifest.ts"),
  banner +
    "// Project public/ asset manifest: generated by scanning local public/ symlinks (untracked)\n" +
    'export type MediaItem = { file: string; dir: string; name: string; kind: "video" | "image" | "audio" };\n' +
    `export const MEDIA_ITEMS: MediaItem[] = ${JSON.stringify(media, null, 2)};\n\n` +
    "/** Sound effects library assets/audio/sfx/<category>/ (public/sfxlib symlink) */\n" +
    "export type LibAudio = { file: string; cat: string; name: string };\n" +
    `export const SFX_LIB: LibAudio[] = ${JSON.stringify(sfxLib, null, 2)};\n\n` +
    "/** BGM library assets/audio/bgm/ (public/bgmlib symlink) */\n" +
    `export const BGM_LIB: LibAudio[] = ${JSON.stringify(bgmLib, null, 2)};\n`,
);

// —— Linked video project metadata ——
const projLink = join(wb, "proj");
const projLinked = existsSync(projLink);
let projDir = "";
let hasManifest = false;
if (projLinked) {
  try { projDir = dirname(realpathSync(projLink)); } catch { projDir = ""; }
  hasManifest = existsSync(join(projLink, "workbench.ts")) || existsSync(join(projLink, "workbench.tsx"));
}
writeFileSync(
  join(wb, "src/projMeta.ts"),
  banner +
    "// Linked video project: generated from local proj symlink (untracked)\n" +
    `export const PROJ_LINKED = ${projLinked};\n` +
    `/** Project root directory (parent of src/; empty if unlinked) */\nexport const PROJ_DIR = ${JSON.stringify(projDir)};\n` +
    `/** Whether project provides src/workbench.ts manifest */\nexport const PROJ_HAS_MANIFEST = ${hasManifest};\n`,
);

const srcCount = demos.reduce((a, d) => ((a[d.durationSource] = (a[d.durationSource] ?? 0) + 1), a), {});
console.log(
  `gen-index: ${demos.length} demo cards (${Object.values(meta).filter((m) => m.preview).length} with preview video; duration sources ${JSON.stringify(srcCount)})` +
    `, ${media.length} project assets, SFX library ${sfxLib.length} / BGM ${bgmLib.length}` +
    `, video project ${projLinked ? `${projDir}${hasManifest ? "" : " (no workbench.ts manifest)"}` : "unlinked"}`,
);
