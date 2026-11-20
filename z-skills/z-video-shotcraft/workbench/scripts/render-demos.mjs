// Batch render all shot cards in demos/ (compositions in workbench Root with id demo-<Stem>) to mp4.
// Bundles once and renders sequentially, ideal for before/after comparison or batch generating samples.
//
//   node scripts/render-demos.mjs --out <dir> [--only A,B] [--scale 0.6667] [--concurrency 4]
//                                 [--force] [--bundle <existing bundle dir>] [--save-bundle <dir>]
//                                 [--durations <json: { Stem: frames }>]
//
// - Existing <Stem>.mp4 skipped by default (--force to re-render); results written to <out>/render-log.json
// - --save-bundle: copies bundle output to specified dir for subsequent --bundle reuse (source changes won't affect snapshot)
// - --durations: override composition duration from table (after adjusting durations, re-render old snapshot with new duration for comparison)
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition, getCompositions } from "@remotion/renderer";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const opt = (k, d) => {
  const i = args.indexOf(`--${k}`);
  return i < 0 ? d : args[i + 1];
};
const flag = (k) => args.includes(`--${k}`);

const out = path.resolve(opt("out", "exports/demos"));
const only = opt("only", "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const scale = Number(opt("scale", "1"));
const concurrency = Number(opt("concurrency", "4"));
mkdirSync(out, { recursive: true });

const proj = existsSync(path.join(ROOT, "proj", "workbench.ts")) ? "proj" : "proj-stub";
let serveUrl = opt("bundle", "");
if (!serveUrl) {
  console.log("bundling…");
  serveUrl = await bundle({
    entryPoint: path.join(ROOT, "src/remotion/index.ts"),
    publicDir: path.join(ROOT, "public"),
    webpackOverride: (c) => ({
      ...c,
      resolve: {
        ...c.resolve,
        symlinks: false,
        alias: {
          ...(c.resolve?.alias ?? {}),
          "@proj": path.join(ROOT, proj),
          "@demos": path.join(ROOT, "demosrc"),
        },
      },
    }),
  });
  const save = opt("save-bundle", "");
  if (save) {
    cpSync(serveUrl, path.resolve(save), { recursive: true });
    serveUrl = path.resolve(save);
    console.log(`bundle saved → ${serveUrl}`);
  }
}

const chromiumOptions = { gl: "angle" };
const comps = (await getCompositions(serveUrl, { chromiumOptions }))
  .map((c) => c.id)
  .filter((id) => id.startsWith("demo-"))
  .filter((id) => !only.length || only.includes(id.slice(5)));

const durPath = opt("durations", "");
const durations = durPath ? JSON.parse(readFileSync(path.resolve(durPath), "utf8")) : {};
const logPath = path.join(out, "render-log.json");
const log = existsSync(logPath) ? JSON.parse(readFileSync(logPath, "utf8")) : {};
let i = 0;
for (const id of comps) {
  i++;
  const stem = id.slice(5);
  const file = path.join(out, `${stem}.mp4`);
  if (existsSync(file) && !flag("force")) continue;
  const t0 = Date.now();
  try {
    const selected = await selectComposition({ serveUrl, id, chromiumOptions });
    const composition = durations[stem] ? { ...selected, durationInFrames: durations[stem] } : selected;
    await renderMedia({
      serveUrl,
      composition,
      codec: "h264",
      crf: 20,
      imageFormat: "jpeg",
      jpegQuality: 90,
      scale,
      concurrency,
      chromiumOptions,
      outputLocation: file,
      muted: true,
      timeoutInMilliseconds: 120000,
    });
    log[stem] = { ok: true, frames: composition.durationInFrames, ms: Date.now() - t0 };
    console.log(`[${i}/${comps.length}] ${stem} ok ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  } catch (e) {
    log[stem] = { ok: false, error: String(e?.message ?? e).slice(0, 800) };
    console.log(`[${i}/${comps.length}] ${stem} FAILED ${String(e?.message ?? e).slice(0, 200)}`);
  }
  writeFileSync(logPath, JSON.stringify(log, null, 2));
}
const failed = Object.entries(log).filter(([, v]) => !v.ok);
console.log(`done: ${comps.length} comps, ${failed.length} failed`);
